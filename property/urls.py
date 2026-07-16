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
    path("bulk_upload_property",views.bulk_upload_property_excel, name="bulk_upload_property_excel"),
    path("property_types", views.property_type_list),
    # Moved from property_management
    path('property/details', views.property_table_view, name='property_table_view'),
    path('parent/property', views.parent_property_view, name='parent_property_view'),
    path('export/property', views.export_property_table_csv, name='export_property_table_csv'),
    path('interested', views.toggle_property_interest, name='toggle_property_interest'),
    path('companies', views.company_list, name='company_list'),
]
