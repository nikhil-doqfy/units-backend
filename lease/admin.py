from django.contrib import admin
from .models import Lease, Template, TemplateFields, TemplateValues


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


@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "template_path", "is_active"]


@admin.register(TemplateFields)
class TemplateFieldsAdmin(admin.ModelAdmin):
    list_display = ["id", "document_template", "name_attribute", "label_attribute", "html_tag"]


@admin.register(TemplateValues)
class TemplateValuesAdmin(admin.ModelAdmin):
    list_display = ["id", "document_template", "lease"]
