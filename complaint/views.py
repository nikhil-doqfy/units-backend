import json
import uuid
from django.utils import timezone
from plugins.logger_plugin import get_logger
from property_management.utils import audit_logs
from utilities.helper_functions import prepare_response, fetch_s3_presigned_url, upload_file_to_s3_base64
from utilities.decorator import is_request_authenticated
from utilities import constants, status
from complaint.models import (
    Complaint, ComplaintImages, ComplaintTimeline,
    ComplaintActivityHistory, ServiceProvider, ComplaintBroadcast,
    Appointment, AppointmentSlot, ComplaintRating,
)
from complaint.serializers import serialize_complaint
from complaint.utility import (
    get_excluded_providers,
    auto_broadcast,
    auto_assign_best_technician,
    format_work_duration,
)
from complaint.email_services import (
    email_complaint_created,
    email_complaint_broadcasted,
    email_complaint_accepted,
    email_complaint_declined,
    email_no_technician_available,
    email_work_started,
    email_work_completed,
    email_complaint_closed,
    email_slot_selected,
)
from property.models import PropertyManagmentCompany, Unit
from notification.utils import (
    notify_complaint_created,
    notify_complaint_assigned,
    notify_complaint_resolved,
    notify_complaint_closed,
)
from django.db.models import Q
import datetime


logger = get_logger(__name__)
# =====================================================
# STEP 1 - complaint_api (GET ALL + POST CREATE)
# =====================================================

@is_request_authenticated
def complaint_api(request):

    # ── GET ALL ───────────────────────────────────────────────────
    if request.method == "GET":
        company = PropertyManagmentCompany.objects.filter(
            company_staff=request.user,
            is_active=True
        ).first()
        if not company:
            logger.warning(
                "COMPLAINT_LIST_FETCH_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id)
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        complaints = Complaint.objects.filter(
            company=company,
            is_active=True
        ).order_by('-id')

        # ── Filters ───────────────────────────────────────────────
        complaint_status = request.GET.get("status", "").strip().upper()
        property_id = request.GET.get("property_id", "").strip()
        search = request.GET.get("search", "").strip()

        if complaint_status:
            complaints = complaints.filter(status=complaint_status)

        if property_id:
            complaints = complaints.filter(
                unit__property_block_tower__property_id=property_id
            )

        if search:
            complaints = complaints.filter(
                Q(code__icontains=search) |
                Q(unit__unit_name__icontains=search) |
                Q(unit__dm_no__icontains=search) |
                Q(unit__property_block_tower__property__property_name__icontains=search) |
                Q(raised_by__user__first_name__icontains=search) |
                Q(raised_by__user__last_name__icontains=search)
            ).distinct()

        # ── Stats ─────────────────────────────────────────────────
        total = complaints.count()
        completed = complaints.filter(status=constants.CLOSED).count()
        in_progress = complaints.filter(status=constants.IN_PROGRESS).count()
        rejected = complaints.filter(status=constants.PENDING).count()

        # ── Pagination ────────────────────────────────────────────
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        start = (page - 1) * page_size
        paginated = complaints[start:start + page_size]

        return prepare_response(
            content=[serialize_complaint(c) for c in paginated],
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            pagination={
                "total_records": total,
                "page": page,
                "page_size": page_size,
                "stats": {
                    "total_complaints": total,
                    "completed": completed,
                    "in_progress": in_progress,
                    "rejected": rejected,
                }
            },
            status=status.HTTP_200_OK
        )

    # ── POST CREATE ───────────────────────────────────────────────
    elif request.method == "POST":
        body = json.loads(request.body)

        company = PropertyManagmentCompany.objects.filter(
            company_staff=request.user,
            is_active=True
        ).first()
        if not company:
            logger.warning(
                "COMPLAINT_CREATE_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id)
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        unit_id = body.get("unit_id")
        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            logger.warning(
                "COMPLAINT_CREATE_FAILED | user_id=%s | unit_id=%s | reason=UNIT_NOT_FOUND",
                request.user.id, unit_id)
            return prepare_response(
                message=constants.UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        description = body.get("description")
        if not description:
            logger.warning(
                "COMPLAINT_CREATE_FAILED | user_id=%s | reason=DESCRIPTION_MISSING",
                request.user.id)
            return prepare_response(
                message="Description is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        service_type = body.get("service_type")
        if not service_type:
            logger.warning(
                "COMPLAINT_CREATE_FAILED | user_id=%s | reason=SERVICE_TYPE_MISSING",
                request.user.id)
            return prepare_response(
                message="Service type is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        slots = body.get("slots", [])
        if not slots:
            logger.warning(
                "COMPLAINT_CREATE_FAILED | user_id=%s | reason=SLOTS_MISSING",
                request.user.id)
            return prepare_response(
                message="At least one appointment slot is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Create complaint ───────────────────────────────────────
        complaint = Complaint.objects.create(
            unit=unit,
            raised_by=request.user,
            company=company,
            description=description,
            service_type=service_type,
            priority=body.get("priority", constants.MEDIUM),
            status=constants.PENDING,
            created_by=request.user.user
        )

        # ── Upload images ──────────────────────────────────────────
        images = body.get("images", [])
        image_count = 0
        for image in images:
            file_name = image.get("file_name")
            file_data = image.get("file_data")
            if file_name and file_data:
                object_name = f"complaints/{complaint.code}/{uuid.uuid4()}_{file_name}"
                file_url = upload_file_to_s3_base64(
                    file_data=file_data,
                    object_name=object_name
                )
                ComplaintImages.objects.create(
                    complaint=complaint,
                    image_path=file_url,
                    file_name=file_name,
                    created_by=request.user.user
                )
                image_count += 1

        # ── Create appointment with slots ──────────────────────────
        appointment = Appointment.objects.create(
            complaint=complaint,
            service_provider=None,
            status=constants.APPOINTMENT_PROPOSED,
            note=body.get("note"),
            created_by=request.user.user
        )

        slot_count = 0
        for slot_epoch in slots:
            slot_time = timezone.datetime.fromtimestamp(slot_epoch, tz=datetime.timezone.utc)
            AppointmentSlot.objects.create(
                appointment=appointment,
                proposed_time=slot_time,
                created_by=request.user.user
            )
            slot_count += 1

        complaint.current_appointment = appointment
        complaint.save()

        # ── Auto broadcast ─────────────────────────────────────────
        providers_count = auto_broadcast(complaint, company)

        # ── Timeline ───────────────────────────────────────────────
        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.CREATED,
            note=f"Complaint created with {slot_count} slots and {image_count} images. Broadcasted to {providers_count} providers.",
            created_by=request.user.user
        )

        # ── Activity ───────────────────────────────────────────────
        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} raised a {complaint.get_service_type_display()} complaint.",
            created_by=request.user.user
        )
        
        audit_logs(
            request,
            f"{request.user.user.first_name} raised complaint {complaint.code}.",
            "COMPLAINT_CREATED"
        )
        # ── Emails ─────────────────────────────────────────────────
        email_complaint_created(complaint)
        if providers_count > 0:
            email_complaint_broadcasted(complaint, providers_count)

        notify_complaint_created(complaint.raised_by, complaint)

        logger.info(
            "COMPLAINT_CREATED | user_id=%s | complaint_code=%s | unit_id=%s | image_count=%d | slot_count=%d | providers_broadcasted=%d",
            request.user.id, complaint.code, unit_id, image_count, slot_count, providers_count)
        return prepare_response(
            content={"code": complaint.code},
            message=constants.COMPLAINT_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    # ── PUT ───────────────────────────────────────────────────────
    elif request.method == "PUT":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(message="code is required", status=status.HTTP_400_BAD_REQUEST)

        company = PropertyManagmentCompany.objects.filter(company_staff=request.user, is_active=True).first()
        if not company:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        complaint = Complaint.objects.filter(code=code, company=company, is_active=True).first()
        if not complaint:
            return prepare_response(message=constants.COMPLAINT_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        unit_id = body.get("unit_id")
        if unit_id:
            unit = Unit.objects.filter(id=unit_id).first()
            if not unit:
                return prepare_response(message=constants.UNIT_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            complaint.unit = unit

        complaint.description = body.get("description", complaint.description)
        complaint.service_type = body.get("service_type", complaint.service_type)
        complaint.priority = body.get("priority", complaint.priority)
        complaint.status = body.get("status", complaint.status)
        complaint.save()

        appointment = complaint.current_appointment
        if appointment:
            appointment.note = body.get("note", appointment.note)
            appointment.save()

        slots = body.get("slots")
        if slots is not None and appointment:
            AppointmentSlot.objects.filter(appointment=appointment).delete()
            for slot_epoch in slots:
                slot_time = timezone.datetime.fromtimestamp(slot_epoch, tz=datetime.timezone.utc)
                AppointmentSlot.objects.create(
                    appointment=appointment,
                    proposed_time=slot_time,
                    created_by=request.user.user
                )

        delete_image_ids = body.get("delete_image_ids", [])
        if delete_image_ids:
            ComplaintImages.objects.filter(complaint=complaint, id__in=delete_image_ids).delete()

        images = body.get("images", [])
        for image in images:
            file_name = image.get("file_name")
            file_data = image.get("file_data")
            if file_name and file_data:
                object_name = f"complaints/{complaint.code}/{uuid.uuid4()}_{file_name}"
                file_url = upload_file_to_s3_base64(file_data=file_data, object_name=object_name)
                ComplaintImages.objects.create(
                    complaint=complaint,
                    image_path=file_url,
                    file_name=file_name,
                    created_by=request.user.user
                )

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.UPDATED,
            note="Complaint details updated.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} updated the complaint.",
            created_by=request.user.user
        )

        audit_logs(
            request,
            f"{request.user.user.first_name} updated complaint {complaint.code}.",
            "COMPLAINT_UPDATED"
        )

        return prepare_response(
            content=serialize_complaint(complaint),
            message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    # ── DELETE ────────────────────────────────────────────────────
    elif request.method == "DELETE":
        code = request.GET.get("code")
        if not code:
            return prepare_response(message="code is required", status=status.HTTP_400_BAD_REQUEST)

        company = PropertyManagmentCompany.objects.filter(company_staff=request.user, is_active=True).first()
        if not company:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        complaint = Complaint.objects.filter(code=code, company=company, is_active=True).first()
        if not complaint:
            return prepare_response(message=constants.COMPLAINT_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        audit_logs(
            request,
            f"{request.user.user.first_name} deleted complaint {complaint.code}.",
            "COMPLAINT_DELETED"
        )
        
        complaint.delete()
        return prepare_response(
            message=constants.COMPLAINT_DELETED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# complaint_detail_api - GET + PUT + DELETE
# code comes from query param (?code=CMP001) for GET/DELETE
# code comes from body for PUT
# =====================================================

@is_request_authenticated
def complaint_detail_api(request):

    company = PropertyManagmentCompany.objects.filter(
        company_staff=request.user,
        is_active=True
    ).first()
    if not company:
        return prepare_response(
            message=constants.COMPANY_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        code = request.GET.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            company=company,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        data = serialize_complaint(complaint)

        data["timeline"] = [
            {
                "id": t.id,
                "timeline_status": {
                    "key": t.timeline_status,
                    "value": t.get_timeline_status_display()
                },
                "user": {
                    "id": t.user.id,
                    "name": f"{t.user.user.first_name} {t.user.user.last_name}".strip(),
                } if t.user else None,
                "note": t.note,
                "time": int(t.time.timestamp()) if t.time else None,
            }
            for t in complaint.timeline.all().order_by("created")
        ]

        data["activity_history"] = [
            {
                "id": a.id,
                "message": a.message,
                "user": {
                    "id": a.user.id,
                    "name": f"{a.user.user.first_name} {a.user.user.last_name}".strip(),
                } if a.user else None,
                "created": int(a.created.timestamp()) if a.created else None,
            }
            for a in complaint.activity_history.all().order_by("-created")
        ]

        data["broadcasts"] = [
            {
                "id": b.id,
                "service_provider": {
                    "id": b.service_provider.id,
                    "name": b.service_provider.name,
                    "phone": b.service_provider.phone,
                    "avg_rating": str(b.service_provider.avg_rating),
                },
                "is_priority": b.is_priority,
                "priority_score": str(b.priority_score),
                "is_accepted": b.is_accepted,
                "is_rejected": b.is_rejected,
                "is_expired": b.is_expired,
                "expires_at": int(b.expires_at.timestamp()) if b.expires_at else None,
                "accepted_at": int(b.accepted_at.timestamp()) if b.accepted_at else None,
            }
            for b in complaint.broadcasts.all().order_by("-priority_score")
        ]

        provider = complaint.assigned_to.first()

        assigned_broadcast = None
        if provider:
            assigned_broadcast = ComplaintBroadcast.objects.filter(
                complaint=complaint,
                service_provider=provider,
                is_accepted=True
            ).order_by("-accepted_at").first()

        data["assigned_engineer"] = {
            "id": provider.id,
            "name": provider.name,
            "phone": provider.phone,
            "avg_rating": str(provider.avg_rating),
            "assigned_at": (
                int(assigned_broadcast.accepted_at.timestamp())
                if assigned_broadcast and assigned_broadcast.accepted_at else None
            ),
        } if provider else None

        data["timeline_summary"] = [
            {
                "title": "Issue raised",
                "date": int(complaint.created.timestamp()) if complaint.created else None,
                "name": (
                    f"{complaint.raised_by.user.first_name} {complaint.raised_by.user.last_name}".strip()
                    if complaint.raised_by else None
                ),
            },
            {
                "title": "Assigned Engineer",
                "date": (
                    int(assigned_broadcast.accepted_at.timestamp())
                    if assigned_broadcast and assigned_broadcast.accepted_at else None
                ),
                "name": provider.name if provider else None,
            },
            {
                "title": "In Progress",
                "date": int(complaint.work_started_at.timestamp()) if complaint.work_started_at else None,
                "name": provider.name if provider else None,
            },
            {
                "title": "Completed",
                "date": int(complaint.work_completed_at.timestamp()) if complaint.work_completed_at else None,
                "name": provider.name if provider else None,
            },
        ]

        appointment = complaint.current_appointment
        if appointment:
            selected_slot = AppointmentSlot.objects.filter(
                appointment=appointment,
                is_selected=True
            ).first()

            data["appointment"] = {
                "id": appointment.id,
                "status": appointment.status,
                "note": appointment.note,
                "selected_slot": (
                    int(selected_slot.proposed_time.timestamp())
                    if selected_slot else None
                ),
                "all_slots": [
                    {
                        "id": slot.id,
                        "proposed_time": int(slot.proposed_time.timestamp()),
                        "is_selected": slot.is_selected
                    }
                    for slot in AppointmentSlot.objects.filter(appointment=appointment)
                ]
            }
        else:
            data["appointment"] = None

        rating = ComplaintRating.objects.filter(complaint=complaint).first()
        data["rating"] = {
            "rating": rating.rating,
            "feedback": rating.feedback
        } if rating else None

        previous_complaints = Complaint.objects.filter(
            unit=complaint.unit,
            is_active=True
        ).exclude(id=complaint.id).order_by("-id")

        previous_search = request.GET.get("previous_search", "").strip()
        previous_status = request.GET.get("previous_status", "").strip().upper()

        if previous_search:
            previous_complaints = previous_complaints.filter(
                Q(code__icontains=previous_search) |
                Q(description__icontains=previous_search) |
                Q(service_type__icontains=previous_search)
            )

        if previous_status:
            previous_complaints = previous_complaints.filter(status=previous_status)

        data["previous_complaints"] = [
            {
                "id": c.id,
                "code": c.code,
                "description": c.description,
                "status": c.status,
                "priority": c.priority,
                "service_type": c.service_type,
                "created": int(c.created.timestamp()) if c.created else None
            }
            for c in previous_complaints
        ]

        data["summary"] = {
            "complaint_code": complaint.code,
            "created": int(complaint.created.timestamp()) if complaint.created else None,
            "broadcasted_at": int(complaint.broadcasted_at.timestamp()) if complaint.broadcasted_at else None,
            "work_started_at": int(complaint.work_started_at.timestamp()) if complaint.work_started_at else None,
            "work_completed_at": int(complaint.work_completed_at.timestamp()) if complaint.work_completed_at else None,
            "issue_closed_on": int(complaint.issue_closed_on.timestamp()) if complaint.issue_closed_on else None,
            "ticket_aging": data.get("ticket_aging"),
            "work_duration": (
                format_work_duration(complaint.work_duration())
                if complaint.work_duration() else None
            )
        }

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )

# =====================================================
# STEP 2A - accept_complaint
# code comes from body
# =====================================================

@is_request_authenticated
def accept_complaint(request):

    if request.method == "PATCH":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status == constants.ASSIGNED:
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | complaint_code=%s | reason=ALREADY_ASSIGNED",
                request.user.id, complaint.code)
            return prepare_response(
                message="Job already taken by another service provider.",
                status=status.HTTP_400_BAD_REQUEST
            )

        service_provider_id = body.get("service_provider_id")
        slot_id = body.get("slot_id")

        if not slot_id:
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | complaint_code=%s | reason=SLOT_ID_MISSING",
                request.user.id, complaint.code)
            return prepare_response(
                message="Slot ID is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        broadcast = ComplaintBroadcast.objects.filter(
            complaint=complaint,
            service_provider_id=service_provider_id,
            is_accepted=False,
            is_rejected=False,
            is_expired=False
        ).first()

        if not broadcast:
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | complaint_code=%s | provider_id=%s | reason=BROADCAST_NOT_FOUND",
                request.user.id, complaint.code, service_provider_id)
            return prepare_response(
                message=constants.COMPLAINT_NOT_ASSIGNED_TO_YOU,
                status=status.HTTP_400_BAD_REQUEST
            )

        if broadcast.expires_at and timezone.now() > broadcast.expires_at:
            broadcast.is_expired = True
            broadcast.save()
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | complaint_code=%s | reason=BROADCAST_EXPIRED",
                request.user.id, complaint.code)
            return prepare_response(
                message="Broadcast has expired.",
                status=status.HTTP_400_BAD_REQUEST
            )

        slot = AppointmentSlot.objects.filter(
            id=slot_id,
            appointment=complaint.current_appointment
        ).first()

        if not slot:
            logger.warning(
                "COMPLAINT_ACCEPT_FAILED | user_id=%s | complaint_code=%s | slot_id=%s | reason=SLOT_NOT_FOUND",
                request.user.id, complaint.code, slot_id)
            return prepare_response(
                message="Slot not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        broadcast.is_accepted = True
        broadcast.accepted_at = timezone.now()
        broadcast.save()

        ComplaintBroadcast.objects.filter(
            complaint=complaint,
            is_accepted=False,
            is_rejected=False
        ).update(is_rejected=True, rejected_at=timezone.now())

        slot.is_selected = True
        slot.selected_at = timezone.now()
        slot.save()

        appointment = complaint.current_appointment
        appointment.service_provider = broadcast.service_provider
        appointment.status = constants.APPOINTMENT_CONFIRMED
        appointment.save()

        complaint.assigned_to.add(broadcast.service_provider)
        complaint.status = constants.ASSIGNED
        complaint.save()

        notify_complaint_assigned(
            complaint.raised_by,
            complaint,
            broadcast.service_provider.name
        )

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.ASSIGNED_TIMELINE,
            note=f"{broadcast.service_provider.name} accepted and confirmed slot: {slot.proposed_time}",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{broadcast.service_provider.name} accepted and selected slot: {slot.proposed_time}",
            created_by=request.user.user
        )

        audit_logs(
            request,
            f"{broadcast.service_provider.name} accepted complaint {complaint.code} and selected slot {slot.proposed_time}.",
            "COMPLAINT_ASSIGNED"
        )

        email_complaint_accepted(complaint, broadcast.service_provider, slot=slot)
        email_slot_selected(complaint, slot)

        logger.info(
            "COMPLAINT_ACCEPTED | user_id=%s | complaint_code=%s | provider_id=%s | slot_id=%s",
            request.user.id, complaint.code, service_provider_id, slot_id)
        return prepare_response(
            content={
                "service_provider_id": broadcast.service_provider.id,
                "confirmed_slot": int(slot.proposed_time.timestamp())
            },
            message="Job accepted and slot confirmed successfully.",
            status=status.HTTP_200_OK
        )

    logger.warning(
        "COMPLAINT_ACCEPT_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 2B - decline_complaint
# code comes from body
# =====================================================

@is_request_authenticated
def decline_complaint(request):

    if request.method == "PATCH":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "COMPLAINT_DECLINE_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        service_provider_id = body.get("service_provider_id")

        broadcast = ComplaintBroadcast.objects.filter(
            complaint=complaint,
            service_provider_id=service_provider_id,
            is_rejected=False
        ).first()

        if not broadcast:
            logger.warning(
                "COMPLAINT_DECLINE_FAILED | user_id=%s | complaint_code=%s | provider_id=%s | reason=BROADCAST_NOT_FOUND",
                request.user.id, complaint.code, service_provider_id)
            return prepare_response(
                message=constants.COMPLAINT_NOT_ASSIGNED_TO_YOU,
                status=status.HTTP_400_BAD_REQUEST
            )

        service_provider = broadcast.service_provider
        company = complaint.company

        # CASE 1 - Decline AFTER accepting
        if broadcast.is_accepted:
            broadcast.is_accepted = False
            broadcast.is_rejected = True
            broadcast.rejected_at = timezone.now()
            broadcast.save()

            complaint.assigned_to.remove(service_provider)
            complaint.status = constants.PENDING
            complaint.save()

            ComplaintActivityHistory.objects.create(
                complaint=complaint,
                user=request.user,
                message=f"{service_provider.name} declined after accepting.",
                created_by=request.user.user
            )
            logger.info(
                "COMPLAINT_DECLINED_AFTER_ACCEPT | user_id=%s | complaint_code=%s | provider=%s",
                request.user.id, complaint.code, service_provider.name)

            audit_logs(
                request,
                f"{service_provider.name} declined complaint {complaint.code} after accepting.",
                "COMPLAINT_DECLINED"
            )

            excluded = get_excluded_providers(complaint)

            if complaint.attempt_count >= 2:
                best = auto_assign_best_technician(complaint, company, excluded)
                if best:
                    complaint.assigned_to.add(best)
                    complaint.status = constants.ASSIGNED
                    complaint.save()
                    ComplaintActivityHistory.objects.create(
                        complaint=complaint,
                        user=request.user,
                        message=f"Auto-assigned to {best.name} (best rated).",
                        created_by=request.user.user
                    )

                    audit_logs(
                        request,
                        f"Complaint {complaint.code} auto-assigned to {best.name}.",
                        "COMPLAINT_AUTO_ASSIGNED"
                    )

                    email_complaint_accepted(complaint, best)
                else:
                    logger.warning(
                        "COMPLAINT_NO_PROVIDER_AVAILABLE | complaint_code=%s",
                        complaint.code)
                    email_no_technician_available(complaint)
            else:
                providers_count = auto_broadcast(complaint, company, excluded)
                if providers_count > 0:
                    ComplaintActivityHistory.objects.create(
                        complaint=complaint,
                        user=request.user,
                        message=f"Re-broadcasted to {providers_count} providers. Attempt #{complaint.attempt_count}",
                        created_by=request.user.user
                    )
    
                    audit_logs(
                        request,
                        f"Complaint {complaint.code} re-broadcasted to {providers_count} providers.",
                        "COMPLAINT_REBROADCASTED"
                    )

                    email_complaint_declined(complaint, service_provider)
                else:
                    logger.warning(
                        "COMPLAINT_NO_PROVIDER_AVAILABLE | complaint_code=%s",
                        complaint.code)
                    email_no_technician_available(complaint)

        # CASE 2 - Normal decline (before accepting)
        else:
            broadcast.is_rejected = True
            broadcast.rejected_at = timezone.now()
            broadcast.save()

            ComplaintActivityHistory.objects.create(
                complaint=complaint,
                user=request.user,
                message=f"{service_provider.name} declined.",
                created_by=request.user.user
            )
            logger.info(
                "COMPLAINT_DECLINED | user_id=%s | complaint_code=%s | provider=%s",
                request.user.id, complaint.code, service_provider.name)

            audit_logs(
                request,
                f"{service_provider.name} declined complaint {complaint.code}.",
                "COMPLAINT_DECLINED"
            )

            pending = ComplaintBroadcast.objects.filter(
                complaint=complaint,
                is_accepted=False,
                is_rejected=False,
                is_expired=False
            )

            if not pending.exists():
                excluded = get_excluded_providers(complaint)

                if complaint.attempt_count >= 2:
                    best = auto_assign_best_technician(complaint, company, excluded)
                    if best:
                        complaint.assigned_to.add(best)
                        complaint.status = constants.ASSIGNED
                        complaint.save()
                        ComplaintActivityHistory.objects.create(
                            complaint=complaint,
                            user=request.user,
                            message=f"Auto-assigned to {best.name} (best rated).",
                            created_by=request.user.user
                        )

                        audit_logs(
                            request,
                            f"Complaint {complaint.code} auto-assigned to {best.name}.",
                            "COMPLAINT_AUTO_ASSIGNED"
                        )

                        email_complaint_accepted(complaint, best)
                    else:
                        logger.warning(
                            "COMPLAINT_NO_PROVIDER_AVAILABLE | complaint_code=%s",
                            complaint.code)
                        email_no_technician_available(complaint)
                else:
                    providers_count = auto_broadcast(complaint, company, excluded)
                    if providers_count > 0:
                        ComplaintActivityHistory.objects.create(
                            complaint=complaint,
                            user=request.user,
                            message=f"All declined. Re-broadcasted to {providers_count} providers. Attempt #{complaint.attempt_count}",
                            created_by=request.user.user
                        )

                        audit_logs(
                            request,
                            f"All providers declined complaint {complaint.code}. Re-broadcasted to {providers_count} providers. Attempt #{complaint.attempt_count}.",
                            "COMPLAINT_REBROADCASTED"
                        )
                        
                        email_complaint_declined(complaint, service_provider)
                    else:
                        logger.warning(
                            "COMPLAINT_NO_PROVIDER_AVAILABLE | complaint_code=%s",
                            complaint.code)
                        email_no_technician_available(complaint)

        return prepare_response(
            message="Complaint declined.",
            status=status.HTTP_200_OK
        )

    logger.warning(
        "COMPLAINT_DECLINE_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 3 - start_work
# code comes from body
# =====================================================

@is_request_authenticated
def start_work(request):

    if request.method == "PATCH":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "WORK_START_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.ASSIGNED:
            logger.warning(
                "WORK_START_FAILED | user_id=%s | complaint_code=%s | current_status=%s | reason=INVALID_STATUS",
                request.user.id, complaint.code, complaint.status)
            return prepare_response(
                message="Complaint must be assigned before starting work.",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status = constants.IN_PROGRESS
        complaint.work_started_at = timezone.now()
        complaint.save()

        service_provider = complaint.assigned_to.first()

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.WORK_STARTED,
            note="Work started.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{service_provider.name if service_provider else 'Technician'} started work.",
            created_by=request.user.user
        )

        audit_logs(
            request,
            f"Work started for complaint {complaint.code}.",
            "WORK_STARTED"
        )

        email_work_started(complaint)

        logger.info(
            "WORK_STARTED | user_id=%s | complaint_code=%s | provider=%s",
            request.user.id, complaint.code,
            service_provider.name if service_provider else "unknown")
        return prepare_response(
            message="Work started successfully.",
            status=status.HTTP_200_OK
        )

    logger.warning(
        "WORK_START_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 4 - complete_work
# code comes from body
# =====================================================

@is_request_authenticated
def complete_work(request):

    if request.method == "PATCH":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "WORK_COMPLETE_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.IN_PROGRESS:
            logger.warning(
                "WORK_COMPLETE_FAILED | user_id=%s | complaint_code=%s | current_status=%s | reason=INVALID_STATUS",
                request.user.id, complaint.code, complaint.status)
            return prepare_response(
                message="Complaint must be in progress before completing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status = constants.RESOLVED
        complaint.work_completed_at = timezone.now()
        complaint.save()

        images = body.get("images", [])
        image_count = 0
        for image in images:
            file_name = image.get("file_name")
            file_data = image.get("file_data")
            if file_name and file_data:
                object_name = f"complaints/{complaint.code}/completion/{uuid.uuid4()}_{file_name}"
                file_url = upload_file_to_s3_base64(
                    file_data=file_data,
                    object_name=object_name
                )
                ComplaintImages.objects.create(
                    complaint=complaint,
                    image_path=file_url,
                    file_name=file_name,
                    created_by=request.user.user
                )
                image_count += 1

        service_provider = complaint.assigned_to.first()
        duration = format_work_duration(complaint.work_duration())

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.WORK_COMPLETED,
            note=f"Work completed. Duration: {duration}",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{service_provider.name if service_provider else 'Technician'} completed work. Duration: {duration}",
            created_by=request.user.user
        )

        audit_logs(
            request,
            f"Work completed for complaint {complaint.code}.",
            "WORK_COMPLETED"
        )

        email_work_completed(complaint)
        notify_complaint_resolved(complaint.raised_by, complaint)

        logger.info(
            "WORK_COMPLETED | user_id=%s | complaint_code=%s | provider=%s | duration=%s | completion_images=%d",
            request.user.id, complaint.code,
            service_provider.name if service_provider else "unknown",
            duration, image_count)
        return prepare_response(
            content={"work_duration": duration},
            message="Work completed successfully.",
            status=status.HTTP_200_OK
        )

    logger.warning(
        "WORK_COMPLETE_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 5 - verify_complaint
# code comes from body
# =====================================================

@is_request_authenticated
def verify_complaint(request):

    if request.method == "PATCH":
        body = json.loads(request.body)
        code = body.get("code")
        if not code:
            return prepare_response(
                message="code is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "COMPLAINT_VERIFY_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.RESOLVED:
            logger.warning(
                "COMPLAINT_VERIFY_FAILED | user_id=%s | complaint_code=%s | current_status=%s | reason=INVALID_STATUS",
                request.user.id, complaint.code, complaint.status)
            return prepare_response(
                message="Complaint must be resolved before closing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        rating = body.get("rating")
        feedback = body.get("feedback")

        complaint.status = constants.CLOSED
        complaint.issue_closed_on = timezone.now()
        complaint.save()

        if rating:
            service_provider = complaint.assigned_to.first()
            if service_provider:
                ComplaintRating.objects.create(
                    complaint=complaint,
                    rated_by=request.user,
                    service_provider=service_provider,
                    rating=rating,
                    feedback=feedback,
                    created_by=request.user.user
                )

                all_ratings = ComplaintRating.objects.filter(service_provider=service_provider)
                avg = sum([r.rating for r in all_ratings]) / all_ratings.count()
                service_provider.avg_rating = round(avg, 2)
                service_provider.save()
                logger.info(
                    "COMPLAINT_RATED | user_id=%s | complaint_code=%s | provider=%s | rating=%s | new_avg=%s",
                    request.user.id, complaint.code, service_provider.name, rating, service_provider.avg_rating)

        duration = format_work_duration(complaint.work_duration())

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.COMPLAINT_CLOSED,
            note=f"Closed. Duration: {duration}. {f'Rating: {rating}⭐' if rating else ''}",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} verified and closed. {f'Rating: {rating}⭐' if rating else ''}",
            created_by=request.user.user
        )

        audit_logs(
            request,
            f"{request.user.user.first_name} closed complaint {complaint.code}.",
            "COMPLAINT_CLOSED"
        )
        

        email_complaint_closed(complaint, rating=rating, feedback=feedback)
        notify_complaint_closed(complaint.raised_by, complaint)

        logger.info(
            "COMPLAINT_VERIFIED_AND_CLOSED | user_id=%s | complaint_code=%s | duration=%s | rating=%s",
            request.user.id, complaint.code, duration, rating or "no_rating")
        return prepare_response(
            message="Complaint verified and closed successfully.",
            status=status.HTTP_200_OK
        )

    logger.warning(
        "COMPLAINT_VERIFY_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# UPLOAD IMAGES (standalone)
# =====================================================

@is_request_authenticated
def upload_complaint_images(request):

    if request.method == "POST":
        body = json.loads(request.body)

        code = body.get("code")
        images = body.get("images", [])

        if not code:
            logger.warning(
                "COMPLAINT_IMAGE_UPLOAD_FAILED | user_id=%s | reason=CODE_MISSING",
                request.user.id)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            logger.warning(
                "COMPLAINT_IMAGE_UPLOAD_FAILED | user_id=%s | code=%s | reason=COMPLAINT_NOT_FOUND",
                request.user.id, code)
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if not images:
            logger.warning(
                "COMPLAINT_IMAGE_UPLOAD_FAILED | user_id=%s | complaint_code=%s | reason=IMAGES_MISSING",
                request.user.id, complaint.code)
            return prepare_response(
                message=constants.COMPLAINT_IMAGES_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_images = []
        for image in images:
            file_name = image.get("file_name")
            file_data = image.get("file_data")
            if not file_name or not file_data:
                continue

            object_name = f"complaints/{code}/{uuid.uuid4()}_{file_name}"
            file_url = upload_file_to_s3_base64(
                file_data=file_data,
                object_name=object_name
            )

            img = ComplaintImages.objects.create(
                complaint=complaint,
                image_path=file_url,
                file_name=file_name,
                created_by=request.user.user
            )

            uploaded_images.append({
                "id": img.id,
                "file_name": img.file_name,
                "image_url": img.image_path,
                "file_presigned_url": fetch_s3_presigned_url(file_url)
            })

        if uploaded_images:
            audit_logs(
                request,
                f"{len(uploaded_images)} image(s) uploaded for complaint {complaint.code}.",
                "COMPLAINT_IMAGE_UPLOADED"
            )

        return prepare_response(
            content=uploaded_images,
            message=constants.COMPLAINT_IMAGES_UPLOADED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    logger.warning(
        "COMPLAINT_IMAGE_UPLOAD_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method)
    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )