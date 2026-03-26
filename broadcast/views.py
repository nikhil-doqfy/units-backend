import json
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from broadcast.models import Announcement, AnnouncementLog, AnnouncementRecipient
from property.models import  Unit
from user_service.models import UserProfile
from utilities import constants
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response

def format_announcement(ann, log=None):
    return {
        "id": ann.id,
        "log_id": ann.log_id,
        "title": ann.title,
        "description": ann.description,
        "priority": ann.priority,
        "status": ann.status,
        "scope": ann.scope,
        "property": {
            "key": ann.property_id,
            "value": ann.property.property_name if ann.property else "All",
        },
        "block": {
            "key": ann.block_id,
            "value": ann.block.block_name if ann.block else "All Blocks/Towers",
        },
        "unit": {
            "key": ann.unit_id,
            "value": ann.unit.unit_name if ann.unit else "All Units",
        },
        "channel": ann.channel,
        "channels": ann.channels if ann.channels else [ann.channel],
        "send_mail": ann.send_mail,
        "banner_image": ann.banner_image.url if ann.banner_image else None,
        "scheduled_at": ann.scheduled_at.isoformat() if ann.scheduled_at else None,
        "sent_at": ann.sent_at.isoformat() if ann.sent_at else None,
        "recipients": log.total_recipients if log else 0,
        "delivered": log.delivered_count if log else 0,
        "failed": log.failed_count if log else 0,
        "created_at": ann.created.isoformat() if ann.created else None,
    }


def format_recipient(r):
    return {
        "id": r.id,
        "tenant_id": r.tenant_id,
        "name": f"{r.tenant.user.first_name} {r.tenant.user.last_name}".strip(),
        "email": getattr(r.tenant, "email", None),
        "channel": r.channel,
        "status": r.status,
        "delivered_at": r.delivered_at.isoformat() if r.delivered_at else None,
        "failure_reason": r.failure_reason,
    }

def _base_qs():
    return Announcement.objects.select_related(
        "property", "block", "unit", "log"
    ).order_by("-id")

def _resolve_tenants(ann):
    qs = UserProfile.objects.all()

    if ann.scope == constants.ALL:
        return qs.filter(interested_properties__isnull=False).distinct()

    if ann.scope == constants.PROPERTY and ann.property_id:
        unit_ids = Unit.objects.filter(
            property_block_tower__property_id=ann.property_id
        ).values_list("id", flat=True)

        return qs.filter(
            interested_properties__property_unit_id__in=unit_ids
        ).distinct()

    if ann.scope == constants.BLOCK and ann.block_id:
        unit_ids = Unit.objects.filter(
            property_block_tower_id=ann.block_id
        ).values_list("id", flat=True)

        return qs.filter(
            interested_properties__property_unit_id__in=unit_ids
        ).distinct()

    if ann.scope == constants.UNIT and ann.unit_id:
        return qs.filter(
            interested_properties__property_unit_id=ann.unit_id
        ).distinct()

    return UserProfile.objects.none()

def _dispatch(ann, created_by):
    tenants = list(_resolve_tenants(ann))

    total = len(tenants)
    delivered = 0
    failed = 0
    email_targets = []

    channels = ann.channels if isinstance(ann.channels, list) else []
    if not channels:
        channels = [ann.channel]

    for tenant in tenants:
        for ch in channels:

            existing = AnnouncementRecipient.objects.filter(
                announcement=ann,
                tenant=tenant,
                channel=ch
            ).first()

            if existing:
                if existing.status == "DELIVERED":
                    delivered += 1
                    continue

                existing.status = "DELIVERED"
                existing.delivered_at = timezone.now()
                existing.failure_reason = None
                existing.save(update_fields=["status", "delivered_at", "failure_reason"])

                delivered += 1

                if ch == constants.EMAIL and getattr(tenant, "email", None):
                    email_targets.append(tenant.email)
                continue

            try:
                AnnouncementRecipient.objects.create(
                    created_by=created_by,
                    announcement=ann,
                    tenant=tenant,
                    channel=ch,
                    status="DELIVERED",
                    delivered_at=timezone.now(),
                )
                delivered += 1

                if ch == constants.EMAIL and getattr(tenant, "email", None):
                    email_targets.append(tenant.email)

            except Exception as exc:
                AnnouncementRecipient.objects.create(
                    created_by=created_by,
                    announcement=ann,
                    tenant=tenant,
                    channel=ch,
                    status="FAILED",
                    failure_reason=str(exc),
                )
                failed += 1

    if email_targets:
        try:
            send_mail(
                subject=ann.title,
                message=ann.description,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=email_targets,
                fail_silently=True,
            )
        except Exception:
            pass

    log, _ = AnnouncementLog.objects.get_or_create(
        announcement=ann,
        defaults={"created_by": created_by}
    )

    log.total_recipients = total
    log.delivered_count = delivered
    log.failed_count = failed
    log.save()

    ann.status = constants.SENT
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
                return prepare_response(message="Not found", status=404)

            return prepare_response(
                content=format_announcement(ann, getattr(ann, "log", None)),
                status=200
            )

        qs = _base_qs()

        page = max(int(request.GET.get("page", 1)), 1)
        page_size = min(int(request.GET.get("page_size", 10)), 100)

        total = qs.count()
        data = qs[(page - 1) * page_size: page * page_size]

        return prepare_response(
            content=[format_announcement(a, getattr(a, "log", None)) for a in data],
            pagination={"total_records": total, "page": page, "page_size": page_size},
            status=200
        )

    elif request.method == "POST":
        data = json.loads(request.body)

        raw_channels = data.get("channels") or []
        if isinstance(raw_channels, str):
            raw_channels = [c.strip().upper() for c in raw_channels.split(",") if c.strip()]

        if not raw_channels:
            raw_channels = [constants.APP]

        ann = Announcement.objects.create(
            created_by=user_profile.user,
            title=data.get("title"),
            description=data.get("description"),
            channels=raw_channels,
            channel=raw_channels[0],
            status=constants.SENT if data.get("send_now") else constants.DRAFT,
        )

        if data.get("send_now"):
            _dispatch(ann, user_profile.user)

        return prepare_response(message="Created", content={"id": ann.id}, status=201)

    elif request.method == "DELETE":
        ann_id = request.GET.get("announcement_id")

        if not ann_id:
            return prepare_response(message="announcement_id required", status=400)

        updated = Announcement.objects.filter(
            id=ann_id,
            status__in=[constants.DRAFT, constants.SCHEDULED]
        ).update(status=constants.DELETED)

        if not updated:
            return prepare_response(message="Cannot delete", status=404)

        return prepare_response(message="Deleted", status=200)

    return prepare_response(message="Method not allowed", status=405)


@is_request_authenticated
def announcement_send(request):
    if request.method != "POST":
        return prepare_response(message="Invalid method", status=405)

    data = json.loads(request.body)
    ann = Announcement.objects.filter(id=data.get("announcement_id")).first()

    if not ann:
        return prepare_response(message="Not found", status=404)

    if ann.status == constants.SENT:
        return prepare_response(message="Already sent", status=400)

    _dispatch(ann, request.user.user)

    return prepare_response(
        message="Sent successfully",
        content={"id": ann.id, "log_id": ann.log_id},
        status=200
    )

@is_request_authenticated
def announcement_banner(request):
    if request.method != "POST":
        return prepare_response(message="Invalid method", status=405)

    ann = Announcement.objects.filter(
        id=request.POST.get("announcement_id")
    ).first()

    if not ann:
        return prepare_response(message="Not found", status=404)

    banner = request.FILES.get("banner_image")

    if not banner:
        return prepare_response(message="File required", status=400)

    ann.banner_image = banner
    ann.save(update_fields=["banner_image"])

    return prepare_response(
        message="Uploaded",
        content={"url": ann.banner_image.url},
        status=200
    )

@is_request_authenticated
def announcement_recipients(request):
    if request.method != "GET":
        return prepare_response(message="Invalid method", status=405)

    ann_id = request.GET.get("announcement_id")

    qs = AnnouncementRecipient.objects.filter(
        announcement_id=ann_id
    ).select_related("tenant__user")

    return prepare_response(
        content=[format_recipient(r) for r in qs],
        status=200
    )