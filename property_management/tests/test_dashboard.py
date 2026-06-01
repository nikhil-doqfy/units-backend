from datetime import date
from django.test import TestCase, Client
from django.utils import timezone
from django.utils.timezone import timedelta
from unittest.mock import patch

from utilities import status, constants
from property_management.tests.factories import (
    UserFactory, CompanyFactory, PropertyManagerFactory,
    OwnerFactory, TenantFactory, PropertyFactory,
    BlockFactory, UnitFactory
)

from lease.models import LeaseTransaction
class DashboardTestCase(TestCase):

    def setUp(self):
        self.client = Client()

        # Create admin user (used as created_by across factories)
        self.admin = UserFactory()

        # Create company
        self.company = CompanyFactory(created_by=self.admin)

        # Create logged-in PropertyManager
        # PropertyManager IS the UserProfile (same pk)
        # decorator sets request.user = UserProfile.filter(user__email=email).first()
        # token must match what is sent in HTTP_AUTHORIZATION header
        self.pm = PropertyManagerFactory(
            company=self.company,
            created_by=self.admin,
            token="pmtoken"
        )
   
        # Create Owner for owner-role tests
        self.owner = OwnerFactory(created_by=self.admin)
        from property_management.models import DashboardVisualization
        for key, _ in constants.DASHBOARD_CHOICES:
            DashboardVisualization.objects.create(
                user=self.pm,
                visualization=key,
                is_visible=True,
                created_by=self.admin,
            )
        for key, _ in constants.DASHBOARD_CHOICES:
            DashboardVisualization.objects.create(
                user=self.owner,
                visualization=key,
                is_visible=True,
                created_by=self.admin,
            )


        # Create Tenant for lease tests
        self.tenant = TenantFactory(created_by=self.admin)

        # Unit.property_block_tower → PropertyBlocks → Property → pmc (company)
        self.property = PropertyFactory(pmc=self.company, created_by=self.admin)
        self.block    = BlockFactory(property=self.property, created_by=self.admin)
        self.unit     = UnitFactory(property_block_tower=self.block, created_by=self.admin)

        # Create active lease — dashboard tenant counts become non-zero
        from lease.models import Lease
        self.lease = Lease.objects.create(
            tenant=self.tenant,
            unit=self.unit,
            lease_status=constants.ACTIVE,
            lease_stage=constants.NEGOTIATION_SENT,
            end_date=timezone.now() + timedelta(days=10),
            created_by=self.admin,
        )

        from user_service.models import DocumentType

        self.doc_type = DocumentType.objects.create(
            name="Lease Cheque",
            section="LEASE_CHEQUE",  
            created_by=self.admin,
        )

        self.transaction = LeaseTransaction.objects.create(
            lease=self.lease,
            amount=5000,
            status=constants.CHEQUE_STATUS_REALIZED,
            cheque_date=timezone.now(),
            is_active=True,
            created_by=self.admin,
            document_type=self.doc_type,   
        )

    # Mocks get_jwt_token -> returns raw token string
    # Mocks decode_jwt_token -> returns payload with email
    # Decorator fetches UserProfile by email -> token matches -> auth passes
    def _mock_as_pm(self, mock_get_token, mock_decode):
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm.user.email}

    def _mock_as_owner(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.owner.token
        mock_decode.return_value = {"email": self.owner.user.email}

    # dashboard_overview — GET /statistics
    # Returns property, tenant, occupancy, revenue, leads summary
    # PM gets dashboard 200
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_200_for_property_manager(self, mock_get_token, mock_decode):
        """GET /statistics by PropertyManager returns dashboard summary successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("content", res.json())

    #  all required top-level keys present
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_contains_all_required_response_keys(self, mock_get_token, mock_decode):
        """Dashboard response contains all required top-level keys."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        content = res.json()["content"]
        for key in (
            "properties", "tenants", "top_properties",
            "top_revenue_properties", "occupancy_data",
            "active_leads_count", "active_complaints_count"
        ):
            self.assertIn(key, content)

    # active tenant count is 1 (lease created in setUp)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_correct_active_tenant_count(self, mock_get_token, mock_decode):
        """Dashboard shows active tenant count based on active lease."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.json()["content"]["tenants"]["active"], 1)

    # upcoming_renewals is 1 (lease ends in 10 days)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_correct_upcoming_renewals_count(self, mock_get_token, mock_decode):
        """Dashboard shows upcoming renewals for leases ending soon."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.json()["content"]["tenants"]["upcoming_renewals"], 1)

    #  total_properties is 1
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_correct_total_property_count(self, mock_get_token, mock_decode):
        """Dashboard shows total properties count correctly."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.json()["content"]["properties"]["total"], 1)

    # property_id filter shows only that property's units
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_filters_data_by_property_id(self, mock_get_token, mock_decode):
        """GET /statistics with property_id filter returns filtered occupancy data."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get(
            "/statistics",
            {"property_id": self.property.id},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["occupancy_data"]["total_units"], 1)

    # top_revenue_properties non-empty (transaction in setUp)
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_top_revenue_properties(self, mock_get_token, mock_decode):
        """Dashboard returns non-empty top revenue properties list."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertTrue(len(res.json()["content"]["top_revenue_properties"]) >= 1)

    # Owner gets dashboard with leads=0
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_zero_leads_for_owner(self, mock_get_token, mock_decode):
        """Owner dashboard response returns active leads count as zero."""
        self._mock_as_owner(mock_get_token, mock_decode)
        res = self.client.get("/statistics", HTTP_AUTHORIZATION=f"Bearer {self.owner.token}")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["active_leads_count"], 0)

    # Negative: PM company set to None → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_404_when_company_not_found(self, mock_get_token, mock_decode):
        """GET /statistics returns 404 if PropertyManager company is deleted."""
        self._mock_as_pm(mock_get_token, mock_decode)
        self.company.delete()
        res = self.client.get("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_dashboard_overview_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /statistics returns 405."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/statistics", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_dashboard_overview_returns_401_without_authentication(self):
        """GET /statistics without authentication returns 401."""
        res = self.client.get("/statistics")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # faq_api — GET /faq_api (public — no auth required)

    # FAQ list returned with question and answer fields
    def test_faq_api_returns_faq_list_successfully(self):
        """GET /faq_api returns FAQ list with question and answer fields."""
        from user_service.models import FAQ
        FAQ.objects.create(question="What is rent?", answer="Monthly payment.")
        res = self.client.get("/faq_api")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertTrue(len(content) >= 1)
        self.assertIn("question", content[0])
        self.assertIn("answer", content[0])

    # empty FAQ list returns empty array
    def test_faq_api_returns_empty_list_when_no_faq_exists(self):
        """GET /faq_api returns empty array when no FAQ records exist."""
        res = self.client.get("/faq_api")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"], [])

    # Negative: wrong method → 405
    def test_faq_api_returns_405_for_invalid_http_method(self):
        """POST request on /faq_api returns 405."""
        res = self.client.post("/faq_api")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # dashboard_monthly_revenue — GET /monthly_revenue
    # Returns total_revenue, MRR, and 12-month revenue breakdown
    # response has correct structure
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_monthly_revenue_returns_summary_successfully(self, mock_get_token, mock_decode):
        """GET /monthly_revenue returns revenue summary with total_revenue, MRR, and monthly_revenue keys."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/monthly_revenue", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertIn("total_revenue", content)
        self.assertIn("MRR", content)
        self.assertIn("monthly_revenue", content)

    # monthly_revenue always has exactly 12 entries
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_monthly_revenue_returns_12_month_breakdown(self, mock_get_token, mock_decode):
        """GET /monthly_revenue always returns exactly 12 months in monthly_revenue breakdown."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/monthly_revenue", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(len(res.json()["content"]["monthly_revenue"]), 12)

    # year filter returns correct year data
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_monthly_revenue_filters_data_by_year(self, mock_get_token, mock_decode):
        """GET /monthly_revenue with year filter returns filtered revenue data successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get(
            "/monthly_revenue",
            {"year": timezone.now().year},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_monthly_revenue_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /monthly_revenue returns 405 Method Not Allowed."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/monthly_revenue", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_monthly_revenue_returns_401_without_authentication(self):
        """GET /monthly_revenue without authentication returns 401 Unauthorized."""
        res = self.client.get("/monthly_revenue")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # dashboard_cheque_visibility — GET /cheque_visibility
    # Returns list of cheques with filters
    # cheques list returned
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_visibility_returns_cheque_list_successfully(self, mock_get_token, mock_decode):
        """GET /cheque_visibility returns cheque list successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/cheque_visibility", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("cheques", res.json()["content"])

    # transaction created in setUp appears in cheque list
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_visibility_includes_existing_transaction(self, mock_get_token, mock_decode):
        """GET /cheque_visibility includes existing cheque transaction in response."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/cheque_visibility", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertTrue(len(res.json()["content"]["cheques"]) >= 1)

    # cheque_status filter works
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_visibility_filters_cheques_by_status(self, mock_get_token, mock_decode):
        """GET /cheque_visibility filters cheque records by cheque_status successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get(
            "/cheque_visibility",
            {"cheque_status": constants.CHEQUE_STATUS_REALIZED},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_visibility_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /cheque_visibility returns 405 Method Not Allowed."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/cheque_visibility", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_cheque_visibility_returns_401_without_authentication(self):
        """GET /cheque_visibility without authentication returns 401 Unauthorized."""
        res = self.client.get("/cheque_visibility")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # dashboard_cheque_aging — GET /cheque_aging
    # Returns cheque summary and aging breakup
    #  response has summary and aging_breakup
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_aging_returns_summary_successfully(self, mock_get_token, mock_decode):
        """GET /cheque_aging returns cheque summary and aging breakup successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/cheque_aging", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertIn("summary", content)
        self.assertIn("aging_breakup", content)

    # summary has correct keys
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_aging_summary_contains_required_keys(self, mock_get_token, mock_decode):
        """GET /cheque_aging summary contains total, realized, and bounced cheque counts."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/cheque_aging", HTTP_AUTHORIZATION="Bearer pmtoken")
        summary = res.json()["content"]["summary"]
        for key in ("total_cheques", "realized_cheques", "bounced_cheques"):
            self.assertIn(key, summary)

    # aging_breakup has correct keys
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_aging_breakup_contains_required_keys(self, mock_get_token, mock_decode):
        """GET /cheque_aging aging_breakup contains all required aging duration keys."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/cheque_aging", HTTP_AUTHORIZATION="Bearer pmtoken")
        breakup = res.json()["content"]["aging_breakup"]
        for key in ("30_days", "60_days", "90_days", "above_90_days"):
            self.assertIn(key, breakup)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_cheque_aging_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /cheque_aging returns 405 Method Not Allowed."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/cheque_aging", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_cheque_aging_returns_401_without_authentication(self):
        """GET /cheque_aging without authentication returns 401 Unauthorized."""
        res = self.client.get("/cheque_aging")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


    # dashboard_other_type_payments — GET /other_type_payments
    # Returns monthly breakdown by payment type (cheque/cash/bank/pdc)
    # response has total_revenue and monthly_data
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_other_type_payments_returns_summary_successfully(self, mock_get_token, mock_decode):
        """GET /other_type_payments returns payment summary and monthly payment data successfully."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/other_type_payments", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertIn("total_revenue", content)
        self.assertIn("monthly_data", content)

    # monthly_data always has exactly 12 entries
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_other_type_payments_returns_12_month_breakdown(self, mock_get_token, mock_decode):
        """GET /other_type_payments always returns exactly 12 months in monthly_data."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/other_type_payments", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(len(res.json()["content"]["monthly_data"]), 12)

    # Happy path: each month entry has payment type keys
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_other_type_payments_month_data_contains_payment_type_keys(self, mock_get_token, mock_decode):
        """GET /other_type_payments month data contains all payment type fields."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/other_type_payments", HTTP_AUTHORIZATION="Bearer pmtoken")
        month = res.json()["content"]["monthly_data"][0]
        for key in ("month", "month_str", "cheque", "cash", "bank_transfer", "pdc", "total"):
            self.assertIn(key, month)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_other_type_payments_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /other_type_payments returns 405 Method Not Allowed."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/other_type_payments", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_other_type_payments_returns_401_without_authentication(self):
        """GET /other_type_payments without authentication returns 401 Unauthorized."""
        res = self.client.get("/other_type_payments")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # dashboard_yearly_dues — GET /dashboard_graph_due
    # Returns year, overall totals, and monthly due breakdown

    #  response has year, overall, monthly_data
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_yearly_dues_returns_summary_successfully(self, mock_get_token, mock_decode):
        """GET /dashboard_graph_due returns yearly due summary with overall and monthly data."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/dashboard_graph_due", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]
        self.assertIn("year", content)
        self.assertIn("overall", content)
        self.assertIn("monthly_data", content)

    # overall block has all expected keys
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_yearly_dues_overall_contains_required_keys(self, mock_get_token, mock_decode):
        """GET /dashboard_graph_due overall section contains all required due summary fields."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/dashboard_graph_due", HTTP_AUTHORIZATION="Bearer pmtoken")
        overall = res.json()["content"]["overall"]
        for key in ("total_amount", "received_amount", "due_amount", "received_percent", "due_percent"):
            self.assertIn(key, overall)

    # monthly_data always has exactly 12 entries
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_yearly_dues_returns_12_month_breakdown(self, mock_get_token, mock_decode):
        """GET /dashboard_graph_due always returns exactly 12 months in monthly_data."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get("/dashboard_graph_due", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(len(res.json()["content"]["monthly_data"]), 12)

    #  year param returns correct year in response
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_yearly_dues_filters_data_by_year(self, mock_get_token, mock_decode):
        """GET /dashboard_graph_due with year filter returns data for requested year."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.get(
            "/dashboard_graph_due",
            {"year": timezone.now().year},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.json()["content"]["year"], timezone.now().year)

    # Negative: wrong method → 405
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_yearly_dues_returns_405_for_invalid_http_method(self, mock_get_token, mock_decode):
        """POST request on /dashboard_graph_due returns 405 Method Not Allowed."""
        self._mock_as_pm(mock_get_token, mock_decode)
        res = self.client.post("/dashboard_graph_due", HTTP_AUTHORIZATION="Bearer pmtoken")
        self.assertEqual(res.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    # Negative: no auth → 401
    def test_yearly_dues_returns_401_without_authentication(self):
        """GET /dashboard_graph_due without authentication returns 401 Unauthorized."""
        res = self.client.get("/dashboard_graph_due")
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
