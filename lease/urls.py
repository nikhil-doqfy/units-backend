from django.urls import path
from . import views

urlpatterns = [
    path("api/lease", views.lease_view, name="lease_view"),
    path("api/tenant-leases", views.tenant_leases_view, name="tenant_leases_view"),
    path("api/lease/onboarding-documents", views.lease_onboarding_documents_view, name="lease_onboarding_documents"),
    path("api/lease/templates", views.get_templates, name="lease_get_templates"),
    path("api/lease/template-fields", views.get_template_fields, name="lease_get_template_fields"),
    path("api/lease/generate-contract", views.generate_contract, name="lease_generate_contract"),
]
