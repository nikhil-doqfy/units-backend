from django.db import models
from django.utils import timezone
from property_management.models import Base
from utilities import constants

class ServiceType(Base):
    name = models.CharField(
        max_length=50,
        choices=constants.SERVICE_TYPE_CHOICES,
        unique=True
    )

    def __str__(self):
        return self.name


class ServiceLocality(Base):
    locality = models.CharField(max_length=255)

    def __str__(self):
        return self.locality


class ServiceProvider(Base):

    name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    email = models.EmailField(null=True, blank=True)
    company = models.ForeignKey(
        'property.PropertyManagmentCompany',
        on_delete=models.CASCADE,
        related_name='service_providers'
    )

    service_types = models.ManyToManyField(
        ServiceType,
        related_name='service_providers'
    )

    localities = models.ManyToManyField(
        ServiceLocality,
        related_name='service_providers'
    )

    avg_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0.00
    )

    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name}"

class Complaint(Base):

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
    assigned_to = models.ManyToManyField(
        ServiceProvider,
        related_name='assigned_complaints',
        blank=True
    )

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
    status = models.CharField(
        max_length=30,
        choices=constants.COMPLAINT_STATUS_CHOICES,
        default=constants.PENDING
    )

    locality = models.CharField(max_length=255, null=True, blank=True)

    is_broadcasted = models.BooleanField(default=False)
    broadcasted_at = models.DateTimeField(null=True, blank=True)
    broadcast_expiry = models.DateTimeField(null=True, blank=True)
    attempt_count = models.IntegerField(default=0)

    current_appointment = models.ForeignKey(
        'Appointment',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+'
    )

    work_started_at = models.DateTimeField(null=True, blank=True)
    work_completed_at = models.DateTimeField(null=True, blank=True)
    issue_closed_on = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
        if self.unit and self.unit.property_block_tower and self.unit.property_block_tower.property:
            prop = self.unit.property_block_tower.property
            if prop.map_address and not self.locality:
                parts = [part.strip() for part in prop.map_address.split(',')]
                if len(parts) > 1:
                    self.locality = parts[1]

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

class ComplaintImages(Base):

    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='complaint_images'
    )
    image_path = models.TextField()
    file_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.complaint.code} - {self.file_name}"


class ComplaintBroadcast(Base):

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

    is_priority = models.BooleanField(default=False)
    priority_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        help_text="Score based on rating + proximity"
    )

    is_accepted = models.BooleanField(default=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    is_rejected = models.BooleanField(default=False)
    rejected_at = models.DateTimeField(null=True, blank=True)

    expires_at = models.DateTimeField(null=True, blank=True)
    is_expired = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.complaint.code} -> {self.service_provider.name}"


class Appointment(Base):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name='appointments'
    )
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='appointments',
        null=True,        
        blank=True
    )
    status = models.CharField(
        max_length=20,
        choices=constants.APPOINTMENT_STATUS_CHOICES,
        default=constants.APPOINTMENT_PROPOSED
    )
    note = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.complaint.code} - {self.status}"

class AppointmentSlot(Base):

    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name='slots'
    )
    proposed_time = models.DateTimeField()
    is_selected = models.BooleanField(default=False)
    selected_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.appointment.complaint.code} - {self.proposed_time}"


class ComplaintRating(Base):

    complaint = models.OneToOneField(
        Complaint,
        on_delete=models.CASCADE,
        related_name='rating'
    )
    rated_by = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.CASCADE,
        related_name='complaint_ratings'
    )
    service_provider = models.ForeignKey(
        ServiceProvider,
        on_delete=models.CASCADE,
        related_name='ratings'
    )
    rating = models.IntegerField(
        choices=[(i, str(i)) for i in range(1, 6)]
    )
    feedback = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.complaint.code} - {self.rating}⭐"


class ComplaintTimeline(Base):

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
    timeline_status = models.CharField(
        max_length=30,
        choices=constants.COMPLAINT_TIMELINE_STATUS_CHOICES
    )
    note = models.TextField(null=True, blank=True)
    time = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.complaint.code} - {self.timeline_status}"

class ComplaintActivityHistory(Base):

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
    message = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.complaint.code} - {self.message}"
