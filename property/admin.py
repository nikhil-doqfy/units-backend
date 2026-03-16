from django.contrib import admin
from property.models import (
    PropertyManagmentCompany, Property, Unit, PropertyImages, PropertyInterest,
    PropertyBlocks, UnitOwner, PropertyManagerDocuments,
)


@admin.register(PropertyManagmentCompany)
class PropertyManagmentCompanyAdmin(admin.ModelAdmin):
    exclude = ["code", "created_by"]
    list_display = ["id", "code", "name", "licence_number", "licence_issuer"]
    search_fields = ["name", "code", "licence_number"]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["id", "code", "property_name", "property_type", "no_of_blocks", "no_of_units", "pincode", "status", "pmc"]
    search_fields = ["property_name", "code"]
    list_filter = ["property_type", "status"]


@admin.register(PropertyBlocks)
class PropertyBlocksAdmin(admin.ModelAdmin):
    list_display = ["id", "block_name", "property", "no_of_floors", "no_of_units"]
    search_fields = ["block_name"]
    list_filter = ["property"]


@admin.register(PropertyImages)
class PropertyImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "file_name", "image_type"]
    list_filter = ["image_type"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["id", "code", "unit_name", "property_block_tower", "floor_no", "is_occupied", "rent"]
    search_fields = ["unit_name", "code"]
    list_filter = ["is_occupied"]


@admin.register(UnitOwner)
class UnitOwnerAdmin(admin.ModelAdmin):
    list_display = ["id", "unit", "name", "email", "contact_number", "emirates_id"]
    search_fields = ["name", "email"]


@admin.register(PropertyInterest)
class PropertyInterestAdmin(admin.ModelAdmin):
    list_display = ("id", "tenant", "property_unit")


@admin.register(PropertyManagerDocuments)
class PropertyManagerDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "company_user", "file_name"]