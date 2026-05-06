import json
import base64
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from unittest.mock import patch
from django.utils import timezone

from utilities import status
from lead.models import Lead
from property.models import Property, PropertyBlocks, Unit, PropertyManagmentCompany
from user_service.models import PropertyManager, Tenant
from lease.models import Lease


class LeadActiveAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # USER 
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass",
            email="test@gmail.com"
        )

        # COMPANY 
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

        # PROPERTY MANAGER 
        self.pm = PropertyManager.objects.create(
            user=self.user,
            email=self.user.email,
            token="validtoken",
            company=self.company,
            created_by=self.user,
            created=timezone.now()
        )

        # PROPERTY 
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

        # LEAD 
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

        # TENANT 
        self.tenant = Tenant.objects.create(
            user=self.user,
            email="tenant@test.com",
            created_by=self.user,
            created=timezone.now()
        )

        self.check_url = reverse("lead_check_active_lease")
        self.import_url = reverse("lead_bulk_import")

    # ── AUTH MOCK ─────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "validtoken"
        mock_decode.return_value = {"email": self.user.email}

    # ACTIVE LEASE CHECK TESTS
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_active_lease_true(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        Lease.objects.create(
            unit=self.unit,
            tenant=self.tenant,
            lease_status="ACTIVE",
            created_by=self.user
        )

        res = self.client.get(
            f"{self.check_url}?lead_id={self.lead.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertTrue(res.json()["content"]["has_active_lease"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_active_lease_false(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.check_url}?lead_id={self.lead.id}",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.json()["content"]["has_active_lease"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_active_lease_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.check_url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_active_lease_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            f"{self.check_url}?lead_id=999",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  BULK IMPORT TESTS
    def generate_csv_base64(self, text):
        return base64.b64encode(text.encode()).decode()

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        csv_data = f"""unit_id,name,email,contact_number,platform,lead_type
{self.unit.id},John,john@test.com,9999999999,WEB,BUY
"""

        res = self.client.post(
            self.import_url,
            data=json.dumps({"file": self.generate_csv_base64(csv_data)}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["created"], 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_missing_file(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.import_url,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_invalid_base64(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.import_url,
            data=json.dumps({"file": "invalid"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_missing_columns(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        csv_data = "name,email\nJohn,john@test.com"

        res = self.client.post(
            self.import_url,
            data=json.dumps({"file": self.generate_csv_base64(csv_data)}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_invalid_unit(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        csv_data = """unit_id,name,email,contact_number,platform,lead_type
999,John,john@test.com,9999999999,WEB,BUY
"""

        res = self.client.post(
            self.import_url,
            data=json.dumps({"file": self.generate_csv_base64(csv_data)}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["skipped"], 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_bulk_import_wrong_method(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.import_url,
            HTTP_AUTHORIZATION="Bearer validtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)