import json
import uuid
from django.utils import timezone
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


# =====================================================
# STEP 1 - complaint_api (GET ALL + POST CREATE)
# Owner creates complaint + uploads images + proposes slots
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
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        complaints = Complaint.objects.filter(
            company=company,
            is_active=True
        ).order_by('-id')
        total = complaints.count()
 
        return prepare_response(
            content=[serialize_complaint(c) for c in complaints],
            pagination={"total_records": total},
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
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
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        unit_id = body.get("unit_id")
        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            return prepare_response(
                message=constants.UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        description = body.get("description")
        if not description:
            return prepare_response(
                message="Description is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        service_type = body.get("service_type")
        if not service_type:
            return prepare_response(
                message="Service type is required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        slots = body.get("slots", [])
        if not slots:
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
            slot_time = timezone.datetime.fromtimestamp(slot_epoch, tz=timezone.utc)
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

        # ── Emails ─────────────────────────────────────────────────
        email_complaint_created(complaint)
        if providers_count > 0:
            email_complaint_broadcasted(complaint, providers_count)

        return prepare_response(
            content={"code": complaint.code},
            message=constants.COMPLAINT_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# complaint_detail_api - GET + PUT + DELETE
# =====================================================

@is_request_authenticated
def complaint_detail_api(request, code):

    company = PropertyManagmentCompany.objects.filter(
        company_staff=request.user,
        is_active=True
    ).first()
    if not company:
        return prepare_response(
            message=constants.COMPANY_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
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

    # ── GET ───────────────────────────────────────────────────────
    if request.method == "GET":
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
            for t in complaint.timeline.all().order_by('created')
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
            for a in complaint.activity_history.all().order_by('-created')
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
            for b in complaint.broadcasts.all().order_by('-priority_score')
        ]

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    # ── PUT ───────────────────────────────────────────────────────
    elif request.method == "PUT":
        body = json.loads(request.body)

        complaint.description = body.get("description", complaint.description)
        complaint.service_type = body.get("service_type", complaint.service_type)
        complaint.priority = body.get("priority", complaint.priority)
        complaint.save()

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} updated the complaint.",
            created_by=request.user.user
        )

        return prepare_response(
            message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    # ── DELETE ────────────────────────────────────────────────────
    elif request.method == "DELETE":
        complaint.is_active = False
        complaint.save()

        return prepare_response(
            message=constants.COMPLAINT_DELETED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 2A - accept_complaint
# Technician accepts + selects slot in one step
# =====================================================

@is_request_authenticated
def accept_complaint(request, code):

    if request.method == "PATCH":
        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status == constants.ASSIGNED:
            return prepare_response(
                message="Job already taken by another service provider.",
                status=status.HTTP_400_BAD_REQUEST
            )

        body = json.loads(request.body)
        service_provider_id = body.get("service_provider_id")
        slot_id = body.get("slot_id")

        if not slot_id:
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
            return prepare_response(
                message=constants.COMPLAINT_NOT_ASSIGNED_TO_YOU,
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Check expiry ───────────────────────────────────────────
        if broadcast.expires_at and timezone.now() > broadcast.expires_at:
            broadcast.is_expired = True
            broadcast.save()
            return prepare_response(
                message="Broadcast has expired.",
                status=status.HTTP_400_BAD_REQUEST
            )

        # ── Validate slot ──────────────────────────────────────────
        slot = AppointmentSlot.objects.filter(
            id=slot_id,
            appointment=complaint.current_appointment
        ).first()

        if not slot:
            return prepare_response(
                message="Slot not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        # ── Accept broadcast ───────────────────────────────────────
        broadcast.is_accepted = True
        broadcast.accepted_at = timezone.now()
        broadcast.save()

        # ── Reject all other pending broadcasts ────────────────────
        ComplaintBroadcast.objects.filter(
            complaint=complaint,
            is_accepted=False,
            is_rejected=False
        ).update(is_rejected=True, rejected_at=timezone.now())

        # ── Select slot ────────────────────────────────────────────
        slot.is_selected = True
        slot.selected_at = timezone.now()
        slot.save()

        # ── Update appointment ─────────────────────────────────────
        appointment = complaint.current_appointment
        appointment.service_provider = broadcast.service_provider
        appointment.status = constants.APPOINTMENT_CONFIRMED
        appointment.save()

        # ── Update complaint ───────────────────────────────────────
        complaint.assigned_to.add(broadcast.service_provider)
        complaint.status = constants.ASSIGNED
        complaint.save()

        # ── Timeline ───────────────────────────────────────────────
        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.ASSIGNED_TIMELINE,
            note=f"{broadcast.service_provider.name} accepted and confirmed slot: {slot.proposed_time}",
            created_by=request.user.user
        )

        # ── Activity ───────────────────────────────────────────────
        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{broadcast.service_provider.name} accepted and selected slot: {slot.proposed_time}",
            created_by=request.user.user
        )

        # ── Emails ─────────────────────────────────────────────────
        email_complaint_accepted(complaint, broadcast.service_provider, slot=slot)
        email_slot_selected(complaint, slot)

        return prepare_response(
            content={
                "service_provider_id": broadcast.service_provider.id,
                "confirmed_slot": int(slot.proposed_time.timestamp())
            },
            message="Job accepted and slot confirmed successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 2B - decline_complaint
# =====================================================

@is_request_authenticated
def decline_complaint(request, code):

    if request.method == "PATCH":
        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        body = json.loads(request.body)
        service_provider_id = body.get("service_provider_id")

        broadcast = ComplaintBroadcast.objects.filter(
            complaint=complaint,
            service_provider_id=service_provider_id,
            is_rejected=False
        ).first()

        if not broadcast:
            return prepare_response(
                message=constants.COMPLAINT_NOT_ASSIGNED_TO_YOU,
                status=status.HTTP_400_BAD_REQUEST
            )

        service_provider = broadcast.service_provider
        company = complaint.company

        # =====================================================
        # CASE 1 - Decline AFTER accepting
        # =====================================================
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

            excluded = get_excluded_providers(complaint)

            # ── attempt_count >= 2 → auto assign ──────────────────
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
                    email_complaint_accepted(complaint, best)
                else:
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
                    email_complaint_declined(complaint, service_provider)
                else:
                    email_no_technician_available(complaint)

        # =====================================================
        # CASE 2 - Normal decline (before accepting)
        # =====================================================
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

            pending = ComplaintBroadcast.objects.filter(
                complaint=complaint,
                is_accepted=False,
                is_rejected=False,
                is_expired=False
            )

            if not pending.exists():
                excluded = get_excluded_providers(complaint)

                # ── attempt_count >= 2 → auto assign ──────────────
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
                        email_complaint_accepted(complaint, best)
                    else:
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
                        email_complaint_declined(complaint, service_provider)
                    else:
                        email_no_technician_available(complaint)

        return prepare_response(
            message="Complaint declined.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 3 - start_work
# =====================================================

@is_request_authenticated
def start_work(request, code):

    if request.method == "PATCH":
        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.ASSIGNED:
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

        email_work_started(complaint)

        return prepare_response(
            message="Work started successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 4 - complete_work (Technician + upload images)
# =====================================================

@is_request_authenticated
def complete_work(request, code):

    if request.method == "PATCH":
        body = json.loads(request.body)

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.IN_PROGRESS:
            return prepare_response(
                message="Complaint must be in progress before completing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status = constants.RESOLVED
        complaint.work_completed_at = timezone.now()
        complaint.save()

        # ── Upload completion images ───────────────────────────────
        images = body.get("images", [])
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

        email_work_completed(complaint)

        return prepare_response(
            content={"work_duration": duration},
            message="Work completed successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 5 - verify_complaint (Owner verifies + rates)
# =====================================================

@is_request_authenticated
def verify_complaint(request, code):

    if request.method == "PATCH":
        body = json.loads(request.body)

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if complaint.status != constants.RESOLVED:
            return prepare_response(
                message="Complaint must be resolved before closing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        rating = body.get("rating")
        feedback = body.get("feedback")

        complaint.status = constants.CLOSED
        complaint.issue_closed_on = timezone.now()
        complaint.save()

        # ── Save rating + update avg ───────────────────────────────
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

                all_ratings = ComplaintRating.objects.filter(
                    service_provider=service_provider
                )
                avg = sum([r.rating for r in all_ratings]) / all_ratings.count()
                service_provider.avg_rating = round(avg, 2)
                service_provider.save()

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

        # ── Email with rating and feedback ─────────────────────────
        email_complaint_closed(complaint, rating=rating, feedback=feedback)

        return prepare_response(
            message="Complaint verified and closed successfully.",
            status=status.HTTP_200_OK
        )

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
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            code=code,
            is_active=True
        ).first()
        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if not images:
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

        return prepare_response(
            content=uploaded_images,
            message=constants.COMPLAINT_IMAGES_UPLOADED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )