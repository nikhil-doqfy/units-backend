from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from property_management import settings
from user_service import urls as user_service_urls  
from auth_service import urls as auth_service_urls
from payment import urls as payment_urls
from . import views
from django.urls import re_path
from charges import urls as charges_urls
from property import urls as property_urls
from lead import urls as lead_urls
from lease import urls as lease_urls


urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include(user_service_urls)),
    path('auth/', include(auth_service_urls)),
    path('payment/', include(payment_urls)),
    path('charges/', include(charges_urls)),
    path('', include(property_urls)),
    path('', include(lead_urls)),
    path('', include(lease_urls)),

    re_path(r"^media/(?P<path>.*)$", views.serve_media),
    path('options', views.options, name='options'),
    path('invitation', views.send_invitation, name='send_invitation'),
    path('property/details', views.property_table_view, name='property_table_view'),
    path('tenant/table', views.tenant_table_view, name='create_property_basic'), 
    path('parent/property', views.parent_property_view, name=' parent_property_view'),
    path('statistics', views.dashboard_overview, name='dashboard_statistics'),
    path('company/owners', views.company_owners_view, name='company_owners_view'),
    path('owner/pmc', views.owner_pmc_view, name='owner_pmc_view'),
    path('save/lease', views.lease_details_view, name='lease_details_view'),
    path('audit_log', views.audit_log, name='audit_log'),
    path('lease_documents', views.lease_documents, name='lease_documents'),
    path('lease/tenancy', views.lease_tenancy, name='lease_tenancy'),
    path("faq_api", views.faq_api, name="faq_api"),
    path('owner_compnay_csv', views.export_owner_pmc_csv, name='export_owner_pmc_csv'),  #after owner login all pmc
    path('export/property', views.export_property_table_csv, name='export_property_table_csv'), #Property
    path('tenant_csv', views.export_tenant_csv, name=' export_tenant_csv'), #tenant table
    path('lease_tenancy_csv', views.export_lease_tenancy_csv, name='export_lease_tenancy_csv'), #export_lease_tenancy_csv
    path('company_owners_csv', views.export_company_owners_csv, name='export_company_owners_csv'), #after pmc login all owners
    path('interested', views.toggle_property_interest, name='toggle_property_interest'),
    path('tenants_Approved_Rejected', views.company_tenants, name='company_tenants'), 
    path('lease_pdf', views.lease_pdf_view, name='lease_pdf_view'), 
    path('monthly_revenue', views.dashboard_monthly_revenue, name='dashboard_monthly_revenue'), 
    path('cheque_visibility', views.dashboard_cheque_visibility, name='dashboard_monthly_revenue'), 
    path('cheque_aging', views.dashboard_cheque_aging, name='dashboard_cheque_aging'),
    path('other_type_payments', views.dashboard_other_type_payments, name='dashboard_other_type_payments'),
    path('dashboard_graph_due', views.dashboard_yearly_dues, name='dashboard_yearly_due'),
    path('lease_term_and_condition', views.lease_term_and_condition, name='lease_term_and_condition'),
    path('property_owner_compny_lease', views.property_owner_compny_lease, name='property_owner_compny_lease'),
    path('property_lease_payment', views.property_lease_payment, name='lease_payment'),
    path('companies', views.company_list, name='company_list'),

    # path('complaint_list', views.complaint_list, name='complaint_list'),

    
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
