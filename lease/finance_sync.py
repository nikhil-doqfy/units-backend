"""
HTTP helper that notifies Finance (units-finance) whenever a LeaseTransaction
is created or its status changes.

units-backend never imports Finance models or writes to any Finance-owned
table -- this module only makes a synchronous outbound HTTP call. See
Story 2.1a (spec-2-1-backend-finance-sync.md) and AD-4/AD-5/AD-6/AD-8 in
docs/finance/ARCHITECTURE-SPINE.md.
"""
import logging
import sys
import time

import requests

from utilities.config import FINANCE_SERVICE_URL, FINANCE_INTERNAL_TOKEN

logger = logging.getLogger(__name__)

# Skip the real HTTP call under Django's test runner (`manage.py test`),
# UNLESS this module's own tests have patched this flag to False (see
# lease/tests/test_finance_sync.py, which patches this to exercise the
# real retry/backoff logic under mocked requests.post/time.sleep).
#
# Pre-existing tests across the codebase (e.g. lease/tests/test_lease_cheque.py,
# property_management/tests/test_dashboard.py) create LeaseTransaction rows
# without mocking this module -- without this guard, this signal would make
# real outbound requests (with real time.sleep retry delays) against a
# Finance endpoint that doesn't exist yet, in every one of those tests.
SKIP_SYNC_UNDER_TEST_RUNNER = "test" in sys.argv

# Manual retry loop -- no tenacity/urllib3.Retry, matching this codebase's
# existing simplicity level (utilities/oauth_utils.py is the only other
# outbound-HTTP pattern here, and it has no retry logic at all).
RETRY_DELAYS = [0.5, 1, 2]
REQUEST_TIMEOUT_SECONDS = 3


def sync_lease_transaction_to_finance(lease_transaction_id):
    """
    Synchronously POST to Finance's internal sync endpoint for the given
    LeaseTransaction id, retrying on failure with short backoff.

    Never raises -- on exhausted retries the failure is logged loudly with
    the source LeaseTransaction.id for manual reconciliation, but the
    caller (the post_save signal, and transitively the original UI request)
    always completes successfully.
    """
    if SKIP_SYNC_UNDER_TEST_RUNNER:
        return

    if not FINANCE_INTERNAL_TOKEN:
        logger.error(
            f"FINANCE_INTERNAL_TOKEN is not configured -- skipping Finance sync "
            f"for LeaseTransaction {lease_transaction_id}"
        )
        return

    url = f"{FINANCE_SERVICE_URL}/internal/lease-transactions/{lease_transaction_id}/sync"
    payload = {"lease_transaction_id": lease_transaction_id}
    headers = {"X-Internal-Token": FINANCE_INTERNAL_TOKEN}

    for attempt_number, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.ok:
                return
        except Exception:
            # Never let a sync failure -- of any kind, not just requests'
            # own exception hierarchy -- propagate out of this signal-driven
            # call and abort the triggering LeaseTransaction save (AD-5/AD-6).
            logger.debug(
                f"Finance sync attempt {attempt_number} failed for "
                f"LeaseTransaction {lease_transaction_id}",
                exc_info=True,
            )

    logger.error(
        f"Finance sync exhausted retries for LeaseTransaction {lease_transaction_id}"
    )


def sync_lease_to_finance(lease_id):
    """
    Synchronously POST to Finance's internal sync endpoint for the given
    Lease id, retrying on failure with short backoff.

    Story 2.6: mirrors sync_lease_transaction_to_finance's exact retry/
    backoff/guard/never-raises contract -- the only difference is the
    target endpoint (POST /internal/leases/{id}/sync). Finance decides
    whether to post by inspecting the current lease_status/security_deposit
    values on every sync, not by diffing what changed here.

    Never raises -- on exhausted retries the failure is logged loudly with
    the source Lease.id for manual reconciliation, but the caller (the
    post_save signal, and transitively the original UI request) always
    completes successfully.
    """
    if SKIP_SYNC_UNDER_TEST_RUNNER:
        return

    if not FINANCE_INTERNAL_TOKEN:
        logger.error(
            f"FINANCE_INTERNAL_TOKEN is not configured -- skipping Finance sync "
            f"for Lease {lease_id}"
        )
        return

    url = f"{FINANCE_SERVICE_URL}/internal/leases/{lease_id}/sync"
    payload = {"lease_id": lease_id}
    headers = {"X-Internal-Token": FINANCE_INTERNAL_TOKEN}

    for attempt_number, delay in enumerate([0] + RETRY_DELAYS, start=1):
        if delay:
            time.sleep(delay)
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.ok:
                return
        except Exception:
            # Never let a sync failure -- of any kind, not just requests'
            # own exception hierarchy -- propagate out of this signal-driven
            # call and abort the triggering Lease save (AD-5/AD-6).
            logger.debug(
                f"Finance sync attempt {attempt_number} failed for Lease {lease_id}",
                exc_info=True,
            )

    logger.error(
        f"Finance sync exhausted retries for Lease {lease_id}"
    )
