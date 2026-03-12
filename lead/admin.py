from django.contrib import admin
from lead.models import Lead

# Register your models here.

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("lead_id", "name", "unit", "email", "contact_number", "status", "platform", "lead_type")
    search_fields = ("lead_id", "name", "email", "contact_number")
    list_filter = ("status", "platform", "lead_type")