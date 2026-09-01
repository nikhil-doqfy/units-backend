from django.db import models

# Create your models here.
from property.models import Property, PropertyBlocks, Unit
from user_service.models import UserProfile
from property_management.models import Base
#from utilities.constants import BROADCAST_PRIORITY_CHOICES, BROADCAST_CHANNEL_CHOICES
from utilities import constants

class BroadcastAnnouncement(Base):
    title = models.CharField(max_length=255)
    description = models.TextField()
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="broadcast_announcements"
    )

    block_tower = models.ForeignKey(
        PropertyBlocks,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="broadcast_announcements"
    )

    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="broadcast_announcements"
    )

    priority = models.CharField(
        max_length=20,
        choices=constants.BROADCAST_PRIORITY_CHOICES,
        default="NORMAL"
    )

    status = models.CharField(
    max_length=20,
    choices=constants.BROADCAST_STATUS_CHOICES,
    default="DRAFT"
    )

    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_date = models.DateTimeField(null=True, blank=True)
    recipient_count = models.IntegerField(default=0)
    delivered_count = models.IntegerField(default=0)
    failed_count = models.IntegerField(default=0)
    channels = models.JSONField(default=list, blank=True)
    banner_image = models.URLField(max_length=2000, null=True, blank=True)

    def __str__(self):
        return self.title

class BroadcastRecipient(Base):
    broadcast = models.ForeignKey(
        BroadcastAnnouncement,
        on_delete=models.CASCADE,
        related_name="broadcast_recipients"
    )
    email = models.EmailField()
    channel = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=constants.BROADCAST_RECIPIENT_STATUS_CHOICES,
        default="PENDING"
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.broadcast.title} - {self.email}"