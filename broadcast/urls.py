from django.urls import path
from .views import broadcast_view, broadcast_detail_view, broadcast_report_view, broadcast_resend_failed_view, broadcast_export_view

urlpatterns = [
    path("broadcast", broadcast_view),
    path("broadcast/<int:broadcast_id>/", broadcast_detail_view),
    path("broadcast/<int:broadcast_id>/report", broadcast_report_view, name="broadcast_report"),
    path("broadcast/<int:broadcast_id>/resend-failed", broadcast_resend_failed_view, name="broadcast_resend_failed"),
    path("broadcast/export", broadcast_export_view, name="broadcast_export"),
]