import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from charges.models import Charge
from property_management.models import Country, State, City
from user_service.models import PropertyManager
from utilities import status
from property.models import PropertyManagmentCompany


class ChargesAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            email="test@gmail.com"
        ) 
        #  Location hierarchy        
        self.country = Country.objects.create(name="India")
        self.state   = State.objects.create(name="Maharashtra", country=self.country)
        self.city    = City.objects.create(name="Pune", state=self.state)

        # PMC Company
        self.company = PropertyManagmentCompany.objects.create(
            name="Test PMC",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC001",
            licence_expiry_date=__import__("django.utils.timezone", fromlist=["now"]).now(),
            licence_issuer="Gov",
            created_by=self.user,
        )

        # Authenticated user profile must also be a PropertyManager because
        # charges.views resolves the PMC with PropertyManager.objects.filter(pk=request.user.pk).
        self.property_manager = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",
            company=self.company,
            created_by=self.user,
            city=self.city,
        )
        self.user_profile = self.property_manager

        # URL
        self.url = reverse("charges")

        # Sample Charge
        self.charge = Charge.objects.create(
            description="Test Charge",
            amount=100,
            tax_code=10,
            is_editable=True,
            country=self.country,
            pmc=self.company,
            created_by=self.user
        )

    # Common JWT mock
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": "test@gmail.com"}

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_charges_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify all charges are fetched successfully for authenticated user.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    #  GET SINGLE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_charge_by_valid_id_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify single charge details are fetched successfully using valid charge ID.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.get(
            f"{self.url}?charge_id={self.charge.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_charge_with_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify 404 is returned when charge ID does not exist.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.get(
            f"{self.url}?charge_id=99999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    #  CREATE
    @patch("charges.views.audit_logs")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_charge_with_valid_data_returns_created_response(self, mock_get_token, mock_decode, mock_audit):
        """
        Verify new charge is created successfully using valid request data.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "description": "New Charge",
            "amount": 200
        }

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_charge_with_missing_fields_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify charge creation fails when required fields are missing.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_charge_missing_amount_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify charge creation fails when amount field is missing.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.post(
            self.url,
            data=json.dumps({"description": "No Amount"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    #  UPDATE
    @patch("charges.views.audit_logs")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_charge_with_valid_data_returns_success_response(self, mock_get_token, mock_decode, mock_audit):
        """
        Verify existing charge is updated successfully using valid charge ID and data.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "charge_id": self.charge.id,
            "description": "Updated Charge",
            "amount": 500
        }

        response = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_charge_with_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify charge update fails when invalid charge ID is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.put(
            self.url,
            data=json.dumps({"charge_id": 999}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_charge_without_charge_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify charge update fails when charge ID is missing in request.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.put(
            self.url,
            data=json.dumps({"description": "No ID"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

   #delete charge
    @patch("charges.views.audit_logs")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_charge_with_valid_id_returns_success_response(self, mock_get_token, mock_decode, mock_audit):
        """
        Verify charge is deleted successfully using valid charge ID.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.delete(
            f"{self.url}?charge_id={self.charge.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Charge.objects.filter(id=self.charge.id).exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_charge_with_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify charge deletion fails when invalid charge ID is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.delete(
            f"{self.url}?charge_id=999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_charge_without_charge_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify charge deletion fails when charge ID is not provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_charges_without_auth_returns_401(self):
        """
        Verify GET /charges without Authorization header returns 401 Unauthorized.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_patch_method_returns_405(self, mock_get_token, mock_decode):
        """
        Verify PATCH request on /charges returns 405 Method Not Allowed since PATCH is not supported on this endpoint.
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.patch(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
