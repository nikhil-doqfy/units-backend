import json
from django.test import TestCase, Client
from django.utils import timezone
from django.utils.timezone import timedelta
from unittest.mock import patch

from utilities import status, constants
from user_service.models import DocumentType

from lease.tests.factories import (
    UserFactory, CompanyFactory, PropertyManagerFactory,
    TenantFactory, PropertyFactory, BlockFactory,
    UnitFactory, LeaseFactory, reset_sequences,
)


def _make_doc_type(created_by):
    """Helper — create a DocumentType for LeaseTransaction (required NOT NULL field)."""
    return DocumentType.objects.create(
        name="Lease Cheque",
        section="LEASE_CHEQUE",
        created_by=created_by,
    )


def _make_transaction(lease, doc_type, created_by, amount=5000,
                      status_val=None, cheque_date=None):
    """Helper — create a LeaseTransaction (inherits Documents needs document_type)."""
    from lease.models import LeaseTransaction
    return LeaseTransaction.objects.create(
        lease=lease,
        document_type=doc_type,
        file_name="",
        file_path="",
        amount=amount,
        status=status_val or constants.CHEQUE_STATUS_CREDITED,
        cheque_date=cheque_date or timezone.now(),
        cheque_type=constants.RENT_CHEQUE,
        payment_type=constants.PAYMENT_TYPE_CHEQUE,
        is_active=True,
        created_by=created_by,
    )


class LeaseChequeTestCase(TestCase):

    def setUp(self):
        reset_sequences()
        self.client = Client()

        # Admin user
        self.admin = UserFactory(email="admin@test.com")

        # Company A — logged-in PM belongs here 
        self.company = CompanyFactory(created_by=self.admin)
        self.pm = PropertyManagerFactory(
            company=self.company,
            created_by=self.admin,
            token="pmtoken"
        )

        #Company B — another company (data isolation test) 
        self.other_admin = UserFactory(email="otheradmin@test.com")
        self.other_company = CompanyFactory(created_by=self.other_admin)
        self.other_pm = PropertyManagerFactory(
            company=self.other_company,
            created_by=self.other_admin,
            token="othertoken"
        )

        # Property hierarchy for Company A 
        self.tenant = TenantFactory(created_by=self.admin)
        self.property = PropertyFactory(company=self.company, created_by=self.admin)
        self.block    = BlockFactory(property=self.property, created_by=self.admin)
        self.unit     = UnitFactory(block=self.block, created_by=self.admin)
        self.lease    = LeaseFactory(
            unit=self.unit,
            tenant=self.tenant,
            lease_status=constants.ACTIVE,
            created_by=self.admin,
        )

        # Property hierarchy for Company B 
        self.other_tenant   = TenantFactory(created_by=self.other_admin)
        self.other_property = PropertyFactory(company=self.other_company, created_by=self.other_admin)
        self.other_block    = BlockFactory(property=self.other_property, created_by=self.other_admin)
        self.other_unit     = UnitFactory(block=self.other_block, created_by=self.other_admin)
        self.other_lease    = LeaseFactory(
            unit=self.other_unit,
            tenant=self.other_tenant,
            lease_status=constants.ACTIVE,
            created_by=self.other_admin,
        )

        # DocumentType (required for LeaseTransaction) 
        self.doc_type = _make_doc_type(self.admin)

        # LeaseTransaction for Company A 
        self.cheque = _make_transaction(
            lease=self.lease,
            doc_type=self.doc_type,
            created_by=self.admin,
            amount=5000,
            status_val=constants.CHEQUE_STATUS_CREDITED,
        )

        # LeaseTransaction for Company B 
        self.other_cheque = _make_transaction(
            lease=self.other_lease,
            doc_type=self.doc_type,
            created_by=self.other_admin,
            amount=9000,
            status_val=constants.CHEQUE_STATUS_REALIZED,
        )

        # URLs
        self.url_cheques         = "/api/lease/cheques"

    # Auth mock helpers
    def _mock_as_pm(self, mock_get_token, mock_decode):
        """Mock auth as Company A PM"""
        mock_get_token.return_value = "pmtoken"
        mock_decode.return_value = {"email": self.pm.user.email}

    def _mock_as_other_pm(self, mock_get_token, mock_decode):
        """Mock auth as Company B PM"""
        mock_get_token.return_value = "othertoken"
        mock_decode.return_value = {"email": self.other_pm.user.email}

    # lease_cheque_view — GET /api/lease/cheques
    # Returns single cheque by cheque_id or list by lease_id
    # get single cheque by cheque_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_cheque_by_cheque_id_returns_200(self, mock_get_token, mock_decode):
        """
        Verify GET request returns single cheque
        details when valid cheque_id is provided.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheques,
            {"cheque_id": self.cheque.id},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # get cheques by lease_id
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_all_cheques_by_lease_id_returns_200(self, mock_get_token, mock_decode):
        """
        Verify GET request returns all cheques
        linked to the given lease_id.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheques,
            {"lease_id": self.lease.id},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    # Negative: cheque_id not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_single_cheque_with_invalid_cheque_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify GET request returns 404 when cheque_id does not exist.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheques,
            {"cheque_id": 99999},
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # Negative: neither cheque_id nor lease_id return 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_get_cheque_without_cheque_id_and_lease_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify GET request returns 400 when both cheque_id and lease_id are missing.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheques,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: no auth → 401
    def test_get_cheque_without_authentication_returns_401(self):
        """
        Verify GET request returns 401 when authorization token is missing.
        """

        res = self.client.get(self.url_cheques)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


    # lease_cheque_view — POST /api/lease/cheques
    # Creates a new LeaseTransaction
    # cheque created successfully
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_new_cheque_returns_201(self, mock_get_token, mock_decode):
        """
        Verify POST request successfully creates a new cheque entry and returns 201.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        payload = {
            "lease_id": self.lease.id,
            "document_type_id": self.doc_type.id,
            "amount": 3000,
            "cheque_number": "CHQ001",
            "cheque_date": timezone.now().isoformat(),
            "cheque_type": constants.RENT_CHEQUE,
            "payment_type": constants.PAYMENT_TYPE_CHEQUE,
        }

        res = self.client.post(
            self.url_cheques,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", res.json()["content"])

    # Negative: lease_id missing return 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_cheque_without_lease_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify POST request returns 400 when lease_id is missing.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_cheques,
            data=json.dumps({"amount": 3000}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: invalid lease_id → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_create_cheque_with_invalid_lease_id_returns_404(self, mock_get_token, mock_decode):
        """
        Verify POST request returns 404 when lease_id does not exist.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.post(
            self.url_cheques,
            data=json.dumps({"lease_id": 99999, "amount": 3000}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # lease_cheque_view — PUT /api/lease/cheques
    # Updates an existing LeaseTransaction
    # cheque updated successfully
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_existing_cheque_returns_200(self, mock_get_token, mock_decode):
        """
        Verify PUT request successfully updates existing cheque details.
        """

        self._mock_as_pm(mock_get_token, mock_decode)

        payload = {
            "cheque_id": self.cheque.id,
            "amount": 6000,
            "status": constants.CHEQUE_STATUS_REALIZED,
        }

        res = self.client.put(
            self.url_cheques,
            data=json.dumps(payload),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        # Verify DB updated
        self.cheque.refresh_from_db()
        self.assertEqual(float(self.cheque.amount), 6000)

    # Negative: cheque_id missing → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_cheque_without_cheque_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify PUT request returns 400 when cheque_id is missing.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_cheques,
            data=json.dumps({"amount": 6000}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: cheque_id not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_update_non_existing_cheque_returns_404(self, mock_get_token, mock_decode):
        """
        Verify PUT request returns 404 when cheque_id does not exist.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.put(
            self.url_cheques,
            data=json.dumps({"cheque_id": 99999, "amount": 6000}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)

    # lease_cheque_view — DELETE /api/lease/cheques
    # Deletes a LeaseTransaction
    # cheque deleted successfully
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_existing_cheque_returns_200(self, mock_get_token, mock_decode):
        """
        Verify DELETE request successfully removes cheque record from database.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_cheques}?cheque_id={self.cheque.id}",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)

        from lease.models import LeaseTransaction
        self.assertFalse(LeaseTransaction.objects.filter(id=self.cheque.id).exists())

    # Negative: cheque_id missing → 400
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_cheque_without_cheque_id_returns_400(self, mock_get_token, mock_decode):
        """
        Verify DELETE request returns 400 when cheque_id is missing.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.delete(
            self.url_cheques,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    # Negative: cheque_id not found → 404
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_delete_non_existing_cheque_returns_404(self, mock_get_token, mock_decode):
        """
        Verify DELETE request returns 404 when cheque_id does not exist.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.delete(
            f"{self.url_cheques}?cheque_id=99999",
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_404_NOT_FOUND)


    # Company A PM — only sees Company A cheques, not Company B cheques
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_data_isolation_pm_sees_only_own_company_cheques(self, mock_get_token, mock_decode):
        """
        Verify Company A property manager can access only Company A cheque summary data.
        """
        self._mock_as_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheque_summary,
            HTTP_AUTHORIZATION="Bearer pmtoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]

        # Company A has 1 cheque of 5000 — total should be 5000, not 14000 (5000+9000)
        total_amount = content["total"]["amount"]
        self.assertEqual(float(total_amount), 5000.0)

    # Company B PM — only sees Company B cheques, not Company A cheques
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_data_isolation_other_pm_sees_only_own_company_cheques(self, mock_get_token, mock_decode):
        """
        Verify Company B property manager can access only Company B cheque summary data.
        """
        self._mock_as_other_pm(mock_get_token, mock_decode)

        res = self.client.get(
            self.url_cheque_summary,
            HTTP_AUTHORIZATION="Bearer othertoken"
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        content = res.json()["content"]

        # Company B has 1 cheque of 9000 — total should be 9000, not 14000 (5000+9000)
        total_amount = content["total"]["amount"]
        self.assertEqual(float(total_amount), 9000.0)

