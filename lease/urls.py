from django.urls import path
from . import views

urlpatterns = [
    path("api/lease", views.lease_view, name="lease_view"),
    path("api/tenant-leases", views.tenant_leases_view, name="tenant_leases_view"),
    path("api/lease/onboarding-documents", views.lease_onboarding_documents_view, name="lease_onboarding_documents"),
    path("api/lease/templates", views.get_templates, name="lease_get_templates"),
    path("api/lease/template-fields", views.get_template_fields, name="lease_get_template_fields"),
    path("api/lease/generate-contract", views.generate_contract, name="lease_generate_contract"),
    path("api/lease/send-negotiation", views.send_negotiation, name="lease_send_negotiation"),
    path("api/lease/send-invite", views.send_lease_invite, name="lease_send_invite"),
    path("api/lease/approval-otp",        views.lease_approval_otp,         name="lease_approval_otp"),
    path("api/lease/approval-otp-verify", views.lease_approval_verify_otp,  name="lease_approval_verify_otp"),
    path("api/lease/approve",             views.approve_lease_view,          name="approve_lease_view"),
    path("api/lease/cheques",             views.lease_cheque_view,            name="lease_cheque_view"),
    path("api/lease/cheque-status",       views.lease_cheque_status,          name="lease_cheque_status"),
    path("api/lease/send-for-signature",  views.send_for_signature,           name="send_for_signature"),
    path("api/lease/signature-otp",       views.lease_signature_otp,          name="lease_signature_otp"),
    path("api/lease/signature-otp-verify",views.lease_signature_verify_otp,   name="lease_signature_verify_otp"),
    path("api/lease/submit-signature",    views.submit_lease_signature,       name="submit_lease_signature"),
]
