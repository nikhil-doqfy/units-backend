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
