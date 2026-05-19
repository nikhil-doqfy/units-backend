import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from utilities import status
from property.models import Property, PropertyBlocks, Unit, PropertyManagmentCompany
from user_service.models import PropertyManager, Role

class StaffAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()
        # Create admin Django user 
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

        # Create existing staff member for GET/PUT/duplicate tests
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

        # Create role for assigning to staff
        self.role = Role.objects.create(
            name="Manager",
            company=self.company,
            created_by=self.pm_django_user,
        )

        # URL
        self.url = "/user/staff_view"

    # Auth mock helper
    # Mocks get_jwt_token -> returns raw token string
    # Mocks decode_jwt_token -> returns payload with email
    # Decorator fetches PropertyManager by email -> token matches -> auth passes
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    # staff_view — GET /user/staff_view
    # Returns paginated list of staff or single staff detail
    # staff list returned with pagination
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_staff_list_returns_paginated_response_successfully(self, mock_get_token, mock_decode):
        """Verify staff list is fetched successfully with pagination."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("content", data)
        self.assertIn("pagination", data)

    # staff list response contains expected fields
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_staff_list_response_contains_required_staff_fields(self, mock_get_token, mock_decode):
        """Verify staff list response contains all expected fields."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        staff = content[0]
        self.assertIn("staff_id", staff)
        self.assertIn("staff_name", staff)
        self.assertIn("contact_number", staff)
        self.assertIn("roles", staff)
        self.assertIn("is_active", staff)

    # single staff detail returned by staff_id
    @patch("property.models.Unit._get_unit_thumbnail")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_staff_details_by_staff_id_returns_successfully(self, mock_get_token, mock_decode, mock_thumb):
        """Verify single staff details are returned successfully using staff_id."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_thumb.return_value = None  # mock S3 thumbnail call

        res = self.client.get(
            self.url,
            {"staff_id": self.staff.pk},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]
        self.assertEqual(data["staff_id"], self.staff.pk)
        self.assertEqual(data["email"], self.staff_django_user.email)

    # single staff detail has all expected fields
    @patch("property.models.Unit._get_unit_thumbnail")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_staff_response_contains_complete_staff_details(self, mock_get_token, mock_decode, mock_thumb):
        """Verify single staff response contains all required detail fields."""
        self._mock_auth(mock_get_token, mock_decode)
        mock_thumb.return_value = None

        res = self.client.get(
            self.url,
            {"staff_id": self.staff.pk},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]
        expected_fields = [
            "staff_id", "staff_name", "first_name", "last_name",
            "email", "contact_number", "roles", "is_active",
            "assigned_properties", "assigned_unit_ids"
        ]
        for field in expected_fields:
            self.assertIn(field, data)

    # search filter returns matching staff only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_staff_list_search_filter_returns_matching_staff_records(self, mock_get_token, mock_decode):
        """Verify search filter returns matching staff records."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "Alice"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)

    # pagination works with page_number and limit params
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_staff_list_pagination_returns_correct_page_results(self, mock_get_token, mock_decode):
        """Verify pagination parameters return correct paginated data."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"page_number": 1, "limit": 5},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        pagination = res.json()["pagination"]
        self.assertIn("current_page", pagination)
        self.assertIn("total_records", pagination)
        self.assertEqual(pagination["current_page"], 1)

    # Negative: staff_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_staff_with_invalid_staff_id_returns_not_found(self, mock_get_token, mock_decode):
        """Verify invalid staff_id returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"staff_id": 99999},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: no auth token provided → 401
    def test_get_staff_without_authentication_returns_unauthorized(self):
        """Verify request without authentication token returns 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_staff_with_deleted_company_returns_not_found(self, mock_get_token, mock_decode):
        """Verify deleted company returns 404 while fetching staff list."""      
        self._mock_auth(mock_get_token, mock_decode)

        # Delete company to simulate company not found scenario
        self.company.delete()

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # staff_view — POST /user/staff_view
    # Creates a new staff member (PropertyManager) for the company
    #  staff created successfully and saved in DB
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_staff_returns_created_response_successfully(self, mock_get_token, mock_decode):
        """Verify new staff member is created successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "New",
            "last_name": "Staff",
            "email": "newstaff@test.com",
            "password": "pass1234",
            "contact_number": "1112223333",
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertIn("staff_id", content)

        # Verify staff is saved in DB
        self.assertTrue(PropertyManager.objects.filter(user__email="newstaff@test.com").exists())

    #  staff created with role assigned
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_staff_with_role_assignment_returns_successfully(self, mock_get_token, mock_decode):
        """Verify staff member is created with assigned role successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "Role",
            "last_name": "Staff",
            "email": "rolestaff@test.com",
            "password": "pass1234",
            "role": self.role.id,
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Verify role is assigned in DB
        pm = PropertyManager.objects.filter(user__email="rolestaff@test.com").first()
        self.assertIsNotNone(pm)
        self.assertIn(self.role, pm.roles.all())

    # Negative: required fields missing (first_name, email, password) → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_staff_with_missing_required_fields_returns_bad_request(self, mock_get_token, mock_decode):
        """Verify missing required fields return 400 response."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {"first_name": "NoEmail"}  # email and password missing

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: email already registered → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_staff_with_existing_email_returns_bad_request(self, mock_get_token, mock_decode):
        """Verify duplicate email returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "Dup",
            "last_name": "Staff",
            "email": "staff@test.com",  # already exists
            "password": "pass1234",
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_staff_with_deleted_company_returns_not_found(self, mock_get_token, mock_decode):
        """Verify deleted company returns 404 during staff creation."""
        self._mock_auth(mock_get_token, mock_decode)

        # Delete company to simulate company not found scenario
        self.company.delete()

        data = {
            "first_name": "No",
            "last_name": "Company",
            "email": "nocompany@test.com",
            "password": "pass1234",
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: no auth token provided → 401
    def test_create_staff_without_authentication_returns_unauthorized(self):
        """Verify request without authentication token returns 401."""
        res = self.client.post(self.url, content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # staff_view — PUT /user/staff_view
    # Updates staff name, contact number, role, assigned properties
    #  staff name updated and saved in DB
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_staff_details_returns_successfully(self, mock_get_token, mock_decode):
        """Verify staff details are updated successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "staff_id": self.staff.pk,
            "first_name": "UpdatedAlice",
            "last_name": "UpdatedSmith",
            "contact_number": "5556667777"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify name is updated in DB
        self.staff_django_user.refresh_from_db()
        self.assertEqual(self.staff_django_user.first_name, "UpdatedAlice")

    #  staff role updated — old roles replaced with new role
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_staff_role_assignment_returns_successfully(self, mock_get_token, mock_decode):
        """Verify staff role is updated successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "staff_id": self.staff.pk,
            "first_name": "Alice",
            "role": self.role.id,
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify role is assigned in DB
        self.staff.refresh_from_db()
        self.assertIn(self.role, self.staff.roles.all())

    # Negative: staff_id not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_staff_without_staff_id_returns_bad_request(self, mock_get_token, mock_decode):
        """Verify missing staff_id returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {"first_name": "NoID"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: staff_id does not exist in company → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_staff_with_invalid_staff_id_returns_not_found(self, mock_get_token, mock_decode):
        """Verify invalid staff_id returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)

        data = {"staff_id": 99999, "first_name": "Ghost"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_staff_with_deleted_company_returns_not_found(self, mock_get_token, mock_decode):
        """Verify deleted company returns 404 during staff update."""
        self._mock_auth(mock_get_token, mock_decode)

        # Delete company to simulate company not found scenario
        self.company.delete()
        data = {"staff_id": self.staff.pk, "first_name": "Updated"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: no auth token provided → 401
    def test_update_staff_without_authentication_returns_unauthorized(self):
        """Verify request without authentication token returns 401."""
        res = self.client.put(
            self.url,
            data=json.dumps({"staff_id": self.staff.pk, "first_name": "Test"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: wrong HTTP method used (DELETE) → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_staff_view_with_invalid_http_method_returns_method_not_allowed(self, mock_get_token, mock_decode):
        """Verify unsupported HTTP method returns 405 response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)