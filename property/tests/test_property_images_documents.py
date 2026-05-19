import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from utilities import status
from property.models import (
    Property, PropertyBlocks, PropertyImages,
    PropertyDocuments, PropertyManagmentCompany
)
from user_service.models import PropertyManager, DocumentType


class PropertyImagesDocumentsAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # ── Users ─────────────────────────────────────────────────────
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com"
        )
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            email="testuser@test.com"
        )

        # ── Company ───────────────────────────────────────────────────
        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC123",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )

        # ── PropertyManager (= UserProfile) ───────────────────────────
        self.pm = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",
            company=self.company,
            created_by=self.admin_user,
        )

        # ── Property ──────────────────────────────────────────────────
        self.property = Property.objects.create(
            property_name="Test Property",
            address_line_1="addr1",
            address_line_2="addr2",
            landmark="landmark",
            pincode="123456",
            no_of_blocks=1,
            no_of_units=1,
            pmc=self.company,
            created_by=self.admin_user,
        )

        # ── DocumentType (section=PROPERTY) ───────────────────────────
        self.doc_type = DocumentType.objects.create(
            name="Title Deed",
            section="PROPERTY",
            created_by=self.admin_user,
        )

        # ── PropertyImages ────────────────────────────────────────────
        self.prop_image = PropertyImages.objects.create(
            property=self.property,
            image_path="path/to/image",
            image_type="EXTERIOR",
            file_name="exterior.jpg",
            created_by=self.admin_user,
        )

        # ── PropertyDocuments ─────────────────────────────────────────
        self.prop_doc = PropertyDocuments.objects.create(
            property=self.property,
            document_type=self.doc_type,
            file_name="title_deed.pdf",
            file_path="path/to/doc",
            created_by=self.admin_user,
        )

        # ── URLs ──────────────────────────────────────────────────────
        self.url_images    = "/property/images"
        self.url_doc_types = "/property/document-types"
        self.url_docs      = "/property/documents"

    # ── Auth mock helper ──────────────────────────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # PROPERTY IMAGES — GET
    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_images_with_valid_property_id_returns_success(self, mock_get_token, mock_decode, mock_s3):
        """
        Verify property images are fetched successfully for a valid property_id.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_s3.return_value = "https://s3.example.com/exterior.jpg"

        res = self.client.get(
            self.url_images,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["image_type"], "EXTERIOR")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_images_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET request without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_images_with_invalid_property_id_returns_empty_list(self, mock_get_token, mock_decode, mock_s3):
        """
        Verify invalid property_id returns an empty images list.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_s3.return_value = "https://s3.example.com/test.jpg"

        res = self.client.get(
            self.url_images,
            {"property_id": 99999},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"], [])

    def test_get_property_images_without_authentication_returns_401(self):
        """
        test_get_property_images_without_auth_returns_401
        """
        res = self.client.get(self.url_images)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ════════════════════════════════════════════════════════════════
    # PROPERTY IMAGES — POST
    # ════════════════════════════════════════════════════════════════

    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_images_with_valid_data_returns_success(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify property images upload succeeds with valid request payload
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".jpg"
        mock_upload.return_value = "https://s3.example.com/uploaded.jpg"

        data = {
            "property_id": self.property.id,
            "images": [
                {
                    "data": "base64imagedata",
                    "file_name": "front.jpg",
                    "type": "EXTERIOR"
                }
            ]
        }

        res = self.client.post(
            self.url_images,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("ids", res.json()["content"])
        self.assertEqual(len(res.json()["content"]["ids"]), 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_images_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify uploading property images without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_images,
            data=json.dumps({"images": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_images_with_invalid_property_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify uploading property images with invalid property_id returns 404 not found.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": 99999,
            "images": [{"data": "base64data", "file_name": "x.jpg"}]
        }

        res = self.client.post(
            self.url_images,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_images_with_empty_image_list_returns_empty_ids(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify uploading empty images list returns success with empty ids list.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".jpg"
        mock_upload.return_value = "https://s3.example.com/x.jpg"

        data = {
            "property_id": self.property.id,
            "images": []
        }

        res = self.client.post(
            self.url_images,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["ids"], [])

    # PROPERTY IMAGES — DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_property_image_with_valid_image_id_returns_success(self, mock_get_token, mock_decode):
        """
        Verify property image is deleted successfully for a valid image_id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_images}?image_id={self.prop_image.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(PropertyImages.objects.filter(id=self.prop_image.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_property_image_without_image_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify DELETE request without image_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_images_put_method_returns_405(self, mock_get_token, mock_decode):
        """
        Verify PUT method is not allowed on property images API endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_images,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # PROPERTY DOCUMENT TYPES — GET
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_document_types_returns_success(self, mock_get_token, mock_decode):
        """
        Verify property document types are fetched successfully.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_doc_types,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        self.assertIn("id", content[0])
        self.assertIn("name", content[0])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_document_types_post_method_returns_405(self, mock_get_token, mock_decode):
        """
         Verify POST method is not allowed on property document types API endpoin
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_doc_types,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_property_document_types_without_authentication_returns_401(self):
        """
        Verify unauthenticated request to property document types API returns 401 unauthorized.
        """
        res = self.client.get(self.url_doc_types)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # PROPERTY DOCUMENTS — GET
    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_documents_with_valid_property_id_returns_success(self, mock_get_token, mock_decode, mock_s3):
        """
        Verify property documents are fetched successfully for a valid property_id.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_s3.return_value = "https://s3.example.com/title_deed.pdf"

        res = self.client.get(
            self.url_docs,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["file_name"], "title_deed.pdf")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_documents_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET request without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_property_documents_without_authentication_returns_401(self):
        """
        Verify unauthenticated request to property documents API returns 401 unauthorized.
        """
        res = self.client.get(self.url_docs)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # PROPERTY DOCUMENTS — POST
    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_documents_with_valid_data_returns_success(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify property documents upload succeeds with valid request payload.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".pdf"
        mock_upload.return_value = "https://s3.example.com/uploaded.pdf"

        data = {
            "property_id": self.property.id,
            "documents": [
                {
                    "data": "base64pdfdata",
                    "file_name": "deed.pdf",
                    "document_type_id": self.doc_type.id,
                }
            ]
        }

        res = self.client.post(
            self.url_docs,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("ids", res.json()["content"])
        self.assertEqual(len(res.json()["content"]["ids"]), 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_documents_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify uploading property documents without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_docs,
            data=json.dumps({"documents": []}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_documents_with_invalid_property_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify uploading property documents with invalid property_id returns 404 not found.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": 99999,
            "documents": [{"data": "base64data", "file_name": "x.pdf", "document_type_id": self.doc_type.id}]
        }

        res = self.client.post(
            self.url_docs,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_property_documents_with_empty_list_returns_empty_ids(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify uploading empty documents list returns success with empty ids list.
        """
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".pdf"
        mock_upload.return_value = "https://s3.example.com/x.pdf"

        data = {
            "property_id": self.property.id,
            "documents": []
        }

        res = self.client.post(
            self.url_docs,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["ids"], [])

    # PROPERTY DOCUMENTS — DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_property_document_with_valid_document_id_returns_success(self, mock_get_token, mock_decode):
        """
        Verify property document is deleted successfully for a valid document_id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_docs}?document_id={self.prop_doc.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(PropertyDocuments.objects.filter(id=self.prop_doc.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_property_document_without_document_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify DELETE request without document_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_documents_put_method_returns_405(self, mock_get_token, mock_decode):
        """
        Verify PUT method is not allowed on property documents API endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_docs,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)