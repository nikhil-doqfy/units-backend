from django.contrib import admin
from lead.models import Lead, ScheduleMeeting

# Register your models here.

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "unit", "email", "contact_number", "status", "platform", "lead_type")
    search_fields = ("code", "name", "email", "contact_number")
    list_filter = ("status", "platform", "lead_type")

@admin.register(ScheduleMeeting)
class ScheduleMeetingAdmin(admin.ModelAdmin):
    list_display = ("id", "lead", "title", "start_time", "end_time", "status", "google_calendar_url", "created",)
    list_filter = ("status", "created",)
    search_fields = ("title", "lead__name", "lead__email",)