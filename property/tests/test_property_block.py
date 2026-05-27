import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import Property, PropertyBlocks, PropertyManagmentCompany
from user_service.models import PropertyManager


class PropertyBlocksAPITestCase(TestCase):

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

        # PropertyManager 
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
        # FLOOR_CHOICES: 0-50, PARKING_CHOICES: 0-10, UNITS_CHOICES: 1-100
        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="Block A",
            no_of_floors=5,
            no_of_parking=2,
            no_of_units=10,
            created_by=self.admin_user,
        )

        # URL 
        self.url = "/property/blocks"

    # ── Auth mock helper ──────────────────────────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    #  GET
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_blocks_with_valid_property_id_returns_success(self, mock_get_token, mock_decode):
        """
        Verify property blocks are fetched successfully for a valid property_id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("content", data)
        self.assertEqual(len(data["content"]), 1)
        self.assertEqual(data["content"][0]["block_name"], "Block A")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_blocks_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET request without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_blocks_with_invalid_property_id_returns_empty_list(self, mock_get_token, mock_decode):
        """
        Verify invalid property_id returns an empty blocks list. 
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"property_id": 99999},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"], [])

    def test_get_property_blocks_without_auth_returns_401(self):
        """
        Verify unauthenticated request to property blocks API returns 401 unauthorized.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  POST
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_blocks_with_valid_data_returns_success(self, mock_get_token, mock_decode):
        """
        verify block created
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": self.property.id,
            "blocks": [
                {
                    "block_name": "Block B",
                    "no_of_floors": 3,
                    "no_of_parking": 1,
                    "no_of_units": 5,
                },
                {
                    "block_name": "Block C",
                    "no_of_floors": 2,
                    "no_of_parking": 0,
                    "no_of_units": 4,
                }
            ]
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        resp = res.json()
        self.assertIn("content", resp)
        self.assertIn("ids", resp["content"])
        self.assertEqual(len(resp["content"]["ids"]), 2)

        # verify in DB created or not
        self.assertEqual(
            PropertyBlocks.objects.filter(property=self.property).count(), 3
        )

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_blocks_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify creating property blocks without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "blocks": [{"block_name": "Block X", "no_of_floors": 1}]
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_blocks_with_invalid_property_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify creating property blocks with invalid property_id returns 404 not found.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": 99999,
            "blocks": [{"block_name": "Block X", "no_of_floors": 1}]
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_blocks_with_empty_blocks_list_returns_empty_ids(self, mock_get_token, mock_decode):
        """
        Verify creating property blocks with empty blocks list returns success with empty ids list.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": self.property.id,
            "blocks": []
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["ids"], [])

    def test_create_property_blocks_without_auth_returns_401(self):
        """
        Verify unauthenticated request to create property blocks returns 401 unauthorized.
        """
        res = self.client.post(self.url, content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  PUT
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_blocks_with_valid_data_returns_success(self, mock_get_token, mock_decode):
        """
        Verify existing property blocks are replaced successfully with updated block details.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": self.property.id,
            "blocks": [
                {
                    "block_name": "Updated Block A",
                    "no_of_floors": 10,
                    "no_of_parking": 5,
                    "no_of_units": 20,
                }
            ]
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        blocks = PropertyBlocks.objects.filter(property=self.property)
        self.assertEqual(blocks.count(), 1)
        self.assertEqual(blocks.first().block_name, "Updated Block A")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_blocks_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify updating property blocks without property_id returns 400 bad request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "blocks": [{"block_name": "Block X"}]
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_blocks_with_invalid_property_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify updating property blocks with invalid property_id returns 404 not found.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": 99999,
            "blocks": [{"block_name": "Block X"}]
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_blocks_with_empty_blocks_list_removes_existing_blocks(self, mock_get_token, mock_decode):
        """
        Verify updating property with empty blocks list removes all existing blocks.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": self.property.id,
            "blocks": []
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PropertyBlocks.objects.filter(property=self.property).count(), 0
        )

    def test_update_property_blocks_without_auth_returns_401(self):
        """
        Verify unauthenticated request to update property blocks returns 401 unauthorized.
        """
        res = self.client.put(self.url, content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  Invalid method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invalid_method_returns_405(self, mock_get_token, mock_decode):
        """
        invalid method return 405
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def _create_other_company_property(self):
        other_company = PropertyManagmentCompany.objects.create(
            name="Other Company",
            address_line_1="other addr1",
            address_line_2="other addr2",
            licence_number="LIC999",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )
        other_property = Property.objects.create(
            property_name="Other Property",
            address_line_1="other addr1",
            address_line_2="other addr2",
            landmark="other landmark",
            pincode="654321",
            no_of_blocks=1,
            no_of_units=1,
            pmc=other_company,
            created_by=self.admin_user,
        )
        other_block = PropertyBlocks.objects.create(
            property=other_property,
            block_name="Other Block",
            no_of_floors=5,
            no_of_parking=2,
            no_of_units=10,
            created_by=self.admin_user,
        )
        return other_property, other_block

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_manager_cannot_get_other_company_property_blocks(
        self, mock_get_token, mock_decode
    ):
        """
        Verify PropertyManager cannot see blocks for another company's property.
        """
        other_property, _ = self._create_other_company_property()
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"property_id": other_property.id},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"], [])
