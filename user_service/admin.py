from django.contrib import admin
from user_service.models import (
    UserProfile, Permission, Role, UserVerification,
    Documents, OwnerDocuments, TenantDocuments,
    Owner, Tenant, PropertyManager,
    FAQ, PrivacyPolicy, Approval
)


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


@admin.register(Owner)
class OwnerAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "get_email", "contact_number",
                    "trade_license_number", "licence_number","licence_expiry_date", "licence_issuer"]
    search_fields = ["user__first_name","user__last_name","user__email","code"]
    list_filter = ["licence_issuer"] 

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email

@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "get_email", "contact_number"]
    search_fields = ["user__first_name","user__last_name","user__email","code"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()

    @admin.display(description="Email")
    def get_email(self, obj):
        return obj.user.email

@admin.register(PropertyManager)
class PropertyManagerAdmin(admin.ModelAdmin):
    list_display = ["id", "get_full_name", "code", "get_email", "contact_number", "company"]
    search_fields = ["user__first_name","user__last_name","user__email","code"]
    list_filter = ["company"]

    @admin.display(description="Full Name")
    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()



@admin.register(PrivacyPolicy)
class PrivacyPolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "title")


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ("id", "question")
   
@admin.register(Approval)
class ApprovalAdmin(admin.ModelAdmin):
    list_display = ("tenant","unit","requested_rent","requested_tenure","approved","approved_by",)
    list_filter = ("approved","approved_at",)
    search_fields = ("tenant__id","unit__unit_name",)
