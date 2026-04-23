from django.contrib import admin
from user_service.models import (
    UserProfile, Permission, Role, UserVerification,
    Documents, OwnerDocuments, TenantDocuments,
    Owner, Tenant, PropertyManager,
    FAQ, PrivacyPolicy, Approval, Documentation, DocumentType, AssignedUnit
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

@admin.register(AssignedUnit)
class AssignedUnitAdmin(admin.ModelAdmin):
    list_display = ["staff_name", "unit"]
 
    @admin.display(description="Staff Name")
    def staff_name(self, obj):
        return f"{obj.property_manager.user.first_name} {obj.property_manager.user.last_name}".strip()
from django.contrib import admin
from .models import Documentation

from django.contrib import admin
from .models import Documentation

@admin.register(Documentation)
class DocumentationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "code",
        "agreement_name",
        "agreement_type",
        "status_display",
        "renewal_status",
        "is_expired",
        "expiry_reminder_sent_count",
        "expiry_expired_sent_count",
        "progress_display",
        "expiry_reminder_sent_at",
        "last_email_sent_date"
    )

    list_filter = (
        "status",
        "is_expired",
        "is_renewed",
        "does_not_expire",
    )

    readonly_fields = (
        "code",
        "status",
        "is_expired",
        "expiry_reminder_sent_count",
        "expiry_expired_sent_count",
    )

    search_fields = (
        "agreement_name",
        "code",
    )

    # =========================
    # DISPLAY METHODS
    # =========================

    def status_display(self, obj):
        return obj.get_status()
    status_display.short_description = "Status"

    def renewal_status(self, obj):
        return "YES" if obj.is_renewed else "NO"
    renewal_status.short_description = "Renewed"

    def progress_display(self, obj):
        return obj.get_expiry_progress()
    progress_display.short_description = "Progress (7-cycle)"







@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'section')
    list_filter = ('section',)
    search_fields = ('name',)
    ordering = ('-id',)
