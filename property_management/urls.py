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
    path('owner/details/', views.submit_owner_details, name='submit_owner_details'),
    path('choose/manage/option/', views.choose_manage_option, name='choose_manage_option'),
    path('upload/owner/documents/', views.upload_owner_documents, name='upload_owner_documents'),
    path("get/owner/documents/", views.get_owner_documents, name="get_owner_documents"),
    path("tenant/details/", views.submit_tenant_details,name="sumbit_tenant_details"),
    path("edit/tenant/details", views.edit_tenant_details,name="edit_tenant_details"),
    path("upload/tenant/documents", views.upload_tenant_documents,name="upload_tenant_documents"), 
    path("update/tenant/documents", views.update_tenant_documents,name="update_tenant_documents"),  
    path('get/tenant/details/', views.get_tenant_details, name='get_tenant_details'), 
    path('submit/pmc/details', views.submit_property_manager_details, name='submit_property_manager_details'), 
    path('upload/pmc/documents', views.upload_pmc_documents, name='upload_pmc_documents'),
    path('edit/pmc/details', views.edit_property_manager_details, name='edit_property_manager_details'),
    path('get/pmc/details', views.get_property_manager_details, name='get_property_manager_details'),
]
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
