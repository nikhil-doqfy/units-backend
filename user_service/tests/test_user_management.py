import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany, Property, PropertyBlocks, Unit, UnitOwner
from user_service.models import PropertyManager, Owner, Tenant, UserProfile
from lease.models import Lease


class UserManagementTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = "/user/management"

        # Admin 
        self.admin = User.objects.create_user(
            username="admin", password="adminpass", email="admin@test.com"
        )
        # Company 
        self.company = PropertyManagmentCompany.objects.create(
            name="Test PMC", address_line_1="addr1", address_line_2="addr2",
            licence_number="LIC001", licence_expiry_date=timezone.now(),
            licence_issuer="Gov", created_by=self.admin,
        )

        # Logged-in PM 
        self.pm_user = User.objects.create_user(
            username="pm@test.com", password="pmpass", email="pm@test.com",
            first_name="John", last_name="Doe",
        )
        self.pm = PropertyManager.objects.create(
            user=self.pm_user, email=self.pm_user.email,
            token="pmtoken", company=self.company, created_by=self.admin,
        )

        # Property → Block → Unit 
        self.property = Property.objects.create(
            property_name="Test Property", address_line_1="addr1",
            address_line_2="addr2", landmark="lm", pincode="123456",
            no_of_blocks=1, no_of_units=1, pmc=self.company, created_by=self.admin,
        )
        self.block = PropertyBlocks.objects.create(
            property=self.property, block_name="Block A",
            no_of_units=1, no_of_floors=3, no_of_parking=5, created_by=self.admin,
        )
        self.unit = Unit.objects.create(
            property_block_tower=self.block, unit_name="Unit 101",
            rent=5000, cycle="MONTHLY", created_by=self.admin,
        )

        # Owner linked to unit (so owner_ids filter works) 
        self.owner_user = User.objects.create_user(
            username="owner@test.com", password="ownerpass", email="owner@test.com",
            first_name="Alice", last_name="Smith",
        )
        self.owner = Owner.objects.create(
            user=self.owner_user, email=self.owner_user.email,
            created_by=self.admin,
        )
        UnitOwner.objects.create(
            unit=self.unit, owner=self.owner, created_by=self.admin,
        )

        # Tenant linked via Lease (so tenant_ids filter works)
        self.tenant_user = User.objects.create_user(
            username="tenant@test.com", password="tenantpass", email="tenant@test.com",
            first_name="Bob", last_name="Jones",
        )
        self.tenant = Tenant.objects.create(
            user=self.tenant_user, email=self.tenant_user.email,
            created_by=self.admin,
        )
        Lease.objects.create(
            unit=self.unit, tenant=self.tenant,
            created_by=self.admin, lease_status="ACTIVE", is_active=True,
        )

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_user.email}

    # POST — create

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_owner_user_with_valid_data_returns_201_and_creates_owner(self, mock_get_token, mock_decode):
        """POST role=OWNER return 201, Owner record created in DB."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(self.url, json.dumps({
            "first_name": "New", "last_name": "Owner",
            "email": "newowner@test.com", "password": "pass1234", "role": "OWNER",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["role"], "OWNER")
        self.assertTrue(Owner.objects.filter(user__email="newowner@test.com").exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_user_with_valid_data_returns_201_and_creates_tenant(self, mock_get_token, mock_decode):
        """POST role=TENANT return 201, Tenant record created in DB."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(self.url, json.dumps({
            "first_name": "New", "last_name": "Tenant",
            "email": "newtenant@test.com", "password": "pass1234", "role": "TENANT",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Tenant.objects.filter(user__email="newtenant@test.com").exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_company_user_with_valid_data_returns_201_and_links_company(self, mock_get_token, mock_decode):
        """POST role=COMPANY_USER return 201, PropertyManager created linked to company."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(self.url, json.dumps({
            "first_name": "New", "last_name": "Manager",
            "email": "newpm@test.com", "password": "pass1234", "role": "COMPANY_USER",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        pm = PropertyManager.objects.filter(user__email="newpm@test.com").first()
        self.assertIsNotNone(pm)
        self.assertEqual(pm.company, self.company)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_with_missing_required_fields_returns_400(self, mock_get_token, mock_decode):
        """POST with any required field missing returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        # missing email, password, role
        res = self.client.post(self.url, json.dumps({
            "first_name": "Test", "last_name": "User",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_with_invalid_role_returns_400(self, mock_get_token, mock_decode):
        """POST with role not in OWNER/TENANT/COMPANY_USER returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(self.url, json.dumps({
            "first_name": "Test", "last_name": "User",
            "email": "x@test.com", "password": "pass", "role": "SUPERADMIN",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_user_with_duplicate_email_returns_400(self, mock_get_token, mock_decode):
        """POST with already registered email returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.post(self.url, json.dumps({
            "first_name": "Dup", "last_name": "User",
            "email": "owner@test.com",  # already exists
            "password": "pass1234", "role": "OWNER",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # GET — list + filters
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_user_management_list_returns_paginated_response(self, mock_get_token, mock_decode):
        """GET returns 200 with content list and pagination block."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertIn("content", body)
        self.assertIn("pagination", body)
        for key in ("current_page", "limit", "total_records", "total_pages"):
            self.assertIn(key, body["pagination"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_filtered_by_owner_role_returns_only_owners(self, mock_get_token, mock_decode):
        """GET role=OWNER returns only users with role=OWNER.
        Owner must be linked via UnitOwner, Unit , Property ,PMC."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"role": "OWNER"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        # All returned users must have role OWNER
        for user in content:
            self.assertEqual(user["role"]["key"], "OWNER")
        # Our linked owner must appear
        emails = [u["email"] for u in content]
        self.assertIn("owner@test.com", emails)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_filtered_by_tenant_role_returns_only_tenants(self, mock_get_token, mock_decode):
        """GET role=TENANT returns only users with role=TENANT.
        Tenant must be linked via Lease, Unit, Property ,PMC."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"role": "TENANT"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        for user in content:
            self.assertEqual(user["role"]["key"], "TENANT")
        emails = [u["email"] for u in content]
        self.assertIn("tenant@test.com", emails)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_filtered_by_company_user_role_returns_property_managers(self, mock_get_token, mock_decode):
        """GET role=COMPANY_USER returns only PropertyManagers."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"role": "COMPANY_USER"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        for user in content:
            self.assertEqual(user["role"]["key"], "PROPERTY_MANAGER")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_with_search_keyword_returns_matching_results(self, mock_get_token, mock_decode):
        """GET search=Alice returns matching user."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"search": "Alice"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in res.json()["content"]]
        self.assertIn("owner@test.com", emails)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_with_non_matching_search_returns_empty_list(self, mock_get_token, mock_decode):
        """GET search with no match returns empty list, not 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"search": "xyznonexistent"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_users_filtered_by_active_status_returns_only_active_users(self, mock_get_token, mock_decode):
        """GET is_active=true returns only active users."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"is_active": "true"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for user in res.json()["content"]:
            self.assertTrue(user["is_active"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_specific_user_by_user_id_returns_single_record(self, mock_get_token, mock_decode):
        """GET user_id=X returns only that specific user."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"user_id": self.pm.id}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]["email"], "pm@test.com")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_user_list_excludes_unlinked_owners(self, mock_get_token, mock_decode):
        """Owner not linked to any unit of this PMC must NOT appear in list."""
        self._mock_auth(mock_get_token, mock_decode)

        # Create owner with no unit link
        orphan_user = User.objects.create_user(
            username="orphan@test.com", email="orphan@test.com", password="pass"
        )
        Owner.objects.create(user=orphan_user, email="orphan@test.com", created_by=self.admin)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        emails = [u["email"] for u in res.json()["content"]]
        self.assertNotIn("orphan@test.com", emails)


    # PUT — update

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_existing_user_details_returns_200_and_updates_db(self, mock_get_token, mock_decode):
        """PUT valid user_id return 200, first_name updated in DB."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(self.url, json.dumps({
            "user_id": self.pm.id,
            "first_name": "UpdatedJohn",
            "contact_number": "1112223333",
        }), content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.pm_user.refresh_from_db()
        self.assertEqual(self.pm_user.first_name, "UpdatedJohn")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_user_without_user_id_returns_400(self, mock_get_token, mock_decode):
        """PUT without user_id return 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(self.url, json.dumps({"first_name": "NoID"}),
            content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_non_existent_user_returns_404(self, mock_get_token, mock_decode):
        """PUT with non-existent user_id return 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.put(self.url, json.dumps({"user_id": 99999, "first_name": "Ghost"}),
            content_type="application/json", HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


    # DELETE — deactivate then permanent delete

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_active_user_performs_soft_delete_and_sets_inactive(self, mock_get_token, mock_decode):
        """DELETE active user return is_active=False (soft delete)."""
        self._mock_auth(mock_get_token, mock_decode)

        target_user = User.objects.create_user(
            username="target@test.com", email="target@test.com", password="pass"
        )
        target = Owner.objects.create(
            user=target_user, email="target@test.com", created_by=self.pm_user,
        )

        res = self.client.delete(
            f"{self.url}?user_id={target.id}", HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        target.refresh_from_db()
        self.assertFalse(target.is_active)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_inactive_user_permanently_removes_user_from_database(self, mock_get_token, mock_decode):
        """DELETE already-inactive user return permanent delete from DB."""
        self._mock_auth(mock_get_token, mock_decode)

        target_user = User.objects.create_user(
            username="permdel@test.com", email="permdel@test.com", password="pass"
        )
        target = Owner.objects.create(
            user=target_user, email="permdel@test.com",
            is_active=False, created_by=self.pm_user,
        )

        res = self.client.delete(
            f"{self.url}?user_id={target.id}", HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(UserProfile.objects.filter(id=target.id).exists())
        self.assertFalse(User.objects.filter(email="permdel@test.com").exists())

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_without_user_id_returns_400(self, mock_get_token, mock_decode):
        """DELETE without user_id return 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_non_existent_user_returns_404(self, mock_get_token, mock_decode):
        """DELETE non-existent user_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(f"{self.url}?user_id=99999", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_user_created_by_different_manager_returns_404(self, mock_get_token, mock_decode):
        """DELETE user created by different PM returns 404 (not accessible)."""
        self._mock_auth(mock_get_token, mock_decode)

        other_user = User.objects.create_user(
            username="other@test.com", email="other@test.com", password="pass"
        )
        other_owner = Owner.objects.create(
            user=other_user, email="other@test.com",
            created_by=self.admin,  # created by admin, not pm_user
        )

        res = self.client.delete(
            f"{self.url}?user_id={other_owner.id}", HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_request_without_authentication_token_returns_401(self):
        """
        Verify unauthenticated request is rejected
        with HTTP 401 UNAUTHORIZED response.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_patch_method_on_user_management_endpoint_returns_405(self, mock_get_token, mock_decode):
        """
        Verify unsupported PATCH request returns HTTP 405 METHOD NOT ALLOWED.
        """
        self._mock_auth(mock_get_token, mock_decode)
        res = self.client.patch(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)