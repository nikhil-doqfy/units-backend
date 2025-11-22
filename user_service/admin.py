from django.contrib import admin
from user_service.models import (
    UserProfile, 
    PropertyManagerCompanyDetails, 
    StaffRole, 
    StaffDetails, 
    PropertyDetails,UserVerification,PropertyDocuments ,PropertyCommercial
)

from property_management.models import OwnerDetails ,TenantDetails,LeasePropertyDetails,LeaseCommercials ,LeaseEjariUpload , OwnerPMCInvitation ,PMCOwnerInvitation , Template , TemplateFields
 
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "user_type"]

class UserVerificationAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "otp"]


class PropertyManagerCompanyDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "company_name", "company_code", "phone_number"]

class StaffRoleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "property_manager"]

class StaffDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "staff_name", "staff_id", "phone_number", "staff_role", "property_manager"]

class PropertyDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "property_name", "owner", "property_manager", "is_occupied", "rental_status"]







admin.site.register(UserProfile, UserProfileAdmin)
admin.site.register(PropertyManagerCompanyDetails, PropertyManagerCompanyDetailsAdmin)
admin.site.register(StaffRole, StaffRoleAdmin)
admin.site.register(StaffDetails, StaffDetailsAdmin)
admin.site.register(PropertyDetails, PropertyDetailsAdmin)
admin.site.register(UserVerification, UserVerificationAdmin)

class OwnerDetailsAdmin(admin.ModelAdmin):
    list_display = [
        "id", "full_name", "emirate_id", "uae_residence_visa", "trade_license_number",
        "owner_number", "mobile_number", "manage_manually", "manage_through_pmc",
        "emirates_id_file","residence_visa_file","dld_certificate_file","dewa_registration_file"
    ]
    search_fields = ["full_name", "emirate_id", "uae_residence_visa", "owner_number", "mobile_number"]
    list_filter = ["manage_manually", "manage_through_pmc"]


class PropertyDocumentsAdmin(admin.ModelAdmin):
    list_display = ["document_id", "document_title", "created", "modified", "property_documents"]
    search_fields = ["document_title"]
    list_filter = ["created", "modified"]


class TenantDetailsAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'full_name', 'mobile_number'
    )

class DocumentTemplateFieldsAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "document_template",
        "tenant",
        "owner",
        "amount",
    ]
    search_fields = ["document_template__name", "tenant__name", "owner__name"]
    list_filter = ["document_template"]


class LeasePropertyDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "lease_property", "lease_tenant","lease_status","lease_start_date","lease_end_date"]


class LeaseCommercialsAdmin(admin.ModelAdmin):
    list_display = ["id", "lease", "annual_amount","booking_amount"]

class LeaseEjariUploadAdmin(admin.ModelAdmin):
    list_display = ["id", "lease", "tenant_doc","ejari_certificates","pmc_docs","cheque"] 


class OwnerPMCInvitationAdmin(admin.ModelAdmin):
    list_display = ["id", "email","invited_by" ,"status","token",] 

class PMCOwnerInvitationAdmin(admin.ModelAdmin):
    list_display = ["id", "email","invited_by" ,"status","token",] 

class PropertyDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id"] 
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "template_path", "is_active"]   

class TemplateFieldsAdmin(admin.ModelAdmin):
    list_display = ["id", "document_template","name_attribute"]    


class PropertyCommercialAdmin(admin.ModelAdmin):
    list_display = ["id"]


admin.site.register(OwnerDetails, OwnerDetailsAdmin)  
# admin.site.register(PropertyDocuments, PropertyDocumentsAdmin)
admin.site.register(TenantDetails, TenantDetailsAdmin)  

admin.site.register(LeasePropertyDetails, LeasePropertyDetailsAdmin)  
admin.site.register(LeaseCommercials, LeaseCommercialsAdmin) 
admin.site.register(LeaseEjariUpload, LeaseEjariUploadAdmin)  

admin.site.register( OwnerPMCInvitation, OwnerPMCInvitationAdmin)  

admin.site.register( PMCOwnerInvitation, PMCOwnerInvitationAdmin)  

admin.site.register( PropertyDocuments, PropertyDocumentsAdmin) 
admin.site.register(Template, TemplateAdmin)
admin.site.register(TemplateFields, TemplateFieldsAdmin)

admin.site.register(PropertyCommercial, PropertyCommercialAdmin)




