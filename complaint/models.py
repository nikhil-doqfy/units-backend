from django.db import models
from django.utils import timezone
from property_management.models import Base
from utilities import constants


class ServiceProvider(Base):

    # ── Details ────────────────────────────────────────────────────
    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    service_type = models.CharField(
        max_length=50,
        choices=constants.SERVICE_TYPE_CHOICES
    )
    company = models.ForeignKey(
        'property.PropertyManagmentCompany',
        on_delete=models.CASCADE,
        related_name='service_providers'
    )
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.service_type}"


class Complaint(Base):

    # ── Relations ─────────────────────────────────────────────────
    unit = models.ForeignKey(
        'property.Unit',
        on_delete=models.CASCADE,
        related_name='complaints'
    )
    raised_by = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.CASCADE,
        related_name='raised_complaints'
    )
    company = models.ForeignKey(
        'property.PropertyManagmentCompany',
        on_delete=models.CASCADE,
        related_name='complaints'
    )
    assigned_to = models.ForeignKey(
        ServiceProvider,
        on_delete=models.SET_NULL,
        related_name='assigned_complaints',
        null=True, blank=True
    )

    # ── Complaint Details ──────────────────────────────────────────
    code = models.CharField(max_length=50, blank=True)
    service_type = models.CharField(
        max_length=50,
        choices=constants.SERVICE_TYPE_CHOICES
    )
    priority = models.CharField(
        max_length=20,
        choices=constants.COMPLAINT_PRIORITY_CHOICES,
        default=constants.MEDIUM
    )
    description = models.TextField()
    locality = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=constants.COMPLAINT_STATUS_CHOICES,
        default=constants.PENDING
    )

    # ── Broadcast ─────────────────────────────────────────────────
    is_broadcasted = models.BooleanField(default=False)
    broadcasted_at = models.DateTimeField(null=True, blank=True)

    # ── Work Details ───────────────────────────────────────────────
    work_started_at = models.DateTimeField(null=True, blank=True)
    work_completed_at = models.DateTimeField(null=True, blank=True)
    issue_closed_on = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"CP{self.pk:04d}"
            Complaint.objects.filter(pk=self.pk).update(code=self.code)

    def work_duration(self):
        if self.work_started_at and self.work_completed_at:
            return self.work_completed_at - self.work_started_at
        return None

    def __str__(self):
        return f"{self.code} - {self.status}"


class ComplaintBroadcast(Base):

    # ── Relations ─────────────────────────────────────────────────
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='broadcasts'
    )
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='broadcast_complaints'
    )

    # ── Status ────────────────────────────────────────────────────
    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_rejected = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.complaint.code} -> {self.service_provider.name}"


class ComplaintImages(Base):

    # ── Relations ─────────────────────────────────────────────────
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='complaint_images'
    )

    # ── Image Details ──────────────────────────────────────────────
    image_path = models.TextField()
    file_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.complaint.code} - {self.file_name}"


class ComplaintTimeline(Base):

    # ── Relations ─────────────────────────────────────────────────
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='timeline'
    )
    user = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='complaint_timeline'
    )

    # ── Timeline Details ───────────────────────────────────────────
    timeline_status = models.CharField(
        max_length=30,
        choices=constants.COMPLAINT_TIMELINE_STATUS_CHOICES
    )
    note = models.TextField(null=True, blank=True)
    time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.complaint.code} - {self.timeline_status}"


class ComplaintActivityHistory(Base):

    # ── Relations ─────────────────────────────────────────────────
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='activity_history'
    )
    user = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.CASCADE,
        related_name='complaint_activities'
    )

    # ── Activity Details ───────────────────────────────────────────
    message = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.complaint.code} - {self.message}"