from django.urls import path
from ticket import views as ticket_views

urlpatterns = [
    path("fetch_ticket_categories/", ticket_views.fetch_ticket_categories),
    path("tenant_create_ticket/", ticket_views.tenant_create_ticket),
    path("fetch_eligible_vendors/", ticket_views.fetch_eligible_vendors),
    path("broadcast_ticket_to_vendors/", ticket_views.broadcast_ticket_to_vendors),
    path("vendor_accept_ticket/", ticket_views.vendor_accept_ticket),
    path("vendor_reject_ticket/", ticket_views.vendor_reject_ticket),
    path("vendor_submit_work_proof/", ticket_views.vendor_submit_work_proof),
    path("tenant_approve_ticket/", ticket_views.tenant_approve_ticket),
    path("tenant_reject_ticket/", ticket_views.tenant_reject_ticket),
    path("ticket_status_lookup/", ticket_views.ticket_status_lookup),

] 