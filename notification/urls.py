from django.urls import path
from notification import views

urlpatterns = [
    path('notification', views.notification_list),
    path('notification/read-all', views.notification_read_all),
    path('notification/clear-all', views.notification_clear_all),
    path('notification/unread-count', views.notification_unread_count),
    path('notification/<int:pk>/read', views.notification_read),
    path('notification/<int:pk>/clear', views.notification_clear),
]
