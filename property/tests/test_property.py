import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import Property, PropertyBlocks, Unit, PropertyManagmentCompany
from user_service.models import PropertyManager


class PropertyAPITestCase(TestCase):

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

        # ── PropertyManager ───────────────────────────────────────────
        # PropertyManager IS the UserProfile — no separate UserProfile
        # decorator: request.user = UserProfile.filter(user__email=email).first()
        # token must match what we send in HTTP_AUTHORIZATION
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
            no_of_blocks=1,       # valid: 1-20
            no_of_units=1,        # valid: 1-100
            pmc=self.company,
            created_by=self.admin_user,
        )

        # ── URL ───────────────────────────────────────────────────────
        self.url = "/property"

    # ── Auth mock helper ──────────────────────────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # GET — list all properties
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_properties_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify GET /property without filters returns all properties with 200 OK status and content key in response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("content", data)

    # GET — single property by id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_property_by_valid_id_returns_correct_property(self, mock_get_token, mock_decode):
        """
        Verify GET /property?property_id=X returns the specific property matching the given property_id with correct id in response.
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
        self.assertEqual(data["content"]["id"], self.property.id)

    # GET — property not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_with_invalid_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify GET /property?property_id=99999 returns 404 Not Found when the property does not exist in the database.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"property_id": 99999},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # GET — search filter
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_properties_with_search_keyword_returns_200(self, mock_get_token, mock_decode):
        """
        Verify GET /property?search=Test filters and returns properties matching the search keyword with 200 OK status.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "Test"},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # GET — CSV export
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_properties_csv_export_returns_csv_file(self, mock_get_token, mock_decode):
        """
        Verify GET /property?export=csv returns a CSV file with correct Content-Type and Content-Disposition headers.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"export": "csv"},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("properties.csv", res["Content-Disposition"])

    # GET — pagination
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_properties_with_pagination_params_returns_pagination_info(self, mock_get_token, mock_decode):
        """
        Verify GET /property?page=1&page_size=5 returns paginated response with pagination metadata included in the response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"page": 1, "page_size": 5},
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("pagination", data)

    # POST — create property success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_with_valid_data_returns_201(self, mock_get_token, mock_decode):
        """
        Verify POST /property with valid data creates the property successfully and returns 201 Created with the new property id.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_name": "New Property",
            "address_line_1": "addr1",
            "address_line_2": "addr2",
            "landmark": "near park",
            "pincode": "411001",
            "no_of_blocks": 2,
            "no_of_units": 10,
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        resp_data = res.json()
        self.assertIn("content", resp_data)
        self.assertIn("id", resp_data["content"])

    # POST — missing property_name → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_without_property_name_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST /property without property_name returns 400 Bad Request since property_name is a required field.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "address_line_1": "addr1",
            "no_of_blocks": 1,
            "no_of_units": 5,
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # POST — no PMC (user is not a PropertyManager) → 403
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_property_by_user_without_pmc_returns_403(self, mock_get_token, mock_decode):
        """
        Verify POST /property by a user who is not linked to any PMC returns 403 Forbidden since only PropertyManagers can create properties.
        """
        other_user = User.objects.create_user(
            username="nopm",
            password="pass",
            email="nopm@test.com"
        )
        from user_service.models import UserProfile
        UserProfile.objects.create(
            user=other_user,
            email=other_user.email,
            token="othertoken",
            created_by=self.admin_user,
        )

        mock_get_token.return_value = "othertoken"
        mock_decode.return_value = {"email": other_user.email}

        data = {"property_name": "Test", "no_of_blocks": 1, "no_of_units": 1}

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer othertoken"
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # PUT — update property success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_with_valid_data_returns_200_and_updates_db(self, mock_get_token, mock_decode):
        """
        Verify PUT /property with valid property_id updates the property_name in the database and returns 200 OK.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": self.property.id,
            "property_name": "Updated Property Name"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.property.refresh_from_db()
        self.assertEqual(self.property.property_name, "Updated Property Name")

    # PUT — missing property_id → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_without_property_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify PUT /property without property_id returns 400 Bad Request since property_id is required to identify which property to update.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {"property_name": "No ID Given"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # PUT — property not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_with_non_existent_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify PUT /property with a property_id that does not exist returns 404 Not Found.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "property_id": 99999,
            "property_name": "Ghost Property"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

     #  Invalid method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_method_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """
        Verify DELETE /property returns 405 Method Not Allowed since DELETE is not supported on this endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    #  No auth token → 401
    def test_get_property_without_auth_token_returns_401(self):
        """
        Verify GET /property without Authorization header returns 401 Unauthorized.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # GET — PropertyManager cannot access another company's property
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_manager_cannot_access_other_company_property(
        self, mock_get_token, mock_decode
    ):
        """
        Verify PropertyManager from one company cannot access properties belonging to another company and receives 404 Not Found.
        """

        # ── Second company ──────────────────────────────────────────
        other_company = PropertyManagmentCompany.objects.create(
            name="Other Company",
            address_line_1="other addr1",
            address_line_2="other addr2",
            licence_number="LIC999",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )

        # ── Second user ────────────────────────────────────────────
        other_user = User.objects.create_user(
            username="otherpm",
            password="testpass",
            email="otherpm@test.com"
        )

        # ── PropertyManager of second company ──────────────────────
        PropertyManager.objects.create(
            user=other_user,
            email=other_user.email,
            token="othervalidtoken",
            company=other_company,
            created_by=self.admin_user,
        )

        # ── Mock auth for second company's manager ────────────────
        mock_get_token.return_value = "othervalidtoken"
        mock_decode.return_value = {"email": other_user.email}

        # Try accessing first company's property
        res = self.client.get(
            self.url,
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer othervalidtoken"
        )

        # Should not be accessible
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_property_manager_property_list_shows_only_own_company_properties(
        self, mock_get_token, mock_decode
    ):
        """
        Verify PropertyManager sees only properties from their own PMC company.
        """
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

        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        property_ids = [prop["id"] for prop in res.json()["content"]]
        self.assertIn(self.property.id, property_ids)
        self.assertNotIn(other_property.id, property_ids)
