from django.contrib import admin
from django.urls import path, include, re_path
from django.conf.urls.static import static
from property_management import settings
from user_service import urls as user_service_urls
from auth_service import urls as auth_service_urls
from payment import urls as payment_urls
from . import views
from charges import urls as charges_urls
from property import urls as property_urls
from lead import urls as lead_urls
from lease import urls as lease_urls
from complaint import urls as complaint_urls
from notification import urls as notification_urls

# User-service views kept here because user_service/urls.py is under the 'user/' prefix
from user_service.views import (
    owner_pmc_view,
    export_owner_pmc_csv,
    export_company_owners_csv,
    export_tenant_csv,
    company_tenants,
    approval_view,
)


urlpatterns = [
    path("admin/reports/<str:filename>/", views.admin_report_file),
    path("admin/reports/", views.reports_view),
    path('admin/', admin.site.urls),
    path('user/', include(user_service_urls)),
    path('auth/', include(auth_service_urls)),
    path('payment/', include(payment_urls)),
    path('', include(charges_urls)),
    path('', include(property_urls)),
    path('', include(lead_urls)),
    path('', include(lease_urls)),
    path('', include(complaint_urls)),
    path('', include(notification_urls)),

    re_path(r"^media/(?P<path>.*)$", views.serve_media),
    path('options', views.options, name='options'),
    path('global_search', views.global_search, name='global_search'),
    path('invitation', views.send_invitation, name='send_invitation'),
    path('statistics', views.dashboard_overview, name='dashboard_statistics'),
    path('audit_log', views.audit_log, name='audit_log'),
    path("faq_api", views.faq_api, name="faq_api"),
    path('monthly_revenue', views.dashboard_monthly_revenue, name='dashboard_monthly_revenue'),
    path('cheque_visibility', views.dashboard_cheque_visibility, name='dashboard_cheque_visibility'),
    path('cheque_aging', views.dashboard_cheque_aging, name='dashboard_cheque_aging'),
    path('other_type_payments', views.dashboard_other_type_payments, name='dashboard_other_type_payments'),
    path('dashboard_graph_due', views.dashboard_yearly_dues, name='dashboard_yearly_due'),
    path('dashboard_property_owned', views.dashboard_property_owned, name='dashboard_property_owned'),
    path('dashboard_visualization', views.dashboard_visualization, name='dashboard_visualization'),

    # User-service views at root level (original paths, before user/ prefix migration)
    path('api/approval', approval_view, name='approval_view'),
    path('owner/pmc', owner_pmc_view, name='owner_pmc_view'),
    path('owner_compnay_csv', export_owner_pmc_csv, name='export_owner_pmc_csv'),
    path('company_owners_csv', export_company_owners_csv, name='export_company_owners_csv'),
    path('tenant_csv', export_tenant_csv, name='export_tenant_csv'),
    path('tenants_Approved_Rejected', company_tenants, name='company_tenants'),

    # path('complaint_list', views.complaint_list, name='complaint_list'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
