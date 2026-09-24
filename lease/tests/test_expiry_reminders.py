"""
Manual-trigger verification of the Phase 6 reminder task (Dubai Leasing
Management Flow): 120-before / 10-before / 10-after cadence, and the
re-run idempotency guarantee from each offset's own send-lock field.
"""
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from lease.tasks import send_lease_expiry_reminders
from lease.tests.factories import LeaseFactory, build_standard_stack, reset_sequences


class LeaseExpiryReminderTaskTestCase(TestCase):
    def setUp(self):
        reset_sequences()
        self.s = build_standard_stack()

    def _lease(self, days_from_today):
        end_date = timezone.now() + timedelta(days=days_from_today)
        return LeaseFactory(
            unit=self.s["unit"], tenant=self.s["tenant"], created_by=self.s["pm_user"],
            lease_status="ACTIVE", is_active=True, end_date=end_date,
        )

    @patch("lease.tasks.send_ses_email")
    def test_sends_120_day_reminder_and_sets_lock(self, mock_email):
        lease = self._lease(120)
        send_lease_expiry_reminders()
        lease.refresh_from_db()
        self.assertEqual(mock_email.call_count, 1)
        self.assertIsNotNone(lease.renewal_reminder_120_sent_at)

    @patch("lease.tasks.send_ses_email")
    def test_sends_10_day_reminder_and_sets_lock(self, mock_email):
        lease = self._lease(10)
        send_lease_expiry_reminders()
        lease.refresh_from_db()
        self.assertEqual(mock_email.call_count, 1)
        self.assertIsNotNone(lease.renewal_reminder_10_sent_at)

    @patch("lease.tasks.send_ses_email")
    def test_sends_legal_notice_10_days_after_expiry(self, mock_email):
        lease = self._lease(-10)
        send_lease_expiry_reminders()
        lease.refresh_from_db()
        self.assertEqual(mock_email.call_count, 1)
        self.assertIsNotNone(lease.legal_notice_10_sent_at)

    @patch("lease.tasks.send_ses_email")
    def test_rerun_does_not_double_send(self, mock_email):
        self._lease(120)
        send_lease_expiry_reminders()
        send_lease_expiry_reminders()
        self.assertEqual(mock_email.call_count, 1)

    @patch("lease.tasks.send_ses_email")
    def test_lease_not_near_any_offset_gets_no_email(self, mock_email):
        self._lease(45)
        send_lease_expiry_reminders()
        self.assertEqual(mock_email.call_count, 0)
