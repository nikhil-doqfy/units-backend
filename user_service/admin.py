from django.contrib import admin
from user_service.models import (
    UserProfile, Company, Permission, Role, 
    Property, PropertyUnitDetails,  PropertyUnitImages,
    PropertyImages, UserVerification,
    Documents, PropertyDocumentsMapping, OwnerDocumentsMapping,
    TenantDocumentsMapping, CompanyUserDocumentsMapping, StaffDocumentsMapping,Country, State, City, CompanyStaff ,FAQ ,PrivacyPolicy ,Complaint ,PropertyInterest
)
from property_management.models import (
    LeasePropertyDetails, UserInvitation, Template, TemplateFields,
    TemplateValues,LeaseDocumentsMapping , TermAndCondition
)

# -------------------- User Service Admin --------------------
class CompanyStaffAdmin(admin.ModelAdmin):
    list_display = ["id", "staff", "company",  "is_active"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "user_role", "contact_number"]

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["id", "company_name", "company_code"]

@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "codename", "name"]

@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "company"]

# @admin.register(PMStaffCompanyMapping)
# class PMStaffCompanyMappingAdmin(admin.ModelAdmin):
#     list_display = ["id", "user_profile", "company"]

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["id", "property_name", "property_code"]

@admin.register(PropertyUnitDetails)
class PropertyUnitDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "property_unit_name", "property", "owner", "is_occupied", "rent","company"]

@admin.register(PropertyImages)
class PropertyImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "file_name", "image_type"]

@admin.register(PropertyUnitImages)
class PropertyUnitImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property_unit", "file_name", "image_type"]

@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "verification_type", "otp", "is_verified"]

@admin.register(Documents)
class DocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "file_name"]

@admin.register(PropertyDocumentsMapping)
class PropertyDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "document"]

@admin.register(OwnerDocumentsMapping)
class OwnerDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "owner", "document"]

@admin.register(TenantDocumentsMapping)
class TenantDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant", "document"]

@admin.register(CompanyUserDocumentsMapping)
class CompanyUserDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "company_user", "document"]

@admin.register(StaffDocumentsMapping)
class StaffDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ["id", "staff", "document"]

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ("id", "user")


@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "title")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("id", "question")

@admin.register(PropertyInterest)
class PropertyInterestAdmin(admin.ModelAdmin):
    list_display = ("tenant", "property_unit") 

# -------------------- Property Management Admin --------------------
@admin.register(LeasePropertyDetails)
class LeasePropertyDetailsAdmin(admin.ModelAdmin):
    list_display = ["id", "lease_property", "tenant", "owner", "lease_status", "lease_start_date", "lease_end_date"]

@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "invited_by", "invitation_type", "status"]

@admin.register(Template)
class TemplateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "template_path", "is_active"]

@admin.register(TemplateFields)
class TemplateFieldsAdmin(admin.ModelAdmin):
    list_display = ["id", "document_template", "name_attribute", "label_attribute", "html_tag"]

@admin.register(TemplateValues)
class TemplateValuesAdmin(admin.ModelAdmin):
    list_display = ["id", "document_template", "lease"]


@admin.register(LeaseDocumentsMapping)
class LeaseDocumentsMappingAdmin(admin.ModelAdmin):
    list_display = ("id", "lease", "document", "document_choice")



@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "code"]
    search_fields = ["name", "code"] 

@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "country", "code"]
    list_filter = ["country"]          
    search_fields = ["name", "code"]   #

@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "state", "code"]
    list_filter = ["state"]          
    search_fields = ["name", "code"]  

@admin.register(TermAndCondition)
class TermAndConditionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "description",
        "term_type",
        "lease",
        "is_predefined",
    )

admin.site.register(CompanyStaff, CompanyStaffAdmin)



