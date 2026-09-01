from django.contrib import admin

# Register your models here.
from .models import BroadcastAnnouncement

@admin.register(BroadcastAnnouncement)
class BroadcastAnnouncementAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "property", "block_tower", "unit", "priority", "recipient_count", "delivered_count", "failed_count", "created", "is_active",)
    list_filter = ("priority", "is_active",)
    search_fields = ("title", "description",)