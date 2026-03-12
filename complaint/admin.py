from django.contrib import admin
from complaint.models import Complaint

# Register your models here.

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "user")