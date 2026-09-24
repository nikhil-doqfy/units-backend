"""
Shared Proposal/Hold logic (Dubai Leasing Management Flow, Phase 1).

`release_expired_hold_for_proposal` is factored out here, separate from the
`release_expired_hold` HTTP view, so the Phase 6 Celery sweep
(`lead/tasks.py:release_expired_holds`) can call the exact same logic
without needing an HTTP `request` object.
"""
from django.template.loader import render_to_string
from django.utils import timezone

from plugins.logger_plugin import get_logger
from utilities import constants
from utilities.helper_functions import send_ses_email

logger = get_logger(__name__)


def release_expired_hold_for_proposal(proposal, triggered_by="user"):
    """Release `proposal`'s hold: unit back to AVAILABLE, status ->
    HOLD_EXPIRED, refund policy note recorded, notification sent.

    Does NOT process any refund payment -- payment/models.py has no
    payment-gateway model capable of that; refund_policy_note is a
    human-readable note for Finance to action manually.
    """
    lead = proposal.lead
    unit = lead.unit if lead else None

    proposal.status = constants.HOLD_EXPIRED
    if not proposal.refund_policy_note:
        holding_amount = proposal.holding_amount or 0
        proposal.refund_policy_note = (
            f"Hold expired on {timezone.now().date().isoformat()}. "
            f"Holding amount of AED {holding_amount} to be reviewed against "
            f"the applicable refund policy and processed manually by Finance."
        )
    proposal.save(update_fields=["status", "refund_policy_note"])

    if unit:
        unit.status = constants.UNIT_AVAILABLE
        unit.save(update_fields=["status"])

    if lead and lead.email:
        context = {
            "recipient_name": lead.name or "Customer",
            "unit_name": unit.unit_name if unit else "",
            "refund_policy_note": proposal.refund_policy_note,
        }
        body_html = render_to_string("email_templates/hold_expired.html", context)
        body_text = (
            f"Dear {context['recipient_name']},\n\n"
            f"Your hold period on {context['unit_name']} has expired without a "
            f"completed lease agreement, so the unit has been released back to "
            f"the market.\n\n{context['refund_policy_note']}"
        )
        send_ses_email(
            lead.email,
            f"Your hold on {context['unit_name']} has expired",
            body_text,
            body_html,
        )

    message = f"Hold released for unit '{unit.unit_name if unit else ''}' (expired)"
    if triggered_by == "system":
        # AuditLog.userprofile/created_by are both required, non-nullable
        # FKs -- a Celery-triggered sweep has no real user to attribute the
        # row to, so this logs instead of fabricating a fake actor
        # (matches the reminder tasks' own fallback, see lease/tasks.py).
        logger.info("HOLD_RELEASED_BY_SYSTEM | proposal_id=%s | %s", proposal.id, message)

    return proposal
