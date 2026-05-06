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
    def test_tenant_login_success(self, mock_token):
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
    def test_company_login_success(self, mock_token):
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
    def test_owner_login_success(self, mock_token):
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
    def test_wrong_password(self):
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
    def test_user_not_found(self):
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
    def test_invalid_method(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    # 7. MISSING FIELDS
    def test_missing_fields(self):
        response = self.client.post(
            self.url,
            data=json.dumps({}),
            content_type="application/json"
        )

        self.assertEqual(response.status_code, 400)

    # 8. INACTIVE USER
    def test_inactive_user(self):
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
    def test_tenant_otp_login_success(self, mock_token):
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
    def test_wrong_otp(self):
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