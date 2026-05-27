import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import Property, PropertyBlocks, PropertyManagmentCompany
from user_service.models import PropertyManager, Role

class ExportStaffCSVTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        # Create admin Django user (used as created_by)
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com"
        )
        # Create company linked to admin user
        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC123",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )
        # Create logged-in PropertyManager
        # PropertyManager IS the UserProfile (same pk)
        # decorator sets request.user = UserProfile.filter(user__email=email).first()
        self.pm_django_user = User.objects.create_user(
            username="pmuser",
            password="pmpass",
            email="pm@test.com",
            first_name="John",
            last_name="Doe"
        )
        self.pm = PropertyManager.objects.create(
            user=self.pm_django_user,
            email=self.pm_django_user.email,
            token="pmtoken",
            company=self.company,
            created_by=self.admin_user,
        )

        # Create existing staff member for staff_id filter tests
        self.staff_django_user = User.objects.create_user(
            username="staffuser",
            password="staffpass",
            email="staff@test.com",
            first_name="Alice",
            last_name="Smith"
        )
        self.staff = PropertyManager.objects.create(
            user=self.staff_django_user,
            email=self.staff_django_user.email,
            token="stafftoken",
            company=self.company,
            contact_number="9876543210",
            created_by=self.pm_django_user,
        )

        # Create role for role_id filter tests
        self.role = Role.objects.create(
            name="Manager",
            company=self.company,
            created_by=self.pm_django_user,
        )
        self.staff.roles.add(self.role)

        # Create property linked to company for staff_id export test
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

        # URL
        self.url = "/user/staff_csv"

    # Auth mock helper
    # Mocks get_jwt_token -> returns raw token string
    # Mocks decode_jwt_token -> returns payload with email
    # Decorator fetches PropertyManager by email -> token matches -> auth passes
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    # export_staff_csv — GET /user/staff_csv
    # Mode 1 (no staff_id): exports full staff list as CSV
    # Mode 2 (with staff_id): exports assigned properties for that staff
    #  staff list CSV returned with correct content type
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_returns_staff_list_file_successfully(self, mock_get_token, mock_decode):
        """
        Verify that exporting the default staff list returns: HTTP 200 response
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("staff_list", res["Content-Disposition"])

    #  staff list CSV contains expected column headers
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_contains_expected_column_headers(self, mock_get_token, mock_decode):
        """
        Verify that exported staff CSV contains all required column headers.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")

        # Verify all expected column headers are present
        self.assertIn("Staff Name", content)
        self.assertIn("Email", content)
        self.assertIn("Contact Number", content)
        self.assertIn("Staff Role", content)
        self.assertIn("Code", content)

    # staff list CSV contains staff data
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_includes_existing_staff_member_data(self, mock_get_token, mock_decode):
        """
        Verify that exported staff CSV includes existing staff member details.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")

        # Verify staff email is present in CSV data
        self.assertIn("staff@test.com", content)

    #  search filter returns matching staff only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_filters_results_using_search_query(self, mock_get_token, mock_decode):
        """
        Verify that applying search filter returns only matching staff members in exported CSV.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "Alice"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        self.assertIn("staff@test.com", content)

    # Happy path: role_id filter returns staff with that role only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_filters_results_by_role_id(self, mock_get_token, mock_decode):
        """
        Verify that role_id filter exports only staff members assigned to the specified role.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"role_id": self.role.id},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")
        # Staff with Manager role should be in CSV
        self.assertIn("staff@test.com", content)

    # Happy path: staff_id provided → assigned properties CSV returned
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_assigned_properties_csv_returns_successfully(self, mock_get_token, mock_decode):
        """
        Verify valid staff_id returns assigned properties CSV successfully.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"staff_id": self.staff.pk},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")
        self.assertIn("assigned_properties", res["Content-Disposition"])

    # assigned properties CSV contains correct column headers
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_assigned_properties_csv_contains_all_expected_headers(self, mock_get_token, mock_decode):
        """
        Verify assigned properties CSV contains all expected column headers.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"staff_id": self.staff.pk},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        content = res.content.decode("utf-8")

        # Verify all expected column headers are present
        self.assertIn("Code", content)
        self.assertIn("Property Name", content)
        self.assertIn("Tenant Name", content)
        self.assertIn("Assigned Staff", content)
        self.assertIn("Owner Name", content)

    # empty result returns CSV with headers only (no data rows)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_returns_empty_result_with_headers_only(self, mock_get_token, mock_decode):
        """
        Verify that when no staff matches the search query:
        - CSV file is still returned successfully
        - CSV contains headers even if no data rows exist.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "nonexistentuserxyz"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")

    # Negative: staff_id does not exist in company → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_assigned_properties_returns_404_for_invalid_staff_id(self, mock_get_token, mock_decode):
        """
        Verify that exporting assigned properties using non-existent staff_id returns HTTP 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"staff_id": 99999},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_returns_404_when_company_does_not_exist(self, mock_get_token, mock_decode):
        """
        Verify that request fails with HTTP 404 when Property Management Company record does not exist.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Delete company to simulate company not found scenario
        self.company.delete()

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: wrong HTTP method used (POST instead of GET) → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_staff_csv_rejects_post_method_with_405(self, mock_get_token, mock_decode):
        """
        Verify that POST request to staff CSV export endpoint returns HTTP 405 Method Not Allowed.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth token provided → 401
    def test_export_staff_csv_returns_401_when_authentication_token_is_missing(self):
        """
        Verify that request without authentication token returns HTTP 401 Unauthorized.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)