from django.contrib import admin
from .models import TermsAndConditions

@admin.register(TermsAndConditions)
class TermsAdmin(admin.ModelAdmin):
    list_display = ('key', 'title', 'is_active')
    list_filter = ('key',)