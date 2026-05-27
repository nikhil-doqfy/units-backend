import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany
from user_service.models import UserProfile, PropertyManager, Owner, Tenant


class UserProfileAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Admin user 
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com"
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

        # ── PropertyManager user ──────────────────────────────────────
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

        # ── Owner user ────────────────────────────────────────────────
        self.owner_django_user = User.objects.create_user(
            username="owneruser",
            password="ownerpass",
            email="owner@test.com",
            first_name="Alice",
            last_name="Smith"
        )
        self.owner = Owner.objects.create(
            user=self.owner_django_user,
            email=self.owner_django_user.email,
            token="ownertoken",
            created_by=self.admin_user,
        )

        # ── Tenant user ───────────────────────────────────────────────
        self.tenant_django_user = User.objects.create_user(
            username="tenantuser",
            password="tenantpass",
            email="tenant@test.com",
            first_name="Bob",
            last_name="Brown"
        )
        self.tenant = Tenant.objects.create(
            user=self.tenant_django_user,
            email=self.tenant_django_user.email,
            token="tenanttoken",
            created_by=self.admin_user,
        )

        # URL 
        self.url = "/user/profile"

    # Auth mock helpers 
    def _mock_as_pm(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    def _mock_as_owner(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "ownertoken"
        mock_decode.return_value = {"email": self.owner_django_user.email}

    def _mock_as_tenant(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "tenanttoken"
        mock_decode.return_value = {"email": self.tenant_django_user.email}

    #  GET — PropertyManager profile
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_property_manager_profile_returns_200_with_company_user_role(self, mock_get_token, mock_decode):
        """
        Verify authenticated PropertyManager can fetch profile details
        successfully with COMPANY_USER role and permissions.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]
        self.assertEqual(data["email"], self.pm_django_user.email)
        self.assertEqual(data["user_role"], "COMPANY_USER")
        self.assertIn("permissions", data)

    #  GET — Owner profile
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_profile_returns_200_with_owner_role(self, mock_get_token, mock_decode):
        """
        Verify authenticated Owner user can successfully retrieve profile details with OWNER role.
        """
        self._mock_as_owner(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer ownertoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]
        self.assertEqual(data["email"], self.owner_django_user.email)
        self.assertEqual(data["user_role"], "OWNER")

    #  GET — Tenant profile
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_profile_returns_200_with_tenant_role(self, mock_get_token, mock_decode):
        """
        Verify authenticated Tenant user can successfully retrieve profile details with TENANT role.
        """
        self._mock_as_tenant(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer tenanttoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]
        self.assertEqual(data["email"], self.tenant_django_user.email)
        self.assertEqual(data["user_role"], "TENANT")

    #  GET — response fields verify
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_profile_response_contains_all_expected_fields(self, mock_get_token, mock_decode):
        """
        Verify GET profile response contains all expected user profile fields and metadata keys.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()["content"]

        expected_fields = [
            "id", "email", "first_name", "last_name",
            "user_role", "profile_image", "city", "state",
            "country", "postal_code", "address",
            "contact_number", "permissions"
        ]
        for field in expected_fields:
            self.assertIn(field, data)


    #  GET — no auth → 401
    def test_get_profile_without_authentication_returns_401(self):
        """
        Verify unauthenticated GET request to profile endpoint returns HTTP 401 UNAUTHORIZED.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  PUT — update name success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_property_manager_name_returns_200_and_updates_user(self, mock_get_token, mock_decode):
        """  
        Verify authenticated PropertyManager can successfully update first_name and last_name through profile endpoint.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        data = {
            "first_name": "UpdatedJohn",
            "last_name": "UpdatedDoe"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.pm_django_user.refresh_from_db()
        self.assertEqual(self.pm_django_user.first_name, "UpdatedJohn")
        self.assertEqual(self.pm_django_user.last_name, "UpdatedDoe")

    #  PUT — update contact number
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_profile_contact_number_returns_200_and_saves_changes(self, mock_get_token, mock_decode):
        """
        Verify PUT request successfully updates contact number for authenticated user profile.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        data = {"contact_number": "9876543210"}

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.pm.refresh_from_db()
        self.assertEqual(self.pm.contact_number, "9876543210")

    #  PUT — restricted fields ignore
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_profile_ignores_restricted_fields_and_updates_allowed_fields(self, mock_get_token, mock_decode):
        """
        Verify restricted fields like email, password, and user_role cannot be modified through profile update endpoint.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        original_email = self.pm_django_user.email

        data = {
            "email": "hacker@evil.com",
            "user_role": "ADMIN",
            "password": "newpassword123",
            "first_name": "SafeUpdate"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.pm_django_user.refresh_from_db()
        self.assertEqual(self.pm_django_user.email, original_email)
        self.assertEqual(self.pm_django_user.first_name, "SafeUpdate")

    #  PUT — update address fields
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_profile_address_fields_returns_200_and_updates_address(self, mock_get_token, mock_decode):
        """
        Verify PUT request successfully updates address-related profile fields including address lines and pin code.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        data = {
            "address": "123 Main Street",
            "additional_address": "Apt 4B",
            "pin_code": "411001",
            "locality": "Pune"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        self.pm.refresh_from_db()
        self.assertEqual(self.pm.address_line_1, "123 Main Street")
        self.assertEqual(self.pm.address_line_2, "Apt 4B")
        self.assertEqual(self.pm.pin_code, "411001")

    #  PUT — Owner profile update
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_owner_profile_returns_200_and_updates_owner_details(self, mock_get_token, mock_decode):
        """
        Verify authenticated Owner user can successfully update profile information through PUT request.
        """
        self._mock_as_owner(mock_get_token, mock_decode)

        data = {
            "first_name": "AliceUpdated",
            "contact_number": "1234567890"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer ownertoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.owner_django_user.refresh_from_db()
        self.assertEqual(self.owner_django_user.first_name, "AliceUpdated")

    #  PUT — Tenant profile update
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_tenant_profile_returns_200_and_updates_tenant_details(self, mock_get_token, mock_decode):
        """
        Verify authenticated Tenant user can successfully update profile information through PUT request.
        """
        self._mock_as_tenant(mock_get_token, mock_decode)

        data = {
            "first_name": "BobUpdated",
            "contact_number": "9999988888"
        }

        res = self.client.put(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer tenanttoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.tenant_django_user.refresh_from_db()
        self.assertEqual(self.tenant_django_user.first_name, "BobUpdated")

    #  PUT — no auth → 401
    def test_update_profile_without_authentication_returns_401(self):
        """
        Verify unauthenticated PUT request to profile endpoint returns HTTP 401 UNAUTHORIZED.
        """
        res = self.client.put(
            self.url,
            data=json.dumps({"first_name": "Hacker"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  Invalid method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_method_on_profile_endpoint_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported DELETE request on profile endpoint returns HTTP 405 METHOD NOT ALLOWED.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)