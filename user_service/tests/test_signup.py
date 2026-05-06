import json
import uuid
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from utilities import constants
from user_service.models import Tenant, PropertyManager
from property.models import PropertyManagmentCompany


class UserSignupTestCase(TestCase):

    def setUp(self):
        self.url = reverse("signup")

        # UNIQUE EMAIL (CRITICAL FOR CI STABILITY)
        self.email = f"test_{uuid.uuid4().hex[:6]}@gmail.com"

        self.valid_tenant_data = {
            "email": self.email,
            "password": "Test@123",
            "confirm_password": "Test@123",
            "user_role": constants.TENANT,
            "first_name": "Test",
            "last_name": "User",
            "emirate_id": "12345",
            "visa_number": "V123",
            "contact_number": "9999999999",
            "pin_code": "411001"
        }
    
    # TENANT SUCCESS

    @patch("user_service.views.upload_document", return_value=None)
    def test_tenant_signup_success(self, mock_upload):
        response = self.client.post(
            self.url,
            data=json.dumps(self.valid_tenant_data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(User.objects.filter(username=self.email).count(), 1)
        self.assertEqual(Tenant.objects.count(), 1)

    # TENANT VALIDATION - MISSING FIELDS
    def test_tenant_missing_fields(self):
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 400)

    
    # PASSWORD MISMATCH

    def test_password_mismatch(self):
        data = self.valid_tenant_data.copy()
        data["confirm_password"] = "Wrong123"

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    
    # COMPANY USER SUCCESS
    
    @patch("user_service.views.upload_document", return_value=None)
    def test_company_user_signup_success(self, mock_upload):

        # Create company user
        company_user = User.objects.create_user(
            username="company_admin@gmail.com",
            email="company_admin@gmail.com",
            password="Test@123"
        )

        company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            licence_expiry_date="2030-12-31",
            created_by=company_user
        )

        data = self.valid_tenant_data.copy()
        data["email"] = f"company_{uuid.uuid4().hex[:6]}@gmail.com"
        data["user_role"] = constants.COMPANY_USER
        data["company_id"] = company.id

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(PropertyManager.objects.count(), 1)

    # COMPANY USER - MISSING COMPANY ID
    
    def test_company_user_missing_company_id(self):

        data = self.valid_tenant_data.copy()
        data["user_role"] = constants.COMPANY_USER
        data["email"] = f"company_{uuid.uuid4().hex[:6]}@gmail.com"

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # INVALID ROLE
    
    def test_invalid_role(self):
        data = self.valid_tenant_data.copy()
        data["user_role"] = "INVALID_ROLE"

        response = self.client.post(
            self.url,
            data=json.dumps(data),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # INVALID METHOD
    
    def test_invalid_method(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)