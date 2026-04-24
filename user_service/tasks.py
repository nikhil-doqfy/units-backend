import logging
from django.template.loader import render_to_string
from django.utils import timezone
from celery import shared_task
from utilities.helper_functions import send_ses_email
from notification.utils import (
    notify_document_expiring,
    notify_document_expired
)

logger = logging.getLogger(__name__)

# =====================================================
# CORE EMAIL SENDER
# =====================================================

def send_expiry_email(agreement, is_expired=False):

    manager = agreement.user
    django_user = getattr(manager, "user", None)

    if not django_user or not django_user.email:
        return False

    if not agreement.end_date:
        return False

    now = timezone.now()

    if is_expired:
        days_overdue = (now.date() - agreement.end_date.date()).days
        subject = f"⚠️ EXPIRED - {agreement.agreement_name}"
        message = f"Your agreement expired {days_overdue} day(s) ago."
        template = "email_templates/documentation_expired.html"
    else:
        days_left = (agreement.end_date.date() - now.date()).days
        subject = f"⏰ Expiring in {days_left} days - {agreement.agreement_name}"
        message = f"Your agreement will expire in {days_left} day(s)."
        template = "email_templates/documentation_expiry_reminder.html"

    try:
        html = render_to_string(template, {
            "user_name": django_user.get_full_name() or django_user.first_name or "User",
            "message": message,
            "code": agreement.code,
            "agreement_name": agreement.agreement_name,
            "agreement_type": agreement.agreement_type,
            "end_date": agreement.end_date.strftime("%A, %d %b %Y"),
        })
    except Exception:
        html = f"<p>{message}</p>"

    try:
        send_ses_email(
            to_email=django_user.email,
            subject=subject,
            body_text=message,
            body_html=html,
        )
        return True
    except Exception as e:
        logger.error(f"Email failed: {e}")
        return False


# =====================================================
# MAIN CELERY TASK (FINAL FIXED)
# =====================================================

@shared_task
def send_agreement_expiry_reminders():

    from user_service.models import Documentation

    now = timezone.now()
    today = now.date()
    seven_days_later = today + timezone.timedelta(days=7)

    sent = 0
    failed = 0

    # =====================================================
    # 🟡 REMINDER (ONLY BEFORE EXPIRY)
    # =====================================================
    expiring_soon = Documentation.objects.filter(
        is_active=True,
        does_not_expire=False,
        is_renewed=False,
        end_date__date__gte=today,
        end_date__date__lte=seven_days_later,
    )

    for agreement in expiring_soon:

        # ❌ skip renewed or expired
        if agreement.is_renewed or agreement.is_expired:
            continue

        # 🔒 DAILY LOCK
        if agreement.last_email_sent_date == today:
            continue

        # 🔒 LIMIT
        if agreement.expiry_reminder_sent_count >= 7:
            continue

        success = send_expiry_email(agreement, is_expired=False)

        if success:
            notify_document_expiring(agreement.user, agreement)
            agreement.last_email_sent_date = today
            agreement.expiry_reminder_sent_count += 1
            agreement.expiry_reminder_sent_at = now

            agreement.save(update_fields=[
                "last_email_sent_date",
                "expiry_reminder_sent_count",
                "expiry_reminder_sent_at"
            ])

            sent += 1
        else:
            failed += 1


    # =====================================================
    # 🔴 EXPIRED (ONLY AFTER EXPIRY)
    # =====================================================
    expired = Documentation.objects.filter(
        is_active=True,
        does_not_expire=False,
        is_renewed=False,
        end_date__lt=now
    )

    for agreement in expired:

        # ❌ skip renewed
        if agreement.is_renewed:
            continue

        # 🔒 DAILY LOCK
        if agreement.last_email_sent_date == today:
            continue

        if agreement.expiry_expired_sent_count >= 7:
            continue

        days_overdue = (now.date() - agreement.end_date.date()).days

        if not (1 <= days_overdue <= 7):
            continue

        success = send_expiry_email(agreement, is_expired=True)

        if success:
            notify_document_expired(agreement.user, agreement)
            agreement.last_email_sent_date = today
            agreement.expiry_expired_sent_count += 1

            agreement.save(update_fields=[
                "last_email_sent_date",
                "expiry_expired_sent_count"
            ])

            sent += 1
        else:
            failed += 1

    return f"Sent: {sent} | Failed: {failed}"


# =====================================================
# RENEWAL EMAIL (FIXED SAFE)
# =====================================================

@shared_task(bind=True, max_retries=3)
def send_renewal_email(self, agreement_id, manager_id):

    try:
        from user_service.models import Documentation, PropertyManager
        from utilities.helper_functions import send_ses_email

        agreement = Documentation.objects.get(id=agreement_id)
        property_manager = PropertyManager.objects.get(id=manager_id)

        django_user = getattr(property_manager, "user", None)

        if not django_user or not django_user.email:
            logger.warning(f"No email found for agreement {agreement_id}")
            return

        html = render_to_string(
            "email_templates/documentation_renew.html",
            {
                "user_name": django_user.get_full_name() or django_user.first_name or "User",
                "code": agreement.code,
                "agreement_name": agreement.agreement_name,
                "agreement_type": agreement.agreement_type,
                "end_date": agreement.end_date,
            }
        )

        cc_list = []
        if hasattr(agreement, "get_cc_emails_list"):
            cc_list = agreement.get_cc_emails_list() or []

        send_ses_email(
            to_email=django_user.email,
            subject=f"🎉 Document Renewed - {agreement.agreement_name}",
            body_text="Your document has been renewed successfully.",
            body_html=html,
            cc=cc_list
        )

        logger.info(f"✅ Renewal email sent for {agreement.code}")

    except Exception as e:
        logger.error(f"❌ Renewal email failed: {str(e)}")

        # 🔁 retry logic
        raise self.retry(exc=e, countdown=60)