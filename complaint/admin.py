from django.contrib import admin
from complaint.models import (
    ServiceType,
    ServiceLocality,
    ServiceProvider,
    Complaint,
    ComplaintImages,
    ComplaintBroadcast,
    Appointment,
    AppointmentSlot,
    ComplaintRating,
    ComplaintTimeline,
    ComplaintActivityHistory,
)


@admin.register(ServiceType)
class ServiceTypeAdmin(admin.ModelAdmin):
    list_display = ("id", "name")


@admin.register(ServiceLocality)
class ServiceLocalityAdmin(admin.ModelAdmin):
    list_display = ("id", "locality")
    search_fields = ("locality",)


@admin.register(ServiceProvider)
class ServiceProviderAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "phone", "email", "avg_rating", "is_available")
    search_fields = ("name", "phone", "email")
    list_filter = ("is_available", "avg_rating", "service_types")
    filter_horizontal = ("service_types", "localities")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "code", "unit", "raised_by", "service_type", "priority", "status", "locality", "is_broadcasted", "attempt_count", "work_started_at", "work_completed_at", "issue_closed_on", "created")
    search_fields = ("code", "description", "locality")
    list_filter = ("status", "service_type", "priority", "is_broadcasted")
    filter_horizontal = ("assigned_to",)


@admin.register(ComplaintImages)
class ComplaintImagesAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "file_name")
    search_fields = ("file_name",)


@admin.register(ComplaintBroadcast)
class ComplaintBroadcastAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "service_provider", "is_priority", "priority_score", "is_accepted", "accepted_at", "is_rejected", "rejected_at", "expires_at", "is_expired")
    list_filter = ("is_accepted", "is_rejected", "is_expired", "is_priority")
    search_fields = ("complaint__code", "service_provider__name")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "service_provider", "status", "is_active", "created")
    list_filter = ("status", "is_active")
    search_fields = ("complaint__code",)


@admin.register(AppointmentSlot)
class AppointmentSlotAdmin(admin.ModelAdmin):
    list_display = ("id", "appointment", "proposed_time", "is_selected", "selected_at")
    list_filter = ("is_selected",)


@admin.register(ComplaintRating)
class ComplaintRatingAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "rated_by", "service_provider", "rating", "created")
    list_filter = ("rating",)
    search_fields = ("complaint__code",)


@admin.register(ComplaintTimeline)
class ComplaintTimelineAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "user", "timeline_status", "time")
    list_filter = ("timeline_status",)
    search_fields = ("complaint__code",)


@admin.register(ComplaintActivityHistory)
class ComplaintActivityHistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "complaint", "user", "message", "created")
    search_fields = ("complaint__code", "message")