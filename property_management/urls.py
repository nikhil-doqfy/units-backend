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
    path('assign/property/by/owner', views.assign_property_by_owner, name='assign_property_by_owner'),
    
    
] 
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)





 
 