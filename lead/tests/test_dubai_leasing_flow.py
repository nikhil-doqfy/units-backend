"""
End-to-end verification of the Dubai Leasing Management Flow (Phases 1-6):
Proposal -> Hold -> Lease creation -> Cheque schedule -> Documents ->
Ejari approval -> Signature -> Handover -> Activation, plus the
hold-expiry release path and proposal versioning (a Lead can accumulate
more than one Proposal; only the confirmed one ever converts to a Lease).

Uses the shared lease/tests/factories.py stack for org/company/PM/unit/
tenant setup, and mocks S3/email exactly like the existing lease test
suite (lease/tests/test_lease_signature.py etc.) does.
"""
import json
from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase, Client
from django.utils import timezone

from lease.tests.factories import (
    build_standard_stack,
    reset_sequences,
)
from lead.models import Lead, Proposal
from lease.models import Lease
from property.models import Unit
from utilities import constants


class DubaiLeasingFlowHappyPathTestCase(TestCase):
    def setUp(self):
        reset_sequences()
        self.client = Client()
        self.s = build_standard_stack()
        self.pm_user = self.s["pm_user"]
        self.token = self.s["token"]
        self.unit = self.s["unit"]
        self.pmc = self.s["company"]

        self.lead = Lead.objects.create(
            unit=self.unit,
            name="Prospect One",
            email="prospect1@test.com",
            contact_number="0500000000",
            platform=constants.DIRECT,
            lead_type=constants.EMAIL,
            pmc=self.pmc,
            created_by=self.pm_user,
        )

    def _auth_headers(self):
        return {"HTTP_AUTHORIZATION": f"Bearer {self.token}"}

    def _mock_auth(self, mock_get_token, mock_decode):
        mock_get_token.return_value = self.token
        mock_decode.return_value = {"email": self.pm_user.email}

    def _post(self, url, payload):
        return self.client.post(
            url, json.dumps(payload), content_type="application/json",
            **self._auth_headers(),
        )

    @patch("lease.views.upload_file_to_s3_base64", return_value="https://s3.example.com/doc.pdf")
    @patch("lead.views.send_ses_email")
    @patch("lease.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_full_happy_path_reaches_active(
        self, mock_get_token, mock_decode, mock_lease_email, mock_lead_email, mock_s3,
    ):
        self._mock_auth(mock_get_token, mock_decode)

        # ── Phase 1: Proposal & Holding ──────────────────────────────────
        res = self._post("/lead/send-proposal", {"lead_id": self.lead.id, "channel": "EMAIL"})
        self.assertEqual(res.status_code, 200, res.content)
        proposal_id = res.json()["content"]["proposal_id"]
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_PROPOSAL_SENT)

        res = self._post("/lead/respond-to-proposal", {
            "proposal_id": proposal_id, "response": "HOLD",
            "holding_amount": 2000, "hold_period_days": 3,
        })
        self.assertEqual(res.status_code, 200, res.content)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_ON_HOLD)
        proposal = Proposal.objects.get(id=proposal_id)
        self.assertEqual(proposal.status, constants.ON_HOLD_STATUS)

        # ── Phase 2: Contract Creation & Registration ────────────────────
        res = self._post("/lead/confirm-hold-and-proceed", {
            "proposal_id": proposal_id,
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "payment_frequency": constants.MONTHLY,
        })
        self.assertEqual(res.status_code, 201, res.content)
        lease_id = res.json()["content"]["lease_id"]
        lease = Lease.objects.get(id=lease_id)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_CONTRACT_IN_PROGRESS)
        self.assertIsNotNone(lease.vat_amount)
        proposal.refresh_from_db()
        self.assertEqual(proposal.status, constants.PROPOSAL_CONVERTED)
        self.assertEqual(proposal.converted_lease_id, lease.id)

        res = self._post("/api/lease/generate-cheque-schedule", {
            "lease_id": lease.id,
            "payment_frequency": constants.MONTHLY,
            "start_date": "2026-01-01",
        })
        self.assertEqual(res.status_code, 201, res.content)
        cheque_total = sum(c["amount"] for c in res.json()["content"])
        self.assertAlmostEqual(cheque_total, float(lease.contract_amount), places=2)

        res = self._post("/lease_documents", {
            "lease_id": lease.id,
            "documents": [{"file_name": "ejari.pdf", "data": "ZmFrZQ==", "type": constants.EJARI_CERTIFICATE}],
        })
        self.assertEqual(res.status_code, 201, res.content)
        lease.refresh_from_db()
        self.assertEqual(lease.lease_stage, constants.EJARI_DOCUMENT_UPLOAD)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_EJARI_PENDING)

        res = self._post("/api/lease/approve-ejari", {"lease_id": lease.id})
        self.assertEqual(res.status_code, 200, res.content)
        lease.refresh_from_db()
        self.assertEqual(lease.lease_stage, constants.EJARI_APPROVED)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_EJARI_APPROVED)

        res = self._post("/api/lease/ejari-send-signature", {"lease_id": lease.id})
        self.assertEqual(res.status_code, 200, res.content)
        lease.refresh_from_db()
        self.assertEqual(lease.lease_stage, constants.EJARI_SIGNING)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_ESIGN_PENDING)

        # Signature is blocked until handover is confirmed.
        from django.core.cache import cache
        verified_key = f"otp_ejari_signature_verified_{lease.id}_{self.s['tenant'].email.lower()}"
        cache.set(verified_key, True, timeout=600)
        res = self.client.post(
            "/api/lease/ejari-submit-signature",
            json.dumps({
                "lease_id": lease.id,
                "email": self.s["tenant"].email,
                "signature_data": "data:image/png;base64,ZmFrZQ==",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 400, res.content)
        self.assertIn("Handover", res.json()["message"])

        # ── Phase 5: Handover ─────────────────────────────────────────────
        res = self._post("/api/lease/confirm-handover", {"lease_id": lease.id, "handover_documents": []})
        self.assertEqual(res.status_code, 200, res.content)
        lease.refresh_from_db()
        self.assertIsNotNone(lease.handover_completed_at)

        # ── Phase 3 (activation) ──────────────────────────────────────────
        cache.set(verified_key, True, timeout=600)
        res = self.client.post(
            "/api/lease/ejari-submit-signature",
            json.dumps({
                "lease_id": lease.id,
                "email": self.s["tenant"].email,
                "signature_data": "data:image/png;base64,ZmFrZQ==",
            }),
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        lease.refresh_from_db()
        self.assertEqual(lease.lease_stage, constants.ACTIVATED)
        self.assertEqual(lease.lease_status, "ACTIVE")
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_ACTIVE)
        self.assertTrue(self.unit.is_leased)

    @patch("lead.views.send_ses_email")
    @patch("utilities.decorator.decode_jwt_token")
    @patch("utilities.decorator.get_jwt_token")
    def test_second_proposal_after_first_closed_only_confirmed_one_converts(
        self, mock_get_token, mock_decode, mock_email,
    ):
        """Proposal versioning: a first proposal that's rejected doesn't
        block a second one from being sent to the same lead, and only the
        proposal that actually gets confirmed ever reaches
        PROPOSAL_CONVERTED / gets a converted_lease -- the first stays
        PROPOSAL_CLOSED with no lease attached."""
        self._mock_auth(mock_get_token, mock_decode)

        # First proposal: customer says not interested.
        res = self._post("/lead/send-proposal", {"lead_id": self.lead.id, "channel": "EMAIL"})
        self.assertEqual(res.status_code, 200, res.content)
        first_proposal_id = res.json()["content"]["proposal_id"]

        res = self._post("/lead/respond-to-proposal", {
            "proposal_id": first_proposal_id, "response": "NOT_INTERESTED",
        })
        self.assertEqual(res.status_code, 200, res.content)
        self.unit.refresh_from_db()
        self.assertEqual(self.unit.status, constants.UNIT_AVAILABLE)

        # Second proposal for the same lead: customer holds this time.
        res = self._post("/lead/send-proposal", {"lead_id": self.lead.id, "channel": "EMAIL"})
        self.assertEqual(res.status_code, 200, res.content)
        second_proposal_id = res.json()["content"]["proposal_id"]
        self.assertNotEqual(first_proposal_id, second_proposal_id)

        res = self._post("/lead/respond-to-proposal", {
            "proposal_id": second_proposal_id, "response": "HOLD",
            "holding_amount": 1000, "hold_period_days": 2,
        })
        self.assertEqual(res.status_code, 200, res.content)

        res = self._post("/lead/confirm-hold-and-proceed", {"proposal_id": second_proposal_id})
        self.assertEqual(res.status_code, 201, res.content)
        lease_id = res.json()["content"]["lease_id"]

        self.assertEqual(self.lead.proposals.count(), 2)

        first_proposal = Proposal.objects.get(id=first_proposal_id)
        self.assertEqual(first_proposal.status, constants.PROPOSAL_CLOSED)
        self.assertIsNone(first_proposal.converted_lease_id)

        second_proposal = Proposal.objects.get(id=second_proposal_id)
        self.assertEqual(second_proposal.status, constants.PROPOSAL_CONVERTED)
        self.assertEqual(second_proposal.converted_lease_id, lease_id)


class DubaiLeasingHoldExpiryTestCase(TestCase):
    def setUp(self):
        reset_sequences()
        self.s = build_standard_stack()
        self.unit = self.s["unit"]
        self.pmc = self.s["company"]
        self.lead = Lead.objects.create(
            unit=self.unit,
            name="Prospect Two",
            email="prospect2@test.com",
            contact_number="0500000001",
            platform=constants.DIRECT,
            lead_type=constants.EMAIL,
            pmc=self.pmc,
            created_by=self.s["pm_user"],
        )
        self.proposal = Proposal.objects.create(
            lead=self.lead,
            created_by=self.s["pm_user"],
            status=constants.ON_HOLD_STATUS,
            holding_amount=1500,
            hold_period_days=3,
            hold_start_date=timezone.now() - timedelta(days=5),
            hold_expiry_date=timezone.now() - timedelta(days=2),
        )
        self.unit.status = constants.UNIT_ON_HOLD
        self.unit.save(update_fields=["status"])

    @patch("lead.services.send_ses_email")
    def test_expired_hold_releases_unit_and_proposal(self, mock_email):
        from lead.services import release_expired_hold_for_proposal

        release_expired_hold_for_proposal(self.proposal, triggered_by="system")

        self.proposal.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(self.proposal.status, constants.HOLD_EXPIRED)
        self.assertIsNotNone(self.proposal.refund_policy_note)
        self.assertEqual(self.unit.status, constants.UNIT_AVAILABLE)

    @patch("lead.services.send_ses_email")
    def test_release_expired_holds_task_sweeps_all_due_proposals(self, mock_email):
        from lead.tasks import release_expired_holds

        release_expired_holds()

        self.proposal.refresh_from_db()
        self.unit.refresh_from_db()
        self.assertEqual(self.proposal.status, constants.HOLD_EXPIRED)
        self.assertEqual(self.unit.status, constants.UNIT_AVAILABLE)
