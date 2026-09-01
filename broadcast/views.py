import json
import logging
import csv

from django.db.models import Q
from django.utils import timezone
from django.http import HttpResponse

from rest_framework.decorators import api_view
from rest_framework import status

from utilities.decorator import is_request_authenticated
from utilities.helper_functions import (
    prepare_response,
    datetime_to_epoch_millis,
    send_ses_email,
    upload_file_to_s3_base64,
)
from utilities import constants

from property.models import Property, PropertyBlocks, Unit
from lease.models import Lease
from lease.views import _get_pmc_ids_for_user

from .models import BroadcastAnnouncement, BroadcastRecipient

logger = logging.getLogger(__name__)


def _get_send_by(user):
    if not user:
        return None

    name = " ".join(
        filter(
            None,
            [
                getattr(user, "first_name", None),
                getattr(user, "last_name", None),
            ],
        )
    ).strip()

    return name or getattr(user, "email", None) or getattr(user, "username", None)


def _broadcast_queryset_for_user(request):
    pmc_ids = _get_pmc_ids_for_user(request.user)

    return BroadcastAnnouncement.objects.select_related(
        "property",
        "block_tower",
        "unit",
        "created_by",
    ).filter(
        is_active=True
    ).filter(
        Q(property__pmc_id__in=pmc_ids) |
        Q(block_tower__property__pmc_id__in=pmc_ids) |
        Q(unit__parent_property__pmc_id__in=pmc_ids) |
        Q(unit__property_block_tower__property__pmc_id__in=pmc_ids)
    ).distinct().order_by("-id")


def _validate_broadcast_access(property_obj, block_obj, unit_obj, pmc_ids):
    if property_obj and property_obj.pmc_id not in pmc_ids:
        return False

    if block_obj and block_obj.property_id:
        if block_obj.property.pmc_id not in pmc_ids:
            return False

    if unit_obj:
        property_ids = []

        if unit_obj.parent_property_id:
            property_ids.append(unit_obj.parent_property_id)

        if unit_obj.property_block_tower_id:
            block_property_id = PropertyBlocks.objects.filter(
                pk=unit_obj.property_block_tower_id
            ).values_list("property_id", flat=True).first()

            if block_property_id:
                property_ids.append(block_property_id)

        allowed = Property.objects.filter(
            id__in=property_ids,
            pmc_id__in=pmc_ids,
        ).exists()

        if not allowed:
            return False

    return True


@api_view(["POST", "GET"])
@is_request_authenticated
def broadcast_view(request):
    if request.method == "POST":
        try:
            body = json.loads(request.body)

            title = body.get("title", "").strip()
            description = body.get("description", "").strip()
            property_id = body.get("property")
            block_id = body.get("block_tower")
            unit_id = body.get("unit")
            priority = body.get("priority", "NORMAL")
            channels = body.get("channels", [])
            banner_image = body.get("banner_image")

            if banner_image:
                object_name = f"broadcast/{timezone.now().strftime('%Y%m%d%H%M%S%f')}.jpg"
                try:
                    banner_image = upload_file_to_s3_base64(banner_image, object_name)
                except Exception as e:
                    logger.exception("BROADCAST_IMAGE_UPLOAD_ERROR | error=%s", str(e))
                    return prepare_response(message="Failed to upload banner image", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            if not title:
                return prepare_response(message="title is required", status=status.HTTP_400_BAD_REQUEST)

            if not description:
                return prepare_response(message="description is required", status=status.HTTP_400_BAD_REQUEST)

            valid_priorities = {choice[0] for choice in constants.BROADCAST_PRIORITY_CHOICES}

            if priority not in valid_priorities:
                return prepare_response(message="Invalid priority", status=status.HTTP_400_BAD_REQUEST)

            valid_channels = {choice[0] for choice in constants.BROADCAST_CHANNEL_CHOICES}

            if not isinstance(channels, list):
                return prepare_response(message="channels must be a list", status=status.HTTP_400_BAD_REQUEST)

            invalid_channels = set(channels) - valid_channels

            if invalid_channels:
                return prepare_response(message=f"Invalid channel(s): {list(invalid_channels)}", status=status.HTTP_400_BAD_REQUEST)

            property_obj = None
            block_obj = None
            unit_obj = None

            if property_id:
                property_obj = Property.objects.filter(pk=property_id, is_active=True).first()

                if not property_obj:
                    return prepare_response(message="Property not found", status=status.HTTP_404_NOT_FOUND)

            if block_id:
                block_obj = PropertyBlocks.objects.filter(pk=block_id, is_active=True).select_related("property").first()

                if not block_obj:
                    return prepare_response(message="Block not found", status=status.HTTP_404_NOT_FOUND)

            if unit_id:
                unit_obj = Unit.objects.filter(pk=unit_id, is_active=True).first()

                if not unit_obj:
                    return prepare_response(message="Unit not found", status=status.HTTP_404_NOT_FOUND)

            pmc_ids = _get_pmc_ids_for_user(request.user)

            if not pmc_ids:
                return prepare_response(message="No PMC access found", status=status.HTTP_403_FORBIDDEN)

            if not _validate_broadcast_access(property_obj, block_obj, unit_obj, pmc_ids):
                return prepare_response(message="You do not have access to the selected property, block or unit", status=status.HTTP_403_FORBIDDEN)

            broadcast = BroadcastAnnouncement.objects.create(
                title=title,
                description=description,
                property=property_obj,
                block_tower=block_obj,
                unit=unit_obj,
                priority=priority,
                channels=channels,
                banner_image=banner_image,
                status="SENT",
                sent_date=timezone.now(),
                created_by=request.user.user
            )

            recipients = []
            delivered_count = 0
            failed_count = 0

            if "MAIL" in channels:
                active_leases = Lease.objects.filter(
                    lease_status="ACTIVE",
                    tenant__isnull=False,
                    is_active=True
                ).select_related("tenant", "unit")

                if unit_obj:
                    active_leases = active_leases.filter(unit=unit_obj)
                elif block_obj:
                    active_leases = active_leases.filter(unit__property_block_tower=block_obj)
                elif property_obj:
                    active_leases = active_leases.filter(
                        Q(unit__parent_property=property_obj) |
                        Q(unit__property_block_tower__property=property_obj)
                    )

                for lease in active_leases:
                    tenant = lease.tenant
                    email = None

                    if getattr(tenant, "user", None):
                        email = tenant.user.email

                    if email:
                        email = email.strip().lower()

                        if email and email not in recipients:
                            recipients.append(email)

                body_text = f"Hello,\n\n{description}\n\nThank you,\nThe Units Team"

                body_html = f"""
                <html>
                    <body>
                        <h2>{title}</h2>
                        <p>{description}</p>
                        <br>
                        <p>Thank you,<br>The Units Team</p>
                    </body>
                </html>
                """

                for email in recipients:
                    recipient = BroadcastRecipient.objects.create(
                        broadcast=broadcast,
                        email=email,
                        channel="MAIL",
                        status="PENDING",
                        created_by=request.user.user
                    )

                    try:
                        ok = send_ses_email(email, title, body_text, body_html)

                        if ok:
                            recipient.status = "DELIVERED"
                            recipient.sent_at = timezone.now()
                            recipient.save(update_fields=["status", "sent_at", "modified"])
                            delivered_count += 1
                        else:
                            recipient.status = "FAILED"
                            recipient.error_message = "Email sending failed"
                            recipient.save(update_fields=["status", "error_message", "modified"])
                            failed_count += 1

                            logger.warning(
                                "BROADCAST_MAIL_FAILED | broadcast_id=%d | email=%s",
                                broadcast.id,
                                email
                            )

                    except Exception as e:
                        recipient.status = "FAILED"
                        recipient.error_message = str(e)
                        recipient.save(update_fields=["status", "error_message", "modified"])
                        failed_count += 1

                        logger.exception(
                            "BROADCAST_MAIL_ERROR | broadcast_id=%d | email=%s | error=%s",
                            broadcast.id,
                            email,
                            str(e)
                        )

            broadcast.recipient_count = len(recipients)
            broadcast.delivered_count = delivered_count
            broadcast.failed_count = failed_count

            broadcast.save(
                update_fields=[
                    "recipient_count",
                    "delivered_count",
                    "failed_count",
                    "modified"
                ]
            )

            return prepare_response(
                message="Broadcast created successfully",
                content={
                    "id": broadcast.id,
                    "log_id": f"BR{broadcast.id:05d}",
                    "title": broadcast.title,
                    "mail_sent_count": delivered_count,
                    "send_by": _get_send_by(broadcast.created_by)
                },
                status=status.HTTP_201_CREATED
            )

        except json.JSONDecodeError:
            return prepare_response(message="Invalid JSON body", status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(
                "BROADCAST_CREATE_ERROR | user_id=%s | error=%s",
                request.user.id,
                str(e)
            )

            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    search = request.GET.get("search", "").strip()
    priority = request.GET.get("priority")
    channel = request.GET.get("channel")
    status_filter = request.GET.get("status")
    property_id = request.GET.get("property_id")
    block_id = request.GET.get("block_tower_id")
    unit_id = request.GET.get("unit_id")

    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
    except ValueError:
        return prepare_response(message="Invalid pagination values", status=status.HTTP_400_BAD_REQUEST)

    qs = _broadcast_queryset_for_user(request)

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(property__property_name__icontains=search) |
            Q(block_tower__block_name__icontains=search) |
            Q(unit__unit_name__icontains=search)
        )

    if priority:
        qs = qs.filter(priority=priority)

    if channel:
        qs = qs.filter(channels__contains=[channel])

    if status_filter:
        qs = qs.filter(status=status_filter)

    if property_id:
        qs = qs.filter(property_id=property_id)

    if block_id:
        qs = qs.filter(block_tower_id=block_id)

    if unit_id:
        qs = qs.filter(unit_id=unit_id)

    total_count = qs.count()
    start = (page - 1) * page_size
    end = start + page_size
    broadcasts = qs[start:end]

    content = []

    for obj in broadcasts:
        content.append({
            "id": obj.id,
            "log_id": f"BR{obj.id:05d}",
            "title": obj.title,
            "description": obj.description,
            "property_name": obj.property.property_name if obj.property else None,
            "block_name": obj.block_tower.block_name if obj.block_tower else None,
            "unit_name": obj.unit.unit_name if obj.unit else None,
            "priority": obj.priority,
            "channel": obj.channels,
            "recipients": obj.recipient_count,
            "delivered": obj.delivered_count,
            "failed": obj.failed_count,
            "sent_date": datetime_to_epoch_millis(obj.sent_date) if obj.sent_date else None,
            "status": obj.status,
            "scheduled_at": datetime_to_epoch_millis(obj.scheduled_at) if obj.scheduled_at else None,
            "banner_image": obj.banner_image,
            "send_by": _get_send_by(obj.created_by),
            "is_active": obj.is_active,
            "created": datetime_to_epoch_millis(obj.created),
            "modified": datetime_to_epoch_millis(obj.modified)
        })

    return prepare_response(
        message="Broadcasts fetched successfully",
        content={
            "content": content,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total_count": total_count,
                "total_pages": (total_count + page_size - 1) // page_size
            }
        },
        status=status.HTTP_200_OK
    )


@api_view(["GET", "PUT", "DELETE"])
@is_request_authenticated
def broadcast_detail_view(request, broadcast_id):
    broadcast = _broadcast_queryset_for_user(request).filter(
        pk=broadcast_id
    ).first()

    if not broadcast:
        return prepare_response(message="Broadcast not found", status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        return prepare_response(
            message="Broadcast fetched successfully",
            content={
                "id": broadcast.id,
                "log_id": f"BR{broadcast.id:05d}",
                "title": broadcast.title,
                "description": broadcast.description,
                "property": broadcast.property_id,
                "block_tower": broadcast.block_tower_id,
                "unit": broadcast.unit_id,
                "priority": broadcast.priority,
                "channel": broadcast.channels,
                "recipients": broadcast.recipient_count,
                "delivered": broadcast.delivered_count,
                "failed": broadcast.failed_count,
                "sent_date": datetime_to_epoch_millis(broadcast.sent_date) if broadcast.sent_date else None,
                "status": broadcast.status,
                "scheduled_at": datetime_to_epoch_millis(broadcast.scheduled_at) if broadcast.scheduled_at else None,
                "banner_image": broadcast.banner_image,
                "send_by": _get_send_by(broadcast.created_by),
                "is_active": broadcast.is_active,
                "created": datetime_to_epoch_millis(broadcast.created),
                "modified": datetime_to_epoch_millis(broadcast.modified)
            },
            status=status.HTTP_200_OK
        )

    if request.method == "PUT":
        try:
            body = json.loads(request.body)

            if "title" in body:
                title = body["title"].strip()

                if not title:
                    return prepare_response(message="title cannot be empty", status=status.HTTP_400_BAD_REQUEST)

                broadcast.title = title

            if "description" in body:
                description = body["description"].strip()

                if not description:
                    return prepare_response(message="description cannot be empty", status=status.HTTP_400_BAD_REQUEST)

                broadcast.description = description

            if "priority" in body:
                valid_priorities = {choice[0] for choice in constants.BROADCAST_PRIORITY_CHOICES}

                if body["priority"] not in valid_priorities:
                    return prepare_response(message="Invalid priority", status=status.HTTP_400_BAD_REQUEST)

                broadcast.priority = body["priority"]

            if "channels" in body:
                valid_channels = {choice[0] for choice in constants.BROADCAST_CHANNEL_CHOICES}

                if not isinstance(body["channels"], list):
                    return prepare_response(message="channels must be a list", status=status.HTTP_400_BAD_REQUEST)

                invalid_channels = set(body["channels"]) - valid_channels

                if invalid_channels:
                    return prepare_response(message=f"Invalid channel(s): {list(invalid_channels)}", status=status.HTTP_400_BAD_REQUEST)

                broadcast.channels = body["channels"]

            property_obj = broadcast.property
            block_obj = broadcast.block_tower
            unit_obj = broadcast.unit

            if "property" in body:
                if body["property"] is None:
                    property_obj = None
                    broadcast.property = None
                else:
                    property_obj = Property.objects.filter(pk=body["property"], is_active=True).first()

                    if not property_obj:
                        return prepare_response(message="Property not found", status=status.HTTP_404_NOT_FOUND)

                    broadcast.property = property_obj

            if "block_tower" in body:
                if body["block_tower"] is None:
                    block_obj = None
                    broadcast.block_tower = None
                else:
                    block_obj = PropertyBlocks.objects.filter(pk=body["block_tower"], is_active=True).select_related("property").first()

                    if not block_obj:
                        return prepare_response(message="Block not found", status=status.HTTP_404_NOT_FOUND)

                    broadcast.block_tower = block_obj

            if "unit" in body:
                if body["unit"] is None:
                    unit_obj = None
                    broadcast.unit = None
                else:
                    unit_obj = Unit.objects.filter(pk=body["unit"], is_active=True).first()

                    if not unit_obj:
                        return prepare_response(message="Unit not found", status=status.HTTP_404_NOT_FOUND)

                    broadcast.unit = unit_obj

            pmc_ids = _get_pmc_ids_for_user(request.user)

            if not _validate_broadcast_access(property_obj, block_obj, unit_obj, pmc_ids):
                return prepare_response(message="You do not have access to the selected property, block or unit", status=status.HTTP_403_FORBIDDEN)

            if "banner_image" in body:
                banner_image = body["banner_image"]

                if banner_image:
                    object_name = f"broadcast/{timezone.now().strftime('%Y%m%d%H%M%S%f')}.jpg"

                    try:
                        broadcast.banner_image = upload_file_to_s3_base64(
                            banner_image,
                            object_name
                        )
                    except Exception as e:
                        logger.exception("BROADCAST_IMAGE_UPLOAD_ERROR | error=%s", str(e))
                        return prepare_response(message="Failed to upload banner image", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                else:
                    broadcast.banner_image = banner_image

            if "status" in body:
                valid_statuses = {choice[0] for choice in constants.BROADCAST_STATUS_CHOICES}

                if body["status"] not in valid_statuses:
                    return prepare_response(message="Invalid broadcast status", status=status.HTTP_400_BAD_REQUEST)

                broadcast.status = body["status"]

            if "scheduled_at" in body:
                broadcast.scheduled_at = body["scheduled_at"]

            if "is_active" in body:
                broadcast.is_active = body["is_active"]

            broadcast.save()

            return prepare_response(
                message="Broadcast updated successfully",
                content={
                    "id": broadcast.id,
                    "log_id": f"BR{broadcast.id:05d}",
                    "send_by": _get_send_by(broadcast.created_by)
                },
                status=status.HTTP_200_OK
            )

        except json.JSONDecodeError:
            return prepare_response(message="Invalid JSON body", status=status.HTTP_400_BAD_REQUEST)

        except Exception as e:
            logger.exception(
                "BROADCAST_UPDATE_ERROR | broadcast_id=%d | error=%s",
                broadcast.id,
                str(e)
            )

            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    broadcast.is_active = False
    broadcast.status = "DELETED"

    broadcast.save(update_fields=["is_active", "status", "modified"])

    return prepare_response(message="Broadcast deleted successfully", status=status.HTTP_200_OK)


@api_view(["GET"])
@is_request_authenticated
def broadcast_report_view(request, broadcast_id):
    broadcast = _broadcast_queryset_for_user(request).filter(
        pk=broadcast_id
    ).first()

    if not broadcast:
        return prepare_response(message="Broadcast not found", status=status.HTTP_404_NOT_FOUND)

    recipients = BroadcastRecipient.objects.filter(
        broadcast=broadcast
    ).order_by("-id")

    recipient_details = []

    for recipient in recipients:
        recipient_details.append({
            "id": recipient.id,
            "email": recipient.email,
            "channel": recipient.channel,
            "status": recipient.status,
            "sent_at": datetime_to_epoch_millis(recipient.sent_at) if recipient.sent_at else None,
            "error_message": recipient.error_message
        })

    return prepare_response(
        message="Broadcast report fetched successfully",
        content={
            "id": broadcast.id,
            "log_id": f"BR{broadcast.id:05d}",
            "title": broadcast.title,
            "description": broadcast.description,
            "priority": broadcast.priority,
            "channel": broadcast.channels,
            "status": broadcast.status,
            "recipients": broadcast.recipient_count,
            "delivered": broadcast.delivered_count,
            "failed": broadcast.failed_count,
            "sent_date": datetime_to_epoch_millis(broadcast.sent_date) if broadcast.sent_date else None,
            "send_by": _get_send_by(broadcast.created_by),
            "recipient_details": recipient_details
        },
        status=status.HTTP_200_OK
    )


@api_view(["POST"])
@is_request_authenticated
def broadcast_resend_failed_view(request, broadcast_id):
    broadcast = _broadcast_queryset_for_user(request).filter(
        pk=broadcast_id
    ).first()

    if not broadcast:
        return prepare_response(message="Broadcast not found", status=status.HTTP_404_NOT_FOUND)

    failed_recipients = BroadcastRecipient.objects.filter(
        broadcast=broadcast,
        status="FAILED",
        channel="MAIL"
    )

    if not failed_recipients.exists():
        return prepare_response(message="No failed recipients found", status=status.HTTP_400_BAD_REQUEST)

    resent_count = 0
    failed_count = 0

    body_text = f"Hello,\n\n{broadcast.description}\n\nThank you,\nThe Units Team"

    body_html = f"""
    <html>
        <body>
            <h2>{broadcast.title}</h2>
            <p>{broadcast.description}</p>
            <br>
            <p>Thank you,<br>The Units Team</p>
        </body>
    </html>
    """

    for recipient in failed_recipients:
        try:
            ok = send_ses_email(
                recipient.email,
                broadcast.title,
                body_text,
                body_html
            )

            if ok:
                recipient.status = "DELIVERED"
                recipient.sent_at = timezone.now()
                recipient.error_message = None
                recipient.save(update_fields=["status", "sent_at", "error_message", "modified"])
                resent_count += 1
            else:
                recipient.status = "FAILED"
                recipient.error_message = "Email sending failed"
                recipient.save(update_fields=["status", "error_message", "modified"])
                failed_count += 1

        except Exception as e:
            recipient.status = "FAILED"
            recipient.error_message = str(e)
            recipient.save(update_fields=["status", "error_message", "modified"])
            failed_count += 1

            logger.exception(
                "BROADCAST_RESEND_ERROR | broadcast_id=%d | email=%s | error=%s",
                broadcast.id,
                recipient.email,
                str(e)
            )

    broadcast.delivered_count = BroadcastRecipient.objects.filter(
        broadcast=broadcast,
        status="DELIVERED"
    ).count()

    broadcast.failed_count = BroadcastRecipient.objects.filter(
        broadcast=broadcast,
        status="FAILED"
    ).count()

    broadcast.save(update_fields=["delivered_count", "failed_count", "modified"])

    return prepare_response(
        message="Failed recipients resend completed",
        content={
            "id": broadcast.id,
            "log_id": f"BR{broadcast.id:05d}",
            "resent_count": resent_count,
            "failed_count": broadcast.failed_count,
            "delivered": broadcast.delivered_count,
            "failed": broadcast.failed_count
        },
        status=status.HTTP_200_OK
    )


@api_view(["GET"])
@is_request_authenticated
def broadcast_export_view(request):
    search = request.GET.get("search", "").strip()
    priority = request.GET.get("priority")
    channel = request.GET.get("channel")
    status_filter = request.GET.get("status")
    property_id = request.GET.get("property_id")
    block_id = request.GET.get("block_tower_id")
    unit_id = request.GET.get("unit_id")

    qs = _broadcast_queryset_for_user(request)

    if search:
        qs = qs.filter(
            Q(title__icontains=search) |
            Q(description__icontains=search) |
            Q(property__property_name__icontains=search) |
            Q(block_tower__block_name__icontains=search) |
            Q(unit__unit_name__icontains=search)
        )

    if priority:
        qs = qs.filter(priority=priority)

    if channel:
        qs = qs.filter(channels__contains=[channel])

    if status_filter:
        qs = qs.filter(status=status_filter)

    if property_id:
        qs = qs.filter(property_id=property_id)

    if block_id:
        qs = qs.filter(block_tower_id=block_id)

    if unit_id:
        qs = qs.filter(unit_id=unit_id)

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="broadcast_export.csv"'

    writer = csv.writer(response)

    writer.writerow([
        "Log ID",
        "Announcement Title",
        "Property Name",
        "Block/Tower",
        "Unit Name",
        "Sent Date",
        "Priority",
        "Channel",
        "Recipients",
        "Delivered",
        "Failed",
        "Status",
        "Send By",
    ])

    for obj in qs:
        writer.writerow([
            f"BR{obj.id:05d}",
            obj.title,
            obj.property.property_name if obj.property else "",
            obj.block_tower.block_name if obj.block_tower else "",
            obj.unit.unit_name if obj.unit else "",
            obj.sent_date.strftime("%Y-%m-%d %H:%M:%S") if obj.sent_date else "",
            obj.priority,
            ", ".join(obj.channels) if obj.channels else "",
            obj.recipient_count,
            obj.delivered_count,
            obj.failed_count,
            obj.status,
            _get_send_by(obj.created_by)
        ])

    return response