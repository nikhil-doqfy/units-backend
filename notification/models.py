from django.db import models
from django.utils import timezone
from property_management.models import Base
from utilities.constants import NOTIFICATION_TYPE_CHOICES

class Notification(Base):
    # ── Who receives this notification ────────────────────────
    user = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.CASCADE,
        related_name='notifications',
        null=True, blank=True,
        help_text="Null = global notification for all users"
    )

    # ── Content ───────────────────────────────────────────────
    title = models.CharField(max_length=255)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=50,
        choices=NOTIFICATION_TYPE_CHOICES,
        default='GENERAL'
    )

    # ── Status ────────────────────────────────────────────────
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    is_cleared = models.BooleanField(default=False)
    cleared_at = models.DateTimeField(null=True, blank=True)

    # ── Global flag ───────────────────────────────────────────
    is_global = models.BooleanField(
        default=False,
        help_text="If True, visible to all users"
    )

    # ── Optional reference ────────────────────────────────────
    reference_id = models.IntegerField(null=True, blank=True)
    reference_code = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        ordering = ['-created']

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])

    def mark_cleared(self):
        self.is_cleared = True
        self.cleared_at = timezone.now()
        self.save(update_fields=['is_cleared', 'cleared_at'])

    def __str__(self):
        return f"{self.title} → {self.user or 'Global'}"
