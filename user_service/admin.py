from django.contrib import admin
from user_service.models import (
    UserProfile, Permission, Role,
    UserVerification, Documents, OwnerDocuments,
    TenantDocuments, \
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
