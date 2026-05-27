import json
from django.test import TestCase, Client
from unittest.mock import patch, MagicMock

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    reset_sequences,
)
from lease.models import LeaseDocuments
from user_service.models import DocumentType
from lease.models import Template, TemplateField

class LeaseOnboardingDocumentsTestCase(TestCase):
    """
    File: lease/tests/test_onboarding_documents.py
    Tests for GET/POST/DELETE /api/lease/onboarding-documents
    """

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease/onboarding-documents"

        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]

        self.lease = LeaseFactory(
            unit=self.unit, tenant=self.tenant,
            created_by=self.pm_user,
        )

        # DocumentType for upload tests
        self.doc_type = DocumentType.objects.create(name="Passport",created_by=self.pm_user)

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    # GET
    @patch("lease.views.fetch_s3_presigned_url", return_value="https://s3.example.com/file.pdf")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_documents_success(self, mock_get_token, mock_decode, mock_s3):
        """
        GET with valid lease_id return 200 with tenant_documents and lease_documents.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn("tenant_documents", content)
        self.assertIn("lease_documents", content)
        self.assertIsInstance(content["tenant_documents"], list)
        self.assertIsInstance(content["lease_documents"], list)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_onboarding_documents_without_lease_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 400 when lease_id query parameter is missing.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_onboarding_documents_with_invalid_lease_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 404 when requested lease does not exist.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"lease_id": 99999},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_onboarding_documents_for_inactive_lease_returns_404(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 404 when lease is soft deleted (is_active=False).
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.lease.is_active = False
        self.lease.save()

        res = self.client.get(
            self.url, {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


    # POST — upload documents
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/doc.pdf")
    @patch("lease.views.get_extension_from_base64", return_value=".pdf")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_onboarding_document_returns_201_and_creates_document(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        POST valid base64 doc with document_type_id return 201 with created id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "lease_id": self.lease.id,
            "documents": [{
                "data": "data:application/pdf;base64,JVBERi0xLjQ=",
                "file_name": "passport.pdf",
                "document_type_id": self.doc_type.id,
            }],
        }
        res = self.client.post(
            self.url, json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        ids = res.json()["content"]["ids"]
        self.assertEqual(len(ids), 1)
        self.assertTrue(LeaseDocuments.objects.filter(id=ids[0]).exists())

    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/doc.pdf")
    @patch("lease.views.get_extension_from_base64", return_value=".pdf")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_document_with_invalid_document_type_returns_empty_ids(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Document with invalid document_type_id is skipped — ids list is empty.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "lease_id": self.lease.id,
            "documents": [{
                "data": "data:application/pdf;base64,JVBERi0xLjQ=",
                "file_name": "test.pdf",
                "document_type_id": 99999,  # does not exist
            }],
        }
        res = self.client.post(
            self.url, json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["ids"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_document_without_lease_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 400 when lease_id is missing in request payload.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url, json.dumps({"documents": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_document_with_invalid_lease_id_returns_404(self, mock_get_token, mock_decode):
        """
        POST with non-existent lease_id return 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url, json.dumps({"lease_id": 99999, "documents": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_empty_documents_list_returns_201_with_empty_ids(self, mock_get_token, mock_decode):
        """
        "POST with empty documents list return 201, ids=[].
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url, json.dumps({"lease_id": self.lease.id, "documents": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["ids"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_document_with_invalid_json_returns_400(self, mock_get_token, mock_decode):
        """
        POST with malformed JSON body return 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url, "not-json",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_onboarding_document_returns_200_and_removes_document(self, mock_get_token, mock_decode):
        """
        DELETE existing document_id return 200, document removed from DB.
        """
        self._mock_auth(mock_get_token, mock_decode)

        doc = LeaseDocuments.objects.create(
            lease=self.lease,
            document_type=self.doc_type,
            file_name="test.pdf",
            file_path="https://s3.example.com/test.pdf",
            created_by=self.pm_user,
        )

        res = self.client.delete(
            f"{self.url}?document_id={doc.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        self.assertFalse(LeaseDocuments.objects.filter(id=doc.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_missing_document_id_returns_400(self, mock_get_token, mock_decode):
        """
        DELETE without document_id return 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Auth & method guards 

    def test_onboarding_documents_without_auth_returns_401(self):
        """    
        Verify API returns HTTP 401 for unauthenticated requests.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_put_method_on_onboarding_documents_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported PUT method returns HTTP 405 Method Not Allowed.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.put(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)


# get_templates   GET /api/lease/templates
class GetTemplatesTestCase(TestCase):
    """
    File: lease/tests/test_templates.py 
    """

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease/templates"

        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.token   = self.s["token"]

        self.t1 = Template.objects.create(name="Standard Lease", is_active=True, created_by=self.pm_user)
        self.t2 = Template.objects.create(name="Commercial Lease", is_active=True, created_by=self.pm_user)
        self.t3 = Template.objects.create(name="Inactive Template", is_active=False, created_by=self.pm_user)

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_templates_returns_only_active_templates(self, mock_get_token, mock_decode):
        """
        GET returns list of active templates only.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")

        self.assertEqual(res.status_code, 200)
        templates = res.json()["content"]["templates"]
        names = [t["name"] for t in templates]
        self.assertIn("Standard Lease", names)
        self.assertIn("Commercial Lease", names)
        # Inactive must not appear
        self.assertNotIn("Inactive Template", names)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_templates_response_contains_id_and_name_fields(self, mock_get_token, mock_decode):
        """
        Each template has id and name.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")

        for t in res.json()["content"]["templates"]:
            self.assertIn("id", t)
            self.assertIn("name", t)

    def test_get_templates_without_auth_returns_401(self):
        """
        Verify templates API returns HTTP 401 for unauthenticated requests.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_method_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported POST method returns HTTP 405 Method Not Allowed.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.post(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

# get_template_fields   GET /api/lease/template-fields
class GetTemplateFieldsTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease/template-fields"

        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]

        self.lease = LeaseFactory(
            unit=self.unit, tenant=self.tenant,
            created_by=self.pm_user,
        )

        self.template = Template.objects.create(name="Test Template", is_active=True, created_by=self.pm_user)
        self.field = TemplateField.objects.create(
            template=self.template,
            id_attribute="tenant_name",
            name_attribute="tenant_name",
            label_attribute="Tenant Name",
            html_tag="input",
            required=True,
            created_by=self.pm_user
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    @patch("lease.views.fetch_s3_presigned_url", return_value="")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_template_fields_returns_200_with_fields_and_defaults(self, mock_get_token, mock_decode, mock_s3):
        """
        GET with valid template_id return 200 with fields list.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"template_id": self.template.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn("fields", content)
        self.assertIn("saved_values", content)
        self.assertIn("lease_defaults", content)
        self.assertEqual(len(content["fields"]), 1)

    @patch("lease.views.fetch_s3_presigned_url", return_value="")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_template_fields_with_lease_id_populates_lease_defaults(self, mock_get_token, mock_decode, mock_s3):
        """
        GET with template_id + lease_id return lease_defaults populated.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"template_id": self.template.id, "lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        lease_defaults = res.json()["content"]["lease_defaults"]
        # tenant_name must be pre-populated
        self.assertIn("tenant_name", lease_defaults)
        self.assertIn("Alice", lease_defaults["tenant_name"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_template_fields_without_template_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 400 when template_id is missing.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_template_fields_non_existent_template_returns_404(self, mock_get_token, mock_decode):
        """
        Verify API returns HTTP 404 when template does not exist.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"template_id": 99999},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_template_fields_api_without_auth_returns_401(self):
        """
        Verify template-fields API returns HTTP 401 for unauthenticated requests.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_method_on_template_fields_api_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported POST method returns HTTP 405 Method Not Allowed.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.post(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

# generate_contract   POST /api/lease/generate-contract
class GenerateContractTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease/generate-contract"

        self.s       = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]

        self.lease = LeaseFactory(
            unit=self.unit, tenant=self.tenant,
            created_by=self.pm_user,
        )
        self.template = Template.objects.create(
            name="Test Template", is_active=True, created_by=self.pm_user,
            template_path="/tmp/test_template.html",  # will be mocked
        )
        self.field = TemplateField.objects.create(
            template=self.template,
            id_attribute="tenant_name",
            name_attribute="tenant_name",
            label_attribute="Tenant Name",
            html_tag="input",
            required=True,
            is_active=True,
            created_by=self.pm_user
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    @patch("lease.views.audit_logs")
    @patch("lease.views.fetch_s3_presigned_url", return_value="https://s3.example.com/lease.pdf")
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/lease.pdf")
    @patch("lease.views.WeasyprintHTML")
    @patch("lease.views.replace_placeholders", return_value="<html>contract</html>")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("os.path.exists", return_value=True)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_returns_200_with_pdf_url_and_filename(
        self, mock_get_token, mock_decode, mock_exists, mock_open,
        mock_replace, mock_weasy, mock_upload, mock_s3, mock_audit
    ):
        """
        POST with valid template_id, lease_id, values returns 200 with pdf_url.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.return_value = b"%PDF-1.4"
        mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"

        payload = {
            "template_id": self.template.id,
            "lease_id": self.lease.id,
            "values": {"tenant_name": "Alice Smith"},
        }
        res = self.client.post(
            self.url, json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertIn("pdf_url", content)
        self.assertIn("file_name", content)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_missing_fields_returns_400(self, mock_get_token, mock_decode):
        """
        POST without template_id / lease_id / values returns 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Missing values
        res = self.client.post(
            self.url,
            json.dumps({"template_id": self.template.id, "lease_id": self.lease.id}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

        # Missing lease_id
        res = self.client.post(
            self.url,
            json.dumps({"template_id": self.template.id, "values": {"k": "v"}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_non_existent_template_returns_404(self, mock_get_token, mock_decode):
        """
        POST with non-existent template_id returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url,
            json.dumps({"template_id": 99999, "lease_id": self.lease.id, "values": {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_non_existent_lease_returns_404(self, mock_get_token, mock_decode):
        """
        POST with non-existent lease_id returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url,
            json.dumps({"template_id": self.template.id, "lease_id": 99999, "values": {}}),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("os.path.exists", return_value=False)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_template_file_missing_returns_404(self, mock_get_token, mock_decode, mock_exists):
        """
        POST when template_path file does not exist on disk returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url,
            json.dumps({
                "template_id": self.template.id,
                "lease_id": self.lease.id,
                "values": {"tenant_name": "Alice"},
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("lease.views.audit_logs")
    @patch("lease.views.fetch_s3_presigned_url", return_value="https://s3.example.com/lease.pdf")
    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/lease.pdf")
    @patch("lease.views.WeasyprintHTML")
    @patch("lease.views.replace_placeholders", return_value="<html></html>")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("os.path.exists", return_value=True)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_generate_contract_saves_pdf_path_to_lease(
        self, mock_get_token, mock_decode, mock_exists, mock_open,
        mock_replace, mock_weasy, mock_upload, mock_s3, mock_audit
    ):
        """After generate, lease.pdf_path is updated in DB."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_weasy.return_value.write_pdf.return_value = b"%PDF-1.4"
        mock_open.return_value.__enter__.return_value.read.return_value = "<html></html>"

        self.client.post(
            self.url,
            json.dumps({
                "template_id": self.template.id,
                "lease_id": self.lease.id,
                "values": {"tenant_name": "Alice"},
            }),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.lease.refresh_from_db()
        self.assertIsNotNone(self.lease.pdf_path)
        self.assertNotEqual(self.lease.pdf_path, "")

    def test_generate_contract_without_auth_returns_401(self):
        """
        Verify generate-contract API returns HTTP 401 for unauthenticated requests.
        """
        res = self.client.post(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_method_on_generate_contract_api_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported GET method returns HTTP 405 Method Not Allowed.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)