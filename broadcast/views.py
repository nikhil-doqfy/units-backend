import csv
import json
from datetime import datetime
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.utils import timezone
from broadcast.models import Announcement, AnnouncementLog, AnnouncementRecipient
from property.models import Property, PropertyBlocks, Unit
from property_management.models import AuditLog
from user_service.models import UserProfile
from utilities import constants, status
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response

def format_announcement(ann, log=None):
    return {
        "id":          ann.id,
        "log_id":      ann.log_id,
        "title":       ann.title,
        "description": ann.description,
        "priority":    ann.priority,
        "status":      ann.status,
        "scope":       ann.scope,
        "property": {
            "key":   ann.property_id,
            "value": ann.property.property_name if ann.property else "All",
        },
        "block": {
            "key":   ann.block_id,
            "value": ann.block.block_name if ann.block else "All Blocks/Towers",
        },
        "unit": {
            "key":   ann.unit_id,
            "value": ann.unit.unit_name if ann.unit else "All Units",
        },
        "channel":      ann.channel,
        "channels":     ann.channels.split(",") if ann.channels else [ann.channel],
        "send_mail":    ann.send_mail,
        "banner_image": ann.banner_image.url if ann.banner_image else None,
        "scheduled_at": ann.scheduled_at.isoformat() if ann.scheduled_at else None,
        "sent_at":      ann.sent_at.isoformat()      if ann.sent_at      else None,
        "recipients":   log.total_recipients if log else 0,
        "delivered":    log.delivered_count  if log else 0,
        "failed":       log.failed_count     if log else 0,
        "created_at": ann.created.isoformat() if ann.created else None,
    }

def format_recipient(r):
    return {
        "id":           r.id,
        "tenant_id":    r.tenant_id,
        "name":         f"{r.tenant.user.first_name} {r.tenant.user.last_name}".strip(),
        "email":        getattr(r.tenant, "email", None),
        "channel":      r.channel,
        "status":       r.status,
        "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
        "failure_reason": r.failure_reason,
    }

def _base_qs():
    return Announcement.objects.select_related(
        "property", "block", "unit", "log"
    ).order_by("-id")

def _resolve_tenants(ann):
    qs = UserProfile.objects.all()

    if ann.scope == "ALL":
        return qs.filter(interested_properties__isnull=False).distinct()

    if ann.scope == "PROPERTY" and ann.property_id:
        unit_ids = Unit.objects.filter(
            property_block_tower__property_id=ann.property_id
        ).values_list("id", flat=True)
        return qs.filter(
            interested_properties__property_unit_id__in=unit_ids
        ).distinct()

    if ann.scope == "BLOCK" and ann.block_id:
        unit_ids = Unit.objects.filter(
            property_block_tower_id=ann.block_id
        ).values_list("id", flat=True)
        return qs.filter(
            interested_properties__property_unit_id__in=unit_ids
        ).distinct()

    if ann.scope == "UNIT" and ann.unit_id:
        return qs.filter(
            interested_properties__property_unit_id=ann.unit_id
        ).distinct()

    return UserProfile.objects.none()

def _dispatch(ann, created_by):
    """Resolve recipients, mark delivery, send e-mail, update the log."""
    tenants   = list(_resolve_tenants(ann))
    total     = len(tenants)
    delivered = 0
    failed    = 0
    email_targets = []

    channels = [c.strip().upper() for c in (ann.channels or "").split(",") if c.strip()]
    if not channels:
        channels = [ann.channel]

    for tenant in tenants:
        for ch in channels:
            existing = AnnouncementRecipient.objects.filter(
                announcement=ann, tenant=tenant, channel=ch
            ).first()

            if existing:
                if existing.status == "DELIVERED":
                    delivered += 1
                    continue

                existing.status        = "DELIVERED"
                existing.delivered_at  = timezone.now()
                existing.failure_reason = None
                existing.save(update_fields=["status", "delivered_at", "failure_reason"])
                delivered += 1
                if ch == constants.EMAIL and getattr(tenant, "email", None):
                    email_targets.append(tenant.email)
                continue

            try:
                AnnouncementRecipient.objects.create(
                    created_by   = created_by,
                    announcement = ann,
                    tenant       = tenant,
                    channel      = ch,
                    status       = "DELIVERED",
                    delivered_at = timezone.now(),
                )
                delivered += 1
                if ch == constants.EMAIL and getattr(tenant, "email", None):
                    email_targets.append(tenant.email)
            except Exception as exc:
                AnnouncementRecipient.objects.create(
                    created_by     = created_by,
                    announcement   = ann,
                    tenant         = tenant,
                    channel        = ch,
                    status         = "FAILED",
                    failure_reason = str(exc),
                )
                failed += 1

    if email_targets:
        try:
            send_mail(
                subject       = ann.title,
                message       = ann.description,
                from_email    = settings.DEFAULT_FROM_EMAIL,
                recipient_list = email_targets,
                fail_silently  = True,
            )
        except Exception:
            pass

    log = AnnouncementLog.objects.filter(announcement=ann).first()
    if log:
        log.total_recipients = total
        log.delivered_count  = delivered
        log.failed_count     = failed
        log.save(update_fields=["total_recipients", "delivered_count", "failed_count"])
    else:
        AnnouncementLog.objects.create(
            created_by       = created_by,
            announcement     = ann,
            total_recipients = total,
            delivered_count  = delivered,
            failed_count     = failed,
        )

    ann.status  = "SENT"
    ann.sent_at = timezone.now()
    ann.save(update_fields=["status", "sent_at"])

@is_request_authenticated
def announcement(request):
    user_profile = request.user

    if request.method == "GET":
        ann_id = request.GET.get("announcement_id")

        if ann_id:
            ann = _base_qs().filter(id=ann_id).first()
            if not ann:
                return prepare_response(
                    message=constants.ANNOUNCEMENT_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND,
                )
            return prepare_response(
                content=format_announcement(ann, getattr(ann, "log", None)),
                status=status.HTTP_200_OK,
            )

        tab = request.GET.get("tab", "SENT").upper()
        if tab not in {"SENT", "SCHEDULED", "DRAFT", "DELETED"}:
            tab = "SENT"

        property_id = request.GET.get("property_id", "").strip()
        block_id    = request.GET.get("block_id",    "").strip()
        unit_id     = request.GET.get("unit_id",     "").strip()
        page        = max(int(request.GET.get("page",      1)),  1)
        page_size   = min(int(request.GET.get("page_size", 10)), 100)
        export      = request.GET.get("export", "").strip().lower()

        qs = _base_qs().filter(status=tab)

        if property_id:
            qs = qs.filter(property_id=property_id)
        if block_id:
            qs = qs.filter(block_id=block_id)
        if unit_id:
            qs = qs.filter(unit_id=unit_id)

        # CSV export
        if export == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="announcements.csv"'
            writer = csv.writer(response)
            writer.writerow([
                "Sl.No", "Log ID", "Announcement Title", "Property Name",
                "Block / Tower", "Unit", "Sent Date",
                "Channel", "Recipients", "Delivered", "Failed",
            ])
            for i, ann in enumerate(qs, start=1):
                f = format_announcement(ann, getattr(ann, "log", None))
                writer.writerow([
                    i, f["log_id"], f["title"],
                    f["property"]["value"],
                    f["block"]["value"],
                    f["unit"]["value"],
                    f["sent_at"] or "",
                    f["channel"],
                    f["recipients"], f["delivered"], f["failed"],
                ])
            return response

        # paginated list
        total   = qs.count()
        start   = (page - 1) * page_size
        page_qs = qs[start:start + page_size]

        return prepare_response(
            content=[format_announcement(a, getattr(a, "log", None)) for a in page_qs],
            pagination={
                "total_records": total,
                "page":          page,
                "page_size":     page_size,
            },
            status=status.HTTP_200_OK,
        )

    elif request.method == "POST":
        data = json.loads(request.body)

        title       = (data.get("title")       or "").strip()
        description = (data.get("description") or "").strip()

        if not title:
            return prepare_response(
                message="title is required",
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not description:
            return prepare_response(
                message="description is required",
                status=status.HTTP_400_BAD_REQUEST,
            )

        scope          = data.get("scope",    "ALL")
        property_id    = data.get("property_id")
        block_id       = data.get("block_id")
        unit_id        = data.get("unit_id")
        raw_channels   = data.get("channels") or []
        if isinstance(raw_channels, str):
            raw_channels = [c.strip().upper() for c in raw_channels.split(",") if c.strip()]
        elif isinstance(raw_channels, list):
            raw_channels = [str(c).strip().upper() for c in raw_channels if str(c).strip()]
        else:
            raw_channels = []

        if not raw_channels:
            raw_channels = [constants.APP]

        channel = raw_channels[0]
        channels = ",".join(raw_channels)
        send_mail_flag = constants.EMAIL in raw_channels
        send_now       = bool(data.get("send_now",  False))

        prop  = Property.objects.filter(id=property_id).first() if property_id else None
        block = PropertyBlocks.objects.filter(id=block_id).first() if block_id else None
        unit  = Unit.objects.filter(id=unit_id).first()           if unit_id   else None

        scheduled_at = None
        if data.get("scheduled_at"):
            try:
                scheduled_at = datetime.fromisoformat(data["scheduled_at"])
            except ValueError:
                return prepare_response(
                    message="Invalid scheduled_at. Use ISO 8601 format.",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        if send_now:
            ann_status = "SENT"
        elif scheduled_at:
            ann_status = "SCHEDULED"
        else:
            ann_status = "DRAFT"

        ann = Announcement.objects.create(
            created_by   = user_profile.user,
            title        = title,
            description  = description,
            priority     = data.get("priority") or constants.NORMAL,
            status       = ann_status,
            scope        = scope,
            property     = prop,
            block        = block,
            unit         = unit,
            channel      = channel,
            channels     = channels,
            send_mail    = send_mail_flag,
            scheduled_at = scheduled_at,
        )

        if send_now:
            _dispatch(ann, user_profile.user)

        AuditLog(request, f"Announcement '{ann.title}' created", constants.CREATED)
        return prepare_response(
            message="Announcement created successfully",
            content={"id": ann.id, "log_id": ann.log_id},
            status=status.HTTP_201_CREATED,
        )

    elif request.method == "PUT":
        data = json.loads(request.body)

        ann = Announcement.objects.filter(id=data.get("announcement_id")).first()
        if not ann:
            return prepare_response(
                message=constants.ANNOUNCEMENT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND,
            )
        if ann.status == "SENT":
            return prepare_response(
                message="Sent announcements cannot be edited",
                status=status.HTTP_400_BAD_REQUEST,
            )

        for field in ("title", "description", "priority", "scope"):
            if data.get(field) is not None:
                setattr(ann, field, data[field])

        if data.get("channels") is not None:
            raw_channels = data.get("channels")
            if isinstance(raw_channels, str):
                parsed = [c.strip().upper() for c in raw_channels.split(",") if c.strip()]
            elif isinstance(raw_channels, list):
                parsed = [str(c).strip().upper() for c in raw_channels if str(c).strip()]
            else:
                parsed = []
            if parsed:
                ann.channels = ",".join(parsed)
                ann.channel = parsed[0]
                ann.send_mail = constants.EMAIL in parsed

        if data.get("channel") is not None:
            ann.channel = data["channel"]

        if "send_mail" in data:
            ann.send_mail = bool(data["send_mail"])

        if data.get("scheduled_at"):
            try:
                ann.scheduled_at = datetime.fromisoformat(data["scheduled_at"])
                ann.status       = "SCHEDULED"
            except ValueError:
                return prepare_response(
                    message="Invalid scheduled_at format",
                    status=status.HTTP_400_BAD_REQUEST,
                )

        ann.save()
        AuditLog(request, f"Announcement '{ann.title}' updated", constants.UPDATED)
        return prepare_response(
            message="Updated successfully",
            content={"id": ann.id},
            status=status.HTTP_200_OK,
        )

    elif request.method == "DELETE":
        ann_id = request.GET.get("announcement_id")
        if not ann_id:
            return prepare_response(
                message="announcement_id is required",
                status=status.HTTP_400_BAD_REQUEST,
            )
        updated = Announcement.objects.filter(
            id=ann_id, status__in=["DRAFT", "SCHEDULED"]
        ).update(status="DELETED")
        if not updated:
            return prepare_response(
                message="Announcement not found or cannot be deleted",
                status=status.HTTP_404_NOT_FOUND,
            )
        AuditLog(request, f"Announcement #{ann_id} deleted", constants.DELETED)
        return prepare_response(message="Deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_405_METHOD_NOT_ALLOWED,
    )

@is_request_authenticated
def announcement_send(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    data = json.loads(request.body)
    ann  = Announcement.objects.filter(id=data.get("announcement_id")).first()
    if not ann:
        return prepare_response(
            message=constants.ANNOUNCEMENT_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND,
        )
    if ann.status == "SENT":
        return prepare_response(
            message="Already sent",
            status=status.HTTP_400_BAD_REQUEST,
        )
    if ann.status == "DELETED":
        return prepare_response(
            message="Cannot send a deleted announcement",
            status=status.HTTP_400_BAD_REQUEST,
        )

    _dispatch(ann, request.user.user)
    AuditLog(request, f"Announcement '{ann.title}' dispatched", constants.UPDATED)
    return prepare_response(
        message="Announcement sent successfully",
        content={"id": ann.id, "log_id": ann.log_id},
        status=status.HTTP_200_OK,
    )

@is_request_authenticated
def announcement_banner(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    ann = Announcement.objects.filter(
        id=request.POST.get("announcement_id")
    ).first()
    if not ann:
        return prepare_response(
            message=constants.ANNOUNCEMENT_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND,
        )

    banner = request.FILES.get("banner_image")
    if not banner:
        return prepare_response(
            message="banner_image file is required",
            status=status.HTTP_400_BAD_REQUEST,
        )
    if banner.size > 5 * 1024 * 1024:
        return prepare_response(
            message="Max file size is 5 MB",
            status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        )

    ann.banner_image = banner
    ann.save(update_fields=["banner_image"])

    AuditLog(request, f"Banner uploaded for '{ann.title}'", constants.UPDATED)
    return prepare_response(
        message="Banner uploaded successfully",
        content={"url": ann.banner_image.url},
        status=status.HTTP_200_OK,
    )

@is_request_authenticated
def announcement_recipients(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    ann_id     = request.GET.get("announcement_id")
    rec_status = request.GET.get("status", "").strip().upper()
    page       = max(int(request.GET.get("page",      1)),  1)
    page_size  = min(int(request.GET.get("page_size", 20)), 100)

    if not ann_id:
        return prepare_response(
            message="announcement_id is required",
            status=status.HTTP_400_BAD_REQUEST,
        )

    qs = AnnouncementRecipient.objects.filter(
        announcement_id=ann_id
    ).select_related("tenant__user").order_by("id")

    if rec_status in ("DELIVERED", "FAILED", "PENDING"):
        qs = qs.filter(status=rec_status)

    total   = qs.count()
    start   = (page - 1) * page_size
    page_qs = qs[start:start + page_size]

    return prepare_response(
        content=[format_recipient(r) for r in page_qs],
        pagination={
            "total_records": total,
            "page":          page,
            "page_size":     page_size,
        },
        status=status.HTTP_200_OK,
    )