from django.contrib import admin
from ticket.models import (
    Category,
    Vendor,
    Ticket,
    TicketImages,
    TicketAuditLog,
    VendorTicketBroadcast,
    WhatsAppMessage,
)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name"]
    

class VendorAdmin(admin.ModelAdmin):
    list_display = ["id", "vendor", "is_available"]


class TicketAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket_code", "priority", "tenant", "status"]


class TicketImagesAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "uploaded_by"]


class TicketAuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action", "ticket", "actor_type"]


class VendorTicketBroadcastAdmin(admin.ModelAdmin):
    list_display = ["id", "ticket", "vendor", "status", "responded_at"]


class WhatsAppMessageAdmin(admin.ModelAdmin):
    list_display = ["id", "status"]


admin.site.register(Category, CategoryAdmin)
admin.site.register(Vendor, VendorAdmin)
admin.site.register(Ticket, TicketAdmin)
admin.site.register(TicketImages, TicketImagesAdmin)
admin.site.register(TicketAuditLog, TicketAuditLogAdmin)
admin.site.register(VendorTicketBroadcast, VendorTicketBroadcastAdmin)
admin.site.register(WhatsAppMessage, WhatsAppMessageAdmin)