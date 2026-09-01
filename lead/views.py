import base64
import csv
import io
import json
from datetime import datetime
from django.db.models import Q
from django.http import HttpResponse
from .models import Lead, ActivityLog, ScheduleMeeting
from property.models import Unit, PMCPMMapping
from user_service.models import PropertyManager, Tenant
from plugins.logger_plugin import get_logger

logger = get_logger(__name__)
def _get_pmc(user_profile):
    pm = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    return pm.company if pm else None
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import status, constants
from lead.swagger import (
    lead_get, lead_post, lead_put, lead_delete,
    activity_get, activity_post, activity_put, activity_delete,
    lead_check_active_lease_get, lead_bulk_import_post
)
from rest_framework.decorators import api_view
def _get_pmc_ids(user_profile):
    pm = PropertyManager.objects.filter(pk=user_profile.pk).first()
    if not pm:
        return []
    pmc_ids = list(PMCPMMapping.objects.filter(pm=pm).values_list("pmc_id", flat=True))
    if not pmc_ids and pm.company_id:
        pmc_ids = [pm.company_id]
    return pmc_ids

def _get_property_thumbnail(prop):
    img = prop.property_images.filter(image_type="EXTERIOR").first()
    if not img:
        img = prop.property_images.first()
    if not img:
        return None
    from utilities.helper_functions import fetch_s3_presigned_url
    return fetch_s3_presigned_url(img.image_path, img.file_name)


def _find_lead_lease(lead):
    """Return the most recent active lease for this lead's unit+tenant combination."""
    from lease.models import Lease
    if lead.tenant_id:
        return Lease.objects.filter(unit=lead.unit, tenant_id=lead.tenant_id, is_active=True).order_by('-id').first()
    # lead.tenant not set yet — try matching by email (tenant created by lease POST)
    tenant = Tenant.objects.filter(email__iexact=lead.email).first()
    if tenant:
        return Lease.objects.filter(unit=lead.unit, tenant=tenant, is_active=True).order_by('-id').first()
    return None


def _serialize_lead(lead):
    unit = lead.unit
    block = unit.property_block_tower
    #prop = block.property
    prop = block.property if block else unit.parent_property
    pmc = prop.pmc

    return {
        "id": lead.id,
        "code": lead.code,
        "name": lead.name,
        "email": lead.email,
        "contact_number": lead.contact_number,
        "nationality": lead.tenant.nationality if lead.tenant else None,
        "status": lead.status,
        "platform": lead.platform,
        "lead_type": lead.lead_type,
        # Unit details
        "unit_id": unit.id,
        "unit_name": unit.unit_name,
        "unit_size": str(unit.unit_size) if unit.unit_size else None,
        "dm_no": unit.dm_no,
        "floor_no": unit.floor_no,
        "makani_no": unit.makani_no,
        "land_no": unit.land_no,
        "dewa_no": unit.dewa_no,
        "rent": str(unit.rent) if unit.rent else None,
        # Block / Property
        # "block_id": block.id,
        # "block_name": block.block_name,
        "block_id": block.id if block else None,
        "block_name": block.block_name if block else None,
        # "property_id": prop.id,
        # "property_name": prop.property_name,
        # "property_thumbnail": _get_property_thumbnail(prop),
        "property_id": prop.id if prop else None,
        "property_name": prop.property_name if prop else None,
        "property_thumbnail": _get_property_thumbnail(prop) if prop else None,
        # All unit owners
        "unit_owners": [
            {
                "owner_id": o.owner_id,
                "name": f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner else None,
                "email": o.owner.email if o.owner else None,
                "contact_number": o.owner.contact_number if o.owner else None,
                "emirates_id": o.owner.emirate_id if o.owner else None,
                "owner_number": o.owner.owner_number if o.owner else None,
                "trade_license_number": o.owner.trade_license_number if o.owner else None,
                "license_number": o.owner.license_number if o.owner else None,
                "license_expiry_date": o.owner.license_expiry_date.strftime("%Y-%m-%d") if o.owner and o.owner.license_expiry_date else None,
                "license_issuer": o.owner.license_issuer if o.owner else None,
                "fax_number": o.owner.fax_number if o.owner else None,
                "po_box_number": o.owner.po_box_number if o.owner else None,
            }
            for o in unit.unit_owners.select_related("owner__user").all()
        ],
        "tenant_id": lead.tenant_id,
        "created_at": lead.created.strftime("%m/%d/%Y %H:%M") if lead.created else None,
    }


def _serialize_lead_with_lease(lead):
    """Serialize a lead and attach lease_id / lease_stage from the matching lease."""
    data = _serialize_lead(lead)
    lease = _find_lead_lease(lead)
    data["lease_id"] = lease.id if lease else None
    data["lease_stage"] = lease.lease_stage if lease else None
    return data

@lead_get
@lead_post
@lead_put
@lead_delete
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@is_request_authenticated
def lead_view(request):
    user_profile = request.user

    # pmc = _get_pmc(user_profile)
    pmc_ids = _get_pmc_ids(user_profile)
    if not pmc_ids:
        return prepare_response(message="Company not found for this user", status=status.HTTP_400_BAD_REQUEST )

    if request.method == "GET":
        lead_id = request.GET.get("lead_id")
        if lead_id:
            lead = Lead.objects.filter(id=lead_id, pmc_id__in=pmc_ids).first()
            if not lead:
                logger.warning(
                    "LEAD_FETCH_FAILED | user_id=%d | lead_id=%s | reason=NOT_FOUND",
                    request.user.id, lead_id )
                return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)
            logger.info(
                "LEAD_FETCH_SINGLE | user_id=%d | lead_id=%s | pmc_ids=%s",
                request.user.id, lead_id, pmc_ids)
            return prepare_response(content=_serialize_lead_with_lease(lead), status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        lead_status = request.GET.get("status", "").strip()
        platform = request.GET.get("platform", "").strip()
        lead_type = request.GET.get("lead_type", "").strip()
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        leads = Lead.objects.filter(pmc_id__in=pmc_ids).order_by("-id")
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
            logger.info(
                "LEAD_CSV_EXPORTED | user_id=%d | total=%d", request.user.id, leads.count())
            return response

        total = leads.count()
        logger.info(
            "LEAD_LIST_FETCHED | user_id=%d | total=%d", request.user.id, total )
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
            logger.warning(
                "LEAD_CREATE_FAILED | user_id=%d | reason=REQUIRED_FIELDS_MISSING", request.user.id)
            return prepare_response(
                message="unit_id, name, email, contact_number, platform, lead_type are required",
                status=status.HTTP_400_BAD_REQUEST,
            )

        unit = Unit.objects.filter(id=unit_id).first()
        if not unit:
            logger.warning(
                "LEAD_CREATE_FAILED | user_id=%d | reason=UNIT_NOT_FOUND",
                request.user.id)
            return prepare_response(message="Unit not found", status=status.HTTP_404_NOT_FOUND)

        if unit.property_block_tower:
            pmc = unit.property_block_tower.property.pmc
        else:
            pmc = unit.parent_property.pmc
        if not pmc:
            return prepare_response( message="PMC not found for selected unit", status=status.HTTP_400_BAD_REQUEST)
        pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).first()
        if not pm_profile:
            return prepare_response( message=constants.NOT_VERIFIED_PROPERTY_MANAGER, status=status.HTTP_403_FORBIDDEN)
        pmc_ids = list(PMCPMMapping.objects.filter(pm=pm_profile).values_list("pmc_id", flat=True))
        if not pmc_ids and pm_profile.company_id:
            pmc_ids = [pm_profile.company_id]
        if pmc.id not in pmc_ids:
            return prepare_response( message="You are not allowed to create lead for this property", status=status.HTTP_403_FORBIDDEN)

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
        logger.info(
            "LEAD_CREATED | user_id=%d | lead_id=%d | unit_id=%d", request.user.id, lead.id, unit.id)

        ActivityLog.objects.create(
            lead=lead,
            activity_type=constants.NOTE,
            title="created this lead",
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

        lead = Lead.objects.for_user(user_profile).filter(id=lead_id).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        if "status" in data and data["status"] is not None:
            current_status = str(lead.status).upper()
            new_status = str(data["status"]).upper()

            if current_status == "NOT_INTERESTED" and new_status == "LEASE_TENANCY":
                return prepare_response(
                    message=constants.CANNOT_CONVERT_LEAD,
                    status=status.HTTP_400_BAD_REQUEST,
                )

        STATUS_LABELS = {
            "INTERESTED": "Interested",
            "NOT_INTERESTED": "Not Interested",
            "LEASE_TENANCY": "Lease/Tenancy",
        }
        changes = []
        for field in ["name", "email", "contact_number", "status", "platform", "lead_type"]:
            if field in data and data[field] is not None:
                old_val = getattr(lead, field)
                new_val = data[field]

                if str(old_val) != str(new_val):
                    if field == "status":
                        changes.append(
                            f"changed status from {STATUS_LABELS.get(str(old_val).upper(), old_val)} "
                            f"to {STATUS_LABELS.get(str(new_val).upper(), new_val)}"
                        )
                    else:
                        changes.append(f"updated {field.replace('_', ' ')}")

                setattr(lead, field, new_val)

        if "unit_id" in data:
            unit = Unit.objects.filter(id=data["unit_id"]).first()
            if unit and unit.id != lead.unit_id:
                changes.append(f"changed unit to {unit.unit_name}")
                lead.unit = unit

        lead.save()
        logger.info(
            "LEAD_UPDATED | user_id=%d | lead_id=%d | changes=%s",
            request.user.id, lead.id, ",".join(changes) if changes else "no_changes")

        comment = (data.get("comment") or "").strip()
        title = " and ".join(changes) if changes else "updated this lead"

        ActivityLog.objects.create(
            lead=lead,
            activity_type=constants.STATUS_CHANGE if any("status" in c for c in changes) else constants.NOTE,
            title=title,
            description=comment,
            created_by=user_profile.user,
        )

        return prepare_response(
            message="Lead updated successfully",
            content={"id": lead.id},
            status=status.HTTP_200_OK
        )

    elif request.method == "DELETE":
        lead_id = request.GET.get("lead_id")
        if not lead_id:
            return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

        lead = Lead.objects.for_user(user_profile).filter(id=lead_id).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        lead.delete()
        logger.info(
            "LEAD_DELETED | user_id=%d | lead_id=%s", request.user.id, lead_id )
        return prepare_response(message="Lead deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def _parse_scheduled_date(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (ValueError, TypeError):
        return None


def _serialize_activity(log):
    created_by = log.created_by
    sched = log.scheduled_date
    if isinstance(sched, str):
        sched = _parse_scheduled_date(sched)
    return {
        "id": log.id,
        "activity_type": log.activity_type,
        "title": log.title,
        "description": log.description,
        "scheduled_date": sched.strftime("%Y-%m-%dT%H:%M") if sched else None,
        "created_at": log.created.strftime("%m/%d/%Y %H:%M") if log.created else None,
        "created_by_name": f"{created_by.first_name} {created_by.last_name}".strip() if created_by else "System",
    }

@activity_get
@activity_post
@activity_put
@activity_delete
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@is_request_authenticated
def activity_log_view(request):
    user_profile = request.user
    pm = PropertyManager.objects.filter(pk=user_profile.pk).first()
    if not pm:
        return prepare_response( message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    pmc_ids = list(PMCPMMapping.objects.filter(pm=pm).values_list("pmc_id", flat=True))
    if not pmc_ids and pm.company_id:
        pmc_ids = [pm.company_id]

    if not pmc_ids:
        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    if request.method == "GET":
        lead_id = request.GET.get("lead_id")
        if not lead_id:
            return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

        lead = Lead.objects.filter(id=lead_id, pmc_id__in=pmc_ids).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        logs = ActivityLog.objects.filter(lead=lead).order_by("-created")
        logger.info(
            "ACTIVITY_LOG_FETCHED | user_id=%d | lead_id=%s | count=%d",
            request.user.id, lead_id, logs.count())
        return prepare_response(content=[_serialize_activity(l) for l in logs], status=status.HTTP_200_OK)

    elif request.method == "POST":
        data = json.loads(request.body)
        lead_id = data.get("lead_id")
        activity_type = data.get("activity_type", constants.NOTE)
        title = (data.get("title") or "").strip()
        description = (data.get("description") or "").strip()
        scheduled_date = data.get("scheduled_date")

        if not lead_id:
            return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

        lead = Lead.objects.filter(id=lead_id, pmc_id__in=pmc_ids).first()
        if not lead:
            return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

        log = ActivityLog.objects.create(
            lead=lead,
            activity_type=activity_type,
            title=title,
            description=description,
            scheduled_date=_parse_scheduled_date(scheduled_date),
            created_by=user_profile.user,
        )
        logger.info(
            "ACTIVITY_LOG_CREATED | user_id=%d | lead_id=%s | type=%s",
            request.user.id, lead_id, activity_type)
        return prepare_response(content=_serialize_activity(log), status=status.HTTP_201_CREATED)

    elif request.method == "PUT":
        data = json.loads(request.body)
        log_id = data.get("log_id")
        if not log_id:
            return prepare_response(message="log_id is required", status=status.HTTP_400_BAD_REQUEST)

        log = ActivityLog.objects.filter(id=log_id, lead__pmc_id__in=pmc_ids).first()
        if not log:
            return prepare_response(message="Activity log not found", status=status.HTTP_404_NOT_FOUND)

        for field in ["activity_type", "title", "description"]:
            if field in data:
                setattr(log, field, data[field])
        if "scheduled_date" in data:
            log.scheduled_date = _parse_scheduled_date(data["scheduled_date"])
        log.save()
        logger.info(
            "ACTIVITY_LOG_UPDATED | user_id=%d | log_id=%s",
            request.user.id, log_id)
        return prepare_response(content=_serialize_activity(log), status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        log_id = request.GET.get("log_id")
        if not log_id:
            return prepare_response(message="log_id is required", status=status.HTTP_400_BAD_REQUEST)

        log = ActivityLog.objects.filter(id=log_id, lead__pmc_id__in=pmc_ids).first()
        if not log:
            return prepare_response(message="Activity log not found", status=status.HTTP_404_NOT_FOUND)

        log.delete()
        logger.info(
            "ACTIVITY_LOG_DELETED | user_id=%d | log_id=%s", request.user.id, log_id)
        return prepare_response(message="Activity log deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@lead_check_active_lease_get
@api_view(['GET'])
@is_request_authenticated
def lead_check_active_lease(request):
    user_profile = request.user
    pm = PropertyManager.objects.filter(pk=user_profile.pk).first()
    if not pm:
        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    pmc_ids = list(PMCPMMapping.objects.filter(pm=pm).values_list("pmc_id", flat=True))
    if not pmc_ids and pm.company_id:
        pmc_ids = [pm.company_id]
    if not pmc_ids:
        return prepare_response( message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lead_id = request.GET.get("lead_id", "").strip()
    if not lead_id:
        return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

    lead = Lead.objects.filter(id=lead_id,pmc_id__in=pmc_ids).select_related("unit").first()
    if not lead:
        return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

    from lease.models import Lease
    has_active_lease = Lease.objects.filter(unit=lead.unit, lease_status="ACTIVE").exists()
    logger.info(
        "LEAD_LEASE_CHECK | user_id=%d | lead_id=%s | has_active_lease=%s",
        request.user.id, lead_id, has_active_lease)

    return prepare_response(content={"has_active_lease": has_active_lease}, status=status.HTTP_200_OK)

@lead_bulk_import_post
@api_view(['POST'])
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
    logger.info(
        "LEAD_BULK_IMPORT_DONE | user_id=%d | created=%d | skipped=%d",
        request.user.id, created, skipped)
    return prepare_response(
        message=f"{created} lead(s) imported successfully. {skipped} skipped.",
        content={"created": created, "skipped": skipped, "errors": errors},
        status=status.HTTP_201_CREATED,
    )

from urllib.parse import urlencode
def generate_google_calendar_url(title, description, start_time, end_time):
    """
    Generate a pre-filled Google Calendar event URL.
    """
    start_time = start_time.astimezone()
    end_time = end_time.astimezone()
    start_str = start_time.strftime("%Y%m%dT%H%M%S")
    end_str = end_time.strftime("%Y%m%dT%H%M%S")

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{start_str}/{end_str}",
        "stz": "Asia/Kolkata",
        "etz": "Asia/Kolkata",
        "details": description or "",
    }
    return (
        "https://calendar.google.com/calendar/r/eventedit?"
        + urlencode(params)
    )

@api_view(["POST"])
@is_request_authenticated
def schedule_meeting_view(request):
    user_profile = request.user
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return prepare_response(message="Invalid JSON", status=status.HTTP_400_BAD_REQUEST)

    lead_id = data.get("lead_id")
    title = (data.get("title") or "").strip()
    description = (data.get("description") or "").strip()
    start_time = data.get("start_time")
    end_time = data.get("end_time")

    if not lead_id:
        return prepare_response(message="lead_id is required", status=status.HTTP_400_BAD_REQUEST)

    if not title:
        return prepare_response(message="title is required", status=status.HTTP_400_BAD_REQUEST)

    if not start_time:
        return prepare_response(message="start_time is required", status=status.HTTP_400_BAD_REQUEST)

    if not end_time:
        return prepare_response(message="end_time is required", status=status.HTTP_400_BAD_REQUEST)

    pmc_ids = _get_pmc_ids(user_profile)
    if not pmc_ids:
        return prepare_response(message="Company not found for this user", status=status.HTTP_400_BAD_REQUEST)

    lead = Lead.objects.filter(id=lead_id, pmc_id__in=pmc_ids, is_active=True).first()

    if not lead:
        return prepare_response(message="Lead not found", status=status.HTTP_404_NOT_FOUND)

    try:
        start_datetime = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end_datetime = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return prepare_response(message="Invalid start_time or end_time format", status=status.HTTP_400_BAD_REQUEST)

    if end_datetime <= start_datetime:
        return prepare_response(message="end_time must be greater than start_time", status=status.HTTP_400_BAD_REQUEST)

    google_calendar_url = generate_google_calendar_url(
        title=title,
        description=description,
        start_time=start_datetime,
        end_time=end_datetime,
    )

    meeting = ScheduleMeeting.objects.create(
        lead=lead,
        title=title,
        description=description,
        start_time=start_datetime,
        end_time=end_datetime,
        status="SCHEDULED",
        google_calendar_url=google_calendar_url,
        created_by=user_profile.user,
    )

    ActivityLog.objects.create(
        lead=lead,
        activity_type=constants.NOTE,
        title="scheduled a meeting",
        description=(
            f"{title} scheduled from "
            f"{start_datetime.strftime('%d %b %Y %I:%M %p')} "
            f"to "
            f"{end_datetime.strftime('%d %b %Y %I:%M %p')}"
        ),
        created_by=user_profile.user,
    )

    return prepare_response(
        message="Meeting scheduled successfully",
        content={
            "id": meeting.id,
            "lead_id": lead.id,
            "lead_name": lead.name,
            "lead_email": lead.email,
            "title": meeting.title,
            "description": meeting.description,
            "start_time": meeting.start_time,
            "end_time": meeting.end_time,
            "status": meeting.status,
            "google_calendar_url": meeting.google_calendar_url,
        },
        status=status.HTTP_201_CREATED
    )