from django.urls import path
from ticket import ticket_admin_views as ticket_views
from ticket import admin_views as ticket_admin_views

urlpatterns = [
    path("tickets/categories/", ticket_views.fetch_ticket_categories),
    path("tenant/ticket/create/", ticket_views.tenant_create_ticket),
    path("vendor/eligible-vendors/", ticket_views.fetch_eligible_vendors),
    path("vendor/broadcast/", ticket_views.broadcast_ticket_to_vendors),
    path("vendor/accept/", ticket_views.vendor_accept_ticket),
    path("vendor/reject/", ticket_views.vendor_reject_ticket),
    path("vendor/submit-work-proof/", ticket_views.vendor_submit_work_proof),
    path("tenant/ticket/approve/", ticket_views.tenant_approve_ticket),
    path("enant/ticket/reject/", ticket_views.tenant_reject_ticket),
    path("ticket/status-lookup/", ticket_views.ticket_status_lookup),
    
    
    # ------------------ Admin APIs ------------------
    path("admin/tickets/", ticket_admin_views.admin_ticket_list, name="admin_ticket_list"),
    path("admin/ticket/detail/", ticket_admin_views.admin_ticket_detail, name="admin_ticket_detail"),
    path("admin/ticket/force-assign-vendor/", ticket_admin_views.admin_force_assign_vendor, name="admin_force_assign_vendor"),
    path("admin/ticket/force-close/", ticket_admin_views.admin_force_ticket_close, name="admin_force_ticket_close"),
    path("admin/vendors/", ticket_admin_views.admin_vendor_list, name="admin_vendor_list"),
    path("admin/vendor/detail/", ticket_admin_views.admin_vendor_detail, name="admin_vendor_detail"),
    path("admin/vendor/toggle-availability/", ticket_admin_views.admin_toggle_vendor_availability, name="admin_toggle_vendor_availability"),
    path("admin/sla-overview/", ticket_admin_views.admin_sla_overview, name="admin_sla_overview"),
    path("admin/messages/", ticket_admin_views.admin_message_log, name="admin_message_log"),
    path("admin/message/resend/", ticket_admin_views.admin_resend_message, name="admin_resend_message"),

] 