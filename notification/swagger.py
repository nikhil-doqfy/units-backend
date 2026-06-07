# Import Swagger tools
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


NOTIFICATION_TAG = ["Notification"]


# ---------------- NOTIFICATION APIs ----------------
# These decorators are used for notification list, read, clear, and unread count APIs.


# GET /notification/
# Get user and global notifications with filters and pagination.
notification_list_get = swagger_auto_schema(
    method="get",
    tags=NOTIFICATION_TAG,
    operation_summary="Get notifications",
    operation_description="Get logged-in user's notifications including global notifications. Supports read/unread filter and pagination.",
    manual_parameters=[
        openapi.Parameter(
            "type",
            openapi.IN_QUERY,
            description="Filter notifications by type: all, read, unread",
            type=openapi.TYPE_STRING,
            required=False,
            example="all",
        ),
        openapi.Parameter(
            "page",
            openapi.IN_QUERY,
            description="Page number",
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
            example=20,
        ),
    ],
)


# PATCH /notification/<pk>/read/
# Mark one notification as read.
notification_read_patch = swagger_auto_schema(
    method="patch",
    tags=NOTIFICATION_TAG,
    operation_summary="Mark notification as read",
    operation_description="Mark a single notification as read using notification ID from URL.",
    manual_parameters=[
        openapi.Parameter(
            "pk",
            openapi.IN_PATH,
            description="Notification ID",
            type=openapi.TYPE_INTEGER,
            required=True,
            example=1,
        ),
    ],
)


# PATCH /notification/read-all/
# Mark all notifications as read.
notification_read_all_patch = swagger_auto_schema(
    method="patch",
    tags=NOTIFICATION_TAG,
    operation_summary="Mark all notifications as read",
    operation_description="Mark all unread and uncleared notifications as read for the logged-in user.",
)


# PATCH /notification/<pk>/clear/
# Clear one notification.
notification_clear_patch = swagger_auto_schema(
    method="patch",
    tags=NOTIFICATION_TAG,
    operation_summary="Clear notification",
    operation_description="Clear a single notification using notification ID from URL.",
    manual_parameters=[
        openapi.Parameter(
            "pk",
            openapi.IN_PATH,
            description="Notification ID",
            type=openapi.TYPE_INTEGER,
            required=True,
            example=1,
        ),
    ],
)


# PATCH /notification/clear-all/
# Clear all notifications.
notification_clear_all_patch = swagger_auto_schema(
    method="patch",
    tags=NOTIFICATION_TAG,
    operation_summary="Clear all notifications",
    operation_description="Clear all uncleared notifications for the logged-in user.",
)


# GET /notification/unread-count/
# Get unread notification count for badge.
notification_unread_count_get = swagger_auto_schema(
    method="get",
    tags=NOTIFICATION_TAG,
    operation_summary="Get unread notification count",
    operation_description="Get unread and uncleared notification count for the logged-in user.",
)