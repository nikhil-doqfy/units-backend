from django.contrib import admin
from .models import TermsAndConditions


@admin.register(TermsAndConditions)
class TermsAndConditionsAdmin(admin.ModelAdmin):
    list_display = ('title', 'effective_date', 'is_active')
    search_fields = ('title',)