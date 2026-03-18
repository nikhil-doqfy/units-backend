import csv
import json
import os
import uuid
from weasyprint import HTML as WeasyprintHTML
from datetime import datetime, date

from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse

from utilities.decorator import is_request_authenticated
from django.template.loader import render_to_string

from utilities.helper_functions import (
    prepare_response, fetch_s3_presigned_url,
    upload_file_to_s3_base64, get_extension_from_base64,
    replace_placeholders, send_ses_email,
)
from utilities import status, constants
from property.models import Unit
from user_service.models import Tenant, TenantDocuments, DocumentType
from property_management import settings
from property_management.utils import audit_logs
from .models import Lease, LeaseDocuments, Template, TemplateField, TemplateValue


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value)[:26], fmt)
        except ValueError:
            continue
    return None


def _get_tenant_photo(tenant):
    if not tenant or not tenant.profile_image:
        return None
    try:
        return fetch_s3_presigned_url(tenant.profile_image)
    except Exception:
        return None


def _get_property_thumbnail(unit):
    if not unit:
        return None
    try:
        pb = unit.property_block_tower
        return pb.property._get_thumbnail() if pb and pb.property else None
    except Exception:
        return None


def _serialize_lease(lease):
    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    unit_owners = []
    if unit:
        for o in unit.unit_owners.select_related("owner__user").all():
            unit_owners.append({
                "id":                   o.id,
                "owner_id":             o.owner_id,
                "name":                 f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner and o.owner.user else None,
                "email":                o.owner.email if o.owner else None,
                "contact_number":       o.owner.contact_number if o.owner else None,
                "emirates_id":          o.owner.emirate_id if o.owner else None,
                "owner_number":         o.owner.owner_number if o.owner else None,
                "trade_license_number": o.owner.trade_license_number if o.owner else None,
                "license_number":       o.owner.license_number if o.owner else None,
                "license_expiry_date":  o.owner.license_expiry_date.isoformat() if o.owner and o.owner.license_expiry_date else None,
                "license_issuer":       o.owner.license_issuer if o.owner else None,
                "fax_number":           o.owner.fax_number if o.owner else None,
                "po_box_number":        o.owner.po_box_number if o.owner else None,
            })

    return {
        "id": lease.id,
        "code": lease.code,
        # property / block
        "property_id":         prop.id if prop else None,
        "property_name":       prop.property_name if prop else None,
        "property_thumbnail":  _get_property_thumbnail(unit),
        "property_block_id":   pb.id if pb else None,
        "property_block_name": pb.block_name if pb else None,
        # unit
        "unit_id":    unit.id if unit else None,
        "unit_name":  unit.unit_name if unit else None,
        "unit_size":  str(unit.unit_size) if unit and unit.unit_size else None,
        "land_no":    unit.land_no if unit else None,
        "dm_no":      unit.dm_no if unit else None,
        "unit_usage": unit.unit_usage if unit else None,
        "unit_type":  unit.unit_type if unit else None,
        "sub_type":   unit.sub_type if unit else None,
        "makani_no":  unit.makani_no if unit else None,
        "floor_no":   unit.floor_no if unit else None,
        "unit_owners": unit_owners,
        # tenant basics
        "tenant_id":    t.id if t else None,
        "tenant_code":  t.code if t else None,
        "tenant_name":  (
            f"{t.user.first_name} {t.user.last_name}".strip()
            if t and t.user else None
        ),
        "tenant_email":   t.user.email if t and t.user else None,
        "tenant_contact": t.contact_number if t else None,
        "emirates_id":    t.emirate_id if t else None,
        "address_line_1": t.address_line_1 if t else None,
        "address_line_2": t.address_line_2 if t else None,
        "passport_number": t.passport_number if t else None,
        "passport_expiry": str(t.passport_expiry_datetime)[:10] if t and t.passport_expiry_datetime else None,
        "visa_number":     t.visa_number if t else None,
        "visa_expiry":     str(t.visa_expiry_datetime)[:10] if t and t.visa_expiry_datetime else None,
        # lease dates & financials
        "lease_status":         lease.lease_status,
        "lease_stage":          lease.lease_stage,
        "start_date":           str(lease.start_date)[:10] if lease.start_date else None,
        "end_date":             str(lease.end_date)[:10] if lease.end_date else None,
        "grace_start_date":     str(lease.grace_start_date)[:10] if lease.grace_start_date else None,
        "grace_end_date":       str(lease.grace_end_date)[:10] if lease.grace_end_date else None,
        "annual_amount":        lease.annual_amount,
        "actual_annual_amount": lease.actual_annual_amount,
        "booking_amount":       lease.booking_amount,
        "maintenance_charges":  lease.maintenance_charges,
        "rent":                 lease.rent,
        "security_deposit":     lease.security_deposit,
        "commission":           lease.commission,
        "notice_period":        lease.notice_period,
        "discount":             lease.discount,
        "contract_amount":      lease.contract_amount,
        "payment_count":        lease.payment_count,
        "shell_and_core":       lease.shell_and_core,
        "remarks":              lease.remarks,
        "pdf_path":             lease.pdf_path,
    }


def _update_tenant_fields(tenant_obj, data):
    user = tenant_obj.user
    name = data.get("tenant_name") or data.get("name") or ""
    if name:
        first_name, _, last_name = name.partition(" ")
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save(update_fields=["first_name", "last_name"])
    for src, dest in [
        ("contact_number", "contact_number"),
        ("emirates_id", "emirate_id"),
        ("address_line_1", "address_line_1"),
        ("address_line_2", "address_line_2"),
        ("passport_number", "passport_number"),
        ("visa_number", "visa_number"),
    ]:
        val = data.get(src)
        if val:
            setattr(tenant_obj, dest, val)
    if data.get("passport_expiry_date"):
        tenant_obj.passport_expiry_datetime = _parse_date(data["passport_expiry_date"])
    if data.get("visa_expiry_date"):
        tenant_obj.visa_expiry_datetime = _parse_date(data["visa_expiry_date"])
    tenant_obj.save()
    return tenant_obj


def _create_tenant(email, data, created_by):
    name = data.get("tenant_name") or data.get("name") or ""
    first_name, _, last_name = name.partition(" ")
    with transaction.atomic():
        django_user = User.objects.create_user(
            username=email, email=email,
            first_name=first_name, last_name=last_name,
            password=User.objects.make_random_password(),
        )
        tenant_obj = Tenant.objects.create(
            user=django_user,
            created_by=created_by.user,
            email=email,
            contact_number=data.get("contact_number") or "",
            emirate_id=data.get("emirates_id") or "",
            address_line_1=data.get("address_line_1") or "",
            address_line_2=data.get("address_line_2") or "",
            passport_number=data.get("passport_number") or "",
            passport_expiry_datetime=_parse_date(data.get("passport_expiry_date")),
            visa_number=data.get("visa_number") or "",
            visa_expiry_datetime=_parse_date(data.get("visa_expiry_date")),
        )
    return tenant_obj


@is_request_authenticated
def lease_view(request):
    user = request.user

    try:
        # ─── GET ───────────────────────────────────────────────────────────────
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")

            if lease_id:
                lease = (
                    Lease.objects
                    .select_related("unit__property_block_tower__property", "tenant__user")
                    .prefetch_related("unit__unit_owners__owner__user")
                    .filter(id=lease_id, is_active=True)
                    .first()
                )
                if not lease:
                    return prepare_response(
                        message="Lease not found",
                        status=status.HTTP_404_NOT_FOUND,
                    )
                return prepare_response(content=_serialize_lease(lease))

            # List with optional filters + pagination
            qs = Lease.objects.select_related("unit__property_block_tower__property", "tenant__user").filter(is_active=True)

            property_id = request.GET.get("property_id")
            tenant_id = request.GET.get("tenant_id")
            lease_status = request.GET.get("lease_status")
            search = request.GET.get("search", "").strip()

            if property_id:
                qs = qs.filter(unit__property_block_tower__property_id=property_id)
            if tenant_id:
                qs = qs.filter(tenant_id=tenant_id)
            if lease_status:
                qs = qs.filter(lease_status=lease_status)
            lease_stage = request.GET.get("lease_stage")
            if lease_stage:
                qs = qs.filter(lease_stage=lease_stage)
            if search:
                qs = qs.filter(code__icontains=search)

            qs = qs.order_by("-created")

            page = int(request.GET.get("page", 1))
            page_size = int(request.GET.get("page_size", 20))
            paginator = Paginator(qs, page_size)
            page_obj = paginator.get_page(page)

            return prepare_response(
                content=[_serialize_lease(l) for l in page_obj],
                paginator=page_obj,
                total_records=paginator.count,
            )

        # ─── POST ──────────────────────────────────────────────────────────────
        elif request.method == "POST":
            body = json.loads(request.body)

            unit_id = body.get("unit_id") or body.get("property_id")
            tenant_id = body.get("tenant_id")
            email = (body.get("email") or "").strip()

            if not unit_id:
                return prepare_response(
                    message="unit_id is required",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            unit_obj = Unit.objects.select_related("property_block_tower__property").filter(id=unit_id).first()
            if not unit_obj:
                return prepare_response(
                    message="Unit not found",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Resolve tenant: by ID → by email → create new
            tenant_obj = None
            if tenant_id:
                tenant_obj = Tenant.objects.select_related("user").filter(id=tenant_id, user__is_active=True).first()

            if not tenant_obj and email:
                tenant_obj = Tenant.objects.select_related("user").filter(
                    Q(email__iexact=email) | Q(user__email__iexact=email),
                    user__is_active=True,
                ).first()

            if tenant_obj:
                # Update fields from body if provided
                _update_tenant_fields(tenant_obj, body)
            elif email:
                tenant_obj = _create_tenant(email, body, user)
            else:
                return prepare_response(
                    message="tenant_id or email is required",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease = Lease.objects.create(
                created_by=user.user,
                unit=unit_obj,
                tenant=tenant_obj,
                start_date=_parse_date(body.get("start_date")),
                end_date=_parse_date(body.get("end_date")),
                grace_start_date=_parse_date(body.get("grace_start_date")),
                grace_end_date=_parse_date(body.get("grace_end_date")),
                annual_amount=body.get("annual_amount") or None,
                actual_annual_amount=body.get("actual_annual_amount") or None,
                booking_amount=body.get("booking_amount") or None,
                maintenance_charges=body.get("maintenance_charges") or None,
                rent=body.get("rent") or None,
                security_deposit=body.get("security_deposit") or None,
                commission=body.get("commission") or None,
                notice_period=body.get("notice_period") or None,
                discount=body.get("discount") or None,
                contract_amount=body.get("contract_amount") or None,
                payment_count=body.get("payment_count") or None,
                shell_and_core=bool(body.get("shell_and_core", False)),
                remarks=body.get("remarks") or "",
                lease_status=body.get("lease_status") or constants.LEASE_STATUS_CHOICES[0][0],
                lease_stage=body.get("lease_stage") or constants.INVITE,
            )

            return prepare_response(
                content=_serialize_lease(lease),
                message="Lease created successfully",
                status=status.HTTP_201_CREATED,
            )

        # ─── PUT ───────────────────────────────────────────────────────────────
        elif request.method == "PUT":
            body = json.loads(request.body)
            lease_id = body.get("lease_id") or body.get("id")
            if not lease_id:
                return prepare_response(
                    message="lease_id is required",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease = Lease.objects.filter(id=lease_id, is_active=True).first()
            if not lease:
                return prepare_response(
                    message="Lease not found",
                    status=status.HTTP_404_NOT_FOUND,
                )

            # Update only fields that are explicitly provided
            updatable = {
                "start_date": _parse_date(body.get("start_date")),
                "end_date": _parse_date(body.get("end_date")),
                "grace_start_date": _parse_date(body.get("grace_start_date")),
                "grace_end_date": _parse_date(body.get("grace_end_date")),
                "annual_amount": body.get("annual_amount"),
                "actual_annual_amount": body.get("actual_annual_amount"),
                "booking_amount": body.get("booking_amount"),
                "maintenance_charges": body.get("maintenance_charges"),
                "rent": body.get("rent"),
                "security_deposit": body.get("security_deposit"),
                "commission": body.get("commission"),
                "notice_period": body.get("notice_period"),
                "discount": body.get("discount"),
                "contract_amount": body.get("contract_amount"),
                "payment_count": body.get("payment_count"),
                "remarks": body.get("remarks"),
                "lease_status": body.get("lease_status"),
                "lease_stage":  body.get("lease_stage"),
            }

            if "shell_and_core" in body:
                updatable["shell_and_core"] = bool(body["shell_and_core"])

            for field, value in updatable.items():
                if value is not None:
                    setattr(lease, field, value)

            lease.save()

            return prepare_response(
                content=_serialize_lease(lease),
                message="Lease updated successfully",
            )

        # ─── DELETE ────────────────────────────────────────────────────────────
        elif request.method == "DELETE":
            lease_id = request.GET.get("lease_id")
            if not lease_id:
                return prepare_response(
                    message="lease_id is required",
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease = Lease.objects.filter(id=lease_id, is_active=True).first()
            if not lease:
                return prepare_response(
                    message="Lease not found",
                    status=status.HTTP_404_NOT_FOUND,
                )

            lease.is_active = False
            lease.save(update_fields=["is_active"])

            return prepare_response(message="Lease deleted successfully")

        return prepare_response(
            message="Method not allowed",
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


def _serialize_tenant_lease(lease):
    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None
    return {
        "lease_id":            lease.id,
        "lease_code":          lease.code,
        "lease_status":        lease.lease_status,
        "lease_stage":         lease.lease_stage,
        "start_date":          str(lease.start_date)[:10] if lease.start_date else None,
        "end_date":            str(lease.end_date)[:10] if lease.end_date else None,
        "rent":                lease.rent,
        "annual_amount":       lease.annual_amount,
        "tenant_id":           t.id if t else None,
        "tenant_code":         t.code if t else None,
        "tenant_name":         f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else None,
        "tenant_photo":        _get_tenant_photo(t),
        "email":               t.email if t else None,
        "contact_number":      t.contact_number if t else None,
        "emirates_id":         t.emirate_id if t else None,
        "unit_id":             unit.id if unit else None,
        "unit_name":           unit.unit_name if unit else None,
        "property_id":         prop.id if prop else None,
        "property_block_id":   pb.id if pb else None,
        "property_block_name": pb.block_name if pb else None,
        "property_name":       prop.property_name if prop else None,
        "property_thumbnail":  _get_property_thumbnail(unit),
    }


@is_request_authenticated
def tenant_leases_view(request):
    if request.method != "GET":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        tab        = request.GET.get("tab", "onboarding")   # onboarding | active | past | rejected
        search     = request.GET.get("search", "").strip()
        page       = int(request.GET.get("page", 1))
        page_size  = int(request.GET.get("page_size", 10))
        export     = request.GET.get("export", "")
        today      = date.today()

        qs = (
            Lease.objects
            .select_related("tenant__user", "unit__property_block_tower__property")
            .prefetch_related("unit__property_block_tower__property__property_images")
            .filter(is_active=True)
        )

        if tab == "onboarding":
            qs = qs.filter(lease_status="DRAFT")
        elif tab == "active":
            qs = qs.filter(
                lease_status="ACTIVE",
                start_date__date__lte=today,
                end_date__date__gte=today,
            )
        elif tab == "past":
            qs = qs.filter(lease_status__in=["INACTIVE", "EXPIRED"])
        elif tab == "rejected":
            qs = qs.filter(lease_status="REJECTED")

        if search:
            qs = qs.filter(
                Q(tenant__user__first_name__icontains=search) |
                Q(tenant__user__last_name__icontains=search) |
                Q(tenant__email__icontains=search) |
                Q(tenant__contact_number__icontains=search) |
                Q(tenant__code__icontains=search) |
                Q(code__icontains=search)
            )

        qs = qs.order_by("-created")

        if export == "csv":
            response = HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="tenants_{tab}.csv"'
            writer = csv.writer(response)
            writer.writerow([
                "Lease Code", "Tenant Code", "Tenant Name", "Email",
                "Contact", "Emirates ID", "Property", "Block",
                "Start Date", "End Date", "Rent", "Status",
            ])
            for l in qs:
                row = _serialize_tenant_lease(l)
                writer.writerow([
                    row["lease_code"], row["tenant_code"], row["tenant_name"],
                    row["email"], row["contact_number"], row["emirates_id"],
                    row["property_name"], row["property_block_name"],
                    row["start_date"], row["end_date"], row["rent"], row["lease_status"],
                ])
            return response

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page)

        return prepare_response(
            content=[_serialize_tenant_lease(l) for l in page_obj],
            pagination={
                "total_records": paginator.count,
                "total_pages":   paginator.num_pages,
                "current_page":  page,
                "page_size":     page_size,
            },
        )

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Lease Onboarding Documents ─────────────────────────────────────────────────

@is_request_authenticated
def lease_onboarding_documents_view(request):
    """
    GET    /api/lease/onboarding-documents?lease_id=X
           Returns tenant_documents, lease_documents for this lease.
    POST   /api/lease/onboarding-documents
           Uploads one or more files (base64) as LeaseDocuments.
    DELETE /api/lease/onboarding-documents?document_id=X
           Hard-deletes a LeaseDocument.
    """
    user = request.user

    if request.method == "GET":
        lease_id = request.GET.get("lease_id")
        if not lease_id:
            return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.filter(id=lease_id, is_active=True).select_related("tenant").first()
        if not lease:
            return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        def _doc(doc, source):
            return {
                "id":                 doc.id,
                "source":             source,
                "file_name":          doc.file_name,
                "document_type_id":   doc.document_type_id,
                "document_type_name": doc.document_type.name,
                "url":                fetch_s3_presigned_url(doc.file_path, doc.file_name),
            }

        tenant_docs = (
            TenantDocuments.objects
            .filter(tenant=lease.tenant, is_active=True)
            .select_related("document_type")
        )
        lease_docs = (
            LeaseDocuments.objects
            .filter(lease=lease, is_active=True)
            .select_related("document_type")
        )

        return prepare_response(content={
            "tenant_documents": [_doc(d, "tenant") for d in tenant_docs],
            "lease_documents":  [_doc(d, "lease")  for d in lease_docs],
        })

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            return prepare_response(message="Invalid JSON", status=status.HTTP_400_BAD_REQUEST)

        lease_id       = data.get("lease_id")
        documents_data = data.get("documents") or []

        if not lease_id:
            return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.filter(id=lease_id, is_active=True).first()
        if not lease:
            return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        created_ids = []
        for doc_data in documents_data:
            base64_data = doc_data.get("data")
            if not base64_data:
                continue

            file_name        = doc_data.get("file_name") or f"{uuid.uuid4()}.pdf"
            document_type_id = doc_data.get("document_type_id")
            doc_type = DocumentType.objects.filter(id=document_type_id).first() if document_type_id else None
            if not doc_type:
                continue

            ext             = get_extension_from_base64(base64_data) or ".pdf"
            unique_filename = f"{uuid.uuid4()}{ext}"
            s3_key          = f"lease/{lease.id}/onboarding/{doc_type.id}/{unique_filename}"
            url             = upload_file_to_s3_base64(base64_data, s3_key)

            doc = LeaseDocuments.objects.create(
                created_by    = user.user,
                lease         = lease,
                document_type = doc_type,
                file_name     = file_name,
                file_path     = url,
            )
            created_ids.append(doc.id)

        return prepare_response(
            message="Documents uploaded successfully",
            content={"ids": created_ids},
            status=status.HTTP_201_CREATED,
        )

    elif request.method == "DELETE":
        document_id = request.GET.get("document_id")
        if not document_id:
            return prepare_response(message="document_id is required", status=status.HTTP_400_BAD_REQUEST)
        LeaseDocuments.objects.filter(id=document_id).delete()
        return prepare_response(message="Document deleted successfully")

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_405_METHOD_NOT_ALLOWED,
    )


# ── Template views ─────────────────────────────────────────────────────────

@is_request_authenticated
def get_templates(request):
    if request.method == "GET":
        try:
            templates = Template.objects.filter(is_active=True).values("id", "name").order_by("id")
            return prepare_response(
                content={"templates": list(templates)},
                message="Templates fetched successfully",
                status=status.HTTP_200_OK,
            )
        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@is_request_authenticated
def get_template_fields(request):
    if request.method == "GET":
        try:
            template_id = request.GET.get("template_id")
            lease_id    = request.GET.get("lease_id")
            if not template_id:
                return prepare_response(
                    message=constants.TEMPLATE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            template = Template.objects.get(id=template_id)
            fields = TemplateField.objects.filter(template=template)

            field_list = []
            for field in fields:
                field_list.append({
                    "id_attribute":    field.id_attribute,
                    "name_attribute":  field.name_attribute,
                    "label":           field.label_attribute,
                    "html_tag":        field.html_tag,
                    "required":        field.required,
                    "min_value":       field.min_value,
                    "max_value":       field.max_value,
                    "min_length":      field.min_length,
                    "max_length":      field.max_length,
                    "pattern":         field.pattern,
                    "predefined_value": field.predefined_value,
                })

            html_content = ""
            if template.template_path and os.path.exists(template.template_path):
                with open(template.template_path, "r", encoding="utf-8") as f:
                    html_content = f.read()

            # ── Saved values (previously submitted for this lease) ─────────
            saved_values = {}
            if lease_id:
                tvs = TemplateValue.objects.filter(
                    template_field__template=template, lease_id=lease_id
                ).select_related("template_field")
                for tv in tvs:
                    saved_values[tv.template_field.name_attribute] = str(tv.value) if tv.value is not None else ""

            # ── Lease-derived defaults (pre-populate on first open) ────────
            lease_defaults = {}
            if lease_id:
                try:
                    lease = Lease.objects.select_related(
                        "tenant__user",
                        "unit__property_block_tower__property",
                    ).prefetch_related("unit__unit_owners__owner__user").get(id=lease_id)

                    t    = lease.tenant
                    unit = lease.unit
                    pb   = unit.property_block_tower if unit else None
                    prop = pb.property if pb else None
                    owner = unit.unit_owners.select_related("owner__user").first() if unit else None
                    o = owner.owner if owner else None

                    def _str(v):
                        return str(v) if v is not None else ""

                    usage = unit.unit_usage if unit else ""
                    lease_defaults = {
                        # Tenant
                        "tenant_name":       f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "",
                        "tenant_email":      t.user.email if t and t.user else "",
                        "tenant_phone":      _str(t.contact_number) if t else "",
                        "tenant_emirates_id": _str(t.emirate_id) if t else "",
                        # Owner / Lessor (first owner)
                        "owner_name":        f"{o.user.first_name} {o.user.last_name}".strip() if o and o.user else "",
                        "lessor_name":       f"{o.user.first_name} {o.user.last_name}".strip() if o and o.user else "",
                        "lessor_email":      _str(o.email) if o else "",
                        "lessor_phone":      _str(o.contact_number) if o else "",
                        "lessor_emirates_id": _str(o.emirate_id) if o else "",
                        "lessor_license_no": _str(o.trade_license_number) if o else "",
                        "lessor_licensing_authority": _str(o.license_issuer) if o else "",
                        # Property / Unit
                        "building_name":  prop.property_name if prop else "",
                        "property_no":    _str(unit.unit_name) if unit else "",
                        "property_type":  _str(unit.unit_type) if unit else "",
                        "property_area":  _str(unit.unit_size) if unit and unit.unit_size else "",
                        "location":       pb.block_name if pb else (prop.property_name if prop else ""),
                        "makani_no":      _str(unit.makani_no) if unit else "",
                        "plot_no":        _str(unit.land_no) if unit else "",
                        "dewa_premises_no": _str(unit.dm_no) if unit else "",
                        # Property usage radio (used as CSS class in template)
                        "property_usage_residential": "filled" if usage == "RESIDENTIAL" else "",
                        "property_usage_commercial":  "filled" if usage == "COMMERCIAL" else "",
                        "property_usage_industrial":  "filled" if usage == "INDUSTRIAL" else "",
                        # Contract
                        "contract_start_date": _str(lease.start_date)[:10] if lease.start_date else "",
                        "contract_end_date":   _str(lease.end_date)[:10] if lease.end_date else "",
                        "annual_rent":         _str(lease.annual_amount) if lease.annual_amount else "",
                        "security_deposit":    _str(lease.security_deposit) if lease.security_deposit else "",
                        "contract_value":      _str(lease.contract_amount) if lease.contract_amount else "",
                        "contract_date":       _str(lease.start_date)[:10] if lease.start_date else "",
                        "mode_of_payment":     "Cheque",
                    }
                except Lease.DoesNotExist:
                    pass

            pdf_url = ""
            if lease_id:
                try:
                    lease_obj = Lease.objects.get(id=lease_id)
                    if lease_obj.pdf_path:
                        pdf_url = fetch_s3_presigned_url(lease_obj.pdf_path)
                except Lease.DoesNotExist:
                    pass

            return prepare_response(
                content={
                    "template_id":    template.id,
                    "template_name":  template.name,
                    "template_path":  template.template_path,
                    "html_content":   html_content,
                    "fields":         field_list,
                    "saved_values":   saved_values,
                    "lease_defaults": lease_defaults,
                    "pdf_url":        pdf_url,
                },
                message=constants.TEMPLATE_FIELDS_FETCHED,
                status=status.HTTP_200_OK,
            )

        except Template.DoesNotExist:
            return prepare_response(
                message=constants.INVALID_TEMPLATE_ID,
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@is_request_authenticated
def generate_contract(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body = json.loads(request.body)
        template_id = body.get("template_id")
        lease_id = body.get("lease_id")
        values_dict = body.get("values")

        if not template_id or not lease_id or not values_dict:
            return prepare_response(
                message=constants.TEMPLATE_LEASE_VALUES_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST,
            )

        template = Template.objects.filter(id=template_id, is_active=True).first()
        if not template:
            return prepare_response(message=constants.INVALID_TEMPLATE_ID, status=status.HTTP_404_NOT_FOUND)

        lease = Lease.objects.filter(id=lease_id).first()
        if not lease:
            return prepare_response(message=constants.INVALID_LAESE_ID, status=status.HTTP_404_NOT_FOUND)

        fields = TemplateField.objects.filter(template=template, is_active=True)
        for field in fields:
            val = str(values_dict.get(field.name_attribute, ""))
            tv, created = TemplateValue.objects.get_or_create(
                template_field=field,
                lease=lease,
                defaults={"value": val, "created_by": request.user.user},
            )
            if not created:
                tv.value = val
                tv.save(update_fields=["value"])

        template_path = template.template_path
        if not template_path or not os.path.exists(template_path):
            return prepare_response(
                message=f"Template not found: {template_path}",
                status=status.HTTP_404_NOT_FOUND,
            )

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()

        mapping = {}
        fields = TemplateField.objects.filter(template=template, is_active=True)
        for field in fields:
            key = field.id_attribute or field.name_attribute
            if key and key in values_dict:
                mapping[key] = values_dict[key]

        html_content = replace_placeholders(html_content, mapping)
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"lease_{timestamp}.html"

        save_dir = os.path.join(settings.MEDIA_ROOT, "generated_templates")
        os.makedirs(save_dir, exist_ok=True)
        save_path = os.path.join(save_dir, filename)
        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)

        pdf_filename = f"lease_{timestamp}.pdf"
        pdf_bytes = WeasyprintHTML(string=html_content).write_pdf()

        s3_object_name = f"generated_templates/{pdf_filename}"
        pdf_s3_url = upload_file_to_s3_base64(pdf_bytes, s3_object_name)

        lease.pdf_path = pdf_s3_url
        lease.save(update_fields=["pdf_path"])

        audit_logs(request, f"Generated lease contract for lease '{lease.code}'", constants.CREATED)

        return prepare_response(
            message=constants.CONTRACT_GENERATED_SUCCESS,
            content={"file_name": filename, "pdf_url": fetch_s3_presigned_url(pdf_s3_url)},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@is_request_authenticated
def send_negotiation(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        if not lease_id:
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related(
            "tenant__user",
            "unit__property_block_tower__property",
        ).prefetch_related(
            "unit__unit_owners__owner__user"
        ).get(id=lease_id)

        t    = lease.tenant
        unit = lease.unit
        pb   = unit.property_block_tower if unit else None
        prop = pb.property if pb else None

        tenant_name  = f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "Tenant"
        tenant_email = t.user.email if t and t.user else None

        owner_emails = []
        if unit:
            for o in unit.unit_owners.select_related("owner__user").all():
                if o.owner and o.owner.email:
                    owner_emails.append({
                        "email": o.owner.email,
                        "name":  f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner.user else "Owner",
                    })

        recipients = []
        if tenant_email:
            recipients.append({"email": tenant_email, "name": tenant_name})
        recipients.extend(owner_emails)

        if not recipients:
            return prepare_response(message="No recipient emails found for this lease", status=status.HTTP_400_BAD_REQUEST)

        ctx = {
            "lease_code":    lease.code,
            "tenant_name":   tenant_name,
            "property_name": prop.property_name if prop else "",
            "unit_name":     unit.unit_name if unit else "",
            "pdf_url":       fetch_s3_presigned_url(lease.pdf_path) if lease.pdf_path else "",
        }

        subject = f"Lease Negotiation Document – {lease.code}"
        failed  = []
        sent    = []
        for r in recipients:
            ctx["recipient_name"] = r["name"]
            body_html = render_to_string("email_templates/lease_negotiation.html", ctx)
            body_text = (
                f"Dear {r['name']},\n\n"
                f"A lease negotiation document has been prepared for lease {lease.code}.\n"
                f"Tenant: {tenant_name} | Property: {ctx['property_name']} | Unit: {ctx['unit_name']}\n"
                + (f"View document: {ctx['pdf_url']}\n" if ctx["pdf_url"] else "")
                + "\nThank you,\nThe Doqfy Team"
            )
            ok = send_ses_email(r["email"], subject, body_text, body_html)
            (sent if ok else failed).append(r["email"])

        audit_logs(request, f"Sent negotiation email for lease '{lease.code}' to {sent}", constants.CREATED)

        return prepare_response(
            message="Negotiation email sent successfully",
            content={"sent": sent, "failed": failed},
            status=status.HTTP_200_OK,
        )

    except Lease.DoesNotExist:
        return prepare_response(message=constants.INVALID_LAESE_ID, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
