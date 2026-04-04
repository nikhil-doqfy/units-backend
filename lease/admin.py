from django.contrib import admin
from .models import Lease, Template, TemplateField, TemplateValue, LeaseTransaction


@admin.register(Lease)
class LeaseAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'code', 'lease_status', 'tenant', 'unit',
        'start_date', 'end_date', 'rent', 'is_active', 'created',
    )
    list_filter = ('lease_status', 'is_active', 'shell_and_core')
    search_fields = ('code', 'tenant__user__first_name', 'tenant__user__last_name', 'tenant__email')
    readonly_fields = ('code', 'created', 'modified')
    raw_id_fields = ('tenant', 'unit', 'created_by')
    date_hierarchy = 'created'
    ordering = ('-created',)


@admin.register(LeaseTransaction)
class LeaseTransactionAdmin(admin.ModelAdmin):
    list_display = (
        'code', 'lease', 'cheque_number', 'cheque_type', 'payment_type',
        'amount', 'status', 'cheque_date', 'is_active', 'created',
    )
    list_filter = ('status', 'cheque_type', 'payment_type', 'is_active')
    search_fields = ('code', 'cheque_number', 'lease__code')
    readonly_fields = ('code', 'created', 'modified')
    raw_id_fields = ('lease', 'origin_bank', 'selltlement_bank', 'created_by')
    date_hierarchy = 'cheque_date'
    ordering = ('-cheque_date',)


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "template_path", "is_active"]


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ["id", "template", "name_attribute", "label_attribute", "html_tag"]


@admin.register(TemplateValue)
class TemplateValueAdmin(admin.ModelAdmin):
    list_display = ["id", "template_field", "lease"]
