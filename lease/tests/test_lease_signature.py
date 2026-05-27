import json
import base64
import io
from django.test import TestCase, Client
from django.core.cache import cache
from unittest.mock import patch, MagicMock, PropertyMock

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    OwnerFactory,
    reset_sequences,
)
from utilities import constants


#Cache key helpers 
def _otp_key(lease_id, role, email):
    return f"otp_lease_signature_{lease_id}_{role}_{email}"

def _verified_key(lease_id, role, email):
    return f"otp_lease_signature_verified_{lease_id}_{role}_{email}"

# Minimal valid base64 PNG (1x1 transparent pixel)
FAKE_SIGNATURE_B64 = (
    "data:image/png;base64,"
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

# Minimal valid PDF bytes as base64 (used for S3 fetch mock)
def _fake_pdf_b64():
    """Returns base64 of a minimal valid PDF."""
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R "
        b"/MediaBox [0 0 595 842] >>\nendobj\n"
        b"xref\n0 4\n0000000000 65535 f\n"
        b"0000000009 00000 n\n0000000058 00000 n\n"
        b"0000000115 00000 n\n"
        b"trailer\n<< /Size 4 /Root 1 0 R >>\n"
        b"startxref\n190\n%%EOF"
    )
    return base64.b64encode(pdf_bytes).decode()


# 1. send_for_signature   POST /api/lease/send-for-signature
class SendForSignatureTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client  = Client()
        self.url     = "/api/lease/send-for-signature"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]

        self.owner = OwnerFactory(created_by=self.pm_user)
        self.unit.unit_owners.create(owner=self.owner, created_by=self.pm_user)

        self.lease   = LeaseFactory(unit=self.unit, tenant=self.tenant, created_by=self.pm_user)
        self.t_email = self.tenant.user.email.lower()
        self.o_email = self.owner.user.email.lower()

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    def _post(self, payload):
        return self.client.post(
            self.url, json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    @patch("lease.views.audit_logs")
    @patch("lease.views.render_to_string", return_value="<html>email</html>")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_successfully_sends_email_to_tenant_and_owner(self, mock_get_token, mock_decode, mock_email, mock_render, mock_audit):
        """
        POST returns emails sent to both tenant and owner, returns 200.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn(self.t_email, content["sent"])
        self.assertIn(self.o_email, content["sent"])
        self.assertEqual(content["failed"], [])

    @patch("lease.views.audit_logs")
    @patch("lease.views.render_to_string", return_value="<html>email</html>")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_calls_ses_email_once_per_recipient(self, mock_get_token, mock_decode, mock_email, mock_render, mock_audit):
        """
        send_ses_email called once per recipient — not a bulk call.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        self.assertEqual(mock_email.call_count, 2)
        called_emails = [c[0][0] for c in mock_email.call_args_list]
        self.assertIn(self.t_email, called_emails)
        self.assertIn(self.o_email, called_emails)

    @patch("lease.views.audit_logs")
    @patch("lease.views.render_to_string", return_value="<html>email</html>")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_updates_lease_stage_to_agreement_signing(self, mock_get_token, mock_decode, mock_email, mock_render, mock_audit):
        """
        lease_stage updated to AGREEMENT_SIGNING after send.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.return_value = True

        self._post({"lease_id": self.lease.id})

        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.AGREEMENT_SIGNING)

    @patch("lease.views.audit_logs")
    @patch("lease.views.render_to_string", return_value="<html>email</html>")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_tracks_failed_email_recipients(self, mock_get_token, mock_decode, mock_email, mock_render, mock_audit):
        """
        If one email fails returns appears in failed, other in sent.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_email.side_effect = lambda email, *a, **k: email == self.t_email

        res = self._post({"lease_id": self.lease.id})

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn(self.t_email, content["sent"])
        self.assertIn(self.o_email, content["failed"])

    # Missing / invalid 
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_without_lease_id_returns_400(self, mock_get_token, mock_decode):
        """
        POST without lease_id return 400.
        """
        self._mock_auth(mock_get_token, mock_decode)
        self.assertEqual(self._post({}).status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_with_invalid_lease_returns_404(self, mock_get_token, mock_decode):
        """
        POST with non-existent lease_id return 404.
        """
        self._mock_auth(mock_get_token, mock_decode)
        self.assertEqual(self._post({"lease_id": 99999}).status_code, status.HTTP_404_NOT_FOUND)

    @patch("lease.views.render_to_string", return_value="<html></html>")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_without_any_valid_recipient_returns_400(self, mock_get_token, mock_decode, mock_email, mock_render):
        """
        No tenant email + no owner email return 400.
        """
        self._mock_auth(mock_get_token, mock_decode)
        self.tenant.user.email = ""
        self.tenant.user.save()
        self.owner.email = ""
        self.owner.save()

        res = self._post({"lease_id": self.lease.id})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        mock_email.assert_not_called()

    def test_send_for_signature_without_auth_returns_401(self):
        """Request without token returns 401."""
        res = self.client.post(self.url, json.dumps({"lease_id": self.lease.id}),
                               content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_send_for_signature_get_method_returns_405(self, mock_get_token, mock_decode):
        """GET method not allowed return 405."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

# 2. lease_signature_otp   POST /api/lease/signature-otp
class LeaseSignatureOTPTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client  = Client()
        self.url     = "/api/lease/signature-otp"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]

        self.owner = OwnerFactory(created_by=self.pm_user)
        self.unit.unit_owners.create(owner=self.owner, created_by=self.pm_user)

        self.lease   = LeaseFactory(unit=self.unit, tenant=self.tenant, created_by=self.pm_user)
        self.t_email = self.tenant.user.email.lower()
        self.o_email = self.owner.user.email.lower()

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    @patch("lease.views.render_to_string", return_value="<html>otp</html>")
    @patch("lease.views.send_ses_email")
    @patch("user_service.utils.request_otp_sent", return_value="123456")
    def test_signature_otp_sent_successfully_to_tenant(self, mock_otp, mock_email, mock_render):
        """
        Valid tenant email returns OTP sent and cached.
        """
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})

        self.assertEqual(res.status_code, 200)
        mock_email.assert_called_once()
        self.assertEqual(str(cache.get(_otp_key(self.lease.id, "tenant", self.t_email))), "123456")

    @patch("lease.views.render_to_string", return_value="<html>otp</html>")
    @patch("lease.views.send_ses_email")
    @patch("user_service.utils.request_otp_sent", return_value="654321")
    def test_signature_otp_sent_successfully_to_owner(self, mock_otp, mock_email, mock_render):
        """
        Valid owner email returns OTP sent and cached.
        """
        res = self._post({"lease_id": self.lease.id, "role": "owner", "email": self.o_email})

        self.assertEqual(res.status_code, 200)
        self.assertEqual(str(cache.get(_otp_key(self.lease.id, "owner", self.o_email))), "654321")

    def test_signature_otp_with_invalid_tenant_email_returns_403(self):
        """
        Tenant email mismatch return 403.
        """
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": "wrong@test.com"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_signature_otp_with_invalid_owner_email_returns_403(self):
        """
        Owner email mismatch return 403.
        """
        res = self._post({"lease_id": self.lease.id, "role": "owner", "email": "notowner@test.com"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_signature_otp_with_invalid_role_returns_400(self):
        """
        Unsupported role value return 400.
        """
        res = self._post({"lease_id": self.lease.id, "role": "admin", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_signature_otp_without_required_fields_returns_400(self):
        """
        Missing lease_id/role/email returns 400.
        """
        self.assertEqual(self._post({"role": "tenant", "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "email": self.t_email}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant"}).status_code, 400)

    def test_signature_otp_with_non_existent_lease_returns_404(self):
        """
        Invalid lease_id return 404.
        """
        res = self._post({"lease_id": 99999, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_signature_otp_get_method_returns_405(self):
        """GET method not allowed return 405."""
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# 3. lease_signature_verify_otp   POST /api/lease/signature-otp-verify
class LeaseSignatureVerifyOTPTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client    = Client()
        self.url       = "/api/lease/signature-otp-verify"
        self.s         = build_standard_stack()
        self.pm_user   = self.s["pm_user"]
        self.tenant    = self.s["tenant"]
        self.lease     = LeaseFactory(unit=self.s["unit"], tenant=self.tenant, created_by=self.pm_user)
        self.t_email   = self.tenant.user.email.lower()
        self.valid_otp = "123456"
        cache.set(_otp_key(self.lease.id, "tenant", self.t_email), self.valid_otp, timeout=600)

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    @patch("lease.views.fetch_s3_presigned_url", return_value="https://s3.example.com/doc.pdf")
    def test_verify_signature_otp_returns_lease_details_on_success(self, mock_s3):
        """Correct OTP return 200 with lease details and verified cache set."""
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        for key in ("pdf_url", "lease_code", "tenant_name", "property_name", "unit_name"):
            self.assertIn(key, content)
        self.assertTrue(cache.get(_verified_key(self.lease.id, "tenant", self.t_email)))

    @patch("lease.views.fetch_s3_presigned_url", return_value="")
    def test_verify_signature_otp_returns_empty_pdf_url_when_no_pdf_exists(self, mock_s3):
        """
        Lease without pdf_path return pdf_url empty string.
        """
        self.lease.pdf_path = ""
        self.lease.save()
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"]["pdf_url"], "")

    def test_verify_signature_otp_with_incorrect_otp_returns_400(self):
        """Wrong OTP return 400."""
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": "000000",
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_signature_otp_with_expired_otp_returns_400(self):
        """Expired or missing OTP cache return 400."""
        cache.clear()
        res = self._post({
            "lease_id": self.lease.id, "role": "tenant",
            "email": self.t_email, "otp": self.valid_otp,
        })
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_verify_signature_otp_without_required_fields_returns_400(self):
        """Missing required payload fields returns 400."""
        self.assertEqual(self._post({"role": "tenant", "email": self.t_email, "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "email": self.t_email, "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant", "otp": self.valid_otp}).status_code, 400)
        self.assertEqual(self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email}).status_code, 400)

    def test_verify_signature_otp_with_non_existent_lease_returns_404(self):
        """Invalid lease_id return 404."""
        cache.set(_otp_key(99999, "tenant", self.t_email), self.valid_otp, timeout=600)
        res = self._post({"lease_id": 99999, "role": "tenant", "email": self.t_email, "otp": self.valid_otp})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_verify_signature_otp_get_method_returns_405(self):
        """
        GET method not allowed returns 405.
        """
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# 4. submit_lease_signature   POST /api/lease/submit-signature
class SubmitLeaseSignatureTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        cache.clear()
        self.client  = Client()
        self.url     = "/api/lease/submit-signature"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.tenant  = self.s["tenant"]
        self.lease   = LeaseFactory(
            unit=self.s["unit"], tenant=self.tenant, created_by=self.pm_user,
        )
        self.lease.pdf_path = "https://s3.example.com/lease.pdf"
        self.lease.save()
        self.t_email = self.tenant.user.email.lower()

    def _set_verified(self, role, email):
        cache.set(_verified_key(self.lease.id, role, email), True, timeout=600)

    def _post(self, payload):
        return self.client.post(self.url, json.dumps(payload), content_type="application/json")

    def _valid_payload(self, role="tenant", email=None):
        return {
            "lease_id":       self.lease.id,
            "role":           role,
            "email":          email or self.t_email,
            "signature_data": FAKE_SIGNATURE_B64,
        }

    def _patch_submit(self):
        """
        Inline imports inside submit_lease_signature must be patched via
        sys.modules since they are imported inside the function body.
        Returns a list of patchers to start/stop.
        """
        import sys
        from unittest.mock import MagicMock

        # Build mock pypdf
        mock_page = MagicMock()
        mock_page.mediabox.width  = 595
        mock_page.mediabox.height = 842

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        mock_writer = MagicMock()
        mock_writer.pages = [mock_page]
        def fake_write(buf):
            buf.write(b"%PDF-1.4 fake")
        mock_writer.write.side_effect = fake_write

        mock_overlay_page = MagicMock()
        mock_overlay_reader = MagicMock()
        mock_overlay_reader.pages = [mock_overlay_page]

        mock_pypdf_mod = MagicMock()
        mock_pypdf_mod.PdfReader.side_effect = [mock_reader, mock_overlay_reader]
        mock_pypdf_mod.PdfWriter.return_value = mock_writer

        # Build mock reportlab canvas
        mock_canvas_mod = MagicMock()
        mock_canvas_inst = MagicMock()
        mock_canvas_mod.Canvas.return_value = mock_canvas_inst

        # Build mock ImageReader
        mock_imgr_mod = MagicMock()

        # Inject into sys.modules so inline imports pick them up
        sys.modules["pypdf"]                    = mock_pypdf_mod
        sys.modules["reportlab.pdfgen"]         = MagicMock(canvas=mock_canvas_mod)
        sys.modules["reportlab.pdfgen.canvas"]  = mock_canvas_mod
        sys.modules["reportlab.lib.utils"]      = MagicMock(ImageReader=mock_imgr_mod)

        return mock_pypdf_mod, mock_canvas_mod

    def _restore_modules(self):
        import sys
        for mod in ["pypdf", "reportlab.pdfgen", "reportlab.pdfgen.canvas", "reportlab.lib.utils"]:
            sys.modules.pop(mod, None)

    # Happy path 
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/signed.pdf")
    @patch("lease.views.fetch_s3_file_as_base64")
    def test_submit_signature_successfully_generates_signed_pdf(self, mock_fetch, mock_upload):
        """
        Valid OTP-verified signature return 200, signed_pdf_url returned.
        """
        self._set_verified("tenant", self.t_email)
        mock_fetch.return_value = _fake_pdf_b64()
        self._patch_submit()

        res = self._post(self._valid_payload())
        self._restore_modules()

        self.assertEqual(res.status_code, 200)
        self.assertIn("signed_pdf_url", res.json()["content"])

    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/signed.pdf")
    @patch("lease.views.fetch_s3_file_as_base64")
    def test_submit_signature_updates_lease_pdf_path_and_stage(self, mock_fetch, mock_upload):
        """
        After sign returns lease.pdf_path and lease_stage updated in DB.
        """
        self._set_verified("tenant", self.t_email)
        mock_fetch.return_value = _fake_pdf_b64()
        self._patch_submit()

        self._post(self._valid_payload())
        self._restore_modules()

        self.lease.refresh_from_db()
        self.assertEqual(self.lease.pdf_path, "https://s3.example.com/signed.pdf")
        self.assertEqual(self.lease.lease_stage, constants.AGREEMENT_SIGNED)

    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/signed.pdf")
    @patch("lease.views.fetch_s3_file_as_base64")
    def test_submit_signature_clears_verified_otp_cache_after_success(self, mock_fetch, mock_upload):
        """Verified cache key deleted after successful signature."""
        self._set_verified("tenant", self.t_email)
        mock_fetch.return_value = _fake_pdf_b64()
        self._patch_submit()

        self._post(self._valid_payload())
        self._restore_modules()

        self.assertIsNone(cache.get(_verified_key(self.lease.id, "tenant", self.t_email)))

    # ── Guards — these run BEFORE inline imports so no mock needed ────────────

    def test_submit_signature_without_verified_otp_returns_500(self):
        """
        OTP not verified before signature submission returns 500.
        """
        res = self._post(self._valid_payload())
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # self.assertIn("otp not verified", res.json()["message"].lower())

    def test_submit_signature_without_reverification_returns_500(self):
        """
        Second submit attempt after cache clear returns 500.
        """
        res = self._post(self._valid_payload())
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_submit_signature_without_existing_lease_pdf_returns_400(self):
        """
        Lease with no pdf_path return 400 (checked after OTP, before PDF ops).
        """
        self._set_verified("tenant", self.t_email)
        self.lease.pdf_path = ""
        self.lease.save()
        self._patch_submit()
        res = self._post(self._valid_payload())
        self._restore_modules()
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("lease.views.fetch_s3_file_as_base64", return_value=None)
    def test_submit_s3_fetch_failure_returns_500(self, mock_fetch):
        """S3 PDF fetch returns None 500."""
        self._set_verified("tenant", self.t_email)
        self._patch_submit()
        res = self._post(self._valid_payload())
        self._restore_modules()
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_missing_required_fields_returns_500(self):
        """Missing fields return 500 before any import runs."""
        # Missing lease_id
        res = self._post({"role": "tenant", "email": self.t_email, "signature_data": FAKE_SIGNATURE_B64})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Missing role
        res = self._post({"lease_id": self.lease.id, "email": self.t_email, "signature_data": FAKE_SIGNATURE_B64})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Missing email
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "signature_data": FAKE_SIGNATURE_B64})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        # Missing signature_data
        res = self._post({"lease_id": self.lease.id, "role": "tenant", "email": self.t_email})
        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    def test_submit_signature_with_non_existent_lease_returns_404(self):
        """
        Non-existent lease_id return 404.
        """
        self._set_verified("tenant", self.t_email)
        cache.set(_verified_key(99999, "tenant", self.t_email), True, timeout=600)
        self._patch_submit()
        res = self._post({
            "lease_id": 99999, "role": "tenant",
            "email": self.t_email, "signature_data": FAKE_SIGNATURE_B64,
        })
        self._restore_modules()
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_submit_signature_get_method_returns_405(self):
        """
        GET method not allowed return 405.
        """
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_405_METHOD_NOT_ALLOWED)