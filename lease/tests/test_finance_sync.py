"""
Tests for Story 2.1a: the units-backend -> Finance sync signal.

Covers the I/O & Edge-Case Matrix from
_bmad-output/implementation-artifacts/spec-2-1-backend-finance-sync.md.
All HTTP is mocked via requests.post -- no dependency on a real Finance
service or Story 2.1b's endpoint. time.sleep is also mocked so the retry
tests run instantly.

lease.finance_sync.SKIP_SYNC_UNDER_TEST_RUNNER normally short-circuits this
sync entirely whenever Django's test runner is detected (so the many
pre-existing tests elsewhere in the codebase that create LeaseTransaction
rows -- e.g. test_lease_cheque.py, test_dashboard.py -- don't make real
outbound HTTP calls). This test class patches that flag to False so its
own tests can exercise the real retry/backoff logic under fully-mocked
requests.post/time.sleep.
"""
import requests
from django.test import TestCase
from django.utils import timezone
from unittest.mock import patch

from utilities import constants
from user_service.models import DocumentType

from lease.models import Lease, LeaseTransaction
from lease.tests.factories import (
    UserFactory, CompanyFactory, PropertyManagerFactory,
    TenantFactory, PropertyFactory, BlockFactory,
    UnitFactory, LeaseFactory, reset_sequences,
)


@patch("lease.finance_sync.SKIP_SYNC_UNDER_TEST_RUNNER", False)
class FinanceSyncSignalTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.admin = UserFactory(email="admin@test.com")
        self.company = CompanyFactory(created_by=self.admin)
        self.pm = PropertyManagerFactory(
            company=self.company, created_by=self.admin, token="pmtoken"
        )
        self.tenant = TenantFactory(created_by=self.admin)
        self.property = PropertyFactory(company=self.company, created_by=self.admin)
        self.block = BlockFactory(property=self.property, created_by=self.admin)
        self.unit = UnitFactory(block=self.block, created_by=self.admin)
        self.lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )
        self.doc_type = DocumentType.objects.create(
            name="Lease Cheque",
            section="LEASE_CHEQUE",
            created_by=self.admin,
        )

    def _make_transaction(self, status_val=None):
        return LeaseTransaction.objects.create(
            lease=self.lease,
            document_type=self.doc_type,
            file_name="",
            file_path="",
            amount=5000,
            status=status_val or constants.CHEQUE_STATUS_BALANCE,
            cheque_date=timezone.now(),
            cheque_type=constants.RENT_CHEQUE,
            payment_type=constants.PAYMENT_TYPE_CHEQUE,
            is_active=True,
            created_by=self.admin,
        )

    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_happy_path_no_retry(self, mock_post, mock_sleep):
        """Finance mocked to return 200 -- post_save fires, POST succeeds on first attempt, no retry."""
        mock_post.return_value = requests.models.Response()
        mock_post.return_value.status_code = 200

        txn = self._make_transaction()

        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

        # Verify the outbound call shape.
        _, kwargs = mock_post.call_args
        self.assertIn(f"/internal/lease-transactions/{txn.id}/sync", mock_post.call_args[0][0])
        self.assertEqual(kwargs["json"]["lease_transaction_id"], txn.id)
        self.assertIn("X-Internal-Token", kwargs["headers"])
        self.assertEqual(kwargs["timeout"], 3)

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_finance_unreachable_retries_and_logs(self, mock_post, mock_sleep, mock_logger):
        """Finance mocked to raise ConnectionError on every attempt -- retries, all fail, logs loudly, save still succeeds."""
        mock_post.side_effect = requests.ConnectionError("boom")

        txn = self._make_transaction()

        # 1 initial attempt + up to 3 retries per RETRY_DELAYS = 4 total calls.
        self.assertEqual(mock_post.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

        mock_logger.error.assert_called_once()
        self.assertIn(str(txn.id), mock_logger.error.call_args[0][0])

        # Original save still succeeded despite Finance being unreachable.
        self.assertTrue(LeaseTransaction.objects.filter(pk=txn.pk).exists())

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_finance_returns_error_status_retries_and_logs(self, mock_post, mock_sleep, mock_logger):
        """Finance mocked to return 500 on every attempt -- same retry/exhaustion/logging behavior as unreachable."""
        error_response = requests.models.Response()
        error_response.status_code = 500
        mock_post.return_value = error_response

        txn = self._make_transaction()

        self.assertEqual(mock_post.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)
        mock_logger.error.assert_called_once()
        self.assertIn(str(txn.id), mock_logger.error.call_args[0][0])
        self.assertTrue(LeaseTransaction.objects.filter(pk=txn.pk).exists())

    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_status_transition_fires_signal_again(self, mock_post, mock_sleep):
        """post_save fires again on a status change via the same write path -- each .save() triggers it independently."""
        mock_post.return_value = requests.models.Response()
        mock_post.return_value.status_code = 200

        txn = self._make_transaction(status_val=constants.CHEQUE_STATUS_BALANCE)
        self.assertEqual(mock_post.call_count, 1)

        txn.status = constants.CHEQUE_STATUS_REALIZED
        txn.save()

        self.assertEqual(mock_post.call_count, 2)

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_non_request_exception_is_caught_and_never_raises(
        self, mock_post, mock_sleep, mock_logger
    ):
        """A non-RequestException error (e.g. TypeError) during an attempt is
        still caught -- the sync must never propagate any exception out of
        the post_save signal and abort the triggering save (AD-5/AD-6)."""
        mock_post.side_effect = TypeError("unexpected error shape")

        txn = self._make_transaction()  # must not raise

        self.assertEqual(mock_post.call_count, 4)
        mock_logger.error.assert_called_once()
        self.assertIn(str(txn.id), mock_logger.error.call_args[0][0])
        self.assertTrue(LeaseTransaction.objects.filter(pk=txn.pk).exists())

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    @patch("lease.finance_sync.FINANCE_INTERNAL_TOKEN", None)
    def test_missing_internal_token_skips_call_and_logs(
        self, mock_post, mock_sleep, mock_logger
    ):
        """FINANCE_INTERNAL_TOKEN unset -- fails fast with a clear log, never
        attempts a request with a broken/None header value."""
        self._make_transaction()

        mock_post.assert_not_called()
        mock_sleep.assert_not_called()
        mock_logger.error.assert_called_once()
        self.assertIn("FINANCE_INTERNAL_TOKEN", mock_logger.error.call_args[0][0])


class FinanceSyncTestRunnerGuardTestCase(TestCase):
    """Outside the class-level SKIP_SYNC_UNDER_TEST_RUNNER override above --
    confirms the default (real) behavior under the test runner is to skip
    the sync entirely, protecting every OTHER test in the codebase that
    creates a LeaseTransaction without mocking this module."""

    def setUp(self):
        reset_sequences()
        self.admin = UserFactory(email="admin2@test.com")
        self.company = CompanyFactory(created_by=self.admin)
        self.tenant = TenantFactory(created_by=self.admin)
        self.property = PropertyFactory(company=self.company, created_by=self.admin)
        self.block = BlockFactory(property=self.property, created_by=self.admin)
        self.unit = UnitFactory(block=self.block, created_by=self.admin)
        self.lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )
        self.doc_type = DocumentType.objects.create(
            name="Lease Cheque",
            section="LEASE_CHEQUE",
            created_by=self.admin,
        )

    @patch("lease.finance_sync.requests.post")
    def test_sync_is_skipped_by_default_under_test_runner(self, mock_post):
        LeaseTransaction.objects.create(
            lease=self.lease,
            document_type=self.doc_type,
            file_name="",
            file_path="",
            amount=5000,
            status=constants.CHEQUE_STATUS_BALANCE,
            cheque_date=timezone.now(),
            cheque_type=constants.RENT_CHEQUE,
            payment_type=constants.PAYMENT_TYPE_CHEQUE,
            is_active=True,
            created_by=self.admin,
        )
        mock_post.assert_not_called()


@patch("lease.finance_sync.SKIP_SYNC_UNDER_TEST_RUNNER", False)
class FinanceLeaseSyncSignalTestCase(TestCase):
    """Post-review addition (Story 2.6, verification-gap finding): mirrors
    FinanceSyncSignalTestCase exactly, but for the new Lease post_save
    signal (sync_lease_on_save / sync_lease_to_finance) rather than the
    LeaseTransaction one. Confirms the outbound call shape (URL, payload
    key, headers, timeout) and the same retry/exhaustion/never-raises
    contract independently for this second signal."""

    def setUp(self):
        reset_sequences()
        self.admin = UserFactory(email="admin3@test.com")
        self.company = CompanyFactory(created_by=self.admin)
        self.tenant = TenantFactory(created_by=self.admin)
        self.property = PropertyFactory(company=self.company, created_by=self.admin)
        self.block = BlockFactory(property=self.property, created_by=self.admin)
        self.unit = UnitFactory(block=self.block, created_by=self.admin)

    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_happy_path_no_retry(self, mock_post, mock_sleep):
        """Finance mocked to return 200 -- Lease.save() fires the signal, POST succeeds on first attempt, no retry."""
        mock_post.return_value = requests.models.Response()
        mock_post.return_value.status_code = 200

        lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )

        self.assertEqual(mock_post.call_count, 1)
        mock_sleep.assert_not_called()

        # Verify the outbound call shape -- the endpoint/payload key this
        # signal must use, distinct from the LeaseTransaction variant.
        _, kwargs = mock_post.call_args
        self.assertIn(f"/internal/leases/{lease.id}/sync", mock_post.call_args[0][0])
        self.assertEqual(kwargs["json"]["lease_id"], lease.id)
        self.assertIn("X-Internal-Token", kwargs["headers"])
        self.assertEqual(kwargs["timeout"], 3)

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_finance_unreachable_retries_and_logs(self, mock_post, mock_sleep, mock_logger):
        """Finance mocked to raise ConnectionError on every attempt -- retries, all fail, logs loudly, save still succeeds."""
        mock_post.side_effect = requests.ConnectionError("boom")

        lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )

        self.assertEqual(mock_post.call_count, 4)
        self.assertEqual(mock_sleep.call_count, 3)
        mock_sleep.assert_any_call(0.5)
        mock_sleep.assert_any_call(1)
        mock_sleep.assert_any_call(2)

        mock_logger.error.assert_called_once()
        self.assertIn(str(lease.id), mock_logger.error.call_args[0][0])

        # Original save still succeeded despite Finance being unreachable.
        self.assertTrue(Lease.objects.filter(pk=lease.pk).exists())

    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    def test_status_change_fires_signal_again(self, mock_post, mock_sleep):
        """post_save fires again on a status change via the same write path -- each .save() triggers it independently."""
        mock_post.return_value = requests.models.Response()
        mock_post.return_value.status_code = 200

        lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status="DRAFT",
            created_by=self.admin,
        )
        self.assertEqual(mock_post.call_count, 1)

        lease.lease_status = constants.ACTIVE
        lease.save(update_fields=["lease_status"])

        self.assertEqual(mock_post.call_count, 2)

    @patch("lease.finance_sync.logger")
    @patch("lease.finance_sync.time.sleep")
    @patch("lease.finance_sync.requests.post")
    @patch("lease.finance_sync.FINANCE_INTERNAL_TOKEN", None)
    def test_missing_internal_token_skips_call_and_logs(
        self, mock_post, mock_sleep, mock_logger
    ):
        """FINANCE_INTERNAL_TOKEN unset -- fails fast with a clear log, never
        attempts a request with a broken/None header value."""
        LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )

        mock_post.assert_not_called()
        mock_sleep.assert_not_called()
        mock_logger.error.assert_called_once()
        self.assertIn("FINANCE_INTERNAL_TOKEN", mock_logger.error.call_args[0][0])
