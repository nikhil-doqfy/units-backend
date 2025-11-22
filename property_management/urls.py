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
    path('owner/details/list/view/', views.owner_details_list_view, name='owner_details_list_view') ,
    path('tenant/list/view', views.tenant_list_view, name='tenant_list_view'),
    path('staff/view/', views.staff_view, name='staff_view') , 
    path('pmc/dashboard/view', views.pmc_dashboard_view, name='pmc_dashboard_view') ,
    path('pmc/owner/view/list/', views.pmc_owner_view_list, name='pmc_owner_view_list') ,   
    path('property/details/list/view/', views.property_details_list_view, name='property_details_list_view') ,
    path('invite/owner/pmc', views.invite_owner_pmc, name='invite_owner_pmc') , 
    path('invite/pmc/owner', views.invite_pmc_to_owner, name='invite_pmc_to_owner'),
    
    path('invite/tenant/pmc', views.invite_tenant_by_pmc, name='invite_tenant_by_pmc'),
    
    path('assign/property/by/owner', views.assign_property_by_owner, name='assign_property_by_owner'),
    path('property/statistics', views.property_statistics, name='dashboard_statistics'),
    path('tenant/property', views.tenant_my_property, name='tenant_my_property'),

    path('tenant/owner/property/', views.property_tenant_list_view, name='property_tenant_list_view'),
    
    path('create/property/basic', views.create_property_basic, name='create_property_basic'),
    path('property/commercial/details', views.add_commercial_details, name='add_commercial_details'),
    path('upload/property/images', views.upload_property_images, name='upload_property_images'), 
    path('get/property/images', views.get_property_images, name='get_property_images'),

    path('upload/property/documents', views.upload_property_documents, name='upload_property_documents'),
    path('fetch/property/documents', views.fetch_property_documents, name='fetch_property_documents'),

    
    path('options/', views.options, name='options'),  

    path('property/images/', views.property_images_view, name='property_images_view'),
    # path("get/template/", views.get_template, name="get_template"), 

    path("save/template", views.save_template_values, name="save_generated_template"),

] 

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

   

    

 





 
