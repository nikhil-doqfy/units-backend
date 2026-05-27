import json
from django.test import TestCase, Client
from django.core.cache import cache
from unittest.mock import patch

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    OwnerFactory,
    reset_sequences,
)
from utilities import constants


def _otp_key(lease_id, role, email):
    return f"otp_lease_approval_{lease_id}_{role}_{email}"

def _verified_key(lease_id, role, email):
    return f"otp_lease_approval_verified_{lease_id}_{role}_{email}"


# 1. POST /api/lease/approval-otp
class LeaseApprovalOTPTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client = Client()
        self.url = "/api/lease/approval-otp"

        self.s        = build_standard_stack()
        self.pm_user  = self.s["pm_user"]
        self.unit     = self.s["unit"]
        self.tenant   = self.s["tenant"]
        self.owner    = OwnerFactory(created_by=self.pm_user)
        self.unit.unit_owners.create(owner=self.owner,created_by=self.pm_user)
        self.lease    = LeaseFactory(unit=self.unit, tenant=self.tenant, created_by=self.pm_user)
        self.t_email  = self.tenant.user.email.lower()
        self.o_email  = self.owner.user.email.lower()

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    # Happy path 
    @patch("lease.views.send_ses_email")
    @patch("user_service.utils.request_otp_sent", return_value="123456")
    def test_send_otp_to_tenant_and_store_in_cache(self, mock_otp, mock_email):
        """
        Verify OTP is sent to tenant email and stored in cache successfully.
        """
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})

        self.assertEqual(res.status_code, 200)
        mock_email.assert_called_once()
        self.assertEqual(str(cache.get(_otp_key(self.lease.id, "tenant", self.t_email))), "123456")

    @patch("lease.views.send_ses_email")
    @patch("user_service.utils.request_otp_sent", return_value="654321")
    def test_send_otp_to_owner_and_store_in_cache(self, mock_otp, mock_email):
        """
        Verify OTP is sent to owner email and stored in cache successfully.
        """
        res = self._post({"lease_id": self.lease.id, "role": "owner", "email": self.o_email})

        self.assertEqual(res.status_code, 200)
        mock_email.assert_called_once()
        self.assertEqual(str(cache.get(_otp_key(self.lease.id, "owner", self.o_email))), "654321")

    # Required fields 
    def test_missing_required_fields_returns_400(self):
        """Missing any of lease_id / role / email return 400."""
        self.assertEqual(self._post({"role": "tenant", "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant"}).status_code, 400)

    # Security 
    def test_approval_otp_with_invalid_tenant_email_returns_403(self):
        """
        Verify API returns 403 when tenant email does not match lease tenant.
        """
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": "wrong@test.com"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_approval_otp_with_invalid_owner_email_returns_403(self):
        """
        Verify API returns 403 when owner email does not match unit owner.
        """
        res = self._post({"lease_id": self.lease.id, "role": "owner", "email": "notowner@test.com"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_approval_otp_with_invalid_role_returns_400(self):
        """
        Verify API returns 400 when invalid role is passed in OTP request.
        """
        res = self._post({"lease_id": self.lease.id, "role": "admin", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approval_otp_for_non_existent_lease_returns_404(self):
        """
        Verify API returns 404 when lease does not exist.
        """
        res = self._post({"lease_id": 99999, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_method_on_approval_otp_api_returns_405(self):
        """
        Verify GET method is not allowed on approval OTP API.
        """
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

# 2. POST /api/lease/approval-otp-verify
class LeaseApprovalVerifyOTPTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client   = Client()
        self.url      = "/api/lease/approval-otp-verify"
        self.s        = build_standard_stack()
        self.pm_user  = self.s["pm_user"]
        self.tenant   = self.s["tenant"]
        self.lease    = LeaseFactory(unit=self.s["unit"], tenant=self.tenant, created_by=self.pm_user)
        self.t_email  = self.tenant.user.email.lower()
        self.valid_otp = "123456"
        cache.set(_otp_key(self.lease.id, "tenant", self.t_email), self.valid_otp, timeout=600)

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    # Happy path 
    @patch("lease.views.fetch_s3_presigned_url", return_value="https://s3.example.com/doc.pdf")
    def test_verify_correct_otp_and_return_lease_details(self, mock_s3):
        """
        Verify valid OTP returns lease details and sets verified cache flag.
        """
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn("lease_code", content)
        self.assertIn("pdf_url", content)
        self.assertTrue(cache.get(_verified_key(self.lease.id, "tenant", self.t_email)))

    @patch("lease.views.fetch_s3_presigned_url", return_value="")
    def test_verify_otp_returns_empty_pdf_url_when_pdf_not_available(self, mock_s3):
        """
        Verify API returns empty pdf_url when lease PDF path is not available.
        """
        self.lease.pdf_path = ""
        self.lease.save()
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"]["pdf_url"], "")

    # OTP failures 
    def test_verify_otp_with_incorrect_otp_returns_400(self):
        """
        Verify API returns 400 for incorrect OTP.
        """
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": "000000",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_expired_otp_returns_400(self):
        """
        Verify API returns 400 when OTP cache is expired or cleared.
        """
        cache.clear()
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Required fields & not found 
    def test_missing_required_fields_returns_400(self):
        """
        Verify API returns 400 when any field missing
        """
        self.assertEqual(self._post({"role": "tenant", "email": self.t_email, "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "email": self.t_email, "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant", "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email}).status_code, 400)

    def test_verify_otp_for_non_existent_lease_returns_404(self):
        """
        Verify API returns 404 for non-existent lease.
        """
        cache.set(_otp_key(99999, "tenant", self.t_email),self.valid_otp,timeout=600)
        res = self._post({"lease_id": 99999, "role": "tenant", "email": self.t_email, "otp": self.valid_otp})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_method_on_otp_verification_api_returns_405(self):
        """
        Verify GET method is not allowed on OTP verification API.
        """
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

# 3. POST /api/lease/approve
class ApproveLeaseViewTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client  = Client()
        self.url     = "/api/lease/approve"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.tenant  = self.s["tenant"]
        self.owner   = OwnerFactory(created_by=self.pm_user)
        self.s["unit"].unit_owners.create(owner=self.owner,created_by=self.pm_user)
        self.lease   = LeaseFactory(
            unit=self.s["unit"], tenant=self.tenant,
            created_by=self.pm_user, lease_stage=constants.NEGOTIATION_SENT,
        )
        self.t_email = self.tenant.user.email.lower()
        self.o_email = self.owner.user.email.lower()

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    def _set_verified(self, role, email):
        cache.set(_verified_key(self.lease.id, role, email), True, timeout=600)

    # Stage transition tests 
    def test_tenant_first_approval_updates_stage_to_tenant_approved(self):
        """
        Verify lease stage changes to TENANT_APPROVED when tenant approves first.
        """
        self._set_verified("tenant", self.t_email)
        self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.TENANT_APPROVED)

    def test_owner_approval_after_tenant_updates_stage_to_waiting_cheque(self):
        """
        Verify lease stage changes to WAITING_CHEQUE when owner approves after tenant approval.
        """
        self.lease.lease_stage = constants.TENANT_APPROVED
        self.lease.save()
        self._set_verified("owner", self.o_email)
        self._post({"lease_id": self.lease.id, "role": "owner", "email": self.o_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.WAITING_CHEQUE)

    def test_owner_first_approval_updates_stage_to_owner_approved(self):
        """
        Verify lease stage changes to OWNER_APPROVED when owner approves first.
        """
        self._set_verified("owner", self.o_email)
        self._post({"lease_id": self.lease.id, "role": "owner", "email": self.o_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.OWNER_APPROVED)

    def test_tenant_approval_after_owner_updates_stage_to_waiting_cheque(self):
        """
        Verify lease stage changes to WAITING_CHEQUE when tenant approves after owner approval.
        """
        self.lease.lease_stage = constants.OWNER_APPROVED
        self.lease.save()
        self._set_verified("tenant", self.t_email)
        self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.WAITING_CHEQUE)

    #── Stage must not go backwards (regression) ──────────────────────────────
    #Bug: else branch moves stage back. After fix: WAITING_CHEQUE stays.""
    def test_waiting_cheque_stage_does_not_change_after_tenant_reapproval(self):
        """
        Verify WAITING_CHEQUE stage does not move backward when tenant approves again.
        """
        self.lease.lease_stage = constants.WAITING_CHEQUE
        self.lease.save()
        self._set_verified("tenant", self.t_email)
        self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.WAITING_CHEQUE)

    def test_waiting_cheque_stage_does_not_change_after_owner_reapproval(self):
        """
        Verify WAITING_CHEQUE stage does not move backward when owner approves again.
        """
        self.lease.lease_stage = constants.WAITING_CHEQUE
        self.lease.save()
        self._set_verified("owner", self.o_email)
        self._post({"lease_id": self.lease.id, "role": "owner", "email": self.o_email})
        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.WAITING_CHEQUE)

    #  Cache behaviour 
    def test_verified_cache_is_removed_after_successful_approval(self):
        """
        Verify verified OTP cache key is cleared after successful approval.
        """
        self._set_verified("tenant", self.t_email)
        self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.assertIsNone(cache.get(_verified_key(self.lease.id, "tenant", self.t_email)))

    def test_approve_request_without_verified_otp_returns_400(self):
        """
        Verify API returns 400 when approval is attempted without OTP verification.
        """
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_second_approval_without_reverification_returns_400(self):
        """
        Verify second approval attempt fails without OTP reverification.
        """
        self._set_verified("tenant", self.t_email)
        self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  Required fields & not found 
    def test_missing_required_fields_returns_400(self):
        """
        Verify API returns 400 when required field missing
        """
        self.assertEqual(self._post({"role": "tenant", "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant"}).status_code, 400)

    def test_approve_request_without_role_returns_400(self):
        """
        Verify API returns 400 when role is missing in approve request.
        """
        self._set_verified("admin", "admin@test.com")
        res = self._post({"lease_id": self.lease.id, "role": "admin", "email": "admin@test.com"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_approve_request_for_non_existent_lease_returns_404(self):
        """
        Verify API returns 404 for non-existent lease.
        """
        cache.set(_verified_key(99999, "tenant", self.t_email),True,timeout=600)
        res = self._post({"lease_id": 99999, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_method_on_approve_lease_api_returns_405(self):
        """
        Verify GET method is not allowed on approve lease API.
        """
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)