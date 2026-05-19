import json
from datetime import date
from unittest.mock import patch
from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from utilities import constants
from user_service.models import (Tenant,Owner,PropertyManager,UserVerification)
from property.models import PropertyManagmentCompany


class UserLoginTestCase(TestCase):

    def setUp(self):
        self.url = reverse("auth_login")

        # BASE USERS

        self.tenant_user = User.objects.create_user(
            username="tenant@gmail.com",
            email="tenant@gmail.com",
            password="Test@123",
            is_active=True
        )

        self.owner_user = User.objects.create_user(
            username="owner@gmail.com",
            email="owner@gmail.com",
            password="Test@123",
            is_active=True
        )

        self.company_user = User.objects.create_user(
            username="company@gmail.com",
            email="company@gmail.com",
            password="Test@123",
            is_active=True
        )

        # TENANT PROFILE

        self.tenant = Tenant.objects.create(
            user=self.tenant_user,
            created_by=self.tenant_user
        )

        # OWNER PROFILE
        self.owner = Owner.objects.create(
            user=self.owner_user,
            created_by=self.owner_user
        )

        # COMPANY + MANAGER PROFILE

        self.company = PropertyManagmentCompany.objects.create(
            name="Test Company",
            licence_expiry_date=date(2030, 12, 31),
            created_by=self.company_user
        )

        self.manager = PropertyManager.objects.create(
            user=self.company_user,
            created_by=self.company_user,
            company=self.company
        )

    # 1. TENANT LOGIN (PASSWORD)
   
    @patch("auth_service.views.create_jwt_token")
    def test_login_with_valid_tenant_credentials_returns_success(self, mock_token):
        """
        Verify tenant user can login successfully using valid email and password.
        """
        mock_token.return_value = "fake-token"

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.tenant_user.email,
                "password": "Test@123",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json()["content"])

    # 2. COMPANY USER LOGIN (PASSWORD)
   
    @patch("auth_service.views.create_jwt_token")
    def test_login_with_valid_company_user_credentials_returns_success(self, mock_token):
        """
        Verify company user can login successfully and receives company details in response.
        """
        mock_token.return_value = "fake-token"

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.company_user.email,
                "password": "Test@123",
                "user_role": constants.COMPANY_USER
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json()["content"])
        self.assertEqual(
            response.json()["content"]["company_name"],
            "Test Company"
        )

    # 3. OWNER LOGIN

    @patch("auth_service.views.create_jwt_token")
    def test_login_with_valid_company_owner_credentials_returns_success(self, mock_token):
        """
        Verify company user can login successfully using valid credential.
        """
        mock_token.return_value = "fake-token"

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.owner_user.email,
                "password": "Test@123",
                "user_role": constants.OWNER
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

    # 4. WRONG PASSWORD
    def test_login_with_invalid_password_returns_bad_request(self):
        """
        Verify login fails when incorrect password is provided for an existing user.
        """
        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.tenant_user.email,
                "password": "WrongPass",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # 5. USER NOT FOUND
    def test_login_with_unregistered_email_returns_bad_request(self):
        """
        Verify login fails when user email does not exist in the system.
        """
        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": "notfound@gmail.com",
                "password": "Test@123",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # 6. INVALID METHOD
    def test_get_request_on_login_api_returns_method_not_allowed(self):
        """
        Verify GET request is not allowed on login API endpoint.
        """
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # 7. MISSING FIELDS
    def test_login_with_missing_required_fields_returns_bad_request(self):
        """
        Verify login fails when required fields are missing in request payload.
        """
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # 8. INACTIVE USER
    def test_login_with_inactive_user_returns_forbidden(self):
        """
        Verify inactive users are not allowed to login into the system.
        """
        self.tenant_user.is_active = False
        self.tenant_user.save()

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.tenant_user.email,
                "password": "Test@123",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 403)


    # 9. OTP LOGIN SUCCESS
    @patch("auth_service.views.create_jwt_token")
    def test_otp_login_with_verified_otp_returns_success(self, mock_token):
        """
        Verify user can login successfully using a verified OTP.
        """
        mock_token.return_value = "fake-token"

        UserVerification.objects.create(
            user_profile=self.tenant,
            otp="123456",
            purpose="login",
            is_verified=True
        )

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.tenant_user.email,
                "otp": "123456",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 200)

    # 10. OTP WRONG
    def test_otp_login_with_invalid_otp_returns_bad_request(self):
        """
        Verify OTP login fails when incorrect OTP is provided.
        """
        UserVerification.objects.create(
            user_profile=self.tenant,
            otp="123456",
            purpose="login",
            is_verified=True
        )

        response = self.client.post(
            self.url,
            data=json.dumps({
                "email": self.tenant_user.email,
                "otp": "000000",
                "user_role": constants.TENANT
            }),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)