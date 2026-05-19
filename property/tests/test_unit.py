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

        # Users
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

        # Company
        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC123",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )

        # PropertyManager (= UserProfile)
        self.pm = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",
            company=self.company,
            created_by=self.admin_user,
        )

        # Property
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

        # Block
        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="Block A",
            no_of_floors=5,
            no_of_parking=2,
            no_of_units=10,
            created_by=self.admin_user,
        )

        # Unit
        self.unit = Unit.objects.create(
            property_block_tower=self.block,
            unit_name="101",
            created_by=self.admin_user,
        )

        # DocumentType
        self.doc_type = DocumentType.objects.create(
            name="Lease Agreement",
            section="UNIT",
            created_by=self.admin_user,
        )

        # UnitImages
        self.unit_image = UnitImages.objects.create(
            unit=self.unit,
            image_path="path/to/image",
            image_type="INTERIOR",
            file_name="test.jpg",
            created_by=self.admin_user,
        )

        # UnitDocuments
        self.unit_doc = UnitDocuments.objects.create(
            unit=self.unit,
            document_type=self.doc_type,
            file_name="test.pdf",
            file_path="path/to/doc",
            created_by=self.admin_user,
        )

        # URLs
        self.url_unit       = "/property/unit"
        self.url_images     = "/property/unit/images"
        self.url_doc_types  = "/property/unit/document-types"
        self.url_docs       = "/property/unit/documents"

    # Auth mock helper
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # UNIT — GET
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_units_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit without filters returns all units with a 200 
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("content", res.json())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_unit_by_unit_id_returns_correct_unit(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?unit_id=X returns the specific unit matching the given unit_id
        """
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
    def test_get_unit_with_invalid_unit_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?unit_id=99999 returns 404 when the unit does not exist in the database.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"unit_id": 99999},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_filtered_by_property_id_returns_200(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?property_id=X filters and returns units belonging to the specified property.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_filtered_by_block_id_returns_200(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?block_id=X filters and returns units belonging to the specified block.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"block_id": self.block.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_units_with_csv_export_returns_csv_file(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?export=csv returns a CSV file with correct Content-Type and Content-Disposition headers.
        """
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
    def test_get_units_with_pagination_params_returns_pagination_info(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit?page=1&page_size=5 returns paginated response with pagination metadata in the response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_unit,
            {"page": 1, "page_size": 5},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("pagination", res.json())

    def test_get_unit_without_auth_token_returns_401(self):
        """
        Verify GET /property/unit without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url_unit)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # UNIT — POST
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_unit_with_valid_data_returns_201(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit with valid block_id and unit_name creates the unit successfully and returns 201 with unit id.
        """
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
    def test_create_unit_without_block_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit without block_id returns 400 Bad Request since block_id is a required field.
        """
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
    def test_create_unit_without_unit_name_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit without unit_name returns 400 Bad Request since unit_name is a required field.
        """
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
    def test_create_unit_with_non_existent_block_returns_404(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit with a block_id that does not exist returns 404 Not Found.
        """
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
    # UNIT — PUT
    # ════════════════════════════════════════════════════════════════

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_unit_with_valid_data_returns_200_and_updates_db(self, mock_get_token, mock_decode):
        """
        Verify PUT /property/unit with valid unit_id updates unit_name and rent in the database and returns 200 OK.
        """
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
    def test_update_unit_without_unit_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify PUT /property/unit without unit_id returns 400 Bad Request since unit_id is required to identify which unit to update.
        """
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
    def test_update_unit_with_non_existent_unit_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify PUT /property/unit with a unit_id that does not exist returns 404 Not Found.
        """
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
    def test_unit_delete_method_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property/unit returns 405 Method Not Allowed since DELETE is not supported on this endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_unit,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # ════════════════════════════════════════════════════════════════
    # UNIT IMAGES — GET
    # ════════════════════════════════════════════════════════════════

    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_images_by_unit_id_returns_200(self, mock_get_token, mock_decode, mock_s3):
        """
        Verify GET /property/unit/images?unit_id=X returns all images for the specified unit with presigned S3 URLs.
        """
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
    def test_get_unit_images_without_unit_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit/images without unit_id returns 400 since unit_id is required to fetch images.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    # UNIT IMAGES — POST
    # ════════════════════════════════════════════════════════════════

    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_images_with_valid_data_returns_201(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify POST /property/unit/images with valid unit_id and base64 image uploads the image to S3 and returns 201 with created image ids.
        """
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
    def test_upload_unit_images_without_unit_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit/images without unit_id returns 400 since unit_id is required to associate images with a unit.
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
    def test_upload_unit_images_with_non_existent_unit_returns_404(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit/images with a unit_id that does not exist returns 404 Not Found.
        """
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

    # UNIT IMAGES — DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_image_by_image_id_removes_from_db(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property/unit/images?image_id=X deletes the image from the database and returns 200 OK.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_images}?image_id={self.unit_image.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(UnitImages.objects.filter(id=self.unit_image.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_image_without_image_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property/unit/images without image_id returns 400 since image_id is required to identify which image to delete.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_images,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # UNIT DOCUMENT TYPES — GET
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_document_types_returns_list_with_id_and_name(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit/document-types returns all available document types with id and name fields in each item.
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
    def test_unit_document_types_post_method_returns_405(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit/document-types returns 405 Method Not Allowed since only GET is supported on this endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_doc_types,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # UNIT DOCUMENTS — GET
    @patch("property.views.fetch_s3_presigned_url")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_unit_documents_by_unit_id_returns_200(self, mock_get_token, mock_decode, mock_s3):
        """
        Verify GET /property/unit/documents?unit_id=X returns all documents for the specified unit with presigned S3 URLs.
        """
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
    def test_get_unit_documents_without_unit_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET /property/unit/documents without unit_id returns 400 since unit_id is required to fetch documents.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # UNIT DOCUMENTS — POST
    @patch("property.views.upload_file_to_s3_base64")
    @patch("property.views.get_extension_from_base64")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_upload_unit_documents_with_valid_data_returns_201(self, mock_get_token, mock_decode, mock_ext, mock_upload):
        """
        Verify POST /property/unit/documents with valid unit_id, base64 data, and document_type_id uploads the document and returns 201 with ids.
        """
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
    def test_upload_unit_documents_without_unit_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit/documents without unit_id returns 400 since unit_id is required to associate documents with a unit.
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
    def test_upload_unit_documents_with_non_existent_unit_returns_404(self, mock_get_token, mock_decode):
        """
        Verify POST /property/unit/documents with a unit_id that does not exist returns 404 Not Found.
        """
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

    # UNIT DOCUMENTS — DELETE

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_document_by_document_id_removes_from_db(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property/unit/documents?document_id=X deletes the document from the database and returns 200 OK.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_docs}?document_id={self.unit_doc.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(UnitDocuments.objects.filter(id=self.unit_doc.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_unit_document_without_document_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property/unit/documents without document_id returns 400 since document_id is required to identify which document to delete.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_docs,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # ════════════════════════════════════════════════════════════════
    # AUTH GUARD — No auth → 401
    # ════════════════════════════════════════════════════════════════

    def test_get_unit_without_auth_token_returns_401(self):
        """
        Verify GET /property/unit without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url_unit)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_unit_images_without_auth_token_returns_401(self):
        """
        Verify GET /property/unit/images without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url_images)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_unit_document_types_without_auth_token_returns_401(self):
        """
        Verify GET /property/unit/document-types without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url_doc_types)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_unit_documents_without_auth_token_returns_401(self):
        """
        Verify GET /property/unit/documents without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url_docs)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)