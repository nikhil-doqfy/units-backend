from django.urls import path
from rest_framework.routers import SimpleRouter
from . import views

# SimpleRouter (not DefaultRouter) -- this urls.py is included at the
# project root (property_management/urls.py: path('', include(lease_urls))),
# and DefaultRouter's auto-generated API-root view would otherwise bind to
# '/' itself. trailing_slash=False matches this app's convention
# (APPEND_SLASH = False in settings.py, no other endpoint here uses one).
router = SimpleRouter(trailing_slash=False)
router.register(r"api/lease", views.LeaseViewSet, basename="lease")

urlpatterns = [
    path("api/lease/onboarding-documents", views.lease_onboarding_documents_view, name="lease_onboarding_documents"),
    path("api/lease/cheques",             views.lease_cheque_view,            name="lease_cheque_view"),
    path("api/lease/cheque-status",       views.lease_cheque_status,          name="lease_cheque_status"),
    path("api/lease/cheque-summary",      views.cheque_summary_view,          name="cheque_summary_view"),
    path("api/lease/cheque-receipt-pdf",  views.cheque_receipt_pdf_view,      name="cheque_receipt_pdf_view"),
    path("api/lease/rent-receipt-months", views.rent_receipt_months_view,     name="rent_receipt_months_view"),
    path("api/lease/activity-history",    views.lease_activity_history_view,  name="lease_activity_history_view"),
    path("api/lease/cheque-file-proxy",   views.cheque_file_proxy_view,       name="cheque_file_proxy_view"),
    path("api/lease/all-cheques",         views.all_cheques_view,             name="all_cheques_view"),
    path("api/lease/cheque-tenant-options", views.cheque_tenant_options_view, name="cheque_tenant_options_view"),
    path("api/lease/cheque-monthly",      views.cheque_monthly_view,          name="cheque_monthly_view"),
    path("api/lease/rent-analytics",      views.rent_analytics_view,          name="rent_analytics_view"),
    path("api/lease/property-analytics",  views.property_analytics_view,      name="property_analytics_view"),
    path("api/lease/property-comparison", views.property_comparison_view,     name="property_comparison_view"),
    path("api/lease/manager-approval",           views.manager_approval_view,          name="manager_approval_view"),
    path("api/lease/verify-cheque",              views.verify_cheque_view,             name="verify_cheque"),
    path("api/lease/generate-cheque-schedule",   views.generate_cheque_schedule_view,  name="generate_cheque_schedule"),
    path("api/lease/approve-ejari",              views.approve_ejari_submission,       name="approve_ejari_submission"),
    path("api/lease/confirm-handover",           views.confirm_handover,               name="confirm_handover"),
    path("api/lease/ejari-send-signature",       views.send_ejari_for_signature,       name="ejari_send_signature"),
    path("api/lease/ejari-signature-otp",        views.ejari_signature_otp,            name="ejari_signature_otp"),
    path("api/lease/ejari-signature-otp-verify", views.ejari_signature_verify_otp,     name="ejari_signature_verify_otp"),
    path("api/lease/ejari-submit-signature",     views.submit_ejari_signature,         name="ejari_submit_signature"),
    path("api/lease/ejari-signing-document",     views.ejari_signing_document,         name="ejari_signing_document"),
    path("api/lease/esign/start",                views.esign_start_view,                name="esign_start"),
    path("api/lease/esign/callback",             views.esign_callback_view,             name="esign_callback"),
    path("api/lease/activate",                   views.activate_lease_view,            name="activate_lease"),

    # Moved from property_management
    path('lease_documents', views.lease_documents, name='lease_documents'),
] + router.urls
