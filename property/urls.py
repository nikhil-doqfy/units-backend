from django.urls import path
from . import views

urlpatterns = [
    path('property', views.property, name='property'),
    path('property/blocks', views.property_blocks, name='property_blocks'),
    path('property/images', views.property_images, name='property_images'),
    path('property/document-types', views.property_document_types, name='property_document_types'),
    path('property/documents', views.property_documents, name='property_documents'),
    path('property/unit', views.unit, name='unit'),
    path('property/unit/images', views.unit_images, name='unit_images'),
    path('property/unit/document-types', views.unit_document_types, name='unit_document_types'),
    path('property/unit/documents', views.unit_documents, name='unit_documents'),
]
