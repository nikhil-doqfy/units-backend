import json
from datetime import datetime
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from unittest.mock import patch

from utilities import status
from property.models import PropertyManagmentCompany
from user_service.models import PropertyManager, Owner


class OwnerCRUDTestCase(TestCase):

    def setUp(self):
        self.client = Client()
        self.url = "/user/owner"

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

        # An existing owner for GET/PUT/DELETE tests
        self.owner_django_user = User.objects.create_user(
            username="owner@test.com",
            password="ownerpass",
            email="owner@test.com",
            first_name="Alice",
            last_name="Smith",
        )
        self.owner = Owner.objects.create(
            user=self.owner_django_user,
            created_by=self.pm_django_user,
            email="owner@test.com",
            contact_number="9876543210",
            emirate_id="784-1990-1234567-1",
            nationality="AE",
            passport_number="AB1234567",
            passport_expiry_datetime=datetime(2027, 6, 30),
            visa_number="VIS12345",
            visa_expiry_datetime=datetime(2026, 12, 31),
            license_expiry_date=datetime(2025, 3, 15).date(),
        )

    # Auth helper 
    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm_django_user.email}

    # _serialize_owner  (pure unit tests — no HTTP)
    def test_serialize_owner_returns_all_owner_fields_correctly(self):
        """Serializer returns all populated owner fields correctly."""
        from user_service.views import _serialize_owner

        result = _serialize_owner(self.owner)

        self.assertEqual(result["id"], self.owner.id)
        self.assertEqual(result["email"], "owner@test.com")
        self.assertEqual(result["name"], "Alice Smith")
        self.assertEqual(result["first_name"], "Alice")
        self.assertEqual(result["last_name"], "Smith")
        self.assertEqual(result["passport_expiry_date"], "2027-06-30")
        self.assertEqual(result["visa_expiry_date"], "2026-12-31")
        self.assertEqual(result["license_expiry_date"], "2025-03-15")
        self.assertEqual(result["emirates_id"], "784-1990-1234567-1")

    def test_serialize_owner_returns_empty_string_for_null_dates(self):
        """
        serializer returns empty string for null date fields.
        """
        from user_service.views import _serialize_owner

        self.owner.passport_expiry_datetime = None
        self.owner.visa_expiry_datetime = None
        self.owner.license_expiry_date = None
        result = _serialize_owner(self.owner)

        self.assertEqual(result["passport_expiry_date"], "")
        self.assertEqual(result["visa_expiry_date"], "")
        self.assertEqual(result["license_expiry_date"], "")

    def test_serialize_owner_returns_empty_string_for_null_optional_fields(self):
        """Serializer returns empty string for optional null fields."""
        from user_service.views import _serialize_owner

        self.owner.code = None
        self.owner.contact_number = None
        self.owner.nationality = None
        result = _serialize_owner(self.owner)

        self.assertEqual(result["code"], "")
        self.assertEqual(result["contact_number"], "")
        self.assertEqual(result["nationality"], "")

    def test_serialize_owner_uses_user_email_when_owner_email_is_blank(self):
        """Serializer falls back to user email when owner email is empty."""
        from user_service.views import _serialize_owner

        self.owner.email = ""
        result = _serialize_owner(self.owner)

        self.assertEqual(result["email"], self.owner_django_user.email)

    def test_serialize_owner_removes_trailing_space_when_last_name_missing(self):
        """Serializer removes trailing space if last name is blank."""
        from user_service.views import _serialize_owner

        self.owner_django_user.last_name = ""
        self.owner_django_user.save()
        result = _serialize_owner(self.owner)

        self.assertEqual(result["name"], "Alice")
        self.assertFalse(result["name"].endswith(" "))


    # GET — list
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_returns_paginated_owner_data_successfully(self, mock_get_token, mock_decode):
        """GET owner list returns paginated response successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")

        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertIn("content", body)
        self.assertIsInstance(body["content"], list)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_response_contains_pagination_keys(self, mock_get_token, mock_decode):
        """GET owner list response contains pagination details."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        body = res.json()

        self.assertIn("pagination", body)
        for key in ("total_records", "total_pages", "current_page", "page_size"):
            self.assertIn(key, body["pagination"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_search_by_name_returns_matching_owner(self, mock_get_token, mock_decode):
        """Search by first name filters results correctly."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"search": "Alice"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        emails = [o["email"] for o in res.json()["content"]]
        self.assertIn("owner@test.com", emails)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_search_by_email(self, mock_get_token, mock_decode):
        """Search by email filters results correctly."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"search": "owner@test.com"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        emails = [o["email"] for o in res.json()["content"]]
        self.assertIn("owner@test.com", emails)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_search_with_no_match_returns_empty_list(self, mock_get_token, mock_decode):
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
    def test_get_owner_list_csv_export_returns_csv_response(self, mock_get_token, mock_decode):
        """CSV export request returns CSV response successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"export": "csv"}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "text/csv")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_list_out_of_range_page_returns_last_available_page(self, mock_get_token, mock_decode):
        """Requesting a page beyond total_pages returns last page, no crash."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"page": 9999}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, 200)

    # GET — detail (owner_id provided)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_detail_returns_owner_information_successfully(self, mock_get_token, mock_decode):
        """GET owner detail returns owner information successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"owner_id": self.owner.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )
        body = res.json()

        self.assertEqual(res.status_code, 200)
        self.assertIn("owner_details", body["content"])
        self.assertIn("table", body["content"])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_detail_with_invalid_owner_id_returns_404(self, mock_get_token, mock_decode):
        """GET with non-existent owner_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url, {"owner_id": 99999}, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_detail_for_inactive_owner_returns_404(self, mock_get_token, mock_decode):
        """Inactive owner should not be returned in detail response."""
        self._mock_auth(mock_get_token, mock_decode)

        self.owner_django_user.is_active = False
        self.owner_django_user.save()

        res = self.client.get(
            self.url,
            {"owner_id": self.owner.id},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_detail_with_occupied_filter_returns_empty_table(self, mock_get_token, mock_decode):
        """Occupied tenancy filter returns empty table when no leases exist."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"owner_id": self.owner.id, "tenancy_status": "OCCUPIED"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["content"]["table"], [])

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_owner_detail_with_vacant_filter_returns_successfully(self, mock_get_token, mock_decode):
        """tenancy_status=VACANT filter works without crash."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.get(
            self.url,
            {"owner_id": self.owner.id, "tenancy_status": "VACANT"},
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, 200)

    # POST — create
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_owner_with_valid_data_returns_201_successfully(self, mock_get_token, mock_decode):
        """POST with valid data creates owner and returns 201."""
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
            "license_expiry_date": "2026-03-01",
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
    def test_post_create_owner_missing_email_returns_400(self, mock_get_token, mock_decode):
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
    def test_post_create_owner_duplicate_email_returns_400(self, mock_get_token, mock_decode):
        """POST with already-registered email returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"first_name": "Alice", "last_name": "Dup", "email": "owner@test.com"}
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_owner_with_invalid_license_expiry_date_returns_empty_value(self, mock_get_token, mock_decode):
        """Malformed license_expiry_date does not crash — stored as None → ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "first_name": "Test",
            "last_name": "User",
            "email": "testbaddate@test.com",
            "license_expiry_date": "not-a-date",
        }
        res = self.client.post(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.json()["content"]["license_expiry_date"], "")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_owner_with_only_required_fields_sets_optional_fields_empty(self, mock_get_token, mock_decode):
        """POST with only required fields — optional fields serialize as ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"first_name": "", "last_name": "", "email": "minimal@test.com"}
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


    # PUT — update
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_owner_with_valid_data_returns_successfully(self, mock_get_token, mock_decode):
        """PUT with valid owner_id updates fields and returns 200."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "owner_id": self.owner.id,
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
    def test_update_owner_without_owner_id_returns_400_response(self, mock_get_token, mock_decode):
        """PUT without owner_id returns 400."""
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
    def test_update_owner_with_invalid_owner_id_returns_404_response(self, mock_get_token, mock_decode):
        """PUT with non-existent owner_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"owner_id": 99999, "first_name": "Ghost"}
        res = self.client.put(
            self.url,
            json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_owner_with_valid_date_fields_updates_dates_correctly(self, mock_get_token, mock_decode):
        """Valid date fields update successfully."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "owner_id": self.owner.id,
            "passport_expiry_date": "2030-01-15",
            "visa_expiry_date": "2029-06-30",
            "license_expiry_date": "2028-12-01",
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
        self.assertEqual(content["license_expiry_date"], "2028-12-01")

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_owner_with_invalid_date_returns_empty_string(self, mock_get_token, mock_decode):
        """PUT with malformed date does not crash — serialized as ''."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {
            "owner_id": self.owner.id,
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
    def test_put_partial_update_only_first_name(self, mock_get_token, mock_decode):
        """PUT changing only first_name leaves last_name unchanged."""
        self._mock_auth(mock_get_token, mock_decode)

        payload = {"owner_id": self.owner.id, "first_name": "Renamed"}
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

    # DELETE — soft delete
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_owner_with_valid_owner_id_deactivates_owner_successfully(self, mock_get_token, mock_decode):
        """DELETE with valid owner_id returns 200 and deactivates user."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?owner_id={self.owner.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.owner_django_user.refresh_from_db()
        self.assertFalse(self.owner_django_user.is_active)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_owner_missing_owner_id_returns_400(self, mock_get_token, mock_decode):
        """Missing owner_id in delete request returns 400."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url, HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_owner_with_invalid_owner_id_returns_404_response(self, mock_get_token, mock_decode):
        """DELETE with non-existent owner_id returns 404."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url}?owner_id=99999",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_deleted_owner_does_not_appear_in_owner_list_response(self, mock_get_token, mock_decode):
        """After soft-delete, owner does not appear in GET list."""
        self._mock_auth(mock_get_token, mock_decode)

        self.client.delete(
            f"{self.url}?owner_id={self.owner.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken",
        )

        res = self.client.get(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        emails = [o["email"] for o in res.json()["content"]]
        self.assertNotIn("owner@test.com", emails)

    # Auth & method guards
    def test_request_without_authentication_returns_401_response(self):
        """Request without auth token is rejected with 401."""
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_unsupported_http_method_returns_405_response(self, mock_get_token, mock_decode):
        """PATCH (unsupported method) returns 405."""
        self._mock_auth(mock_get_token, mock_decode)

        res = self.client.patch(self.url, HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)