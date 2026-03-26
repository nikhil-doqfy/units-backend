from django.contrib import admin

from broadcast.models import Announcement, AnnouncementLog, AnnouncementRecipient


class AnnouncementRecipientInline(admin.TabularInline):
    model       = AnnouncementRecipient
    extra       = 0
    readonly_fields = (
        "tenant", "channel", "status",
        "delivered_at", "failure_reason", 'created', 'modified',
    )
    can_delete  = False

    def has_add_permission(self, request, obj=None):
        return False


class AnnouncementLogInline(admin.StackedInline):
    model           = AnnouncementLog
    extra           = 0
    readonly_fields = ("total_recipients", "delivered_count", "failed_count", 'created', 'modified')
    can_delete      = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = (
        "log_id", "title", "priority", "status",
        "scope", "send_mail",
        "scheduled_at", "sent_at", 'created', 'modified',
    )
    list_filter  = ("status", "priority", "scope", "send_mail")
    search_fields = ("log_id", "title", "description")
    readonly_fields = ("log_id", "sent_at", 'created', 'modified')
    ordering      = ("-id",)
    inlines       = [AnnouncementLogInline, AnnouncementRecipientInline]

    fieldsets = (
        ("Basic Info", {
            "fields": ("log_id", "title", "description", "priority", "status"),
        }),
        ("Targeting", {
            "fields": ("scope", "property", "block", "unit"),
        }),
        ("Delivery", {
            "fields": ("channel", "send_mail", "banner_image", "scheduled_at", "sent_at"),
        }),
        ("Meta", {
            "fields": ("created_by", 'created', 'modified'),
            "classes": ("collapse",),
        }),
    )


@admin.register(AnnouncementRecipient)
class AnnouncementRecipientAdmin(admin.ModelAdmin):
    list_display  = (
        "id", "announcement", "tenant",
        "channel", "status", "delivered_at", 'created', 'modified'
    )
    list_filter   = ("status", "channel")
    search_fields = ("announcement__log_id", "tenant__user__email")
    readonly_fields = ("delivered_at", 'created', 'modified')
    ordering      = ("-id",)


@admin.register(AnnouncementLog)
class AnnouncementLogAdmin(admin.ModelAdmin):
    list_display  = (
        "announcement", "total_recipients",
        "delivered_count", "failed_count", 'created', 'modified'
    )
    readonly_fields = (
        "announcement", "total_recipients",
        "delivered_count", "failed_count", 'created', 'modified'
    )
    ordering = ("-id",)