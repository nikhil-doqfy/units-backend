import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from django.utils import timezone
from utilities import status
from lead.models import Lead
from property.models import Property, PropertyBlocks, Unit, PropertyManagmentCompany
from user_service.models import PropertyManager


class LeadAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()
        #  User 
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            email="test@gmail.com"
        )
       # Company 
        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="123",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.user,
            created=timezone.now()
        )
       
        self.pm = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",       
            company=self.company,
            created_by=self.user,
            created=timezone.now()
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
            created_by=self.user,
            pmc=self.company
        )

        # Block 
        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="A",
            no_of_floors=1,
            no_of_parking=1,
            no_of_units=1,
            created_by=self.user
        )
        # Unit 
        self.unit = Unit.objects.create(
            property_block_tower=self.block,
            unit_name="101",
            created_by=self.user
        )
        # Lead 
        self.lead = Lead.objects.create(
            unit=self.unit,
            name="Test Lead",
            email="lead@test.com",
            contact_number="9999999999",
            status="INTERESTED",
            platform="WEB",
            lead_type="BUY",
            pmc=self.company,
            created_by=self.user
        )

        # URL 
        self.url = reverse("lead_view")

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    #  GET — list all leads
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_leads_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify all leads are fetched successfully for authenticated user.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — single lead by id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lead_by_valid_id_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify single lead details are fetched successfully using valid lead ID.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?lead_id={self.lead.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — lead not found
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lead_with_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify API returns not found response when invalid lead ID is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?lead_id=99999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  GET — search filter
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_leads_with_search_filter_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify leads are filtered successfully using search query parameter.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?search=Test",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — status filter
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_leads_with_status_filter_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify leads are filtered successfully using status query parameter.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?status=INTERESTED",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — CSV export
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_leads_as_csv_returns_csv_file_response(self, mock_get_token, mock_decode):
        """
        Verify leads are exported successfully as CSV file response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?export=csv",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("leads.csv", res["Content-Disposition"])

    #  POST — create lead success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lead_with_valid_data_returns_created_response(self, mock_get_token, mock_decode):
        """
        Verify new lead is created successfully using valid request payload.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": self.unit.id,
            "name": "New Lead",
            "email": "new@test.com",
            "contact_number": "8888888888",
            "platform": "WEB",
            "lead_type": "BUY"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    #  POST — missing required fields → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lead_with_missing_required_fields_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify lead creation fails when required fields are missing.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": self.unit.id,
            "name": "Incomplete Lead"
            # missing email, contact_number, platform, lead_type
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  POST — invalid unit → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lead_with_invalid_unit_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify lead creation fails when invalid unit ID is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "unit_id": 99999,           # non-existent unit
            "name": "New Lead",
            "email": "new@test.com",
            "contact_number": "8888888888",
            "platform": "WEB",
            "lead_type": "BUY"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  PUT — update lead name
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lead_with_valid_data_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify existing lead is updated successfully using valid lead ID and data.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "lead_id": self.lead.id,
            "name": "Updated Name"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  PUT — block NOT_INTERESTED → LEASE_TENANCY
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lead_from_not_interested_to_lease_tenancy_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify lead status update fails when attempting to change status from NOT_INTERESTED to LEASE_TENANCY.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # First set lead to NOT_INTERESTED
        self.lead.status = "NOT_INTERESTED"
        self.lead.save()

        data = {
            "lead_id": self.lead.id,
            "status": "LEASE_TENANCY"   # this should be blocked
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  PUT — missing lead_id → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lead_without_lead_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify lead update fails when lead ID is missing in request payload.
        """
        self._mock_auth(mock_get_token, mock_decode)

        data = {"name": "No ID Given"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  DELETE — success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_lead_with_valid_id_returns_success_response(self, mock_get_token, mock_decode):
        """
        verify lead is deleted successfully using valid lead ID.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?lead_id={self.lead.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Confirm lead is actually deleted from DB
        self.assertFalse(Lead.objects.filter(id=self.lead.id).exists())

    #  DELETE — missing lead_id → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_lead_without_lead_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify lead deletion fails when lead ID is not provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,           # no lead_id in query params
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  DELETE — lead not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_lead_with_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify lead deletion fails when invalid lead ID is provided.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?lead_id=99999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  No auth token → 401
    def test_request_without_auth_token_returns_unauthorized(self):
        """
        Verify API returns unauthorized response when authentication token is missing.
        """
        res = self.client.get(self.url)   # no HTTP_AUTHORIZATION header
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)