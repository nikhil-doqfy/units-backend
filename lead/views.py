import base64
import csv
import io
import json
from django.db.models import Q
from django.http import HttpResponse
from .models import Lead
from property.models import Unit
from user_service.models import PropertyManager

def _get_pmc(user_profile):
    pm = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    return pm.company if pm else None
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import status, constants


def _get_property_thumbnail(prop):
    img = prop.property_images.filter(image_type="EXTERIOR").first()
    if not img:
        img = prop.property_images.first()
    if not img:
        return None
    from utilities.helper_functions import fetch_s3_presigned_url
    return fetch_s3_presigned_url(img.image_path, img.file_name)


def _serialize_lead(lead):
    unit = lead.unit
    block = unit.property_block_tower
    prop = block.property
    return {
        "id": lead.id,
        "code": lead.code,
        "name": lead.name,
        "email": lead.email,
        "contact_number": lead.contact_number,
        "status": lead.status,
        "platform": lead.platform,
        "lead_type": lead.lead_type,
        "unit_id": unit.id,
        "unit_name": unit.unit_name,
        "rent": str(unit.rent) if unit.rent else None,
        "property_id": prop.id,
        "property_name": prop.property_name,
        "property_thumbnail": _get_property_thumbnail(prop),
        "created_at": lead.created.strftime("%m/%d/%Y %H:%M") if lead.created else None,
    }


@is_request_authenticated
def lead_view(request):
    user_profile = request.user

    pmc = _get_pmc(user_profile)
    if not pmc:
        return prepare_response(message="Company not found for this user", status=status.HTTP_400_BAD_REQUEST)

    if request.method == "GET":
        lead_id = request.GET.get("lead_id")
        if lead_id:
            lead = Lead.objects.filter(id=lead_id, pmc=pmc).first()
            if not lead:
                return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)
            return prepare_response(content=_serialize_lead(lead), status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        lead_status = request.GET.get("status", "").strip()
        platform = request.GET.get("platform", "").strip()
        lead_type = request.GET.get("lead_type", "").strip()
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        leads = Lead.objects.filter(pmc=pmc).order_by("-id")
        if search:
            leads = leads.filter(Q(name__icontains=search) | Q(email__icontains=search))
        if lead_status:
            leads = leads.filter(status=lead_status)
        if platform:
            leads = leads.filter(platform=platform)
        if lead_type:
            leads = leads.filter(lead_type=lead_type)

        export = request.GET.get("export", "").strip()
        if export == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = 'attachment; filename="leads.csv"'
            writer = csv.writer(response)
            writer.writerow(["Lead ID", "Name", "Email", "Contact", "Status", "Platform", "Lead Type", "Unit", "Property", "Created At"])
            for l in leads:
                s = _serialize_lead(l)
                writer.writerow([s["code"], s["name"], s["email"], s["contact_number"], s["status"], s["platform"], s["lead_type"], s["unit_name"], s["property_name"], s["created_at"]])
            return response

        total = leads.count()
        start = (page - 1) * page_size
        leads = leads[start:start + page_size]

        return prepare_response(
            content=[_serialize_lead(l) for l in leads],
            pagination={"total_records": total, "page": page, "page_size": page_size},
            status=status.HTTP_200_OK,
        )

    elif request.method == "POST":
        data = json.loads(request.body)
        unit_id = data.get("unit_id")
        name = (data.get("name") or "").strip()
        email = (data.get("email") or "").strip()
        contact_number = (data.get("contact_number") or "").strip()
        lead_status = data.get("status", constants.INTERESTED)
        platform = data.get("platform")
        lead_type = data.get("lead_type")

        if not all([unit_id, name, email, contact_number, platform, lead_type]):
            return prepare_response(
                message="unit_id, name, email, contact_number, platform, lead_type are required",
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            return prepare_response(message="Unit not found", status=status.HTTP_404_NOT_FOUND)

        lead = Lead.objects.create(
            unit=unit,
            name=name,
            email=email,
            contact_number=contact_number,
            status=lead_status,
            platform=platform,
            lead_type=lead_type,
            pmc=pmc,
            created_by=user_profile.user,
        )

        return prepare_response(
            message="Lead created successfully",
            content={"id": lead.id, "code": lead.code},
            status=status.HTTP_201_CREATED,
        )

    elif request.method == "PUT":
        data = json.loads(request.body)
        lead_id = data.get("lead_id")
        if not lead_id:
            return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

        lead = Lead.objects.filter(id=lead_id).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        for field in ["name", "email", "contact_number", "status", "platform", "lead_type"]:
            if field in data and data[field] is not None:
                setattr(lead, field, data[field])

        if "unit_id" in data:
            unit = Unit.objects.filter(id=data["unit_id"]).first()
            if unit:
                lead.unit = unit

        lead.save()
        return prepare_response(message="Lead updated successfully", content={"id": lead.id}, status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        lead_id = request.GET.get("lead_id")
        if not lead_id:
            return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

        lead = Lead.objects.filter(id=lead_id).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        lead.delete()
        return prepare_response(message="Lead deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@is_request_authenticated
def lead_bulk_import(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    user_profile = request.user
    pmc = _get_pmc(user_profile)
    if not pmc:
        return prepare_response(message="Company not found for this user", status=status.HTTP_400_BAD_REQUEST)

    data = json.loads(request.body)
    file_b64 = data.get("file", "")
    if not file_b64:
        return prepare_response(message="file is required", status=status.HTTP_400_BAD_REQUEST)

    # Strip data URL prefix if present
    if "," in file_b64:
        file_b64 = file_b64.split(",", 1)[1]

    try:
        csv_bytes = base64.b64decode(file_b64)
        csv_text = csv_bytes.decode("utf-8-sig")
    except Exception:
        return prepare_response(message="Invalid file encoding", status=status.HTTP_400_BAD_REQUEST)

    reader = csv.DictReader(io.StringIO(csv_text))
    required_fields = {"unit_id", "name", "email", "contact_number", "platform", "lead_type"}

    created, skipped = 0, 0
    errors = []

    for i, row in enumerate(reader, start=2):
        row = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        missing = required_fields - set(row.keys())
        if missing:
            return prepare_response(
                message=f"CSV missing required columns: {', '.join(missing)}",
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit_id = row.get("unit_id")
        name = row.get("name")
        email = row.get("email")
        contact_number = row.get("contact_number")
        platform = row.get("platform", "").upper()
        lead_type = row.get("lead_type", "").upper()
        lead_status = row.get("status", constants.INTERESTED).upper() or constants.INTERESTED

        if not all([unit_id, name, email, contact_number, platform, lead_type]):
            errors.append(f"Row {i}: missing required values")
            skipped += 1
            continue

        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            errors.append(f"Row {i}: unit_id '{unit_id}' not found")
            skipped += 1
            continue

        Lead.objects.create(
            unit=unit,
            name=name,
            email=email,
            contact_number=contact_number,
            status=lead_status,
            platform=platform,
            lead_type=lead_type,
            pmc=pmc,
            created_by=user_profile.user,
        )
        created += 1

    return prepare_response(
        message=f"{created} lead(s) imported successfully. {skipped} skipped.",
        content={"created": created, "skipped": skipped, "errors": errors},
        status=status.HTTP_201_CREATED,
    )
