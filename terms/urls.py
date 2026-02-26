from django.urls import path
from .views import terms_list_create

urlpatterns = [
    path('', terms_list_create, name='terms-list-create'),
]