from django.contrib import admin
from .models import TermCategory, TermsAndConditions


class TermCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")
    ordering = ("id",)


class TermsAndConditionsAdmin(admin.ModelAdmin):
    list_display = ("id", "key", "title", "country", "category", "is_active")
    list_filter = ("country", "category", "is_active", "key")
    search_fields = ("title", "description", "key")
    ordering = ("country", "category", "key")
    list_editable = ("is_active",)


admin.site.register(TermCategory, TermCategoryAdmin)
admin.site.register(TermsAndConditions, TermsAndConditionsAdmin)