from django.urls import path
from user_service import views as user_serviceviews
from user_service import views

urlpatterns = [
    path("signup", user_serviceviews.user_sign_up),
    path("profile", views.userprofile_view, name='userprofile_view'),
    path("management", views.user_management, name='user_management'),
    path('add_role', views.create_role, name='create_role'),
    path('role_table', views.role_table_view, name='role_table_view'),
    path('users_csv', views.export_users_csv, name='export_users_csv'),
    path('staff_view', views.staff_view, name='staff_view'),
    path('staff_csv', views.export_staff_csv, name='export_staff_csv'),
    path("search_details", views.contact_list_view, name="contact_list"),
    path("approval/", views.approval, name="approval"),
    path('owner', views.owner_crud, name='owner_crud'),
    path('tenant', views.tenant_crud, name='tenant_crud'),
    # Moved from property_management
    path('owner/pmc', views.owner_pmc_view, name='owner_pmc_view'),
    path('owner_compnay_csv', views.export_owner_pmc_csv, name='export_owner_pmc_csv'),
    path('company_owners_csv', views.export_company_owners_csv, name='export_company_owners_csv'),
    path('tenant_csv', views.export_tenant_csv, name='export_tenant_csv'),
    path('tenants_Approved_Rejected', views.company_tenants, name='company_tenants'),
]
