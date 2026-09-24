"""
Hold-expiry sweep (Dubai Leasing Management Flow, Phase 6): releases any
ON_HOLD lead/unit whose hold_expiry_date has passed. Lives in `lead`, not
`lease`, since it only ever touches Lead/Unit.
"""
import logging

from celery import shared_task
from django.utils import timezone

from lead.models import Proposal
from lead.services import release_expired_hold_for_proposal
from utilities import constants

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def release_expired_holds(self):
    """Hourly sweep -- a stale ON_HOLD unit needlessly blocks other
    prospects the longer it isn't released, so this runs more often than
    the daily reminder sweep."""
    try:
        expired_proposals = Proposal.objects.select_related("lead__unit").filter(
            status=constants.ON_HOLD_STATUS,
            hold_expiry_date__lt=timezone.now(),
        )
        count = 0
        for proposal in expired_proposals:
            release_expired_hold_for_proposal(proposal, triggered_by="system")
            count += 1
        logger.info("EXPIRED_HOLDS_RELEASED | count=%s", count)
    except Exception as e:
        logger.exception("RELEASE_EXPIRED_HOLDS_ERROR | error=%s", str(e))
        raise self.retry(exc=e, countdown=60)
