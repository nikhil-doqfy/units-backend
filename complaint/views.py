# import json
# import uuid
# from django.utils import timezone
# from utilities.helper_functions import prepare_response, fetch_s3_presigned_url, upload_file_to_s3_base64
# from utilities.decorator import is_request_authenticated
# from utilities import constants, status
# from complaint.models import Complaint, ComplaintImages
# from property.models import PropertyManagmentCompany, Unit


# def get_ticket_aging(created):
#     delta = timezone.now() - created
#     days = delta.days
#     hours = delta.seconds // 3600
#     seconds = delta.seconds % 60
#     return f"{days}d, {hours}hr, {seconds}sec"


# @is_request_authenticated
# def complaint_api(request):

#     if request.method == "GET":
#         company = PropertyManagmentCompany.objects.filter(
#             company_staff=request.user,
#             is_active=True
#         ).first()
#         if not company:
#             return prepare_response(
#                 message=constants.COMPANY_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         complaints = Complaint.objects.filter(
#             company=company,
#             is_active=True
#         ).order_by('-id')

#         data = [
#             {
#                 "id": c.id,
#                 "complaint_id": c.complaint_id,
#                 "unit": {
#                     "id": c.unit.id,
#                     "unit_name": c.unit.unit_name,
#                     "property_name": c.unit.property_block_tower.property.property_name if c.unit.property_block_tower else None,
#                 },
#                 "raised_by": {
#                     "id": c.raised_by.id,
#                     "name": f"{c.raised_by.user.first_name} {c.raised_by.user.last_name}".strip(),
#                     "profile_image": c.raised_by.profile_image,
#                 },
#                 "description": c.description,
#                 "status": {
#                     "key": c.status,
#                     "value": c.get_status_display()
#                 },
#                 "ticket_aging": get_ticket_aging(c.created),
#                 "images": [
#                     {
#                         "id": img.id,
#                         "file_name": img.file_name,
#                         "url": fetch_s3_presigned_url(img.image_path, file_name=img.file_name),
#                     }
#                     for img in c.complaint_images.all()
#                 ],
#                 "images_count": c.complaint_images.count(),
#                 "created": c.created,
#             }
#             for c in complaints
#         ]

#         return prepare_response(
#             content=data,
#             message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
#             status=status.HTTP_200_OK
#         )

#     elif request.method == "POST":
#         body = json.loads(request.body)

#         company = PropertyManagmentCompany.objects.filter(
#             company_staff=request.user,
#             is_active=True
#         ).first()
#         if not company:
#             return prepare_response(
#                 message=constants.COMPANY_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         unit_id = body.get("unit_id")
#         unit = Unit.objects.filter(id=unit_id).first()
#         if not unit:
#             return prepare_response(
#                 message=constants.UNIT_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         description = body.get("description")
#         if not description:
#             return prepare_response(
#                 message="Description is required.",
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         complaint = Complaint.objects.create(
#             unit=unit,
#             raised_by=request.user,
#             company=company,
#             description=description,
#             status=constants.PENDING,
#             created_by=request.user.user
#         )

#         return prepare_response(
#             content={"complaint_id": complaint.complaint_id},
#             message=constants.COMPLAINT_CREATED_SUCCESSFULLY,
#             status=status.HTTP_201_CREATED
#         )

#     return prepare_response(
#         message=constants.METHOD_NOT_ALLOWED,
#         status=status.HTTP_405_METHOD_NOT_ALLOWED
#     )


# @is_request_authenticated
# def complaint_detail_api(request, complaint_id):

#     company = PropertyManagmentCompany.objects.filter(
#         company_staff=request.user,
#         is_active=True
#     ).first()
#     if not company:
#         return prepare_response(
#             message=constants.COMPANY_NOT_FOUND,
#             status=status.HTTP_404_NOT_FOUND
#         )

#     complaint = Complaint.objects.filter(
#         complaint_id=complaint_id,
#         company=company,
#         is_active=True
#     ).first()
#     if not complaint:
#         return prepare_response(
#             message=constants.COMPLAINT_NOT_FOUND,
#             status=status.HTTP_404_NOT_FOUND
#         )

#     if request.method == "GET":
#         data = {
#             "id": complaint.id,
#             "complaint_id": complaint.complaint_id,
#             "unit": {
#                 "id": complaint.unit.id,
#                 "unit_name": complaint.unit.unit_name,
#                 "property_name": complaint.unit.property_block_tower.property.property_name if complaint.unit.property_block_tower else None,
#             },
#             "raised_by": {
#                 "id": complaint.raised_by.id,
#                 "name": f"{complaint.raised_by.user.first_name} {complaint.raised_by.user.last_name}".strip(),
#                 "profile_image": complaint.raised_by.profile_image,
#             },
#             "description": complaint.description,
#             "status": {
#                 "key": complaint.status,
#                 "value": complaint.get_status_display()
#             },
#             "ticket_aging": get_ticket_aging(complaint.created),
#             "images": [
#                 {
#                     "id": img.id,
#                     "file_name": img.file_name,
#                     "url": f"https://your-bucket-name.s3.amazonaws.com/{img.image_path}",
#                 }
#                 for img in complaint.complaint_images.all()
#             ],
#             "images_count": complaint.complaint_images.count(),
#             "created": complaint.created,
#         }

#         return prepare_response(
#             content=data,
#             message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
#             status=status.HTTP_200_OK
#         )

#     elif request.method == "PUT":
#         body = json.loads(request.body)

#         unit_id = body.get("unit_id")
#         if unit_id:
#             unit = Unit.objects.filter(id=unit_id).first()
#             if not unit:
#                 return prepare_response(
#                     message=constants.UNIT_NOT_FOUND,
#                     status=status.HTTP_404_NOT_FOUND
#                 )
#             complaint.unit = unit

#         complaint.description = body.get("description", complaint.description)
#         complaint.save()

#         return prepare_response(
#             message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
#             status=status.HTTP_200_OK
#         )

#     elif request.method == "PATCH":
#         body = json.loads(request.body)
#         complaint.status = body.get("status", complaint.status)
#         complaint.save()

#         return prepare_response(
#             message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
#             status=status.HTTP_200_OK
#         )

#     elif request.method == "DELETE":
#         complaint.is_active = False
#         complaint.save()

#         return prepare_response(
#             message=constants.COMPLAINT_DELETED_SUCCESSFULLY,
#             status=status.HTTP_200_OK
#         )

#     return prepare_response(
#         message=constants.METHOD_NOT_ALLOWED,
#         status=status.HTTP_405_METHOD_NOT_ALLOWED
#     )


# @is_request_authenticated
# def upload_complaint_images(request):

#     if request.method == "POST":
#         body = json.loads(request.body)

#         complaint_id = body.get("complaint_id")
#         images = body.get("images", [])

#         if not complaint_id:
#             return prepare_response(
#                 message=constants.COMPLAINT_NOT_FOUND,
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         complaint = Complaint.objects.filter(
#             complaint_id=complaint_id,
#             is_active=True
#         ).first()

#         if not complaint:
#             return prepare_response(
#                 message=constants.COMPLAINT_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         if not images:
#             return prepare_response(
#                 message="Images are required.",
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         uploaded_images = []

#         for image in images:
#             file_name = image.get("file_name")
#             file_data = image.get("file_data")

#             if not file_name or not file_data:
#                 continue

#             object_name = f"complaints/{complaint_id}/{uuid.uuid4()}_{file_name}"

#             file_url = upload_file_to_s3_base64(
#                 file_data=file_data,
#                 object_name=object_name
#             )

#             img = ComplaintImages.objects.create(
#                 complaint=complaint,
#                 image_path=file_url,
#                 file_name=file_name,
#                 created_by=request.user.user
#             )

#             uploaded_images.append({
#                 "id": img.id,
#                 "file_name": img.file_name,
#                 "image_url": img.image_path,
#                 "file_presigned_url":fetch_s3_presigned_url(file_url)
#             })

#         return prepare_response(
#             content=uploaded_images,
#             message="Images uploaded successfully.",
#             status=status.HTTP_201_CREATED
#         )

#     return prepare_response(
#         message=constants.METHOD_NOT_ALLOWED,
#         status=status.HTTP_405_METHOD_NOT_ALLOWED
#     )

import json
import uuid
from django.utils import timezone
from utilities.helper_functions import prepare_response, fetch_s3_presigned_url, upload_file_to_s3_base64
from utilities.decorator import is_request_authenticated
from utilities import constants, status
from complaint.models import (
    Complaint, ComplaintImages, ComplaintTimeline,
    ComplaintActivityHistory, ServiceProvider, ComplaintBroadcast
)
from property.models import PropertyManagmentCompany, Unit
from user_service.models import UserProfile


def get_ticket_aging(created):
    delta = timezone.now() - created
    days = delta.days
    hours = delta.seconds // 3600
    minutes = (delta.seconds % 3600) // 60
    seconds = delta.seconds % 60
    return f"{days}d, {hours}hr, {minutes}min, {seconds}sec"


def serialize_complaint(c):
    return {
        "id": c.id,
        "code": c.code,
        "unit": {
            "id": c.unit.id,
            "unit_name": c.unit.unit_name,
            "property_name": c.unit.property_block_tower.property.property_name if c.unit.property_block_tower else None,
        },
        "raised_by": {
            "id": c.raised_by.id,
            "name": f"{c.raised_by.user.first_name} {c.raised_by.user.last_name}".strip(),
            "profile_image": c.raised_by.profile_image,
        },
        "assigned_to": {
            "id": c.assigned_to.id,
            "name": c.assigned_to.name,
            "phone": c.assigned_to.phone,
            "service_type": c.assigned_to.service_type,
        } if c.assigned_to else None,
        "service_type": {
            "key": c.service_type,
            "value": c.get_service_type_display()
        },
        "priority": {
            "key": c.priority,
            "value": c.get_priority_display()
        },
        "description": c.description,
        "locality": c.locality,
        "status": {
            "key": c.status,
            "value": c.get_status_display()
        },
        "is_broadcasted": c.is_broadcasted,
        "broadcasted_at": c.broadcasted_at,
        "work_started_at": c.work_started_at,
        "work_completed_at": c.work_completed_at,
        "work_duration": str(c.work_duration()) if c.work_duration() else None,
        "issue_closed_on": c.issue_closed_on,
        "ticket_aging": get_ticket_aging(c.created),
        "images": [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": fetch_s3_presigned_url(img.image_path, file_name=img.file_name),
            }
            for img in c.complaint_images.all()
        ],
        "images_count": c.complaint_images.count(),
        "created": c.created,
    }


@is_request_authenticated
def complaint_api(request):

    # ===================== GET ALL =====================
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

        data = [serialize_complaint(c) for c in complaints]

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    # ===================== POST - Create =====================
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

        complaint = Complaint.objects.create(
            unit=unit,
            raised_by=request.user,
            company=company,
            description=description,
            locality=body.get("locality"),
            service_type=service_type,
            priority=body.get("priority", constants.MEDIUM),
            status=constants.PENDING,
            created_by=request.user.user
        )

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.CREATED,
            note="Complaint created.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} raised a complaint.",
            created_by=request.user.user
        )

        return prepare_response(
            content={"code": complaint.code},
            message=constants.COMPLAINT_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


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

    # ===================== GET SINGLE =====================
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
                "time": t.time,
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
                "created": a.created,
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
                },
                "is_accepted": b.is_accepted,
                "is_rejected": b.is_rejected,
                "accepted_at": b.accepted_at,
            }
            for b in complaint.broadcasts.all()
        ]

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    # ===================== PUT - Update =====================
    elif request.method == "PUT":
        body = json.loads(request.body)

        complaint.description = body.get("description", complaint.description)
        complaint.locality = body.get("locality", complaint.locality)
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

    # ===================== DELETE =====================
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


@is_request_authenticated
def broadcast_complaint(request, code):

    if request.method == "POST":
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

        providers = ServiceProvider.objects.filter(
            company=company,
            service_type=complaint.service_type,
            is_available=True,
            is_active=True
        )

        if not providers.exists():
            return prepare_response(
                message="No available service providers found.",
                status=status.HTTP_404_NOT_FOUND
            )

        # ── Delete old unaccepted broadcasts ───────────────────────
        ComplaintBroadcast.objects.filter(
            complaint=complaint,
            is_accepted=False
        ).delete()

        # ── Create new broadcasts ──────────────────────────────────
        for provider in providers:
            ComplaintBroadcast.objects.create(
                complaint=complaint,
                service_provider=provider,
                created_by=request.user.user
            )

        complaint.is_broadcasted = True
        complaint.broadcasted_at = timezone.now()
        complaint.status = constants.PENDING
        complaint.assigned_to = None
        complaint.save()

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.CREATED,
            note=f"Broadcasted to {providers.count()} service providers.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} broadcasted to {providers.count()} providers.",
            created_by=request.user.user
        )

        return prepare_response(
            content={"broadcasted_to": providers.count()},
            message="Complaint broadcasted successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


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

        broadcast = ComplaintBroadcast.objects.filter(
            complaint=complaint,
            service_provider_id=service_provider_id,
            is_accepted=False,
            is_rejected=False
        ).first()

        if not broadcast:
            return prepare_response(
                message="Broadcast not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        broadcast.is_accepted = True
        broadcast.accepted_at = timezone.now()
        broadcast.save()

        ComplaintBroadcast.objects.filter(
            complaint=complaint,
            is_accepted=False
        ).update(is_rejected=True)

        complaint.assigned_to = broadcast.service_provider
        complaint.status = constants.ASSIGNED
        complaint.save()

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.ASSIGNED_TIMELINE,
            note=f"{broadcast.service_provider.name} accepted the job.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{broadcast.service_provider.name} accepted the complaint.",
            created_by=request.user.user
        )

        return prepare_response(
            message="Job accepted successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


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
            message=f"{request.user.user.first_name} started work on complaint.",
            created_by=request.user.user
        )

        return prepare_response(
            message="Work started successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@is_request_authenticated
def complete_work(request, code):

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

        if complaint.status != constants.IN_PROGRESS:
            return prepare_response(
                message="Complaint must be in progress before completing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status = constants.RESOLVED
        complaint.work_completed_at = timezone.now()
        complaint.save()

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.WORK_COMPLETED,
            note=f"Work completed. Duration: {complaint.work_duration()}",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} completed work. Duration: {complaint.work_duration()}",
            created_by=request.user.user
        )

        return prepare_response(
            content={"work_duration": str(complaint.work_duration())},
            message="Work completed successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@is_request_authenticated
def verify_complaint(request, code):

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

        if complaint.status != constants.RESOLVED:
            return prepare_response(
                message="Complaint must be resolved before closing.",
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint.status = constants.CLOSED
        complaint.issue_closed_on = timezone.now()
        complaint.save()

        ComplaintTimeline.objects.create(
            complaint=complaint,
            user=request.user,
            timeline_status=constants.COMPLAINT_CLOSED,
            note="Owner verified and closed the complaint.",
            created_by=request.user.user
        )

        ComplaintActivityHistory.objects.create(
            complaint=complaint,
            user=request.user,
            message=f"{request.user.user.first_name} verified and closed the complaint.",
            created_by=request.user.user
        )

        return prepare_response(
            message="Complaint verified and closed successfully.",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


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
                message="COMPLAINT_IMAGES_REQUIRED",
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
            message="COMPLAINT_IMAGES_UPLOADED_SUCCESSFULLY",
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )