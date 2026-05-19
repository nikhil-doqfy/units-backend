import json
from django.test import TestCase, Client
from unittest.mock import patch, call

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    OwnerFactory,
    reset_sequences,
)

class SendNegotiationTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease/send-negotiation"

        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]
        self.admin   = self.s["admin"]

        # Owner linked to the unit
        self.owner = OwnerFactory(created_by=self.pm_user)
        self.unit.unit_owners.create(owner=self.owner,created_by=self.pm_user)

        self.lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            created_by=self.pm_user,
            lease_status="DRAFT",
        )

    # Helpers 
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    def _post(self, payload):
        return self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    # tenant only (no owner email)
    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_to_tenant_only_success(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """
        POST sends email to tenant when no owner email exists; returns 200.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        # Remove owner email so only tenant receives
        self.owner.email = ""
        self.owner.save()

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn(self.tenant.user.email, content["sent"])
        self.assertEqual(content["failed"], [])

    #  both tenant AND owner receive email
    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_to_tenant_and_owner_success(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """POST sends separate emails to both tenant and owner."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]

        self.assertIn(self.tenant.user.email, content["sent"])
        self.assertIn(self.owner.email, content["sent"])
        self.assertEqual(len(content["sent"]), 2)
        self.assertEqual(content["failed"], [])

    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_calls_ses_separately_per_recipient(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """send_ses_email is called once per recipient — not a single bulk call."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        # 2 recipients → 2 separate SES calls
        self.assertEqual(mock_email.call_count, 2)

        called_emails = [c[0][0] for c in mock_email.call_args_list]
        self.assertIn(self.tenant.user.email, called_emails)
        self.assertIn(self.owner.email, called_emails)

    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_subject_contains_lease_code(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """Every email sent has subject containing the lease code."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        for c in mock_email.call_args_list:
            subject = c[0][1]
            self.assertIn(self.lease.code, subject)

    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_lease_stage_updated_to_negotiation_sent(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """lease_stage is updated to NEGOTIATION_SENT regardless of email result."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        self.lease.refresh_from_db()
        from utilities import constants
        self.assertEqual(self.lease.lease_stage, constants.NEGOTIATION_SENT)

    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_audit_log_called_on_success(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """audit_logs is called once after sending."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        self.assertTrue(mock_audit.called)

    # Partial failure — one recipient fails
    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_partial_failure_tracked(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """If one email fails, it appears in 'failed' and the other in 'sent'."""
        self._mock_auth(mock_get_token, mock_decode)

        # Tenant email succeeds, owner email fails
        def _side_effect(email, *args, **kwargs):
            return email == self.tenant.user.email

        mock_email.side_effect = _side_effect

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn(self.tenant.user.email, content["sent"])
        self.assertIn(self.owner.email, content["failed"])

    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_all_fail_still_returns_200(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """All emails failing still returns 200 — sent=[], failed=[both]."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = False

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertEqual(content["sent"], [])
        self.assertEqual(len(content["failed"]), 2)

    # No recipients at all
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_no_recipients_returns_400(self, mock_get_token, mock_decode, mock_email):
        """If tenant has no email and no owner has email, returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        self.tenant.user.email = ""
        self.tenant.user.save()
        self.owner.email = ""
        self.owner.save()

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("recipient", res.json()["message"].lower())
        mock_email.assert_not_called()

    # Missing / invalid input
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_without_lease_id_returns_400(self, mock_get_token, mock_decode):
        """POST without lease_id returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self._post({})

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("lease_id", res.json()["message"].lower())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_with_invalid_lease_id_returns_404(self, mock_get_token, mock_decode):
        """POST with non-existent lease_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self._post({"lease_id": 99999})

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Exception handling
    @patch("lease.views.audit_logs")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_unexpected_exception_returns_500(self, mock_get_token, mock_decode, mock_email, mock_audit):
        """Unexpected exception during email send is caught and returns 500."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.side_effect = Exception("AWS timeout")

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("AWS timeout", res.json()["message"])

    # HTTP method guard
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_get_method_returns_405(self, mock_get_token, mock_decode):
        """GET returns 405."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_negotiation_put_method_returns_405(self, mock_get_token, mock_decode):
        """PUT returns 405."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Auth guard
    def test_send_negotiation_without_auth_returns_401(self):
        """Request without auth token is rejected with 401."""
        res = self.client.post(
            self.url,
            json.dumps({"lease_id": self.lease.id}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # @patch("lease.views.send_ses_email")
    # @patch("utilities.decorator.decode_jwt_token")
    # @patch("utilities.decorator.get_jwt_token")
    # def test_send_negotiation_not_sent_twice(self,mock_get_token,mock_decode,mock_email):

    #     """Negotiation email should not be sent twice."""

    #     self._mock_auth(mock_get_token, mock_decode)

    #      # Assume already sent
    #     self.lease.lease_stage = "NEGOTIATION_SENT"
    #     self.lease.save()

    #     res = self._post({
    #             "lease_id": self.lease.id
    #         })

    #     self.assertEqual(
    #         res.status_code,status.HTTP_400_BAD_REQUEST)

    #     mock_email.assert_not_called()