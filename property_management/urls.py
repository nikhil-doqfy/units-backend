from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from property_management import settings
from user_service import urls as user_service_urls  
from auth_service import urls as auth_service_urls
from . import views
urlpatterns = [ 
    path('admin/', admin.site.urls),
    path('user/', include(user_service_urls)),
    path('auth/', include(auth_service_urls)), 
    path('owner/details/list/view/', views.owner_details_list_view, name='owner_details_list_view') ,
    path('tenant/list/view', views.tenant_list_view, name='tenant_list_view'),
    path('property/details/list/view/', views.property_details_list_view, name='property_details_list_view') ,
    path('pmc/owner/view/list/', views.pmc_owner_view_list, name='pmc_owner_view_list') , 
    path('staff/view/', views.staff_view, name='staff_view'), 

    path("lease/property/view/", views.lease_property_view, name="lease_property_view"),





    path('owner/details/', views.owner_details_view, name='owner_details_view'),
    path('choose/manage/option/', views.choose_manage_option, name='choose_manage_option'),
    path('upload/owner/documents/', views.upload_owner_documents, name='upload_owner_documents'),
    path("get/owner/documents/", views.get_owner_documents, name="get_owner_documents"),     
    path("upload/tenant/documents", views.upload_tenant_documents,name="upload_tenant_documents"), 
    path("update/tenant/documents", views.update_tenant_documents,name="update_tenant_documents"),
    path('upload/pmc/documents', views.upload_pmc_documents, name='upload_pmc_documents'),
    path('property/details/', views.property_details_view, name='property_details_view'), 
    path('tenant/details/', views.tenant_details_view, name='tenant_details_view'),
    path('owner/properties/tenants/', views.owner_property_tenants_view, name='owner_tenants_list'),
    path('property/manager/details/', views.property_manager_details_view, name='property_manager_details_view'),
    path('property/manager/list/', views.property_manager_list, name='property_manager_list'), 
    
    path('pmc/dashboard/view', views.pmc_dashboard_view, name='pmc_dashboard_view') ,
      
    path('invite/owner/pmc', views.invite_owner_pmc, name='invite_owner_pmc') , 
    path('invite/pmc/owner', views.invite_pmc_to_owner, name='invite_pmc_to_owner'),
    path('invite/tenant/pmc', views.invite_tenant_by_pmc, name='invite_tenant_by_pmc'),
    path('assign/property/by/owner', views.assign_property_by_owner, name='assign_property_by_owner'),
    path('property/statistics', views.property_statistics, name='dashboard_statistics'),
    path('tenant/property', views.tenant_my_property, name='tenant_my_property'),
    path('tenant/owner/property/', views.property_tenant_list_view, name='property_tenant_list_view'),
    path('create/property/basic', views.create_property_basic, name='create_property_basic'),
    path('property/commercial/details', views.add_commercial_details, name='add_commercial_details'),
    path('property/documents/view', views.property_documents_view, name='property_documents_view'),
    path('options/', views.options, name='options'),  
    path('property/images/', views.property_images_view, name='property_images_view'),
    path("save/template", views.generate_contract, name="save_generated_template"), 

    path("get/template/fields/", views.get_template_fields, name="get_template_fields"), 
    

    
    path("lease/commercials/view/", views.lease_commercials_view, name="lease_commercials_view"),  

    path("lease/ejari/documents/view/", views.lease_ejari_documents_view, name="lease_ejari_documents_view"), 
    # path("get/pdf/template/", views.get_pdf_template, name="get_pdf_template"), 


    path("export/property/csv", views.export_property_csv, name="export_property_csv"),  
    path("export/staff/csv", views.export_staff_csv, name="export_staff_csv"),  
    path("export/tenant/csv", views.export_tenant_csv, name="export_tenant_csv"), 

    path("export/owner/csv", views.export_owner_csv, name="export_owner_csv"), 


    path("export/pmc/csv", views.export_pmc_csv, name="export_pmc_csv"),  
    path("export/lease/tenecy/csv", views.export_lease_tenecy_csv, name="export_lease_tenecy_csv"),

  
] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

   

    

 





 
