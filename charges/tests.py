import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from charges.models import Charge
from property_management.models import Country, State, City
from user_service.models import UserProfile
from utilities import status


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
        self.state = State.objects.create(name="Maharashtra", country=self.country)
        self.city = City.objects.create(name="Pune", state=self.state)

        # UserProfile 
        self.user_profile = UserProfile.objects.create(
            user=self.user,
            token="validtoken",
            created_by=self.user,
            city=self.city
        )
        #URL
        self.url = reverse("charges")

        # Sample Charge
        self.charge = Charge.objects.create(
            description="Test Charge",
            amount=100,
            tax_code=10,
            is_editable=True,
            country=self.country,
            created_by=self.user
        )

    # Common JWT mock
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": "test@gmail.com"}

    # GET ALL
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

    #  CREATE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_charge_with_valid_data_returns_created_response(self, mock_get_token, mock_decode):
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

    #  CREATE MISSING
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

    #  UPDATE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_charge_with_valid_data_returns_success_response(self, mock_get_token, mock_decode):
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

    #  UPDATE INVALID
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

    #  UPDATE WITHOUT ID
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

    #  DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_charge_with_valid_id_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify charge is deleted successfully using valid charge ID. 
        """
        self._mock_auth(mock_get_token, mock_decode)

        response = self.client.delete(
            f"{self.url}?charge_id={self.charge.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    #  DELETE INVALID
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

    # DELETE WITHOUT ID
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