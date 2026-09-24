from django.urls import path
from rest_framework.routers import SimpleRouter
from lead import views

# SimpleRouter (not DefaultRouter) -- this urls.py is included at the
# project root (property_management/urls.py: path('', include(lead_urls))),
# and DefaultRouter's auto-generated API-root view would otherwise bind to
# '/' itself. trailing_slash=False matches this app's convention
# (APPEND_SLASH = False in settings.py, no other endpoint here uses one).
router = SimpleRouter(trailing_slash=False)
router.register(r"lead", views.LeadViewSet, basename="lead")

urlpatterns = [
    path('lead/bulk-import', views.lead_bulk_import, name='lead_bulk_import'),
    path('lead/activity-log', views.activity_log_view, name='activity_log_view'),
    path('lead/check-active-lease', views.lead_check_active_lease, name='lead_check_active_lease'),
    # Dubai Leasing Management Flow, Phase 1: Proposal & Holding
    path("lead/send-proposal", views.send_proposal, name="send_proposal"),
    path("lead/respond-to-proposal", views.respond_to_proposal, name="respond_to_proposal"),
    path("lead/confirm-hold-and-proceed", views.confirm_hold_and_proceed, name="confirm_hold_and_proceed"),
    path("lead/release-expired-hold", views.release_expired_hold, name="release_expired_hold"),
] + router.urls
