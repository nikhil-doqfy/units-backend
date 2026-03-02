from django.urls import path
from .views import terms_list_create ,terms_update_delete

urlpatterns = [
    path('', terms_list_create, name='terms-list-create'),
    path('<int:pk>/', terms_update_delete, name='terms-update-delete'),
]