import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch, MagicMock

from utilities import status
from property.models import (
    Property, PropertyBlocks, Unit, UnitImages,
    UnitDocuments, PropertyManagmentCompany
)
from user_service.models import PropertyManager, DocumentType


class UnitAPITestCase(TestCase):

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

        # ── Block ─────────────────────────────────────────────────────
        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="Block A",
            no_of_floors=5,
            no_of_parking=2,
            no_of_units=10,
            created_by=self.admin_user,
        )

        # ── Unit ──────────────────────────────────────────────────────
        self.unit = Unit.objects.create(
            property_block_tower=self.block,
            unit_name="101",
            created_by=self.admin_user,
        )

        # ── DocumentType (needed for UnitDocuments) ───────────────────
        self.doc_type = DocumentType.objects.create(
            name="Lease Agreement",
            section="UNIT",
            created_by=self.admin_user,
        )

        # ── UnitImages ────────────────────────────────────────────────
        self.unit_image = UnitImages.objects.create(
            unit=self.unit,
            image_path="path/to/image",
            image_type="INTERIOR",
            file_name="test.jpg",
            created_by=self.admin_user,
        )

        # ── UnitDocuments ─────────────────────────────────────────────
        self.unit_doc = UnitDocuments.objects.create(
            unit=self.unit,
            document_type=self.doc_type,
            file_name="test.pdf",
            file_path="path/to/doc",
            created_by=self.admin_user,
        )

        # ── URLs ──────────────────────────────────────────────────────
        self.url_unit       = "/property/unit"
        self.url_images     = "/property/unit/images"
        self.url_doc_types  = "/property/unit/document-types"
        self.url_docs       = "/property/unit/documents"

    # ── Auth mock helper ──────────────────────────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # ════════════════════════════════════════════════════════════════
    #  UNIT — GET
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_units(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("content", res.json())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_unit(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"unit_id": self.unit.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["id"], self.unit.id)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"unit_id": 99999},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_by_property_filter(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_by_block_filter(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"block_id": self.block.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_csv_export(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"export": "csv"},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("units.csv", res["Content-Disposition"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_pagination(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"page": 1, "page_size": 5},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", res.json())

    def test_get_unit_no_auth(self):
        res = self.client.get(self.url_unit)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ════════════════════════════════════════════════════════════════
    #  UNIT — POST
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_unit_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "block_id": self.block.id,
            "unit_name": "102",
            "rent": 5000,
        }

        res = self.client.post(
            self.url_unit,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.json()["content"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_unit_missing_block_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {"unit_name": "103"}

        res = self.client.post(
            self.url_unit,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_unit_missing_unit_name(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {"block_id": self.block.id}

        res = self.client.post(
            self.url_unit,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_unit_invalid_block(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {"block_id": 99999, "unit_name": "104"}

        res = self.client.post(
            self.url_unit,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ════════════════════════════════════════════════════════════════
    #  UNIT — PUT
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_unit_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": self.unit.id,
            "unit_name": "Updated 101",
            "rent": 6000,
        }

        res = self.client.put(
            self.url_unit,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.unit_name, "Updated 101")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_unit_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_unit,
            data=json.dumps({"unit_name": "No ID"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_unit_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_unit,
            data=json.dumps({"unit_id": 99999, "unit_name": "Ghost"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_unit_invalid_method(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_unit,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ════════════════════════════════════════════════════════════════
    #  UNIT IMAGES — GET
    # ════════════════════════════════════════════════════════════════
    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_images_success(self, mock_get_token, mock_decode, mock_s3):
        self._mock_auth(mock_get_token, mock_decode)
        mock_s3.return_value = "https://s3.example.com/test.jpg"

        res = self.client.get(
            self.url_images,
            {"unit_id": self.unit.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("content", res.json())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_images_missing_unit_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    #  UNIT IMAGES — POST (S3 upload mock करतो)
    # ════════════════════════════════════════════════════════════════
    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_images_success(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".jpg"
        mock_upload.return_value = "https://s3.example.com/uploaded.jpg"

        data = {
            "unit_id": self.unit.id,
            "images": [
                {
                    "data": "base64encodeddata",
                    "file_name": "photo.jpg",
                    "type": "INTERIOR"
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

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_images_missing_unit_id(self, mock_get_token, mock_decode):
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
    def test_upload_unit_images_invalid_unit(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": 99999,
            "images": [{"data": "base64data", "file_name": "x.jpg"}]
        }

        res = self.client.post(
            self.url_images,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ════════════════════════════════════════════════════════════════
    #  UNIT IMAGES — DELETE
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_image_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_images}?image_id={self.unit_image.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(UnitImages.objects.filter(id=self.unit_image.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_image_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    #  UNIT DOCUMENT TYPES — GET
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_document_types(self, mock_get_token, mock_decode):
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
    def test_unit_document_types_invalid_method(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_doc_types,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ════════════════════════════════════════════════════════════════
    #  UNIT DOCUMENTS — GET
    # ════════════════════════════════════════════════════════════════
    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_documents_success(self, mock_get_token, mock_decode, mock_s3):
        self._mock_auth(mock_get_token, mock_decode)
        mock_s3.return_value = "https://s3.example.com/test.pdf"

        res = self.client.get(
            self.url_docs,
            {"unit_id": self.unit.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("content", res.json())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_documents_missing_unit_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    #  UNIT DOCUMENTS — POST (S3 mock)
    # ════════════════════════════════════════════════════════════════
    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_documents_success(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        self._mock_auth(mock_get_token, mock_decode)
        mock_ext.return_value = ".pdf"
        mock_upload.return_value = "https://s3.example.com/uploaded.pdf"

        data = {
            "unit_id": self.unit.id,
            "documents": [
                {
                    "data": "base64pdfdata",
                    "file_name": "lease.pdf",
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

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_documents_missing_unit_id(self, mock_get_token, mock_decode):
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
    def test_upload_unit_documents_invalid_unit(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": 99999,
            "documents": [{"data": "base64data", "file_name": "x.pdf", "document_type_id": self.doc_type.id}]
        }

        res = self.client.post(
            self.url_docs,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # ════════════════════════════════════════════════════════════════
    #  UNIT DOCUMENTS — DELETE
    # ════════════════════════════════════════════════════════════════
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_document_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_docs}?document_id={self.unit_doc.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(UnitDocuments.objects.filter(id=self.unit_doc.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_document_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    #  No auth → 401
    # ════════════════════════════════════════════════════════════════
    def test_no_auth_unit(self):
        res = self.client.get(self.url_unit)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_auth_images(self):
        res = self.client.get(self.url_images)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_auth_doc_types(self):
        res = self.client.get(self.url_doc_types)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_no_auth_documents(self):
        res = self.client.get(self.url_docs)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)