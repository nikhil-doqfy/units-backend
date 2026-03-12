from django.contrib import admin
from property_service.models import (
    Company, Property, Unit, PropertyImages, PropertyInterest,
    PropertyDocumentsMapping, CompanyUserDocumentsMapping, StaffDocumentsMapping,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["id", "company_name", "company_code"]


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["id", "property_name", "property_type", "no_of_blocks", "no_of_units", "pincode"]
    search_fields = ["property_name"]
    list_filter = ["property_type"]


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ["id", "unit_name", "property", "property_block_tower", "property_type", "floor_no", "no_of_bedrooms", "is_occupied", "company"]
    search_fields = ["unit_name", "plot_no", "makani_no", "dewa_no"]
    list_filter = ["property_type", "is_occupied", "step_status"]


@admin.register(PropertyImages)
class PropertyImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "file_name", "image_type"]


@admin.register(PropertyDocumentsMapping)
class PropertyDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "document"]


@admin.register(CompanyUserDocumentsMapping)
class CompanyUserDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "company_user", "document"]


@admin.register(StaffDocumentsMapping)
class StaffDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "staff", "document"]


@admin.register(PropertyInterest)
class PropertyInterestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "property_unit")
