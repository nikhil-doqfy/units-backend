from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


# Lead GET API Swagger documentation
lead_get = swagger_auto_schema(
    method='get',
    operation_summary="Get lead list or single lead",
    operation_description="Fetch all leads, search leads, filter leads, export CSV, or get a single lead using lead_id.",
    manual_parameters=[
        openapi.Parameter('lead_id', openapi.IN_QUERY, description="Lead ID to get single lead details", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter('search', openapi.IN_QUERY, description="Search lead by name or email", type=openapi.TYPE_STRING, required=False, example="Rahul"),
        openapi.Parameter('status', openapi.IN_QUERY, description="Filter leads by status", type=openapi.TYPE_STRING, required=False, example="INTERESTED"),
        openapi.Parameter('platform', openapi.IN_QUERY, description="Filter leads by platform", type=openapi.TYPE_STRING, required=False, example="WEBSITE"),
        openapi.Parameter('lead_type', openapi.IN_QUERY, description="Filter leads by lead type", type=openapi.TYPE_STRING, required=False, example="RENT"),
        openapi.Parameter('page', openapi.IN_QUERY, description="Page number for pagination", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter('page_size', openapi.IN_QUERY, description="Number of records per page", type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter('export', openapi.IN_QUERY, description="Use csv to export leads", type=openapi.TYPE_STRING, required=False, example="csv"),
    ],
)


# Lead POST API Swagger documentation
lead_post = swagger_auto_schema(
    method='post',
    operation_summary="Create lead",
    operation_description="Create a new lead for a unit.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['unit_id', 'name', 'email', 'contact_number', 'platform', 'lead_type'],
        properties={
            'unit_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Unit ID where the lead is interested", example=1),
            'name': openapi.Schema(type=openapi.TYPE_STRING, description="Full name of the lead", example="Rahul Sharma"),
            'email': openapi.Schema(type=openapi.TYPE_STRING, description="Email address of the lead", example="rahul@example.com"),
            'contact_number': openapi.Schema(type=openapi.TYPE_STRING, description="Contact number of the lead", example="+971501234567"),
            'status': openapi.Schema(type=openapi.TYPE_STRING, description="Current lead status", example="INTERESTED"),
            'platform': openapi.Schema(type=openapi.TYPE_STRING, description="Source platform of the lead", example="WEBSITE"),
            'lead_type': openapi.Schema(type=openapi.TYPE_STRING, description="Lead type such as RENT or BUY", example="RENT"),
        },
    ),
)


# Lead PUT API Swagger documentation
lead_put = swagger_auto_schema(
    method='put',
    operation_summary="Update lead",
    operation_description="Update existing lead details using lead_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['lead_id'],
        properties={
            'lead_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Existing lead ID", example=1),
            'unit_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Updated unit ID", example=2),
            'name': openapi.Schema(type=openapi.TYPE_STRING, description="Updated lead name", example="Amit Patil"),
            'email': openapi.Schema(type=openapi.TYPE_STRING, description="Updated lead email", example="amit@example.com"),
            'contact_number': openapi.Schema(type=openapi.TYPE_STRING, description="Updated contact number", example="+971509876543"),
            'status': openapi.Schema(type=openapi.TYPE_STRING, description="Updated lead status", example="LEASE_TENANCY"),
            'platform': openapi.Schema(type=openapi.TYPE_STRING, description="Updated lead platform", example="FACEBOOK"),
            'lead_type': openapi.Schema(type=openapi.TYPE_STRING, description="Updated lead type", example="BUY"),
            'comment': openapi.Schema(type=openapi.TYPE_STRING, description="Comment stored in activity log", example="Lead converted to tenancy"),
        },
    ),
)


# Lead DELETE API Swagger documentation
lead_delete = swagger_auto_schema(
    method='delete',
    operation_summary="Delete lead",
    operation_description="Delete a lead using lead_id.",
    manual_parameters=[
        openapi.Parameter('lead_id', openapi.IN_QUERY, description="Lead ID to delete", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# Activity Log GET API Swagger documentation
activity_get = swagger_auto_schema(
    method='get',
    operation_summary="Get activity logs",
    operation_description="Get all activity logs related to a lead.",
    manual_parameters=[
        openapi.Parameter('lead_id', openapi.IN_QUERY, description="Lead ID to fetch activity logs", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# Activity Log POST API Swagger documentation
activity_post = swagger_auto_schema(
    method='post',
    operation_summary="Create activity log",
    operation_description="Create a new activity log for a lead.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['lead_id'],
        properties={
            'lead_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Lead ID related to activity", example=1),
            'activity_type': openapi.Schema(type=openapi.TYPE_STRING, description="Type of activity such as NOTE, CALL, STATUS_CHANGE", example="NOTE"),
            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Activity title", example="Follow-up call"),
            'description': openapi.Schema(type=openapi.TYPE_STRING, description="Activity description", example="Called customer and discussed rent details"),
            'scheduled_date': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME, description="Scheduled date and time for activity", example="2026-06-06T10:30"),
        },
    ),
)


# Activity Log PUT API Swagger documentation
activity_put = swagger_auto_schema(
    method='put',
    operation_summary="Update activity log",
    operation_description="Update an existing activity log using log_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['log_id'],
        properties={
            'log_id': openapi.Schema(type=openapi.TYPE_INTEGER, description="Existing activity log ID", example=1),
            'activity_type': openapi.Schema(type=openapi.TYPE_STRING, description="Updated activity type", example="CALL"),
            'title': openapi.Schema(type=openapi.TYPE_STRING, description="Updated activity title", example="Second follow-up call"),
            'description': openapi.Schema(type=openapi.TYPE_STRING, description="Updated activity description", example="Customer asked for more details"),
            'scheduled_date': openapi.Schema(type=openapi.TYPE_STRING, format=openapi.FORMAT_DATETIME, description="Updated scheduled date and time", example="2026-06-07T11:00"),
        },
    ),
)


# Activity Log DELETE API Swagger documentation
activity_delete = swagger_auto_schema(
    method='delete',
    operation_summary="Delete activity log",
    operation_description="Delete an activity log using log_id.",
    manual_parameters=[
        openapi.Parameter('log_id', openapi.IN_QUERY, description="Activity log ID to delete", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# Lead Active Lease Check API Swagger documentation
lead_check_active_lease_get = swagger_auto_schema(
    method='get',
    operation_summary="Check active lease for lead",
    operation_description="Check whether the lead unit has an active lease.",
    manual_parameters=[
        openapi.Parameter('lead_id', openapi.IN_QUERY, description="Lead ID to check active lease", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# Lead Bulk Import API Swagger documentation
lead_bulk_import_post = swagger_auto_schema(
    method='post',
    operation_summary="Bulk import leads",
    operation_description="Import multiple leads using a base64 encoded CSV file.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=['file'],
        properties={
            'file': openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Base64 encoded CSV file",
                example="data:text/csv;base64,dW5pdF9pZCxuYW1lLGVtYWlsLGNvbnRhY3RfbnVtYmVyLHBsYXRmb3JtLGxlYWRfdHlwZQoxLFJhaHVsLHJhaHVsQGV4YW1wbGUuY29tLCs5NzE1MDEyMzQ1NjcsV0VCU0lURSxSRU5U"
            )
        },
    ),
)