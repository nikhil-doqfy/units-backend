import json
from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany
from user_service.models import PropertyManager, Tenant


class TenantCRUDTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = "/user/tenant"

        # Admin Django user (used as created_by)
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass",
            email="admin@test.com",
        )

        # PMC company
        self.company = PropertyManagmentCompany.objects.create(
            name="Test PMC",
            address_line_1="addr1",
            address_line_2="addr2",
            licence_number="LIC001",
            licence_expiry_date=timezone.now(),
            licence_issuer="Gov",
            created_by=self.admin_user,
        )

        # Logged-in PropertyManager (the authenticated user)
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

        # An existing tenant for GET/PUT tests
        self.tenant_django_user = User.objects.create_user(
            username="tenant@test.com",
            password="tenantpass",
            email="tenant@test.com",
            first_name="Alice",
            last_name="Smith",
        )
        self.tenant = Tenant.objects.create(
            user=self.tenant_django_user,
            created_by=self.pm_django_user,
            email="tenant@test.com",
            contact_number="9876543210",
            emirate_id="784-1990-1234567-1",
            nationality="AE",
            passport_number="AB1234567",
            passport_expiry_datetime=datetime(2027, 6, 30),
            visa_number="VIS12345",
            visa_expiry_datetime=datetime(2026, 12, 31),
        )

    # Auth helper 
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}


    # _serialize_tenant  (pure unit tests — no HTTP)
    def test_serialize_tenant_returns_all_fields_correctly(self):
        """All populated fields are serialized correctly."""
        from user_service.views import _serialize_tenant

        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["id"], self.tenant.id)
        self.assertEqual(result["email"], "tenant@test.com")
        self.assertEqual(result["name"], "Alice Smith")
        self.assertEqual(result["first_name"], "Alice")
        self.assertEqual(result["last_name"], "Smith")
        self.assertEqual(result["passport_expiry_date"], "2027-06-30")
        self.assertEqual(result["visa_expiry_date"], "2026-12-31")
        self.assertEqual(result["emirates_id"], "784-1990-1234567-1")
        self.assertEqual(result["contact_number"], "9876543210")
        self.assertIn("document_groups", result)
        self.assertIsInstance(result["document_groups"], list)

    def test_serialize_tenant_returns_empty_string_for_null_date_fields(self):
        """Null date fields must return '' not None or crash."""
        from user_service.views import _serialize_tenant

        self.tenant.passport_expiry_datetime = None
        self.tenant.visa_expiry_datetime = None
        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["passport_expiry_date"], "")
        self.assertEqual(result["visa_expiry_date"], "")

    def test_serialize_tenant_returns_empty_string_for_null_optional_fields(self):
        """Optional string fields that are None must return ''."""
        from user_service.views import _serialize_tenant

        self.tenant.code = None
        self.tenant.contact_number = None
        self.tenant.nationality = None
        self.tenant.pin_code = None
        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["code"], "")
        self.assertEqual(result["contact_number"], "")
        self.assertEqual(result["nationality"], "")
        self.assertEqual(result["pin_code"], "")

    def test_serialize_tenant_email_falls_back_to_user_email(self):
        """If tenant.email is blank, falls back to tenant.user.email."""
        from user_service.views import _serialize_tenant

        self.tenant.email = ""
        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["email"], self.tenant_django_user.email)

    def test_serialize_tenant_removes_trailing_space_when_last_name_is_missing(self):
        """Verify full name does not contain trailing whitespace when last name is blank."""
        from user_service.views import _serialize_tenant

        self.tenant_django_user.last_name = ""
        self.tenant_django_user.save()
        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["name"], "Alice")
        self.assertFalse(result["name"].endswith(" "))

    def test_serialize_tenant_returns_empty_document_groups_when_no_documents_exist(self):
        """document_groups is empty list when no lease documents exist."""
        from user_service.views import _serialize_tenant

        result = _serialize_tenant(self.tenant)

        self.assertEqual(result["document_groups"], [])

    # GET — by tenant_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_details_by_id_returns_success_response(self, mock_get_token, mock_decode):
        """GET with tenant_id returns tenant detail with 200."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"tenant_id": self.tenant.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertEqual(content["email"], "tenant@test.com")
        self.assertEqual(content["name"], "Alice Smith")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_details_with_invalid_tenant_id_returns_404(self, mock_get_token, mock_decode):
        """"Verify GET request returns 404 when tenant_id does not exist."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"tenant_id": 99999}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_inactive_tenant_by_id_returns_404_response(self, mock_get_token, mock_decode):
        """Verify GET request returns 404 for inactive tenant records."""
        self._mock_auth(mock_get_token, mock_decode)

        self.tenant_django_user.is_active = False
        self.tenant_django_user.save()

        res = self.client.get(
            self.url,
            {"tenant_id": self.tenant.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # GET — by email
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_details_by_email_returns_success_response(self, mock_get_token, mock_decode):
        """"Verify GET request with valid email returns matching tenant details."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"email": "tenant@test.com"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"]["email"], "tenant@test.com")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_details_by_email_is_case_insensitive(self, mock_get_token, mock_decode):
        """GET email lookup is case-insensitive."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"email": "TENANT@TEST.COM"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"]["email"], "tenant@test.com")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_details_with_unknown_email_returns_404(self, mock_get_token, mock_decode):
        """GET with non-existent email returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"email": "nobody@test.com"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # GET — list (paginated lease table)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_returns_paginated_response_successfully(self, mock_get_token, mock_decode):
        """GET without filters returns paginated list with 200."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("content", body)
        self.assertIsInstance(body["content"], list)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_response_contains_required_pagination_fields(self, mock_get_token, mock_decode):
        """Verify pagination object contains all required pagination keys."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        body = res.json()

        self.assertIn("pagination", body)
        for key in ("total_records", "total_pages", "current_page", "page_size"):
            self.assertIn(key, body["pagination"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_with_onboarding_tab_returns_successfully(self, mock_get_token, mock_decode):
        """Verify onboarding tab filter returns successful response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"tab": "onboarding"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_with_active_tab_returns_successfully(self, mock_get_token, mock_decode):
        """Verify active tab filter returns successful response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"tab": "active"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_with_past_tab_returns_successfully(self, mock_get_token, mock_decode):
        """Verify past tab filter returns successful response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"tab": "past"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_with_rejected_tab_returns_successfully(self, mock_get_token, mock_decode):
        """Verify rejected tab filter returns successful response."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"tab": "rejected"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_tenant_list_with_non_matching_search_returns_empty_list(self, mock_get_token, mock_decode):
        """Search with no matching term returns empty list, not 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"search": "xyznonexistent99"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_export_tenant_list_as_csv_without_data_returns_404(self, mock_get_token, mock_decode):
        """export=csv with no matching leases returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"export": "csv"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        # No leases exist in test DB so export returns 404
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # POST — create
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_with_valid_data_returns_201(self, mock_get_token, mock_decode):
        """POST with valid data creates tenant and returns 201."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "first_name": "Bob",
            "last_name": "Jones",
            "email": "bob@test.com",
            "contact_number": "1234567890",
            "nationality": "US",
            "passport_number": "P987654",
            "passport_expiry_date": "2028-01-01",
            "visa_number": "V111",
            "visa_expiry_date": "2027-06-01",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertEqual(content["email"], "bob@test.com")
        self.assertEqual(content["name"], "Bob Jones")
        self.assertEqual(content["passport_expiry_date"], "2028-01-01")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_with_name_field_splits_first_and_last_name_correctly(self, mock_get_token, mock_decode):
        """"Verify full name provided in name field is split into first and last name."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"name": "Charlie Brown", "email": "charlie@test.com"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertEqual(content["first_name"], "Charlie")
        self.assertEqual(content["last_name"], "Brown")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_without_email_returns_400(self, mock_get_token, mock_decode):
        """POST without email returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"first_name": "No", "last_name": "Email"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_existing_tenant_email_updates_record_instead_of_creating_duplicate(self, mock_get_token, mock_decode):
        """Verify existing tenant email updates existing record instead of creating duplicate."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "email": "tenant@test.com",   # already exists
            "contact_number": "1111111111",
            "nationality": "IN",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )
        # Should update, not error
        self.assertEqual(res.status_code, 200)
        content = res.json()["content"]
        self.assertEqual(content["contact_number"], "1111111111")
        self.assertEqual(content["nationality"], "IN")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_tenant_with_minimal_payload_sets_optional_fields_to_empty(self, mock_get_token, mock_decode):
        """POST with only email — optional fields serialize as ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"email": "minimal@test.com"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        content = res.json()["content"]
        self.assertEqual(content["contact_number"], "")
        self.assertEqual(content["passport_number"], "")
        self.assertEqual(content["visa_number"], "")
        self.assertEqual(content["nationality"], "")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_post_create_tenant_invalid_date_ignored(self, mock_get_token, mock_decode):
        """Malformed passport_expiry_date does not crash — stored as None returns ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "email": "baddateuser@test.com",
            "passport_expiry_date": "not-a-date",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["passport_expiry_date"], "")

    # PUT — update
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_tenant_with_valid_data_returns_success_response(self, mock_get_token, mock_decode):
        """PUT with valid tenant_id updates fields and returns 200."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "first_name": "Updated",
            "last_name": "Name",
            "contact_number": "1111111111",
            "nationality": "IN",
        }
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(content["name"], "Updated Name")
        self.assertEqual(content["contact_number"], "1111111111")
        self.assertEqual(content["nationality"], "IN")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_put_update_tenant_via_name_field(self, mock_get_token, mock_decode):
        """PUT using 'name' field (no first/last) splits and updates correctly."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": self.tenant.id, "name": "Jane Doe"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(content["first_name"], "Jane")
        self.assertEqual(content["last_name"], "Doe")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_tenant_without_tenant_id_returns_400(self, mock_get_token, mock_decode):
        """PUT without tenant_id returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"first_name": "No ID"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_non_existing_tenant_returns_404(self, mock_get_token, mock_decode):
        """PUT with non-existent tenant_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": 99999, "first_name": "Ghost"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_tenant_date_fields_with_valid_dates_updates_successfully(self, mock_get_token, mock_decode):
        """PUT with valid date strings updates both date fields."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "passport_expiry_date": "2030-01-15",
            "visa_expiry_date": "2029-06-30",
        }
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(content["passport_expiry_date"], "2030-01-15")
        self.assertEqual(content["visa_expiry_date"], "2029-06-30")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_tenant_with_invalid_date_returns_empty_date_field(self, mock_get_token, mock_decode):
        """PUT with malformed date does not crash — serialized as ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "tenant_id": self.tenant.id,
            "passport_expiry_date": "bad-date",
        }
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["passport_expiry_date"], "")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_partial_update_of_tenant_only_updates_specified_fields(self, mock_get_token, mock_decode):
        """PUT changing only first_name leaves last_name unchanged."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"tenant_id": self.tenant.id, "first_name": "Renamed"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertEqual(content["first_name"], "Renamed")
        self.assertEqual(content["last_name"], "Smith")  # untouched

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_inactive_tenant_returns_404_response(self, mock_get_token, mock_decode):
        """Verify updating inactive tenant returns 404 response."""
        self._mock_auth(mock_get_token, mock_decode)

        self.tenant_django_user.is_active = False
        self.tenant_django_user.save()

        payload = {"tenant_id": self.tenant.id, "first_name": "Ghost"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    def test_request_without_authentication_returns_401(self):
        """Request without auth token is rejected with 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_request_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """Verify DELETE request returns 405 because endpoint does not support DELETE."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?tenant_id={self.tenant.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_patch_request_returns_405_method_not_allowed(self, mock_get_token, mock_decode):
        """PATCH (unsupported method) returns 405."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.patch(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)