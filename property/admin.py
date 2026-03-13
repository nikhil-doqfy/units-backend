from django.contrib import admin
from property.models import (
    PropertyManagmentCompany, Property, Unit, PropertyImages, PropertyInterest,
)


@admin.register(PropertyManagmentCompany)
class PropertyManagmentCompanyAdmin(admin.ModelAdmin):
    exclude = ["code", "created_by"]
    list_display = ["id", "name"]

    def save_model(self, request, obj, form, change):
        if not obj.pk: # Only set 'created_by' when the object is first created
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["id", "property_name", "property_type", "no_of_blocks", "no_of_units", "pincode"]
    search_fields = ["property_name"]
    list_filter = ["property_type"]



@admin.register(PropertyInterest)
class PropertyInterestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "property_unit")
