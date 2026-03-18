<<<<<<< terms-api
from django.contrib import admin
from user_service.models import (
    UserProfile, Company, Permission, Role, 
    Property, UnitDetails,  PropertyUnitImages,
    PropertyImages, UserVerification,
    Documents, PropertyDocumentsMapping, OwnerDocumentsMapping,
    TenantDocumentsMapping, CompanyUserDocumentsMapping, StaffDocumentsMapping,Country, State, City, CompanyStaff ,FAQ ,PrivacyPolicy ,Complaint ,
    PropertyInterest, Lead, UnitDetails
    UserProfile, Permission, Role,
    UserVerification, Documents, OwnerDocuments,
    TenantDocuments,
        FAQ, PrivacyPolicy
)
from property_management.models import (
    LeasePropertyDetails, UserInvitation, Template, TemplateFields,
    TemplateValues, LeaseDocumentsMapping, TermAndCondition
)


# -------------------- User Service Admin --------------------
class CompanyStaffAdmin(admin.ModelAdmin):
    list_display = ["id", "staff", "company", "is_active"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "contact_number"]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "module_name"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "company"]

# @admin.register(PMStaffCompanyMapping)
# class PMStaffCompanyMappingAdmin(admin.ModelAdmin):
#     list_display = ["id", "user_profile", "company"]

@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = ["id", "property_name", "property_code"]


@admin.register(PropertyImages)
class PropertyImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property", "file_name", "image_type"]

@admin.register(PropertyUnitImages)
class PropertyUnitImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "property_unit", "file_name", "image_type"]

@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = ["id", "verification_type", "otp", "is_verified"]


@admin.register(Documents)
class DocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "file_name"]


@admin.register(OwnerDocuments)
class OwnerDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "owner"]


@admin.register(TenantDocuments)
class TenantDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant"]



@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "title")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("id", "question")



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


@admin.register(TermAndCondition)
class TermAndConditionAdmin(admin.ModelAdmin):
    list_display = ("id", "description", "term_type", "lease", "is_predefined")
=======
from django.contrib import admin
from user_service.models import (
    UserProfile, Permission, Role,
    UserVerification, Documents, OwnerDocuments,
    TenantDocuments, FAQ, PrivacyPolicy, Owner, Tenant, PropertyManager
)
from property_management.models import UserInvitation, TermAndCondition
from lease.models import Template, TemplateFields, TemplateValues


# -------------------- User Service Admin --------------------
class CompanyStaffAdmin(admin.ModelAdmin):
    list_display = ["id", "staff", "company", "is_active"]


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "contact_number"]


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ["id", "module_name"]


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "company"]


@admin.register(UserVerification)
class UserVerificationAdmin(admin.ModelAdmin):
    list_display = ["id", "verification_type", "otp", "is_verified"]


@admin.register(Documents)
class DocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "file_name"]


@admin.register(OwnerDocuments)
class OwnerDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "owner"]


@admin.register(TenantDocuments)
class TenantDocumentsAdmin(admin.ModelAdmin):
    list_display = ["id", "tenant"]



@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "title")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("id", "question")


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "email", "contact_number",
                    "owner_number", "trade_license_number", "license_number",
                    "license_expiry_date", "license_issuer", "fax_number", "po_box_number"]
    search_fields = ["user__first_name", "user__last_name", "email", "code", "owner_number"]
    list_filter = ["license_issuer"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "email", "contact_number", "emirate_id"]
    search_fields = ["user__first_name", "user__last_name", "email", "code"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


@admin.register(PropertyManager)
class PropertyManagerAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "email", "contact_number", "company"]
    search_fields = ["user__first_name", "user__last_name", "email", "code"]
    list_filter = ["company"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


@admin.register(UserInvitation)
class UserInvitationAdmin(admin.ModelAdmin):
    list_display = ["id", "email", "invited_by", "invitation_type", "status"]


@admin.register(TermAndCondition)
class TermAndConditionAdmin(admin.ModelAdmin):
    list_display = ("id", "description", "term_type", "lease", "is_predefined")

>>>>>>> develop
