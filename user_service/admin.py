from django.contrib import admin
from user_service.models import (
    UserProfile, Permission, Role,
    UserVerification, Documents, OwnerDocuments,
    TenantDocuments, FAQ, PrivacyPolicy, Owner, Tenant, PropertyManager, Approval
)
from property_management.models import UserInvitation, TermAndCondition
from lease.models import Template, TemplateField, TemplateValue


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

@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("tenant","unit","requested_rent","requested_tenure","approved","approved_by",)
    list_filter = ("approved","approved_at",)
    search_fields = ("tenant__id","unit__unit_name",)