from django.contrib import admin
from .models import TermCategory, TermsAndConditions


@admin.register(TermCategory)
class TermCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")
    ordering = ("id",)



@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "title", "country", "category", "is_active")
    list_filter = ("country", "category", "is_active")
    search_fields = ("key", "title", "description")
    ordering = ("country", "category", "key")
    list_editable = ("is_active",)