from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from property_management import settings
from user_service import urls as user_service_urls  
from auth_service import urls as auth_service_urls
from payment import urls as payment_urls
from . import views
from django.urls import re_path


urlpatterns = [ 
    path('admin/', admin.site.urls),
    path('user/', include(user_service_urls)),
    path('auth/', include(auth_service_urls)), 
    path('payment/', include(payment_urls)), 

    
    re_path(r"^media/(?P<path>.*)$", views.serve_media), 
    path('options', views.options, name='options'),   
    path('invitation', views.send_invitation, name='send_invitation'),
    path('property/details', views.property_table_view, name='property_table_view'),
    path('save/property', views.save_property, name='save_property'),
    path('tenant/table', views.tenant_table_view, name='create_property_basic'), 
    path('property/images', views.property_images, name='property_images'),
    path('property/documents', views.property_documents, name='property_images'), 
    path('parent/property', views.parent_property_view, name=' parent_property_view'),
    path('statistics', views.dashboard_overview, name='dashboard_statistics'),
    path('company/owners', views.company_owners_view, name='company_owners_view'),
    path('owner/pmc', views.owner_pmc_view, name='owner_pmc_view'),
    
    # path('most/revenue', views.most_revenue_generating_properties, name='most_revenue_generating_properties'),
    path('save/lease', views.lease_details_view, name='lease_details_view'),
    path('generate/contract', views.generate_contract, name='generate_contract'),
    path('export/property', views.export_property_table_csv, name='export_property_table_csv'),
    path('owner/compnay/csv', views.export_owner_pmc_csv, name='export_owner_pmc_csv'),
    
    

    # path('property/commercial/details', views.add_commercial_details, name='add_commercial_details'),    
#     path('staff/view/', views.staff_view, name='staff_view'), 
#     path("lease/property/view/", views.lease_property_view, name="lease_property_view"),
#     
#     path("get/template/fields/", views.get_template_fields, name="get_template_fields"), 
#     path("get/lease/pdf", views.get_lease_pdf, name="get_lease_pdf"),
#     
#     path('options/', views.options, name='options'),  
#     path('property/images/', views.property_images_view, name='property_images_view'),
#     path("save/template", views.generate_contract, name="save_generated_template"), 
#     path("lease/commercials/view/", views.lease_commercials_view, name="lease_commercials_view"),  
#     path("lease/ejari/documents/view/", views.lease_ejari_documents_view, name="lease_ejari_documents_view"), 
#     path('invite/owner/pmc', views.invite_owner_pmc, name='invite_owner_pmc') , 
#     path('invite/pmc/owner', views.invite_pmc_to_owner, name='invite_pmc_to_owner'),
#     path('invite/tenant/pmc', views.invite_tenant_by_pmc, name='invite_tenant_by_pmc'),
#     path('property/statistics', views.property_statistics, name='dashboard_statistics'),
#     path('property/documents/view', views.property_documents_view, name='property_documents_view'), 
#     path('pmc/approval/list', views.pmc_approval_list, name='pmc_approval_list'),
#     path('assign/property/by/owner', views.assign_property_by_owner, name='assign_property_by_owner'),
#     path('tenant/details/', views.tenant_details_view, name='tenant_details_view'),
# # -----------------------------------------------------Export CSV APIs-------------------------------------------------------- 
#     path("export/property/csv", views.export_property_csv, name="export_property_csv"),  
#     path("export/staff/csv", views.export_staff_csv, name="export_staff_csv"),  
#     path("export/tenant/csv", views.export_tenant_csv, name="export_tenant_csv"), 
#     path("export/owner/csv", views.export_owner_csv, name="export_owner_csv"), 
#     path("export/pmc/csv", views.export_pmc_csv, name="export_pmc_csv"),  
#     path("export/lease/tenecy/csv", views.export_lease_tenecy_csv, name="export_lease_tenecy_csv"),
# # -------------------------------------------------------------------------------------------------------------------------------------------------------  
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

   

    

 





 
