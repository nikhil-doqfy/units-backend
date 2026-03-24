from django.db import models
from property_management.models import Base
from property.models import Property, PropertyBlocks, Unit
from utilities import constants

class Announcement(Base):
    log_id = models.CharField(max_length=20, blank=True, db_index=True)
    title       = models.CharField(max_length=255)
    description = models.TextField()
    priority = models.CharField(max_length=20,choices=constants.PRIORITY_CHOICES,default=constants.NORMAL,)
    status = models.CharField(max_length=15,choices=constants.ANNOUNCEMENT_STATUS,default=constants.DRAFT,)
    scope = models.CharField(max_length=10,choices=constants.SCOPE_CHOICES,default=constants.ALL,)
    channel = models.CharField(max_length=50,choices=constants.CHANNEL_CHOICES,default=constants.APP,)
    channels = models.CharField(max_length=255, null=True, blank=True,help_text="Comma-separated channels (APP, SMS, EMAIL, WHATSAPP)")
    property = models.ForeignKey(Property,on_delete=models.CASCADE,related_name="announcements", null=True, blank=True)
    block = models.ForeignKey(PropertyBlocks,on_delete=models.CASCADE,related_name="announcements", null=True, blank=True)
    unit = models.ForeignKey(Unit,on_delete=models.CASCADE,related_name="announcements", null=True, blank=True)
    send_mail = models.BooleanField(default=False) # for EMAIL channel, may also be derived from channels.
    banner_image = models.ImageField(upload_to="announcements/banners/", null=True, blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at      = models.DateTimeField(null=True, blank=True)

    def save(self, *args, **kwargs):
     if not self.pk:
        super().save(*args, **kwargs)

     if not self.log_id:
        prefix = "LP"

        pmc = getattr(getattr(self.created_by, "propertymanager", None), "company", None)

        if pmc and pmc.code:
            prefix = pmc.code[:2].upper()
        self.log_id = f"{prefix}{self.pk:04d}"

        super().save(update_fields=["log_id"])

class AnnouncementRecipient(Base):
    announcement = models.ForeignKey(Announcement,on_delete=models.CASCADE,related_name="recipients",)
    tenant = models.ForeignKey("user_service.UserProfile",on_delete=models.CASCADE,related_name="announcement_receipts",)
    channel = models.CharField(max_length=50,choices=constants.CHANNEL_CHOICES,)
    status = models.CharField(max_length=10, choices=constants.RECIPIENT_STATUS, default=constants.PENDING)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)
    status = models.CharField(max_length=10,choices=constants.RECIPIENT_STATUS,default=constants.PENDING,)
    delivered_at   = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"{self.announcement.log_id} → tenant#{self.tenant_id}"

class AnnouncementLog(Base):
    announcement = models.OneToOneField(Announcement,on_delete=models.CASCADE,related_name="log",)

    total_recipients = models.IntegerField(default=0)
    delivered_count  = models.IntegerField(default=0)
    failed_count     = models.IntegerField(default=0)

    def __str__(self):
        return f"Log: {self.announcement.log_id}"