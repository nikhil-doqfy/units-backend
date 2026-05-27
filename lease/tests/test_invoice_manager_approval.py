import json
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    reset_sequences,
)
from utilities import constants
from user_service.models import Approval


class InvoiceViewTestCase(TestCase):
    """GET /api/lease/invoice"""

    def setUp(self):
        reset_sequences()
        self.client  = Client()
        self.url     = "/api/lease/invoice"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.token   = self.s["token"]
        self.lease   = LeaseFactory(
            unit=self.s["unit"], tenant=self.s["tenant"],
            created_by=self.pm_user,
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_with_valid_lease_id_returns_200_with_all_sections(self, mock_get_token, mock_decode):
        """
        Verify invoice response returns 200 with tenant, property,transactions and totals sections when valid lease_id is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        for key in ("tenant", "property", "transactions", "totals"):
            self.assertIn(key, content)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invoice_tenant_block_contains_required_keys(self, mock_get_token, mock_decode):
        """
        Verify tenant info block has name, email, contact, address keys.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        tenant = res.json()["content"]["tenant"]
        for key in ("name", "email", "contact", "address_line_1", "address_line_2", "code"):
            self.assertIn(key, tenant)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invoice_property_block_contains_required_keys(self, mock_get_token, mock_decode):
        """
        Verify property info block has property_name, unit_name, lease_code etc.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        prop = res.json()["content"]["property"]
        for key in ("property_name", "block_name", "unit_name", "start_date", "end_date", "lease_code"):
            self.assertIn(key, prop)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invoice_totals_block_contains_subtotal_vat_and_grand_total(self, mock_get_token, mock_decode):
        """
        Verify totals block has subtotal, vat_total, grand_total keys.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        totals = res.json()["content"]["totals"]
        for key in ("subtotal", "vat_total", "grand_total"):
            self.assertIn(key, totals)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invoice_with_no_cheques_returns_empty_transactions_and_zero_grand_total(self, mock_get_token, mock_decode):
        """
        Verify lease with no cheques returns transactions=[] and grand_total=0.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        content = res.json()["content"]
        self.assertEqual(content["transactions"], [])
        self.assertEqual(content["totals"]["grand_total"], 0)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_without_lease_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify 400 is returned when lease_id is not provided in the request.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_with_non_existent_lease_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify 404 is returned when the provided lease_id does not exist in DB.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url, {"lease_id": 99999},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_with_soft_deleted_lease_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify soft-deleted lease (is_active=False) returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)
        self.lease.is_active = False
        self.lease.save()

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_invoice_without_auth_token_returns_unauthorized(self):
        """
        Verify 401 is returned when no Authorization header is provided.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_method_on_invoice_endpoint_returns_method_not_allowed(self, mock_get_token, mock_decode):
        """
        Verify 405 is returned when POST method is used on invoice endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.post(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# invoice_pdf_view   GET /api/lease/invoice-pdf
class InvoicePdfViewTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client  = Client()
        self.url     = "/api/lease/invoice-pdf"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.token   = self.s["token"]
        self.lease   = LeaseFactory(
            unit=self.s["unit"], tenant=self.s["tenant"],
            created_by=self.pm_user,
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    @patch("lease.views.fetch_s3_presigned_url_for_download", return_value="https://s3.example.com/invoice.pdf")
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/invoice.pdf")
    @patch("lease.views.WeasyprintHTML")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_pdf_with_valid_lease_id_returns_pdf_url_and_filename(self, mock_get_token, mock_decode, mock_weasy, mock_upload, mock_s3):
        """
        Verify GET with valid lease_id returns 200 with pdf_url and file_name fields.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.return_value = b"%PDF-1.4"

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn("pdf_url", content)
        self.assertIn("file_name", content)

    @patch("lease.views.fetch_s3_presigned_url_for_download", return_value="https://s3.example.com/invoice.pdf")
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/invoice.pdf")
    @patch("lease.views.WeasyprintHTML")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generated_pdf_filename_contains_lease_code(self, mock_get_token, mock_decode, mock_weasy, mock_upload, mock_s3):
        """
        Verify the generated PDF file_name contains the lease code for identification.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.return_value = b"%PDF-1.4"

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        file_name = res.json()["content"]["file_name"]
        self.assertIn(self.lease.code, file_name)

    @patch("lease.views.WeasyprintHTML")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_pdf_generation_failure_due_to_weasyprint_crash_returns_500(self, mock_get_token, mock_decode, mock_weasy):
        """
        Verify 500 is returned when WeasyprintHTML raises an exception during PDF generation.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.side_effect = Exception("Weasyprint crash")

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertIn("PDF generation failed", res.json()["message"])

    @patch("lease.views.upload_file_to_s3_base64", return_value=None)
    @patch("lease.views.WeasyprintHTML")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_pdf_s3_upload_failure_returns_500(self, mock_get_token, mock_decode, mock_weasy, mock_upload):
        """
        Verify 500 is returned when S3 upload returns None indicating upload failure.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.return_value = b"%PDF-1.4"

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_pdf_without_lease_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify 400 is returned when lease_id is not provided in the request.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_invoice_pdf_with_non_existent_lease_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify 404 is returned when the provided lease_id does not exist in DB.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url, {"lease_id": 99999},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_invoice_pdf_without_auth_token_returns_unauthorized(self):
        """
        Verify 401 is returned when no Authorization header is provided.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_method_on_invoice_pdf_endpoint_returns_method_not_allowed(self, mock_get_token, mock_decode):
        """
        Verify 405 is returned when POST method is used on invoice-pdf endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.post(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# manager_approval_view   POST /api/lease/manager-approval
class ManagerApprovalViewTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client  = Client()
        self.url     = "/api/lease/manager-approval"
        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.token   = self.s["token"]
        self.tenant  = self.s["tenant"]
        self.unit    = self.s["unit"]
        self.lease   = LeaseFactory(
            unit=self.unit, tenant=self.tenant,
            created_by=self.pm_user,
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    def _post(self, payload):
        return self.client.post(
            self.url, json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_with_valid_lease_id_returns_201_with_approval_id(self, mock_get_token, mock_decode):
        """
        Verify POST with valid lease_id creates approval and returns 201 with approval_id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self._post({"lease_id": self.lease.id, "requested_rent": 4500, "requested_tenure": "12 months"})

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("approval_id", res.json()["content"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_updates_lease_stage_to_manager_approval_required(self, mock_get_token, mock_decode):
        """
        Verify lease_stage is updated to MANAGER_APPROVAL_REQUIRED after approval is created.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self._post({"lease_id": self.lease.id, "requested_rent": 4500})

        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.MANAGER_APPROVAL_REQUIRED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_saves_correct_tenant_unit_and_rent_in_db(self, mock_get_token, mock_decode):
        """
        Verify Approval record is created in DB with correct tenant, unit and requested_rent.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self._post({"lease_id": self.lease.id, "requested_rent": 4500})

        approval = Approval.objects.filter(tenant=self.tenant, unit=self.unit).first()
        self.assertIsNotNone(approval)
        self.assertEqual(float(approval.requested_rent), 4500.0)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_when_pending_approval_already_exists_returns_200_with_same_id(self, mock_get_token, mock_decode):
        """
        Verify if pending approval already exists, returns 200 with same approval_id and does not create a duplicate record.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Create pending approval first
        existing = Approval.objects.create(
            created_by=self.pm_user,
            tenant=self.tenant,
            unit=self.unit,
            requested_rent=4000,
            approved=False,
        )

        res = self._post({"lease_id": self.lease.id, "requested_rent": 5000})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["approval_id"], existing.id)
        # No duplicate created
        self.assertEqual(Approval.objects.filter(tenant=self.tenant, unit=self.unit).count(), 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_existing_pending_approval_path_still_updates_lease_stage(self, mock_get_token, mock_decode):
        """
        Verify lease_stage is updated to MANAGER_APPROVAL_REQUIRED even when an existing pending approval is found instead of creating a new one.
        """
        self._mock_auth(mock_get_token, mock_decode)

        Approval.objects.create(
            created_by=self.pm_user,
            tenant=self.tenant, unit=self.unit,
            requested_rent=4000, approved=False,
        )

        self._post({"lease_id": self.lease.id})

        self.lease.refresh_from_db()
        self.assertEqual(self.lease.lease_stage, constants.MANAGER_APPROVAL_REQUIRED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_without_requested_rent_defaults_to_lease_annual_amount(self, mock_get_token, mock_decode):
        """
        Verify requested_rent defaults to lease.annual_amount when not provided in request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.lease.annual_amount = 60000
        self.lease.save()

        self._post({"lease_id": self.lease.id})

        approval = Approval.objects.filter(tenant=self.tenant, unit=self.unit).first()
        self.assertIsNotNone(approval)
        self.assertEqual(float(approval.requested_rent), 60000.0)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_without_lease_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify 400 is returned when lease_id is not provided in the request body.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self._post({})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_manager_approval_with_non_existent_lease_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify 404 is returned when the provided lease_id does not exist in DB.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self._post({"lease_id": 99999})
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_manager_approval_without_auth_token_returns_unauthorized(self):
        """
        Verify 401 is returned when no Authorization header is provided.
        """
        res = self.client.post(
            self.url, json.dumps({"lease_id": self.lease.id}),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_method_on_manager_approval_endpoint_returns_method_not_allowed(self, mock_get_token, mock_decode):
        """
        Verify 405 is returned when GET method is used on manager-approval endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)