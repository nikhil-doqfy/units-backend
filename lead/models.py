from django.db import models
from user_service.models import UserProfile
from property_management.models import Base
from utilities import constants
from utilities.org_scope import get_pmc_ids_for_user


class LeadQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(pmc_id__in=pmc_ids)


class Lead(Base):
    objects = LeadQuerySet.as_manager()
    code = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey("property.Unit",on_delete=models.CASCADE,related_name="leads")
    tenant = models.ForeignKey(UserProfile,on_delete=models.SET_NULL,related_name="tenant_leads",null=True,blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20,choices=constants.LEAD_STATUS_CHOICES,default=constants.INTERESTED)
    platform = models.CharField(max_length=20,choices=constants.PLATFORM_CHOICES)
    lead_type = models.CharField(max_length=20,choices=constants.LEAD_TYPE_CHOICES)
    referred_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="referred_leads",
        null=True,
        blank=True
    )
    pmc = models.ForeignKey(
        "property.PropertyManagmentCompany",
        on_delete=models.CASCADE,
        related_name="leads"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            from utilities.helper_functions import generate_lead_code
            self.code = generate_lead_code()
            Lead.objects.filter(pk=self.pk).update(code=self.code)


class Proposal(Base):
    """One proposal-and-hold cycle for a Lead (Dubai Leasing Management
    Flow, Phase 1). A Lead can accumulate several of these over time --
    e.g. a first proposal is rejected or its hold expires, so a second
    proposal is sent -- only the one that reaches PROPOSAL_CONVERTED ever
    produces a Lease. Previously these fields lived directly on Lead, which
    could only ever represent the single most recent proposal; extracted
    here so proposal history isn't destroyed by a re-proposal.
    """
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="proposals")

    # Stored independently from Unit.rent/Unit.maintenance_charges since an
    # offer can differ from the unit's list price.
    offered_rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    offered_maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    # List of {"description": str, "amount": float} -- deliberately not FK
    # rows into charges.Charge: most proposals never convert, so creating
    # durable catalog rows for them is premature. They graduate into real
    # LeaseTransaction(cheque_type=OTHER_CHARGE) rows only at conversion
    # (see confirm_hold_and_proceed).
    other_charges = models.JSONField(null=True, blank=True, default=list)
    proposal_sent_at = models.DateTimeField(null=True, blank=True)
    proposal_channel = models.CharField(max_length=20, choices=constants.LEAD_TYPE_CHOICES, null=True, blank=True)

    # ── Hold ────────────────────────────────────────────────────────────────
    holding_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    hold_start_date = models.DateTimeField(null=True, blank=True)
    hold_expiry_date = models.DateTimeField(null=True, blank=True)
    hold_period_days = models.IntegerField(null=True, blank=True)
    # Policy note only -- no automated refund. payment/models.py is just a
    # Bank branch directory; no payment-gateway model exists anywhere in
    # this codebase capable of executing a real refund transaction.
    refund_policy_note = models.TextField(null=True, blank=True)

    # A Proposal row only ever gets created once a proposal is actually
    # sent -- "not proposed" is represented by the absence of any Proposal
    # row for a lead, not a state a Proposal itself can be in (unlike the
    # old Lead.proposal_status, which defaulted to NOT_PROPOSED).
    status = models.CharField(
        max_length=20,
        choices=constants.PROPOSAL_STATUS_CHOICES,
        default=constants.PROPOSAL_SENT_STATUS,
    )

    # ── Conversion linkage ───────────────────────────────────────────────────
    converted_lease = models.ForeignKey(
        "lease.Lease",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_proposal",
    )


class ActivityLog(Base):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activity_logs")
    activity_type = models.CharField(
        max_length=20,
        choices=constants.ACTIVITY_TYPE_CHOICES,
        default=constants.NOTE,
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)

class ScheduleMeeting(Base):
    STATUS_CHOICES = (
        ("SCHEDULED", "Scheduled"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    )

    lead = models.ForeignKey(
        Lead,
        on_delete=models.CASCADE,
        related_name="meetings"
    )

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="SCHEDULED"
    )
    google_calendar_url = models.URLField(max_length=1000, blank=True, null=True)

    def __str__(self):
        return f"{self.title} - {self.lead}"