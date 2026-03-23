from django.contrib import admin
from complaint.models import Complaint, ComplaintImages


class ComplaintImagesInline(admin.TabularInline):
    model = ComplaintImages
    extra = 0


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ["complaint_id", "unit", "raised_by", "company", "status", "created"]
    search_fields = ["complaint_id", "description"]
    list_filter = ["status", "company"]
    inlines = [ComplaintImagesInline]


@admin.register(ComplaintImages)
class ComplaintImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "complaint", "file_name"]