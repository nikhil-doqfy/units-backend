from django.contrib import admin
from .models import TermAndCondition, TermCategory


@admin.register(TermCategory)
class TermCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")
    ordering = ("id",)


@admin.register(TermAndCondition)
class TermsAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "key",
        "title",
        "category",
        "country",
        "is_active",
    )
    list_filter = (
        "category",
        "country",
        "is_active",
    )
    search_fields = (
        "key",
        "title",
        "description",
    )
    ordering = ("id",)