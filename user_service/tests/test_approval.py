import json
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany, Property, PropertyBlocks, Unit
from user_service.models import PropertyManager, Tenant, Approval


class ApprovalViewTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = "/user/approval/"

        # Create admin Django user (used as created_by)
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com",
            first_name="Admin",
            last_name="User",
        )

        # Create company linked to admin user
        self.company = PropertyManagmentCompany.objects.create(
            name="Test PMC",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC001",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )

        # Create logged-in PropertyManager
        # PropertyManager IS the UserProfile (same pk)
        # decorator sets request.user = UserProfile.filter(user__email=email).first()
        self.pm_django_user = User.objects.create_user(
            username="pm@test.com",
            password="pmpass",
            email="pm@test.com",
            first_name="John",
            last_name="Doe",
        )
        self.pm = PropertyManager.objects.create(
            user=self.pm_django_user,
            email=self.pm_django_user.email,
            token="pmtoken",
            company=self.company,
            created_by=self.admin_user,
        )

        # Create property hierarchy (property → block → unit)
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
        self.block = PropertyBlocks.objects.create(
            property=self.property,
            block_name="Block A",
            no_of_floors=1,
            no_of_units=1,
            no_of_parking=2,
            created_by=self.admin_user,
        )
        self.unit = Unit.objects.create(
            property_block_tower=self.block,
            unit_name="Unit 101",
            rent=5000,
            cycle="MONTHLY",
            created_by=self.admin_user,
        )

        # Create Tenant — token required by decorator
        self.tenant_django_user = User.objects.create_user(
            username="tenant@test.com",
            password="tenantpass",
            email="tenant@test.com",
            first_name="Alice",
            last_name="Smith",
        )
        self.tenant = Tenant.objects.create(
            user=self.tenant_django_user,
            email="tenant@test.com",
            token="tenanttoken",
            created_by=self.pm_django_user,
        )

        # Create existing Approval for GET/PUT tests
        self.approval = Approval.objects.create(
            created_by=self.pm_django_user,
            tenant=self.tenant,
            unit=self.unit,
            requested_rent=4500,
            requested_tenure="12 months",
        )

    # Auth mock helper
    # Mocks get_jwt_token -> returns raw token string
    # Mocks decode_jwt_token -> returns payload with email
    # Decorator fetches PropertyManager by email -> token matches -> auth passes
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    # approval_view — GET /user/approval/?approval_id=<id>
    # Returns single approval detail by approval_id
    #  approval detail returned by approval_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_by_id_returns_approval_details_successfully(self, mock_get_token, mock_decode):
        """
        GET with valid approval_id should return approval details with 200.
        """
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"approval_id": self.approval.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(content["id"], self.approval.id)
        self.assertEqual(content["unit"], "Unit 101")

    # approval_id response contains all expected keys
    # Note: approval_id GET does NOT return 'status' field (only lease_id GET does)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_details_response_contains_all_expected_approval_fields(self, mock_get_token, mock_decode):
        """Approval detail response should contain all required approval-related fields."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"approval_id": self.approval.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        for key in (
            "id", "tenant", "unit",
            "requested_rent", "requested_tenure",
            "actual_rent", "actual_tenure",
            "approved", "approved_by", "approved_at",
        ):
            self.assertIn(key, content)

    #  approved_by is None for a pending approval
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_pending_approval_details_returns_null_approved_by_field(self, mock_get_token, mock_decode):
        """Pending approval should return approved_by as None because no action is taken yet."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"approval_id": self.approval.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertIsNone(res.json()["content"]["approved_by"])

    # approval_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_details_by_invalid_approval_id_returns_404_not_found(self, mock_get_token, mock_decode):
        """Invalid or non-existent approval_id should return 404 approval not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"approval_id": 99999},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # approval_view — GET /user/approval/?lease_id=<id>
    # Returns approval for a given lease
    # Negative: lease_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_by_invalid_lease_id_returns_404_when_lease_does_not_exist(self, mock_get_token, mock_decode):
        """Non-existent lease_id should return 404 lease not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"lease_id": 99999},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    #  lease exists but no approval found for it → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_by_lease_id_returns_404_when_no_approval_exists_for_lease(self, mock_get_token, mock_decode):
        """Existing lease without linked approval should return 404 approval not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        from lease.models import Lease
        lease = Lease.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            lease_status="DRAFT",
            created_by=self.pm_django_user,
        )
        # Delete the approval so none exists for this lease
        self.approval.delete()

        res = self.client.get(
            self.url,
            {"lease_id": lease.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)
    # approval_view — GET /user/approval/ (paginated list)
    # Returns paginated list of all approvals with optional status filter
    #  list returned with 200 and content array
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_returns_paginated_approval_records_with_200_response(self, mock_get_token, mock_decode):
        """Approval listing endpoint should return paginated approval records successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        body = res.json()
        self.assertIn("content", body)
        self.assertIsInstance(body["content"], list)

    # pagination block has all required keys
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_response_contains_complete_pagination_metadata(self, mock_get_token, mock_decode):
        """Pagination metadata should contain all required pagination-related fields."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        body = res.json()

        self.assertIn("pagination", body)
        for key in ("total_records", "page", "page_size", "total_pages"):
            self.assertIn(key, body["pagination"])

    #  status=PENDING filter returns pending approvals only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_with_pending_status_filter_returns_only_pending_approvals(self, mock_get_token, mock_decode):
        """status=PENDING filter should return only pending approval records."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"status": "PENDING"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        for item in content:
            self.assertEqual(item["status"], "PENDING")

    # status=APPROVED filter returns approved approvals only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_with_approved_status_filter_returns_only_approved_approvals(self, mock_get_token, mock_decode):
        """status=APPROVED filter should return only approved approval records."""
        self._mock_auth(mock_get_token, mock_decode)

        # Mark approval as approved
        self.approval.approved = True
        self.approval.approved_by = self.pm
        self.approval.save()

        res = self.client.get(
            self.url, {"status": "APPROVED"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for item in res.json()["content"]:
            self.assertEqual(item["status"], "APPROVED")

    # status=REJECTED filter returns rejected approvals only
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_with_rejected_status_filter_returns_only_rejected_approvals(self, mock_get_token, mock_decode):
        """status=REJECTED filter should return only rejected approval records."""
        self._mock_auth(mock_get_token, mock_decode)

        # Mark approval as rejected (approved=False, approved_by set)
        self.approval.approved = False
        self.approval.approved_by = self.pm
        self.approval.save()

        res = self.client.get(
            self.url, {"status": "REJECTED"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        for item in res.json()["content"]:
            self.assertEqual(item["status"], "REJECTED")

    #  pending approval has status=PENDING and approved=False
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_pending_approval_record_contains_correct_pending_status_and_approval_flag(self, mock_get_token, mock_decode):
        """Pending approval record should contain correct status and approved flag values."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"status": "PENDING"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        items = res.json()["content"]
        matching = [i for i in items if i["id"] == self.approval.id]
        self.assertTrue(len(matching) == 1)
        self.assertEqual(matching[0]["status"], "PENDING")
        self.assertFalse(matching[0]["approved"])

    #  out of range page returns last page without crash
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_approval_list_with_out_of_range_page_number_returns_valid_response(self, mock_get_token, mock_decode):
        """Requesting page number beyond available pages should not crash the API response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"page": 9999}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # approval_view — POST /user/approval/
    # Creates a new rent approval request
    # approval created successfully with all required fields
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_with_valid_payload_returns_201_created(self, mock_get_token, mock_decode):
        """Valid approval creation payload should successfully create new approval record."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "unit_id": self.unit.id,
            "requested_rent": "4000",
            "requested_tenure": "6 months",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.json()["content"])

    #  requested_tenure is optional — POST succeeds without it
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_without_requested_tenure_creates_approval_successfully(self, mock_get_token, mock_decode):
        """Approval creation should succeed even when requested_tenure is omitted."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "unit_id": self.unit.id,
            "requested_rent": "3500",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

    # Negative: tenant_id not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_without_tenant_id_returns_400_bad_request(self, mock_get_token, mock_decode):
        """Missing tenant_id in approval creation request should return 400 bad request."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"unit_id": self.unit.id, "requested_rent": "4000"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: unit_id not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_without_unit_id_returns_400_bad_request(self, mock_get_token, mock_decode):
        """Missing unit_id in approval creation request should return 400 bad request."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": self.tenant.id, "requested_rent": "4000"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: requested_rent not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_without_requested_rent_returns_400_bad_request(self, mock_get_token, mock_decode):
        """Missing requested_rent in approval creation request should return 400 bad request."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": self.tenant.id, "unit_id": self.unit.id}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: tenant_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_with_invalid_tenant_id_returns_404_not_found(self, mock_get_token, mock_decode):
        """Non-existent tenant_id should return 404 tenant not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": 99999,
            "unit_id": self.unit.id,
            "requested_rent": "4000",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: unit_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_with_invalid_unit_id_returns_404_not_found(self, mock_get_token, mock_decode):
        """Non-existent unit_id should return 404 unit not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "unit_id": 99999,
            "requested_rent": "4000",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: user is not a PropertyManager → 403
    # Note: decorator returns 404 if UserProfile not found
    # but if UserProfile exists and is not PropertyManager → view returns 403
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_approval_request_by_non_property_manager_returns_403_forbidden(self, mock_get_token, mock_decode):
        """Authenticated user who is not a PropertyManager should receive 403 forbidden response."""
        # Create Tenant user — has UserProfile but not PropertyManager
        other_user = User.objects.create_user(
            username="other@test.com",
            password="otherpass",
            email="other@test.com",
        )
        from user_service.models import Tenant as TenantModel
        TenantModel.objects.create(
            user=other_user,
            email=other_user.email,
            token="othertoken",
            created_by=self.admin_user,
        )
        mock_get_token.return_value = "othertoken"
        mock_decode.return_value = {"email": other_user.email}

        payload = {
            "tenant_id": self.tenant.id,
            "unit_id": self.unit.id,
            "requested_rent": "4000",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer othertoken",
        )

        # View checks PropertyManager.filter(user=user_profile.user).exists()
        # If not PM → 403
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # approval_view — PUT /user/approval/
    # Approve or reject a rent approval request
    # Negative: approval_id not provided → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_approval_request_without_approval_id_returns_400_bad_request(self, mock_get_token, mock_decode):
        """Missing approval_id in update request payload should return 400 bad request."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"action": "APPROVE", "rent": 4500}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: approval_id does not exist → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_approval_request_with_invalid_approval_id_returns_404_not_found(self, mock_get_token, mock_decode):
        """Non-existent approval_id should return 404 approval not found response."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"approval_id": 99999, "action": "APPROVE"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: user is not a PropertyManager → 403
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_approval_request_by_non_property_manager_returns_403_forbidden(self, mock_get_token, mock_decode):
        """Non-PropertyManager user attempting to update approval should receive 403 forbidden response."""
        other_user = User.objects.create_user(
            username="other2@test.com",
            password="otherpass",
            email="other2@test.com",
        )
        from user_service.models import Tenant as TenantModel
        TenantModel.objects.create(
            user=other_user,
            email=other_user.email,
            token="othertoken2",
            created_by=self.admin_user,
        )
        mock_get_token.return_value = "othertoken2"
        mock_decode.return_value = {"email": other_user.email}

        payload = {"approval_id": self.approval.id, "action": "APPROVE"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer othertoken2",
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    # Negative: no auth token provided → 401
    def test_approval_view_without_authentication_token_returns_401_unauthorized(self):
        """Request without authorization token should return 401 unauthorized response."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # Negative: DELETE method not supported → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_request_on_approval_endpoint_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """DELETE method should not be allowed for approval endpoint."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: PATCH method not supported → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_patch_request_on_approval_endpoint_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """PATCH method should not be allowed for approval endpoint."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.patch(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)