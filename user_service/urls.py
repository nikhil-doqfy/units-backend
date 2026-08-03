from django.urls import path
from user_service import views as user_serviceviews
from user_service import views

urlpatterns = [
    path("signup", user_serviceviews.user_sign_up, name="signup"),
    path("profile", views.userprofile_view, name='userprofile_view'),
    path("management", views.user_management, name='user_management'),
    path('add_role', views.create_role, name='create_role'),
    path('role_table', views.role_table_view, name='role_table_view'),
    path('users_csv', views.export_users_csv, name='export_users_csv'),
    path('staff_view', views.staff_view, name='staff_view'),
    path('staff_csv', views.export_staff_csv, name='export_staff_csv'),
    path("search_details", views.contact_list_view, name="contact_list"),
    path("approval/", views.approval_view, name="approval"),
    path('owner', views.owner_crud, name='owner_crud'),
    path('tenant', views.tenant_crud, name='tenant_crud'),
    # Moved from property_management
    path('owner/pmc', views.owner_pmc_view, name='owner_pmc_view'),
    path('owner_compnay_csv', views.export_owner_pmc_csv, name='export_owner_pmc_csv'),
    path('company_owners_csv', views.export_company_owners_csv, name='export_company_owners_csv'),
    path('tenant_csv', views.export_tenant_csv, name='export_tenant_csv'),
    path('tenants_Approved_Rejected', views.company_tenants, name='company_tenants'),
    path('agreement', views.agreement_api),
    path('agreement/<int:pk>', views.agreement_detail_api),
    path('agreement/<int:pk>/renew', views.renew_agreement),
    path('agreement/<int:pk>/upload', views.upload_agreement_document),
    path('reset_password', views.reset_user_password, name='reset_user_password'),
    path('share_profile', views.share_profile, name='share_profile'),
    path("privacy_policy", views.privacy_policy_api),
    path('tenant_documents', views.tenant_document_api, name='tenant_document_api'),
 
]
