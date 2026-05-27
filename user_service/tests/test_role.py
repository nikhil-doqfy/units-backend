import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch
from utilities import status
from property.models import PropertyManagmentCompany
from user_service.models import PropertyManager, Role, Permission


class RoleAPITestCase(TestCase):

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

        # Create PropertyManager — this is the logged-in user
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

        # Create existing role for update/duplicate tests
        self.role = Role.objects.create(
            name="Manager",
            company=self.company,
            created_by=self.pm_django_user,
        )

        # URLs
        self.url_add_role   = "/user/add_role"
        self.url_role_table = "/user/role_table"

    # Auth mock helper
   
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    # create_role — POST /user/add_role
    # Creates a new role for the logged-in user's company
    # role created successfully and saved in DB
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_with_valid_data_returns_201_successfully(self, mock_get_token, mock_decode):
        """Valid role data creates role successfully."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"name": "Accountant"}
        res = self.client.post(
            self.url_add_role,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertIn("id", content)
        self.assertEqual(content["name"], "Accountant")
        # Verify role is saved in DB
        self.assertTrue(Role.objects.filter(name="Accountant", company=self.company).exists())

    #  role created with permissions — permissions saved in DB
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_with_permissions_saves_permissions_successfully(self, mock_get_token, mock_decode):
        """Role permissions are saved successfully."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {
            "name": "Sales",
            "permissions": [
                {"module_name": "PROPERTY", "create": True, "edit": True, "delete": False, "view": True}
            ]
        }
        res = self.client.post(
            self.url_add_role,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Verify permissions are saved in DB
        role = Role.objects.filter(name="Sales", company=self.company).first()
        self.assertIsNotNone(role)
        self.assertEqual(role.permissions.count(), 1)
        perm = role.permissions.first()
        self.assertTrue(perm.create)
        self.assertTrue(perm.view)
        self.assertFalse(perm.delete)

    # Negative: role name not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_without_name_returns_400_response(self, mock_get_token, mock_decode):
        """Missing role name returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.post(
            self.url_add_role,
            data=json.dumps({}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: role with same name already exists in company → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_with_duplicate_name_returns_400_response(self, mock_get_token, mock_decode):
        """Duplicate role name returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"name": "Manager"}
        res = self.client.post(
            self.url_add_role,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: duplicate check is case-insensitive ("manager" = "Manager") → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_with_case_insensitive_duplicate_name_returns_400(self, mock_get_token, mock_decode):
        """Case-insensitive duplicate role name returns 400."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"name": "manager"}  # lowercase version of existing "Manager"
        res = self.client.post(
            self.url_add_role,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: wrong HTTP method used (GET instead of POST) → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_with_invalid_http_method_returns_405_response(self, mock_get_token, mock_decode):
        """Unsupported HTTP method returns 405 response."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url_add_role,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth token provided → 401
    def test_create_role_without_authentication_returns_401_response(self):
        """Request without auth token returns 401."""
        res = self.client.post(self.url_add_role, content_type="application/json")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_role_when_company_not_found_returns_404_response(self, mock_get_token, mock_decode):
        """Missing company returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)
        # Delete company to simulate company not found scenario
        self.company.delete()
        data = {"name": "New Role"}
        res = self.client.post(
            self.url_add_role,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # role_table_view — GET /user/role_table
    # Returns paginated list of roles for the logged-in user's company
    # roles list returned with pagination
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_returns_paginated_response_successfully(self, mock_get_token, mock_decode):
        """GET roles list returns paginated response."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url_role_table,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.json()
        self.assertIn("content", data)
        self.assertIn("pagination", data)

    #  response contains expected fields (role_id, role_name, permissions)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_response_contains_expected_fields(self, mock_get_token, mock_decode):
        """Role response contains expected fields."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url_role_table,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        role = content[0]
        self.assertIn("role_id", role)
        self.assertIn("role_name", role)
        self.assertIn("permissions", role)

    #  search filter returns matching roles only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_search_filter_returns_matching_roles(self, mock_get_token, mock_decode):
        """Search filter returns matching roles."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url_role_table,
            {"search": "Manager"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        self.assertEqual(content[0]["role_name"], "Manager")

    #  pagination works correctly with page and limit params
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_pagination_returns_correct_pagination_data(self, mock_get_token, mock_decode):
        """Pagination parameters work correctly."""
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.get(
            self.url_role_table,
            {"page": 1, "limit": 5},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        pagination = res.json()["pagination"]
        self.assertIn("current_page", pagination)
        self.assertIn("total_records", pagination)
        self.assertEqual(pagination["current_page"], 1)

    # is_active=false returns only inactive roles
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_with_inactive_filter_returns_inactive_roles(self, mock_get_token, mock_decode):
        """Inactive filter returns inactive roles only."""
        self._mock_auth(mock_get_token, mock_decode)
        # Create an inactive role to filter
        Role.objects.create(
            name="InactiveRole",
            company=self.company,
            created_by=self.pm_django_user,
            is_active=False
        )
        res = self.client.get(
            self.url_role_table,
            {"is_active": "false"},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        names = [r["role_name"] for r in content]
        self.assertIn("InactiveRole", names)

    # Negative: no auth token provided → 401
    def test_get_roles_list_without_authentication_returns_401_response(self):
        """Request without auth token returns 401."""
        res = self.client.get(self.url_role_table)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_roles_list_when_company_not_found_returns_404_response(self, mock_get_token, mock_decode):
        """Missing company returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)
        # Delete company to simulate company not found scenario
        self.company.delete()
        res = self.client.get(
            self.url_role_table,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


    # role_table_view — PUT /user/role_table
    # Updates role name and replaces permissions for a given role
    #  role name updated and saved in DB
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_with_valid_data_updates_role_successfully(self, mock_get_token, mock_decode):
        """Valid role update request updates role successfully."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"role_id": self.role.id, "name": "Senior Manager"}
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Verify name is updated in DB
        self.role.refresh_from_db()
        self.assertEqual(self.role.name, "Senior Manager")

    # role updated with new permissions — old permissions replaced
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_with_permissions_replaces_old_permissions_successfully(self, mock_get_token, mock_decode):
        """Role permissions are replaced successfully."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {
            "role_id": self.role.id,
            "name": "Manager",
            "permissions": [
                {"module_name": "UNIT", "create": False, "edit": True, "delete": False, "view": True}
            ]
        }
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Verify permissions are replaced in DB
        self.role.refresh_from_db()
        self.assertEqual(self.role.permissions.count(), 1)
        perm = self.role.permissions.first()
        self.assertEqual(perm.module_name, "UNIT")
        self.assertTrue(perm.view)

    # Negative: role_id or name not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_without_required_fields_returns_400_response(self, mock_get_token, mock_decode):
        """Missing required fields returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"role_id": self.role.id}  # name is missing
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: role_id does not exist in DB → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_with_invalid_role_id_returns_404_response(self, mock_get_token, mock_decode):
        """Invalid role_id returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)
        data = {"role_id": 99999, "name": "Ghost Role"}
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: new name already belongs to another role in same company → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_with_duplicate_name_returns_400_response(self, mock_get_token, mock_decode):
        """Duplicate role name returns 400 response."""
        self._mock_auth(mock_get_token, mock_decode)
        # Create second role to cause name conflict
        Role.objects.create(
            name="Supervisor",
            company=self.company,
            created_by=self.pm_django_user
        )
        data = {
            "role_id": self.role.id,
            "name": "Supervisor"  # already exists in same company
        }
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: no auth token provided → 401
    def test_update_role_without_authentication_returns_401_response(self):
        """Request without auth token returns 401."""
        res = self.client.put(
            self.url_role_table,
            data=json.dumps({"role_id": self.role.id, "name": "Test"}),
            content_type="application/json"
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: company not found — user exists but company is deleted → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_role_when_company_not_found_returns_404_response(self, mock_get_token, mock_decode):
        """Missing company returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)
        # Delete company to simulate company not found scenario
        self.company.delete()
        data = {"role_id": self.role.id, "name": "Updated Role"}
        res = self.client.put(
            self.url_role_table,
            data=json.dumps(data),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)