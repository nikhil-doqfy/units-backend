from django.contrib import admin
from complaint.models import (
    ServiceProvider, Complaint, ComplaintBroadcast,
    ComplaintImages, ComplaintTimeline, ComplaintActivityHistory
)


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "service_type", "company", "is_available")
    search_fields = ("name", "phone")
    list_filter = ("service_type", "is_available")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "unit", "raised_by", "assigned_to", "service_type", "priority", "status", "is_broadcasted", "work_started_at", "work_completed_at", "issue_closed_on", "created")
    search_fields = ("code", "description")
    list_filter = ("status", "service_type", "priority", "is_broadcasted")


@admin.register(ComplaintBroadcast)
class ComplaintBroadcastAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "service_provider", "is_accepted", "accepted_at", "is_rejected")
    list_filter = ("is_accepted", "is_rejected")


@admin.register(ComplaintImages)
class ComplaintImagesAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "file_name")


@admin.register(ComplaintTimeline)
class ComplaintTimelineAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "user", "timeline_status", "time")
    list_filter = ("timeline_status",)


@admin.register(ComplaintActivityHistory)
class ComplaintActivityHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "user", "message", "created")