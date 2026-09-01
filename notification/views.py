import json
from django.utils import timezone
from django.db.models import Q
from utilities.helper_functions import prepare_response
from utilities.decorator import is_request_authenticated
from utilities import status
from notification.models import Notification
from rest_framework.decorators import api_view

from .swagger import (
    notification_list_get,
    notification_read_patch,
    notification_read_all_patch,
    notification_clear_patch,
    notification_clear_all_patch,
    notification_unread_count_get,
)


def serialize_notification(n):
    return {
        "id": n.id,
        "title": n.title,
        "message": n.message,
        "notification_type": n.notification_type,
        "is_read": n.is_read,
        "is_cleared": n.is_cleared,
        "is_global": n.is_global,
        "reference_id": n.reference_id,
        "reference_code": n.reference_code,
        "read_at": int(n.read_at.timestamp()) if n.read_at else None,
        "created": int(n.created.timestamp()) if n.created else None,
    }


# =====================================================
# GET ALL NOTIFICATIONS (user + global)
# =====================================================

@notification_list_get
@api_view(["GET"])
@is_request_authenticated
def notification_list(request):

    if request.method == "GET":

        filter_type = request.GET.get("type", "all").lower()

        # ── User's own + global notifications ────────────────
        notifications = Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            is_cleared=False
        ).order_by('-created')

        # ── Filter by type ────────────────────────────────────
        if filter_type == "read":
            notifications = notifications.filter(is_read=True)
        elif filter_type == "unread":
            notifications = notifications.filter(is_read=False)

        # ── Counts ────────────────────────────────────────────
        all_notifications = Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            is_cleared=False
        )
        total = all_notifications.count()
        unread = all_notifications.filter(is_read=False).count()
        read = all_notifications.filter(is_read=True).count()

        # ── Pagination ────────────────────────────────────────
        page_size = int(request.GET.get("page_size", 20))
        page = int(request.GET.get("page", 1))
        start = (page - 1) * page_size
        end = start + page_size
        paginated = notifications[start:end]

        return prepare_response(
            content={
                "results": [serialize_notification(n) for n in paginated],
                "counts": {
                    "all": total,
                    "unread": unread,
                    "read": read,
                    "cleared": Notification.objects.filter(
                        Q(user=request.user) | Q(is_global=True),
                        is_cleared=True
                    ).count()
                },
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            },
            message="Notifications fetched successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# MARK SINGLE AS READ
# =====================================================

@notification_read_patch
@api_view(["PATCH"])
@is_request_authenticated
def notification_read(request, pk):

    if request.method == "PATCH":
        notification = Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            id=pk
        ).first()

        if not notification:
            return prepare_response(
                message="Notification not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        notification.mark_read()

        return prepare_response(
            content=serialize_notification(notification),
            message="Notification marked as read.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# MARK ALL AS READ
# =====================================================

@notification_read_all_patch
@api_view(["PATCH"])
@is_request_authenticated
def notification_read_all(request):

    if request.method == "PATCH":
        Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            is_read=False,
            is_cleared=False
        ).update(
            is_read=True,
            read_at=timezone.now()
        )

        return prepare_response(
            message="All notifications marked as read.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# CLEAR SINGLE NOTIFICATION
# =====================================================

@notification_clear_patch
@api_view(["PATCH"])
@is_request_authenticated
def notification_clear(request, pk):

    if request.method == "PATCH":
        notification = Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            id=pk
        ).first()

        if not notification:
            return prepare_response(
                message="Notification not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        notification.mark_cleared()

        return prepare_response(
            message="Notification cleared.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# CLEAR ALL NOTIFICATIONS
# =====================================================

@notification_clear_all_patch
@api_view(["PATCH"])
@is_request_authenticated
def notification_clear_all(request):

    if request.method == "PATCH":
        Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            is_cleared=False
        ).update(
            is_cleared=True,
            cleared_at=timezone.now()
        )

        return prepare_response(
            message="All notifications cleared.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# UNREAD COUNT (for badge)
# =====================================================

@notification_unread_count_get
@api_view(["GET"])
@is_request_authenticated
def notification_unread_count(request):

    if request.method == "GET":
        count = Notification.objects.filter(
            Q(user=request.user) | Q(is_global=True),
            is_read=False,
            is_cleared=False
        ).count()

        return prepare_response(
            content={"unread_count": count},
            message="Unread count fetched.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message="Method not allowed.",
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )
