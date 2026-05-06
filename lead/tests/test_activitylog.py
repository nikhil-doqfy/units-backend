import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from django.utils import timezone

from utilities import status
from lead.models import Lead, ActivityLog
from property.models import Property, PropertyBlocks, Unit, PropertyManagmentCompany
from user_service.models import PropertyManager

class ActivityLogAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()

        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            email="test@gmail.com"
        )

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

        # ── PropertyManager  ─────
        self.pm = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",
            company=self.company,
            created_by=self.user,
            created=timezone.now()
        )

        # ── Property hierarchy ──────────────
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

        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="A",
            no_of_floors=1,
            no_of_parking=1,
            no_of_units=1,
            created_by=self.user
        )

        self.unit = Unit.objects.create(
            property_block_tower=self.block,
            unit_name="101",
            created_by=self.user
        )

        # ── Lead ────────────────────────────
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

        #  Activity Log 
        self.log = ActivityLog.objects.create(
            lead=self.lead,
            activity_type="NOTE",
            title="Initial Note",
            description="Test description",
            created_by=self.user
        )

        self.url = reverse("activity_log_view")

    # ── Auth Mock ─────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # GET
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_activity_logs(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?lead_id={self.lead.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_logs_missing_lead_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer validtoken")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_logs_invalid_lead(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.url}?lead_id=999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # POST
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_activity_log(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "lead_id": self.lead.id,
            "activity_type": "NOTE",
            "title": "New Activity",
            "description": "Test activity"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_log_missing_lead_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # PUT
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_activity_log(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "log_id": self.log.id,
            "title": "Updated Title"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_log_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # DELETE
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_activity_log(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?log_id={self.log.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_log_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_log_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?log_id=999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # AUTH FAIL
    def test_no_auth(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

