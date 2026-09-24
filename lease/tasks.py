"""
Lease expiry reminder engine (Dubai Leasing Management Flow, Phase 6):
120-days-before / 10-days-before / 10-days-after cadence.

Deliberately a NEW file, not an addition to user_service/tasks.py -- that
file's send_agreement_expiry_reminders imports a nonexistent `Documentation`
model (removed from the schema) and is unrelated to Lease anyway. This
reuses that task's reusable structural patterns (per-offset send-lock
field, @shared_task, send_ses_email, retry-with-backoff) rebuilt fresh
against Lease.end_date, which has no such offset logic today.
"""
import logging

from celery import shared_task
from django.template.loader import render_to_string
from django.utils import timezone

from lease.models import Lease
from utilities.helper_functions import send_ses_email

logger = logging.getLogger(__name__)


def _tenant_context(lease):
    tenant = lease.tenant
    recipient_email = tenant.user.email if tenant and tenant.user else None
    recipient_name = (
        f"{tenant.user.first_name} {tenant.user.last_name}".strip()
        if tenant and tenant.user else "Tenant"
    )
    return recipient_email, {
        "recipient_name": recipient_name,
        "unit_name": lease.unit.unit_name if lease.unit else "",
        "lease_code": lease.code,
        "end_date": lease.end_date.strftime("%A, %d %b %Y") if lease.end_date else "",
    }


def _send_reminder(lease, template, subject, sent_at_field):
    recipient_email, context = _tenant_context(lease)
    if not recipient_email:
        logger.warning(
            "LEASE_REMINDER_SKIPPED | lease_id=%s | reason=NO_TENANT_EMAIL", lease.id)
        return
    try:
        body_html = render_to_string(f"email_templates/{template}", context)
    except Exception:
        body_html = f"<p>{subject}</p>"
    body_text = f"{subject}\n\nUnit: {context['unit_name']}\nLease: {context['lease_code']}\nEnd date: {context['end_date']}"
    send_ses_email(recipient_email, subject, body_text, body_html)
    setattr(lease, sent_at_field, timezone.now())
    lease.save(update_fields=[sent_at_field])


@shared_task(bind=True, max_retries=3)
def send_lease_expiry_reminders(self):
    """Daily sweep over active leases, sending the 120-before/10-before/
    10-after reminders. Each offset has its own one-time send-lock field
    on Lease so re-running this task never double-sends."""
    try:
        today = timezone.localdate()

        due_120 = Lease.objects.select_related("tenant__user", "unit").filter(
            lease_status="ACTIVE",
            is_active=True,
            end_date__date=today + timezone.timedelta(days=120),
            renewal_reminder_120_sent_at__isnull=True,
        )
        for lease in due_120:
            _send_reminder(
                lease, "lease_renewal_reminder_120.html",
                f"Lease Renewal Reminder — {lease.unit.unit_name if lease.unit else lease.code}",
                "renewal_reminder_120_sent_at",
            )

        due_10 = Lease.objects.select_related("tenant__user", "unit").filter(
            lease_status="ACTIVE",
            is_active=True,
            end_date__date=today + timezone.timedelta(days=10),
            renewal_reminder_10_sent_at__isnull=True,
        )
        for lease in due_10:
            _send_reminder(
                lease, "lease_renewal_reminder_10.html",
                f"Final Reminder: Lease Expiring Soon — {lease.unit.unit_name if lease.unit else lease.code}",
                "renewal_reminder_10_sent_at",
            )

        overdue_10 = Lease.objects.select_related("tenant__user", "unit").filter(
            lease_status="ACTIVE",
            is_active=True,
            end_date__date=today - timezone.timedelta(days=10),
            legal_notice_10_sent_at__isnull=True,
        )
        for lease in overdue_10:
            _send_reminder(
                lease, "lease_legal_notice.html",
                f"Notice: Lease Expired — {lease.unit.unit_name if lease.unit else lease.code}",
                "legal_notice_10_sent_at",
            )

        logger.info(
            "LEASE_EXPIRY_REMINDERS_SENT | due_120=%s | due_10=%s | overdue_10=%s",
            due_120.count(), due_10.count(), overdue_10.count())
    except Exception as e:
        logger.exception("LEASE_EXPIRY_REMINDERS_ERROR | error=%s", str(e))
        raise self.retry(exc=e, countdown=60)
