import json
from django.test import TestCase, Client
from unittest.mock import patch

from utilities import status
from lease.tests.factories import (
    build_standard_stack,
    LeaseFactory,
    TenantFactory,
    UnitFactory,
    reset_sequences,
)

class LeaseViewTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.url = "/api/lease"

        # Build the full stack in one call
        self.s = build_standard_stack()
        self.pm      = self.s["pm"]
        self.pm_user = self.s["pm_user"]
        self.unit    = self.s["unit"]
        self.tenant  = self.s["tenant"]
        self.token   = self.s["token"]

        # A lease ready for GET/PUT/DELETE tests
        self.lease = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            created_by=self.pm_user,
            lease_status="DRAFT",
        )

    # Auth helper 
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    # GET — by lease_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_by_id_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify GET request with valid lease_id returns lease details successfully.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertEqual(content["id"], self.lease.id)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_by_invalid_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify GET request with non-existing lease_id returns 404 response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"lease_id": 99999},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_soft_deleted_lease_returns_404(self, mock_get_token, mock_decode):
        """
        Verify inactive lease cannot be fetched using GET API.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.lease.is_active = False
        self.lease.save()

        res = self.client.get(
            self.url,
            {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # GET — list with filters
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_list_returns_success_response(self, mock_get_token, mock_decode):
        """
        Verify GET request without filters returns lease list successfully.        
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")

        self.assertEqual(res.status_code, 200)
        self.assertIsInstance(res.json()["content"], list)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_list_filtered_by_tenant_id_returns_matching_leases(self, mock_get_token, mock_decode):
        """ 
        Verify tenant_id filter returns only matching tenant leases.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"tenant_id": self.tenant.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        ids = [item["id"] for item in res.json()["content"]]
        self.assertIn(self.lease.id, ids)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_list_filtered_by_lease_status_returns_matching_results(self, mock_get_token, mock_decode):
        """
        Verify lease_status filter returns leases with matching status only.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"lease_status": "DRAFT"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        for item in res.json()["content"]:
            self.assertEqual(item["lease_status"], "DRAFT")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_list_filtered_by_unit_id_returns_matching_leases(self, mock_get_token, mock_decode):
        """
        GET with unit_id filter returns only leases for that unit.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"unit_id": self.unit.id},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        ids = [item["id"] for item in res.json()["content"]]
        self.assertIn(self.lease.id, ids)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_lease_list_search_with_invalid_keyword_returns_empty_list(self, mock_get_token, mock_decode):
        """
        Verify search with unmatched keyword returns empty lease list.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "XYZNOTEXIST"},
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_list_soft_deleted_leases_excluded(self, mock_get_token, mock_decode):
        """
        Soft-deleted leases (is_active=False) are excluded from list.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.lease.is_active = False
        self.lease.save()

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        ids = [item["id"] for item in res.json()["content"]]
        self.assertNotIn(self.lease.id, ids)

    # POST — create lease
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_with_valid_tenant_id_returns_success(self, mock_get_token, mock_decode):
        """
        POST with unit_id + tenant_id creates lease and returns 201.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Use a fresh tenant (no active lease)
        new_tenant = TenantFactory(created_by=self.pm_user)

        payload = {
            "unit_id": self.unit.id,
            "tenant_id": new_tenant.id,
            "rent": 4500,
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.json()["content"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_with_new_email_creates_tenant_successfully(self, mock_get_token, mock_decode):
        """
        Verify lease creation with new email automatically creates tenant profile.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "unit_id": self.unit.id,
            "email": "brandnew@test.com",
            "tenant_name": "Brand New",
            "rent": 3500,
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_with_existing_email_reuses_existing_tenant(self, mock_get_token, mock_decode):
        """
        Verify existing tenant is reused when email already exists.        
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Use a second unit to avoid active-lease conflict
        second_unit = UnitFactory(block=self.s["block"], created_by=self.s["admin"])
        new_tenant = TenantFactory(created_by=self.pm_user, email="existing@test.com")

        payload = {
            "unit_id": second_unit.id,
            "email": "existing@test.com",
            "rent": 3000,
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        # Confirm no duplicate tenant was created
        from user_service.models import Tenant
        count = Tenant.objects.filter(email="existing@test.com").count()
        self.assertEqual(count, 1)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_without_unit_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        POST without unit_id returns 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": self.tenant.id, "rent": 4000}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_without_tenant_id_and_email_returns_bad_request(self, mock_get_token, mock_decode):
        """
        POST without tenant_id and without email returns 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"unit_id": self.unit.id, "rent": 4000}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_lease_with_invalid_unit_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify lease creation with invalid unit_id returns 400 response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "unit_id": 99999,
            "tenant_id": self.tenant.id,
            "rent": 4000,
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_tenant_with_active_lease_returns_400(self, mock_get_token, mock_decode):
        """
        POST for tenant who already has ACTIVE lease returns 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        # Give this tenant an active lease first
        second_unit = UnitFactory(block=self.s["block"], created_by=self.s["admin"])
        LeaseFactory(
            unit=second_unit,
            tenant=self.tenant,
            created_by=self.pm_user,
            lease_status="ACTIVE",
        )

        payload = {
            "unit_id": self.unit.id,
            "tenant_id": self.tenant.id,
            "rent": 4000,
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("active lease", res.json()["message"].lower())

    # PUT — update lease
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lease_with_valid_data_returns_success(self, mock_get_token, mock_decode):
        """
        PUT with valid lease_id updates fields and returns 200.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "lease_id": self.lease.id,
            "rent": 5500,
            "lease_status": "ACTIVE",
            "remarks": "Updated via test",
        }
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertEqual(content["lease_status"], "ACTIVE")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lease_without_lease_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        PUT without lease_id returns 400.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"rent": 5000}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_non_existing_lease_id_returns_not_found(self, mock_get_token, mock_decode):
        """
        PUT with non-existent lease_id returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"lease_id": 99999, "rent": 5000}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_soft_deleted_lease_returns_not_found(self, mock_get_token, mock_decode):
        """
        Verify updating soft-deleted lease
        returns 404 response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.lease.is_active = False
        self.lease.save()

        payload = {"lease_id": self.lease.id, "rent": 5000}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_lease_date_fields_returns_success(self, mock_get_token, mock_decode):
        """
        Verify lease start_date and end_date
        are updated successfully.
        """
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "lease_id": self.lease.id,
            "start_date": "2025-03-01",
            "end_date": "2026-02-28",
        }
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_put_shell_and_core_bool_field(self, mock_get_token, mock_decode):
        """PUT shell_and_core=true is stored as boolean True."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"lease_id": self.lease.id, "shell_and_core": True}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        self.lease.refresh_from_db()
        self.assertTrue(self.lease.shell_and_core)

    # DELETE — soft delete
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_lease_with_valid_id_marks_lease_inactive_and_returns_success(self, mock_get_token, mock_decode):
        """
        Verify DELETE request with valid lease_id marks lease as inactive and returns 200 response
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?lease_id={self.lease.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, 200)
        self.lease.refresh_from_db()
        self.assertFalse(self.lease.is_active)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_lease_without_lease_id_returns_bad_request(self, mock_get_token, mock_decode):
        """
        Verify DELETE request without lease_id returns 400 bad request response.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url,
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_non_existent_lease_returns_not_found(self, mock_get_token, mock_decode):
        """
        DELETE with non-existent lease_id returns 404.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?lease_id=99999",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_deleted_lease_is_not_visible_in_lease_list(self, mock_get_token, mock_decode):
        """
        After DELETE, lease no longer appears in GET list.
        """
        self._mock_auth(mock_get_token, mock_decode)

        self.client.delete(
            f"{self.url}?lease_id={self.lease.id}",
            HTTP_AUTHORIZATION=f"Bearer {self.token}",
        )

        res = self.client.get(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        ids = [item["id"] for item in res.json()["content"]]
        self.assertNotIn(self.lease.id, ids)

    # Auth & method guards
    def test_request_without_auth_token_returns_unauthorized(self):
        """
        Request without auth token is rejected with 401.
        """
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_patch_method_on_lease_api_returns_method_not_allowed(self, mock_get_token, mock_decode):
        """
        PATCH (unsupported method) returns 405.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.patch(self.url, HTTP_AUTHORIZATION=f"Bearer {self.token}")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)