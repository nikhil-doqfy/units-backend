import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany
from user_service.models import UserProfile, PropertyManager, Owner, Tenant


class UserManagementAPITestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Admin Django user 
        self.admin_django_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com"
        )

        #  Company 
        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC123",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_django_user,
        )

        #  Logged-in PropertyManager 
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
            created_by=self.admin_django_user,
        )

        # ── Existing Owner (for GET/PUT/DELETE tests) ─────────────────
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
            created_by=self.admin_django_user,
        )

        self.url = "/user/management"

    # ── Auth mock helper ──────────────────────────────────────────────
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    #  POST — create Owner
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_owner_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "New",
            "last_name": "Owner",
            "email": "newowner@test.com",
            "password": "pass1234",
            "contact_number": "9876543210",
            "role": "OWNER"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertIn("user_id", content)
        self.assertEqual(content["role"], "OWNER")

        # DB verify
        self.assertTrue(Owner.objects.filter(user__email="newowner@test.com").exists())

    #  POST — create Tenant
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "New",
            "last_name": "Tenant",
            "email": "newtenant@test.com",
            "password": "pass1234",
            "role": "TENANT"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tenant.objects.filter(user__email="newtenant@test.com").exists())

    #  POST — create CompanyUser (PropertyManager)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_company_user_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "New",
            "last_name": "Manager",
            "email": "newpm@test.com",
            "password": "pass1234",
            "role": "COMPANY_USER"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(PropertyManager.objects.filter(user__email="newpm@test.com").exists())

    #  POST — missing required fields → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_missing_fields(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "Incomplete",
            # missing last_name, email, password, role
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  POST — invalid role → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_invalid_role(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "Test",
            "last_name": "User",
            "email": "invalid@test.com",
            "password": "pass1234",
            "role": "SUPERADMIN"  # invalid role
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  POST — duplicate email → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_duplicate_email(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "first_name": "Dup",
            "last_name": "User",
            "email": "owner@test.com",  # already exists
            "password": "pass1234",
            "role": "OWNER"
        }

        res = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  GET — list users
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("content", data)
        self.assertIn("pagination", data)

    #  GET — filter by role
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_filter_by_role(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"role": "OWNER"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — search filter
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_search(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "John"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  GET — single user by user_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_user(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"user_id": self.pm.id},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    #  PUT — update user success
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_user_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        data = {
            "user_id": self.pm.id,
            "first_name": "UpdatedJohn",
            "contact_number": "1112223333"
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

    #  PUT — missing user_id → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_user_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url,
            data=json.dumps({"first_name": "NoID"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  PUT — user not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_user_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(
            self.url,
            data=json.dumps({"user_id": 99999, "first_name": "Ghost"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  DELETE — deactivate user (first delete = deactivate)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_deactivate_user_success(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        # Create a user created_by pm_django_user for DELETE to work
        target_django_user = User.objects.create_user(
            username="target",
            password="pass",
            email="target@test.com"
        )
        target_profile = Owner.objects.create(
            user=target_django_user,
            email="target@test.com",
            token="targettoken",
            created_by=self.pm_django_user,  # ✅ created_by must match logged-in user
        )

        res = self.client.delete(
            f"{self.url}?user_id={target_profile.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        target_profile.refresh_from_db()
        self.assertFalse(target_profile.is_active)

    #  DELETE — permanently delete (second delete = permanent)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_permanently_delete_user(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        # Create inactive user
        target_django_user = User.objects.create_user(
            username="permdel",
            password="pass",
            email="permdel@test.com"
        )
        target_profile = Owner.objects.create(
            user=target_django_user,
            email="permdel@test.com",
            token="permdeltoken",
            is_active=False,  # already deactivated
            created_by=self.pm_django_user,
        )

        res = self.client.delete(
            f"{self.url}?user_id={target_profile.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # User permanently deleted
        self.assertFalse(UserProfile.objects.filter(id=target_profile.id).exists())

    #  DELETE — missing user_id → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_user_missing_id(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    #  DELETE — user not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_user_not_found(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?user_id=99999",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  No auth → 401
    def test_no_auth_returns_401(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    #  Invalid method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_invalid_method_returns_405(self, mock_get_token, mock_decode):
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.patch(
            self.url,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)