from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from property_management import settings
from user_service import urls as user_service_urls  
from auth_service import urls as auth_service_urls
from payment import urls as payment_urls
from property_management import views as pm_views
from lease import views as lease_views
from django.urls import re_path
from terms import urls as terms_urls
from charges import urls as charges_urls
from property import urls as property_urls
from lead import urls as lead_urls
from broadcast import urls as broadcast_urls

urlpatterns = [
    path('admin/', admin.site.urls),
    path('user/', include(user_service_urls)),
    path('auth/', include(auth_service_urls)),
    path('payment/', include(payment_urls)),
    path('charges/', include(charges_urls)),
    path('', include(property_urls)),
    path('', include(lead_urls)),
    path('broadcast/', include(broadcast_urls)),

    re_path(r"^media/(?P<path>.*)$", pm_views.serve_media),
    path('options', pm_views.options, name='options'),
    path('invitation', pm_views.send_invitation, name='send_invitation'),
    path('property/details', pm_views.property_table_view, name='property_table_view'),
    path('tenant/table', pm_views.tenant_table_view, name='create_property_basic'), 
    path("property/images", pm_views.property_images, name="property_images"),
    path('property/documents', pm_views.property_documents, name='property_images'), 
    path('parent/property', pm_views.parent_property_view, name=' parent_property_view'),
    path('statistics', pm_views.dashboard_overview, name='dashboard_statistics'),
    path('company/owners', pm_views.company_owners_view, name='company_owners_view'),
    path('owner/pmc', pm_views.owner_pmc_view, name='owner_pmc_view'),
    path('save/lease', pm_views.lease_details_view, name='lease_details_view'),
    path('generate/contract', lease_views.generate_contract, name='generate_contract'), 
    path('audit_log', pm_views.audit_log, name='audit_log'),
    
    path('lease_documents', pm_views.lease_documents, name='lease_documents'), 
    path('get_template_fields', lease_views.get_template_fields, name='get_template_fields'),
    path('lease/tenancy', pm_views.lease_tenancy, name='lease_tenancy'),
    path("complaint", pm_views.complaint, name="complaint_api"),
    path("faq_api", pm_views.faq_api, name="faq_api"),
    path('owner_compnay_csv',pm_views.export_owner_pmc_csv, name='export_owner_pmc_csv'),  #after owner login all pmc
    path('export/property', pm_views.export_property_table_csv, name='export_property_table_csv'), #Property
    path('tenant_csv', pm_views.export_tenant_csv, name=' export_tenant_csv'), #tenant table
    path('lease_tenancy_csv', pm_views.export_lease_tenancy_csv, name='export_lease_tenancy_csv'), #export_lease_tenancy_csv
    path('company_owners_csv', pm_views.export_company_owners_csv, name='export_company_owners_csv'), #after pmc login all owners
    path('interested', pm_views.toggle_property_interest, name='toggle_property_interest'),
    path('tenants_Approved_Rejected', pm_views.company_tenants, name='company_tenants'), 
    path('lease_pdf', pm_views.lease_pdf_view, name='lease_pdf_view'), 
    path('monthly_revenue', pm_views.dashboard_monthly_revenue, name='dashboard_monthly_revenue'), 
    path('cheque_visibility', pm_views.dashboard_cheque_visibility, name='dashboard_monthly_revenue'), 
    path('cheque_aging', pm_views.dashboard_cheque_aging, name='dashboard_cheque_aging'),
    path('other_type_payments', pm_views.dashboard_other_type_payments, name='dashboard_other_type_payments'),
    path('dashboard_graph_due', pm_views.dashboard_yearly_dues, name='dashboard_yearly_due'),
    path('lease_term_and_condition', pm_views.lease_term_and_condition, name='lease_term_and_condition'),
    path('property_owner_compny_lease', pm_views.property_owner_compny_lease, name='property_owner_compny_lease'),
    path('property_lease_payment', pm_views.property_lease_payment, name='lease_payment'),
    path('terms/',  include(terms_urls)),
    path('companies', pm_views.company_list, name='company_list'),

    # path('complaint_list', views.complaint_list, name='complaint_list'),

] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

   

    

 





 
