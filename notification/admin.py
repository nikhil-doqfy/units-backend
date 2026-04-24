from django.contrib import admin
from notification.models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id", "title", "user", "notification_type",
        "is_global", "is_read", "is_cleared", "created"
    )
    search_fields = ("title", "message", "reference_code")
    list_filter = ("notification_type", "is_global", "is_read", "is_cleared")
