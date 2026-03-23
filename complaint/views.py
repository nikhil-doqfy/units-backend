import json
import uuid
from django.utils import timezone
from utilities.helper_functions import prepare_response, fetch_s3_presigned_url, upload_file_to_s3_base64
from utilities.decorator import is_request_authenticated
from utilities import constants, status
from complaint.models import Complaint, ComplaintImages
from property.models import PropertyManagmentCompany, Unit


def get_ticket_aging(created):
    delta = timezone.now() - created
    days = delta.days
    hours = delta.seconds // 3600
    seconds = delta.seconds % 60
    return f"{days}d, {hours}hr, {seconds}sec"


@is_request_authenticated
def complaint_api(request):

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

        data = [
            {
                "id": c.id,
                "complaint_id": c.complaint_id,
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
                "description": c.description,
                "status": {
                    "key": c.status,
                    "value": c.get_status_display()
                },
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
            for c in complaints
        ]

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

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

        complaint = Complaint.objects.create(
            unit=unit,
            raised_by=request.user,
            company=company,
            description=description,
            status=constants.PENDING,
            created_by=request.user.user
        )

        return prepare_response(
            content={"complaint_id": complaint.complaint_id},
            message=constants.COMPLAINT_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@is_request_authenticated
def complaint_detail_api(request, complaint_id):

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
        complaint_id=complaint_id,
        company=company,
        is_active=True
    ).first()
    if not complaint:
        return prepare_response(
            message=constants.COMPLAINT_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        data = {
            "id": complaint.id,
            "complaint_id": complaint.complaint_id,
            "unit": {
                "id": complaint.unit.id,
                "unit_name": complaint.unit.unit_name,
                "property_name": complaint.unit.property_block_tower.property.property_name if complaint.unit.property_block_tower else None,
            },
            "raised_by": {
                "id": complaint.raised_by.id,
                "name": f"{complaint.raised_by.user.first_name} {complaint.raised_by.user.last_name}".strip(),
                "profile_image": complaint.raised_by.profile_image,
            },
            "description": complaint.description,
            "status": {
                "key": complaint.status,
                "value": complaint.get_status_display()
            },
            "ticket_aging": get_ticket_aging(complaint.created),
            "images": [
                {
                    "id": img.id,
                    "file_name": img.file_name,
                    "url": f"https://your-bucket-name.s3.amazonaws.com/{img.image_path}",
                }
                for img in complaint.complaint_images.all()
            ],
            "images_count": complaint.complaint_images.count(),
            "created": complaint.created,
        }

        return prepare_response(
            content=data,
            message=constants.COMPLAINT_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "PUT":
        body = json.loads(request.body)

        unit_id = body.get("unit_id")
        if unit_id:
            unit = Unit.objects.filter(id=unit_id).first()
            if not unit:
                return prepare_response(
                    message=constants.UNIT_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            complaint.unit = unit

        complaint.description = body.get("description", complaint.description)
        complaint.save()

        return prepare_response(
            message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "PATCH":
        body = json.loads(request.body)
        complaint.status = body.get("status", complaint.status)
        complaint.save()

        return prepare_response(
            message=constants.COMPLAINT_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

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
def upload_complaint_images(request):

    if request.method == "POST":
        body = json.loads(request.body)

        complaint_id = body.get("complaint_id")
        images = body.get("images", [])

        if not complaint_id:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        complaint = Complaint.objects.filter(
            complaint_id=complaint_id,
            is_active=True
        ).first()

        if not complaint:
            return prepare_response(
                message=constants.COMPLAINT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if not images:
            return prepare_response(
                message="Images are required.",
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_images = []

        for image in images:
            file_name = image.get("file_name")
            file_data = image.get("file_data")

            if not file_name or not file_data:
                continue

            object_name = f"complaints/{complaint_id}/{uuid.uuid4()}_{file_name}"

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
                "file_presigned_url":fetch_s3_presigned_url(file_url)
            })

        return prepare_response(
            content=uploaded_images,
            message="Images uploaded successfully.",
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )