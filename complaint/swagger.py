# Import Swagger tools
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi


COMPLAINT_TAG = ["Complaint"]


# Common image object schema
# Used when uploading complaint images or completion proof images
complaint_image_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    description="List of complaint images in base64 format",
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "file_name": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Image file name",
                example="complaint_image.jpg",
            ),
            "file_data": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Base64 encoded image data",
                example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ...",
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT GET API
# ─────────────────────────────────────────────
# This API is used to fetch complaint list.
# Supports filtering by status, property, search text, and pagination.
complaint_get = swagger_auto_schema(
    methods=["get"],
    tags=COMPLAINT_TAG,
    operation_summary="Get complaint list",
    operation_description="Get all complaints with filters like status, property_id, search, page, and page_size.",
    manual_parameters=[
        openapi.Parameter(
            "status",
            openapi.IN_QUERY,
            description="Complaint status filter",
            type=openapi.TYPE_STRING,
            enum=["PENDING", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"],
            required=False,
            example="PENDING",
        ),
        openapi.Parameter(
            "property_id",
            openapi.IN_QUERY,
            description="Property ID filter",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=1,
        ),
        openapi.Parameter(
            "search",
            openapi.IN_QUERY,
            description="Search complaint by code, description, tenant, unit, etc.",
            type=openapi.TYPE_STRING,
            required=False,
            example="water leakage",
        ),
        openapi.Parameter(
            "page",
            openapi.IN_QUERY,
            description="Page number for pagination",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=1,
        ),
        openapi.Parameter(
            "page_size",
            openapi.IN_QUERY,
            description="Number of records per page",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=10,
        ),
    ],
)


# ─────────────────────────────────────────────
# COMPLAINT POST API
# ─────────────────────────────────────────────
# This API is used to create a new complaint.
# Required fields are unit_id, description, service_type, and slots.
complaint_post = swagger_auto_schema(
    methods=["post"],
    tags=COMPLAINT_TAG,
    operation_summary="Create complaint",
    operation_description="Create a new complaint for a unit with service type, priority, slots, and optional note.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id", "description", "service_type", "slots"],
        properties={
            "unit_id": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Unit ID related to complaint",
                example=1,
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint description",
                example="Water leakage in bathroom pipeline.",
            ),
            "service_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Type of service required",
                example="Plumbing",
            ),
            "priority": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint priority",
                enum=["LOW", "MEDIUM", "HIGH"],
                example="HIGH",
            ),
            "slots": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="Preferred slot IDs for service visit",
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                example=[1, 2],
            ),
            "note": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Additional note for complaint",
                example="Tenant is available after 5 PM.",
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT PUT API
# ─────────────────────────────────────────────
# This API is used to update complaint information.
# Complaint is identified using complaint code.
complaint_put = swagger_auto_schema(
    methods=["put"],
    tags=COMPLAINT_TAG,
    operation_summary="Update complaint",
    operation_description="Update an existing complaint using complaint code.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "description": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Updated complaint description",
                example="Water leakage increased near bathroom ceiling.",
            ),
            "service_type": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Updated service type",
                example="Plumbing",
            ),
            "priority": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Updated priority",
                enum=["LOW", "MEDIUM", "HIGH"],
                example="MEDIUM",
            ),
            "status": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Updated complaint status",
                enum=["PENDING", "ASSIGNED", "IN_PROGRESS", "RESOLVED", "CLOSED"],
                example="ASSIGNED",
            ),
            "note": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Update note",
                example="Service provider assigned.",
            ),
            "slots": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="Updated slot IDs",
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                example=[2, 3],
            ),
            "delete_image_ids": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="Image IDs to delete from complaint",
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                example=[5, 6],
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT DELETE API
# ─────────────────────────────────────────────
# This API is used to delete complaint using complaint code.
complaint_delete = swagger_auto_schema(
    methods=["delete"],
    tags=COMPLAINT_TAG,
    operation_summary="Delete complaint",
    operation_description="Delete complaint using complaint code.",
    manual_parameters=[
        openapi.Parameter(
            "code",
            openapi.IN_QUERY,
            description="Complaint code to delete",
            type=openapi.TYPE_STRING,
            required=True,
            example="CMP00001",
        ),
    ],
)


# ─────────────────────────────────────────────
# COMPLAINT DETAIL API
# ─────────────────────────────────────────────
# This API is used to get complete complaint details.
# It includes complaint timeline, activity logs, and broadcasts.
complaint_detail_get = swagger_auto_schema(
    methods=["get"],
    tags=COMPLAINT_TAG,
    operation_summary="Get complaint detail",
    operation_description="Get complaint detail with timeline, activity logs, and broadcasts.",
    manual_parameters=[
        openapi.Parameter(
            "code",
            openapi.IN_QUERY,
            description="Complaint code",
            type=openapi.TYPE_STRING,
            required=True,
            example="CMP00001",
        ),
    ],
)


# ─────────────────────────────────────────────
# COMPLAINT ACCEPT API
# ─────────────────────────────────────────────
# This API is used when a service provider accepts a complaint.
# It confirms the selected slot.
complaint_accept = swagger_auto_schema(
    methods=["patch"],
    tags=COMPLAINT_TAG,
    operation_summary="Accept complaint",
    operation_description="Accept a complaint and confirm selected service slot.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code", "service_provider_id", "slot_id"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "service_provider_id": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Service provider user/profile ID",
                example=1,
            ),
            "slot_id": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Selected slot ID",
                example=2,
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT DECLINE API
# ─────────────────────────────────────────────
# This API is used when a service provider declines a complaint.
complaint_decline = swagger_auto_schema(
    methods=["patch"],
    tags=COMPLAINT_TAG,
    operation_summary="Decline complaint",
    operation_description="Decline a complaint by service provider.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code", "service_provider_id"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "service_provider_id": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Service provider user/profile ID",
                example=1,
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT START API
# ─────────────────────────────────────────────
# This API changes complaint status to work started/in progress.
complaint_start = swagger_auto_schema(
    methods=["patch"],
    tags=COMPLAINT_TAG,
    operation_summary="Start complaint work",
    operation_description="Start work on a complaint using complaint code.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT COMPLETE API
# ─────────────────────────────────────────────
# This API is used to mark complaint work as completed.
# Completion images can also be uploaded.
complaint_complete = swagger_auto_schema(
    methods=["patch"],
    tags=COMPLAINT_TAG,
    operation_summary="Complete complaint work",
    operation_description="Complete complaint work and optionally upload completion proof images.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "images": complaint_image_schema,
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT VERIFY API
# ─────────────────────────────────────────────
# This API is used to verify complaint completion and close complaint.
# Rating and feedback can be submitted.
complaint_verify = swagger_auto_schema(
    methods=["patch"],
    tags=COMPLAINT_TAG,
    operation_summary="Verify complaint",
    operation_description="Verify and close complaint with rating and feedback.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "rating": openapi.Schema(
                type=openapi.TYPE_INTEGER,
                description="Rating from 1 to 5",
                enum=[1, 2, 3, 4, 5],
                example=5,
            ),
            "feedback": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Feedback for service work",
                example="Work completed properly and on time.",
            ),
        },
    ),
)


# ─────────────────────────────────────────────
# COMPLAINT IMAGE UPLOAD API
# ─────────────────────────────────────────────
# This API is used to upload images for an existing complaint.
complaint_upload_images = swagger_auto_schema(
    methods=["post"],
    tags=COMPLAINT_TAG,
    operation_summary="Upload complaint images",
    operation_description="Upload one or more images for an existing complaint.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["code", "images"],
        properties={
            "code": openapi.Schema(
                type=openapi.TYPE_STRING,
                description="Complaint code",
                example="CMP00001",
            ),
            "images": complaint_image_schema,
        },
    ),
)