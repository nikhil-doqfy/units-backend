import csv
import json
import os
import uuid
from weasyprint import HTML as WeasyprintHTML
from datetime import datetime, date

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.contrib.auth.models import User
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from utilities.decorator import is_request_authenticated
from django.template.loader import render_to_string

from utilities.helper_functions import (
    prepare_response, fetch_s3_presigned_url,
    upload_file_to_s3_base64, get_extension_from_base64,
    replace_placeholders, send_ses_email, fetch_s3_file_as_base64,
    safe_epoch_to_datetime, export_to_csv, datetime_to_epoch_millis,
    fetch_s3_presigned_url_for_download, translate_to_arabic,
)
from utilities import status, constants
from property.models import Unit
from user_service.models import Tenant, TenantDocuments, DocumentType, UserProfile, Documents, Approval
from property_management import settings
from property_management.utils import audit_logs, get_tenant_detail_by_id
from property_management.models import TermAndCondition
from payment.models import Bank
from .models import Lease, LeaseDocuments, LeaseTransaction, Template, TemplateField, TemplateValue
from charges.models import Charge
from .serializers import serialize_lease, serialize_tenant_lease, group_lease_cheques, serialize_cheque_list_row, serialize_lease_cheque


def _parse_date(value):
    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            return datetime.strptime(str(value)[:26], fmt)
        except ValueError:
            continue
    return None


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
        ("nationality", "nationality"),
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
            nationality=data.get("nationality") or "",
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
                return prepare_response(content=serialize_lease(lease))

            # List with optional filters + pagination
            qs = Lease.objects.select_related("unit__property_block_tower__property", "tenant__user").filter(is_active=True)

            property_id = request.GET.get("property_id")
            unit_id = request.GET.get("unit_id")
            tenant_id = request.GET.get("tenant_id")
            lease_status = request.GET.get("lease_status")
            search = request.GET.get("search", "").strip()

            if property_id:
                qs = qs.filter(unit__property_block_tower__property_id=property_id)
            if unit_id:
                qs = qs.filter(unit_id=unit_id)
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
                content=[serialize_lease(l) for l in page_obj],
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

            # Block if tenant already has an active lease
            active_lease = Lease.objects.filter(
                tenant=tenant_obj,
                lease_status="ACTIVE",
                is_active=True,
            ).first()
            if active_lease:
                return prepare_response(
                    message=f"Tenant already has an active lease ({active_lease.code}). A new lease cannot be created while an active lease exists.",
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
                platform=body.get("platform") or None,
            )

            return prepare_response(
                content=serialize_lease(lease),
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
                "platform":     body.get("platform"),
            }

            if "shell_and_core" in body:
                updatable["shell_and_core"] = bool(body["shell_and_core"])

            for field, value in updatable.items():
                if value is not None:
                    setattr(lease, field, value)

            lease.save()

            other_charges = body.get("other_charges")
            if other_charges is not None:
                incoming_charge_ids = {item["charge_id"] for item in other_charges if item.get("charge_id")}
                # Delete removed other-charge transactions
                lease.lease_cheques.filter(
                    cheque_type=constants.OTHER_CHARGE,
                ).exclude(charge_id__in=incoming_charge_ids).delete()
                for item in other_charges:
                    charge_id = item.get("charge_id")
                    amount = item.get("amount")
                    if not charge_id or amount is None:
                        continue
                    charge = Charge.objects.filter(id=charge_id).first()
                    if not charge:
                        continue
                    existing = lease.lease_cheques.filter(
                        cheque_type=constants.OTHER_CHARGE,
                        charge_id=charge_id,
                    ).first()
                    if existing:
                        existing.amount = float(amount)
                        existing.save()
                    else:
                        LeaseTransaction.objects.create(
                            lease=lease,
                            cheque_type=constants.OTHER_CHARGE,
                            charge=charge,
                            amount=float(amount),
                            file_name='',
                            file_path='',
                            created_by=user.user,
                        )

            return prepare_response(
                content=serialize_lease(lease),
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
def send_lease_invite(request):
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
        ).get(id=lease_id)

        t    = lease.tenant
        unit = lease.unit
        pb   = unit.property_block_tower if unit else None
        prop = pb.property if pb else None

        tenant_name  = f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "Tenant"
        tenant_email = t.user.email if t and t.user else None

        if not tenant_email:
            return prepare_response(message="Tenant email not found", status=status.HTTP_400_BAD_REQUEST)

        from utilities.config import FRONTEND_URL
        from urllib.parse import urlencode
        first_name = t.user.first_name if t and t.user else ""
        last_name  = t.user.last_name  if t and t.user else ""
        contact    = t.contact_number  if t else ""
        qs = urlencode({
            "role":            "tenant",
            "email":           tenant_email,
            "first_name":      first_name,
            "last_name":       last_name,
            "contact_number":  contact,
        })
        signup_url = f"{FRONTEND_URL}/auth/new-user?{qs}"

        ctx = {
            "tenant_name":   tenant_name,
            "lease_code":    lease.code,
            "property_name": prop.property_name if prop else "",
            "unit_name":     unit.unit_name if unit else "",
            "signup_url":    signup_url,
        }
        body_html = render_to_string("email_templates/lease_invite_tenant.html", ctx)
        body_text = (
            f"Dear {tenant_name},\n\n"
            f"Your lease {lease.code} is currently being processed.\n"
            f"Please sign up and complete your profile at: {signup_url}\n\n"
            f"Thank you,\nThe Doqfy Team"
        )

        ok = send_ses_email(tenant_email, f"Your Lease is in Progress – {lease.code}", body_text, body_html)

        audit_logs(request, f"Sent invite email for lease '{lease.code}' to {tenant_email}", constants.CREATED)

        return prepare_response(
            message="Invite email sent successfully",
            content={"sent": tenant_email, "success": ok},
            status=status.HTTP_200_OK,
        )

    except Lease.DoesNotExist:
        return prepare_response(message=constants.INVALID_LAESE_ID, status=status.HTTP_404_NOT_FOUND)
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
                        "role":  "owner",
                    })

        recipients = []
        if tenant_email:
            recipients.append({"email": tenant_email, "name": tenant_name, "role": "tenant"})
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

        from utilities.config import FRONTEND_URL

        lease.lease_stage = constants.NEGOTIATION_SENT
        lease.save(update_fields=["lease_stage"])

        subject = f"Lease Negotiation Document – {lease.code}"
        failed  = []
        sent    = []
        for r in recipients:
            ctx["recipient_name"] = r["name"]
            ctx["approval_url"] = (
                f"{FRONTEND_URL}/lease-approval"
                f"?lease={lease.id}&role={r['role']}&email={r['email']}"
            )
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


@csrf_exempt
def lease_approval_otp(request):
    """Send OTP to owner/tenant for lease approval. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from user_service.utils import request_otp_sent
        from django.core.cache import cache
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        role     = body.get("role")        # "owner" or "tenant"
        email    = body.get("email", "").strip().lower()
        if not lease_id or not role or not email:
            return prepare_response(message="lease_id, role and email are required", status=status.HTTP_400_BAD_REQUEST)
        lease = Lease.objects.select_related(
            "tenant__user",
            "unit__property_block_tower__property",
        ).prefetch_related(
            "unit__unit_owners__owner__user",
        ).get(id=lease_id)

        # ── Security: verify the email actually belongs to this lease ──────
        if role == "tenant":
            expected = lease.tenant.user.email.strip().lower() if lease.tenant and lease.tenant.user else None
            if not expected or expected != email:
                return prepare_response(message="Email does not match the tenant for this lease.", status=status.HTTP_403_FORBIDDEN)
        elif role == "owner":
            owner_emails = set()
            if lease.unit:
                for uo in lease.unit.unit_owners.all():
                    if uo.owner and uo.owner.user:
                        owner_emails.add(uo.owner.user.email.strip().lower())
            if email not in owner_emails:
                return prepare_response(message="Email does not match any owner for this lease.", status=status.HTTP_403_FORBIDDEN)
        else:
            return prepare_response(message="Invalid role.", status=status.HTTP_400_BAD_REQUEST)

        otp = request_otp_sent()
        cache_key = f"otp_lease_approval_{lease_id}_{role}_{email}"
        cache.set(cache_key, otp, timeout=600)
        role_label    = "Owner" if role == "owner" else "Tenant"
        role_label_ar = "المالك" if role == "owner" else "المستأجر"
        ctx = {
            "otp":           otp,
            "recipient_name": email,
            "lease_code":    lease.code,
            "role_label":    role_label,
            "role_label_ar": role_label_ar,
        }
        subject   = f"OTP for Lease Approval – {lease.code}"
        body_text = f"Your OTP for lease approval ({lease.code}) is: {otp}\nThis OTP expires in 10 minutes."
        body_html = render_to_string("email_templates/lease_approval_otp.html", ctx)
        send_ses_email(email, subject, body_text, body_html)
        return prepare_response(message="OTP sent successfully", status=status.HTTP_200_OK)
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def lease_approval_verify_otp(request):
    """Verify OTP and return lease PDF + details. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from django.core.cache import cache
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        role     = body.get("role")
        email    = body.get("email", "").strip().lower()
        otp      = body.get("otp")
        if not lease_id or not role or not email or not otp:
            return prepare_response(message="lease_id, role, email and otp are required", status=status.HTTP_400_BAD_REQUEST)
        cache_key = f"otp_lease_approval_{lease_id}_{role}_{email}"
        stored    = cache.get(cache_key)
        if not stored or str(stored) != str(otp):
            return prepare_response(message="Invalid or expired OTP", status=status.HTTP_400_BAD_REQUEST)
        # OTP verified — store a verified flag (don't delete yet, needed for approve step)
        verified_key = f"otp_lease_approval_verified_{lease_id}_{role}_{email}"
        cache.set(verified_key, True, timeout=600)
        lease = Lease.objects.select_related(
            "tenant__user",
            "unit__property_block_tower__property",
        ).get(id=lease_id)
        unit = lease.unit
        pb   = unit.property_block_tower if unit else None
        prop = pb.property if pb else None
        pdf_url = fetch_s3_presigned_url(lease.pdf_path, file_name="agreement.pdf") if lease.pdf_path else ""
        return prepare_response(
            message="OTP verified",
            content={
                "pdf_url":       pdf_url,
                "lease_code":    lease.code,
                "tenant_name":   f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}".strip() if lease.tenant and lease.tenant.user else "",
                "property_name": prop.property_name if prop else "",
                "unit_name":     unit.unit_name if unit else "",
            },
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def approve_lease_view(request):
    """Mark owner or tenant approval. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from django.core.cache import cache
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        role     = body.get("role")
        email    = body.get("email", "").strip().lower()
        if not lease_id or not role or not email:
            return prepare_response(message="lease_id, role and email are required", status=status.HTTP_400_BAD_REQUEST)
        verified_key = f"otp_lease_approval_verified_{lease_id}_{role}_{email}"
        if not cache.get(verified_key):
            return prepare_response(message="OTP not verified. Please verify OTP first.", status=status.HTTP_400_BAD_REQUEST)
        lease = Lease.objects.get(id=lease_id)
        current = lease.lease_stage
        if role == "tenant":
            if current == constants.OWNER_APPROVED:
                lease.lease_stage = constants.WAITING_CHEQUE
            else:
                lease.lease_stage = constants.TENANT_APPROVED
        elif role == "owner":
            if current == constants.TENANT_APPROVED:
                lease.lease_stage = constants.WAITING_CHEQUE
            else:
                lease.lease_stage = constants.OWNER_APPROVED
        else:
            return prepare_response(message="Invalid role", status=status.HTTP_400_BAD_REQUEST)
        lease.save(update_fields=["lease_stage"])
        cache.delete(verified_key)
        return prepare_response(
            message="Lease approved successfully",
            content={"lease_stage": lease.lease_stage},
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@is_request_authenticated
@csrf_exempt
def send_for_signature(request):
    """Send signature-request emails to tenant and owners. Requires auth."""
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

        owner_recipients = []
        if unit:
            for o in unit.unit_owners.select_related("owner__user").all():
                if o.owner and o.owner.email:
                    owner_recipients.append({
                        "email": o.owner.email,
                        "name":  f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner.user else "Owner",
                        "role":  "owner",
                    })

        recipients = []
        if tenant_email:
            recipients.append({"email": tenant_email, "name": tenant_name, "role": "tenant"})
        recipients.extend(owner_recipients)

        if not recipients:
            return prepare_response(message="No recipient emails found for this lease", status=status.HTTP_400_BAD_REQUEST)

        from utilities.config import FRONTEND_URL

        ctx_base = {
            "lease_code":    lease.code,
            "tenant_name":   tenant_name,
            "property_name": prop.property_name if prop else "",
            "unit_name":     unit.unit_name if unit else "",
        }

        lease.lease_stage = constants.AGREEMENT_SIGNING
        lease.save(update_fields=["lease_stage"])

        subject = f"Lease Agreement – Signature Required – {lease.code}"
        failed  = []
        sent    = []
        for r in recipients:
            ctx = dict(ctx_base)
            ctx["recipient_name"] = r["name"]
            ctx["signature_url"]  = (
                f"{FRONTEND_URL}/lease-sign"
                f"?lease={lease.id}&role={r['role']}&email={r['email']}"
            )
            body_html = render_to_string("email_templates/lease_signature_request.html", ctx)
            body_text = (
                f"Dear {r['name']},\n\n"
                f"Your signature is required for lease agreement {lease.code}.\n"
                f"Tenant: {tenant_name} | Property: {ctx_base['property_name']} | Unit: {ctx_base['unit_name']}\n"
                f"Sign here: {ctx['signature_url']}\n\nThank you,\nThe Doqfy Team"
            )
            ok = send_ses_email(r["email"], subject, body_text, body_html)
            (sent if ok else failed).append(r["email"])

        audit_logs(request, f"Sent signature request emails for lease '{lease.code}' to {sent}", constants.CREATED)

        return prepare_response(
            message="Signature request emails sent successfully",
            content={"sent": sent, "failed": failed},
            status=status.HTTP_200_OK,
        )

    except Lease.DoesNotExist:
        return prepare_response(message=constants.INVALID_LAESE_ID, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def lease_signature_otp(request):
    """Send OTP to owner/tenant for lease signature. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from user_service.utils import request_otp_sent
        from django.core.cache import cache
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        role     = body.get("role")
        email    = body.get("email", "").strip().lower()
        if not lease_id or not role or not email:
            return prepare_response(message="lease_id, role and email are required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related(
            "tenant__user",
            "unit__property_block_tower__property",
        ).prefetch_related(
            "unit__unit_owners__owner__user",
        ).get(id=lease_id)

        # Verify the email actually belongs to this lease
        if role == "tenant":
            expected = lease.tenant.user.email.strip().lower() if lease.tenant and lease.tenant.user else None
            if not expected or expected != email:
                return prepare_response(message="Email does not match the tenant for this lease.", status=status.HTTP_403_FORBIDDEN)
        elif role == "owner":
            owner_emails = set()
            if lease.unit:
                for uo in lease.unit.unit_owners.all():
                    if uo.owner and uo.owner.user:
                        owner_emails.add(uo.owner.user.email.strip().lower())
            if email not in owner_emails:
                return prepare_response(message="Email does not match any owner for this lease.", status=status.HTTP_403_FORBIDDEN)
        else:
            return prepare_response(message="Invalid role.", status=status.HTTP_400_BAD_REQUEST)

        otp = request_otp_sent()
        cache_key = f"otp_lease_signature_{lease_id}_{role}_{email}"
        cache.set(cache_key, otp, timeout=600)
        role_label    = "Owner" if role == "owner" else "Tenant"
        role_label_ar = "المالك" if role == "owner" else "المستأجر"
        ctx = {
            "otp":            otp,
            "recipient_name": email,
            "lease_code":     lease.code,
            "role_label":     role_label,
            "role_label_ar":  role_label_ar,
        }
        subject   = f"OTP for Lease Signature – {lease.code}"
        body_text = f"Your OTP for lease signature ({lease.code}) is: {otp}\nThis OTP expires in 10 minutes."
        body_html = render_to_string("email_templates/lease_approval_otp.html", ctx)
        send_ses_email(email, subject, body_text, body_html)
        return prepare_response(message="OTP sent successfully", status=status.HTTP_200_OK)
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def lease_signature_verify_otp(request):
    """Verify OTP and return lease PDF + details for signing. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from django.core.cache import cache
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        role     = body.get("role")
        email    = body.get("email", "").strip().lower()
        otp      = body.get("otp")
        if not lease_id or not role or not email or not otp:
            return prepare_response(message="lease_id, role, email and otp are required", status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"otp_lease_signature_{lease_id}_{role}_{email}"
        stored    = cache.get(cache_key)
        if not stored or str(stored) != str(otp):
            return prepare_response(message="Invalid or expired OTP", status=status.HTTP_400_BAD_REQUEST)

        # Store verified flag for submit step
        verified_key = f"otp_lease_signature_verified_{lease_id}_{role}_{email}"
        cache.set(verified_key, True, timeout=600)

        lease = Lease.objects.select_related(
            "tenant__user",
            "unit__property_block_tower__property",
        ).get(id=lease_id)
        unit = lease.unit
        pb   = unit.property_block_tower if unit else None
        prop = pb.property if pb else None
        pdf_url = fetch_s3_presigned_url(lease.pdf_path, file_name="agreement.pdf") if lease.pdf_path else ""
        return prepare_response(
            message="OTP verified",
            content={
                "pdf_url":       pdf_url,
                "lease_code":    lease.code,
                "tenant_name":   f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}".strip() if lease.tenant and lease.tenant.user else "",
                "property_name": prop.property_name if prop else "",
                "unit_name":     unit.unit_name if unit else "",
            },
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def submit_lease_signature(request):
    """Emboss signature onto lease PDF and save. No auth required."""
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        import io
        import base64 as _b64
        import pypdf
        from reportlab.pdfgen import canvas as rl_canvas
        from reportlab.lib.utils import ImageReader
        from django.core.cache import cache

        body           = json.loads(request.body)
        lease_id       = body.get("lease_id")
        role           = body.get("role")
        email          = (body.get("email") or "").strip().lower()
        signature_data = body.get("signature_data", "")

        if not lease_id or not role or not email or not signature_data:
            return prepare_response(message="lease_id, role, email and signature_data are required", status=status.HTTP_400_BAD_REQUEST)

        # Check that OTP was verified
        verified_key = f"otp_lease_signature_verified_{lease_id}_{role}_{email}"
        if not cache.get(verified_key):
            return prepare_response(message="OTP not verified. Please verify OTP first.", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.get(id=lease_id)
        if not lease.pdf_path:
            return prepare_response(message="No PDF available for this lease.", status=status.HTTP_400_BAD_REQUEST)

        # Download original PDF bytes
        pdf_b64 = fetch_s3_file_as_base64(lease.pdf_path)
        if not pdf_b64:
            return prepare_response(message="Failed to fetch lease PDF from storage.", status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        original_pdf_bytes = _b64.b64decode(pdf_b64)

        # Decode signature image (strip data URL prefix if present)
        if "," in signature_data:
            sig_b64 = signature_data.split(",", 1)[1]
        else:
            sig_b64 = signature_data
        sig_bytes = _b64.b64decode(sig_b64)

        # Read original PDF
        reader = pypdf.PdfReader(io.BytesIO(original_pdf_bytes))
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        # Get last page dimensions
        last_page = writer.pages[-1]
        page_width  = float(last_page.mediabox.width)
        page_height = float(last_page.mediabox.height)

        # Create signature overlay PDF using reportlab
        sig_width  = 180.0
        sig_height = 60.0
        margin     = 40.0
        # Owner → bottom-left, Tenant → bottom-right
        if role.lower() == "owner":
            sig_x = margin
        else:
            sig_x = page_width - sig_width - margin
        sig_y = margin

        overlay_buf = io.BytesIO()
        c = rl_canvas.Canvas(overlay_buf, pagesize=(page_width, page_height))

        # Draw signature label
        c.setFont("Helvetica", 8)
        c.setFillColorRGB(0.4, 0.4, 0.4)
        c.drawString(sig_x, sig_y + sig_height + 6, f"Signed by: {email} ({role})")

        # Draw signature image
        sig_img = ImageReader(io.BytesIO(sig_bytes))
        c.drawImage(sig_img, sig_x, sig_y, width=sig_width, height=sig_height, preserveAspectRatio=True, mask="auto")

        # Draw a thin line above the signature block
        c.setStrokeColorRGB(0.6, 0.6, 0.6)
        c.setLineWidth(0.5)
        c.line(sig_x - 5, sig_y + sig_height + 20, sig_x + sig_width + 5, sig_y + sig_height + 20)

        c.save()
        overlay_buf.seek(0)

        # Stamp overlay onto last page
        overlay_reader = pypdf.PdfReader(overlay_buf)
        overlay_page   = overlay_reader.pages[0]
        last_page.merge_page(overlay_page)

        # Output final signed PDF
        output_buf = io.BytesIO()
        writer.write(output_buf)
        signed_pdf_bytes = output_buf.getvalue()

        # Upload to S3
        object_name  = f"signed_agreements/signed_{lease_id}_{role}.pdf"
        signed_url   = upload_file_to_s3_base64(signed_pdf_bytes, object_name)

        # Update lease
        lease.pdf_path    = signed_url
        lease.lease_stage = constants.AGREEMENT_SIGNED
        lease.save(update_fields=["pdf_path", "lease_stage"])

        # Invalidate verified flag
        cache.delete(verified_key)

        return prepare_response(
            message="Signature submitted successfully",
            content={"signed_pdf_url": signed_url},
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@is_request_authenticated
@csrf_exempt
@is_request_authenticated
def lease_cheque_view(request):
    """CRUD for LeaseTransaction. GET ?lease_id=X, POST/PUT body JSON, DELETE ?cheque_id=X"""

    # ── GET list / single ─────────────────────────────────────────────────────
    if request.method == "GET":
        cheque_id = request.GET.get("cheque_id")
        if cheque_id:
            try:
                cheque = LeaseTransaction.objects.select_related(
                    "origin_bank", "selltlement_bank"
                ).get(id=cheque_id)
            except LeaseTransaction.DoesNotExist:
                return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)
            return prepare_response(content=serialize_lease_cheque(cheque), status=status.HTTP_200_OK)

        lease_id = request.GET.get("lease_id")
        if not lease_id:
            return prepare_response(message="lease_id or cheque_id is required", status=status.HTTP_400_BAD_REQUEST)
        cheques = LeaseTransaction.objects.filter(lease_id=lease_id).select_related(
            "origin_bank", "selltlement_bank", "document_type"
        )
        return prepare_response(content=group_lease_cheques(cheques), status=status.HTTP_200_OK)

    # ── POST create ───────────────────────────────────────────────────────────
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)

        lease_id = data.get("lease_id")
        if not lease_id:
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            lease = Lease.objects.get(id=lease_id)
        except Lease.DoesNotExist:
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        from user_service.models import DocumentType
        document_type_id = data.get("document_type_id")
        try:
            doc_type = DocumentType.objects.get(id=document_type_id) if document_type_id else DocumentType.objects.first()
        except DocumentType.DoesNotExist:
            return prepare_response(message="Document type not found", status=status.HTTP_404_NOT_FOUND)

        from payment.models import Bank
        origin_bank_id      = data.get("origin_bank_id")
        settlement_bank_id  = data.get("settlement_bank_id")
        try:
            origin_bank     = Bank.objects.get(id=origin_bank_id)     if origin_bank_id     else None
            settlement_bank = Bank.objects.get(id=settlement_bank_id) if settlement_bank_id else None
        except Bank.DoesNotExist:
            return prepare_response(message="Bank not found", status=status.HTTP_404_NOT_FOUND)

        file_path = ""
        file_name = data.get("file_name", "")
        if data.get("file_data") and data.get("file_name"):
            ext = get_extension_from_base64(data["file_data"])
            file_path = upload_file_to_s3_base64(
                data["file_data"],
                f"lease_cheques/{lease_id}/{uuid.uuid4()}.{ext}",
            ) or ""
            file_name = data["file_name"]

        cheque = LeaseTransaction.objects.create(
            lease=lease,
            document_type=doc_type,
            file_name=file_name,
            file_path=file_path,
            cheque_type=data.get("cheque_type", constants.RENT_CHEQUE),
            payment_type=data.get("payment_type", constants.PAYMENT_TYPE_CHEQUE),
            cheque_number=data.get("cheque_number") or "",
            start_date=_parse_date(data.get("start_date")),
            end_date=_parse_date(data.get("end_date")),
            cheque_date=_parse_date(data.get("cheque_date")) or date.today(),
            origin_bank=origin_bank,
            selltlement_bank=settlement_bank,
            origin_account_number=data.get("origin_account_number") or 0,
            settlement_account_number=data.get("settlement_account_number") or 0,
            amount=data.get("amount") or 0,
            created_by=request.user.user,
        )
        return prepare_response(
            message="Cheque created successfully",
            content={"id": cheque.id},
            status=status.HTTP_201_CREATED,
        )

    # ── PUT update ────────────────────────────────────────────────────────────
    elif request.method == "PUT":
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)

        cheque_id = data.get("cheque_id")
        if not cheque_id:
            return prepare_response(message="cheque_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            cheque = LeaseTransaction.objects.get(id=cheque_id)
        except LeaseTransaction.DoesNotExist:
            return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)

        from payment.models import Bank
        updatable = ["cheque_type", "payment_type", "origin_account_number",
                     "settlement_account_number", "amount", "status", "cheque_number"]
        for field in updatable:
            if field in data:
                setattr(cheque, field, data[field])

        for date_field in ["start_date", "end_date", "cheque_date"]:
            if date_field in data:
                setattr(cheque, date_field, _parse_date(data[date_field]))

        for bank_field, attr in [("origin_bank_id", "origin_bank"), ("selltlement_bank_id", "selltlement_bank")]:
            if bank_field in data and data[bank_field]:
                try:
                    setattr(cheque, attr, Bank.objects.get(id=data[bank_field]))
                except Bank.DoesNotExist:
                    pass

        if data.get("file_data") and data.get("file_name"):
            ext = get_extension_from_base64(data["file_data"])
            cheque.file_path = upload_file_to_s3_base64(
                data["file_data"],
                f"lease_cheques/{cheque.lease_id}/{uuid.uuid4()}.{ext}",
            ) or cheque.file_path
            cheque.file_name = data["file_name"]

        cheque.save()
        from notification.utils import (
            notify_cheque_bounced,
            notify_cheque_realized,
        )

        tenant_user_profile = cheque.lease.tenant
        print("Logged in user:", request.user)
        print("Tenant user:", tenant_user_profile)

        if cheque.status == "BOUNCED":
            notify_cheque_bounced(tenant_user_profile, cheque)

        elif cheque.status == "REALIZED":
            notify_cheque_realized(tenant_user_profile, cheque)
        return prepare_response(message="Cheque updated successfully", status=status.HTTP_200_OK)

    # ── DELETE ────────────────────────────────────────────────────────────────
    elif request.method == "DELETE":
        cheque_id = request.GET.get("cheque_id")
        if not cheque_id:
            return prepare_response(message="cheque_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            LeaseTransaction.objects.get(id=cheque_id).delete()
        except LeaseTransaction.DoesNotExist:
            return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)
        return prepare_response(message="Cheque deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def lease_cheque_status(request):
    """Legacy — kept for backward compat. Delegates to lease_cheque_view."""
    return lease_cheque_view(request)


def _scope_transactions_to_user(qs, user):
    """Filter LeaseTransaction queryset to the logged-in user's company or owner scope."""
    from user_service.models import PropertyManager, Owner
    pm = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
    owner = Owner.objects.filter(pk=user.pk).first()
    if pm:
        return qs.filter(lease__unit__property_block_tower__property__pmc=pm.company)
    elif owner:
        return qs.filter(lease__unit__unit_owners__owner=owner)
    return qs.none()


@is_request_authenticated
@csrf_exempt
def cheque_summary_view(request):
    """GET summary counts and totals grouped by cheque status."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Count, Sum

    qs = _scope_transactions_to_user(LeaseTransaction.objects.all(), request.user)

    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()
    year        = request.GET.get("year", "").strip()

    if property_id:
        qs = qs.filter(lease__unit__property_block_tower__property_id=property_id)
    if block_id:
        qs = qs.filter(lease__unit__property_block_tower_id=block_id)
    if unit_id:
        qs = qs.filter(lease__unit_id=unit_id)
    if year:
        qs = qs.filter(cheque_date__year=year)

    total_count  = qs.count()
    total_amount = qs.aggregate(total=Sum("amount"))["total"] or 0

    def _stats(status_val):
        agg = qs.filter(status=status_val).aggregate(cnt=Count("id"), amt=Sum("amount"))
        return {"count": agg["cnt"] or 0, "amount": agg["amt"] or 0}

    summary = {
        "total":    {"count": total_count,  "amount": total_amount},
        "credited": _stats(constants.CHEQUE_STATUS_CREDITED),
        "realized": _stats(constants.CHEQUE_STATUS_REALIZED),
        "bounce":   _stats(constants.CHEQUE_STATUS_BOUNCED),
        "balance":  _stats(constants.CHEQUE_STATUS_BALANCE),
    }
    return prepare_response(content=summary, status=status.HTTP_200_OK)


@is_request_authenticated
@csrf_exempt
def all_cheques_view(request):
    """GET all cheques across all leases with pagination and search."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    page        = int(request.GET.get("page", 1))
    page_size   = int(request.GET.get("page_size", 10))
    search      = request.GET.get("search", "").strip()
    cheque_status_filter = request.GET.get("status", "").strip()
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()
    year        = request.GET.get("year", "").strip()

    qs = LeaseTransaction.objects.select_related(
        "lease__unit__property_block_tower__property",
        "lease__tenant__user",
        "selltlement_bank",
    ).order_by("-id")

    if cheque_status_filter:
        qs = qs.filter(status=cheque_status_filter)
    if property_id:
        qs = qs.filter(lease__unit__property_block_tower__property_id=property_id)
    if block_id:
        qs = qs.filter(lease__unit__property_block_tower_id=block_id)
    if unit_id:
        qs = qs.filter(lease__unit_id=unit_id)
    if year:
        qs = qs.filter(cheque_date__year=year)

    if search:
        from django.db.models import Q
        qs = qs.filter(
            Q(cheque_number__icontains=search) |
            Q(lease__unit__code__icontains=search) |
            Q(lease__tenant__user__first_name__icontains=search) |
            Q(lease__tenant__user__last_name__icontains=search) |
            Q(lease__unit__property_block_tower__property__property_name__icontains=search)
        )

    from django.core.paginator import Paginator
    paginator   = Paginator(qs, page_size)
    page_obj    = paginator.get_page(page)
    rows        = [serialize_cheque_list_row(c) for c in page_obj]

    return prepare_response(
        content=rows,
        pagination={
            "total_records": paginator.count,
            "total_pages":   paginator.num_pages,
            "current_page":  page,
            "page_size":     page_size,
        },
        status=status.HTTP_200_OK,
    )


@is_request_authenticated
@csrf_exempt
def cheque_monthly_view(request):
    """GET month-wise cheque amount totals for a given year."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Sum
    from django.db.models.functions import ExtractMonth

    year        = request.GET.get("year", "").strip() or str(datetime.now().year)
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()

    qs = LeaseTransaction.objects.filter(cheque_date__year=year)
    if property_id:
        qs = qs.filter(lease__unit__property_block_tower__property_id=property_id)
    if block_id:
        qs = qs.filter(lease__unit__property_block_tower_id=block_id)
    if unit_id:
        qs = qs.filter(lease__unit_id=unit_id)

    monthly = (
        qs.annotate(month=ExtractMonth("cheque_date"))
          .values("month")
          .annotate(total=Sum("amount"))
          .order_by("month")
    )

    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
    result = {m: 0 for m in range(1, 13)}
    for row in monthly:
        result[row["month"]] = float(row["total"] or 0)

    data = [{"month": month_names[m - 1], "amount": result[m]} for m in range(1, 13)]
    return prepare_response(content=data, status=status.HTTP_200_OK)


@is_request_authenticated
@csrf_exempt
def rent_analytics_view(request):
    """GET summary + month-wise rent analytics (3 series: received, bounce, total)."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Sum
    from django.db.models.functions import ExtractMonth

    year        = request.GET.get("year", "").strip() or str(datetime.now().year)
    lease_id    = request.GET.get("lease_id", "").strip()
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()

    qs = LeaseTransaction.objects.filter(cheque_date__year=year)
    if lease_id:
        qs = qs.filter(lease_id=lease_id)
    if property_id:
        qs = qs.filter(lease__unit__property_block_tower__property_id=property_id)
    if block_id:
        qs = qs.filter(lease__unit__property_block_tower_id=block_id)
    if unit_id:
        qs = qs.filter(lease__unit_id=unit_id)

    # Summary totals
    total_amount    = float(qs.aggregate(t=Sum("amount"))["t"] or 0)
    received_amount = float(
        qs.filter(status__in=[constants.CHEQUE_STATUS_CREDITED, constants.CHEQUE_STATUS_REALIZED])
          .aggregate(t=Sum("amount"))["t"] or 0
    )
    pending_amount  = total_amount - received_amount

    # Month-wise breakdown helper
    month_names = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

    def monthly_agg(filter_statuses=None):
        result = {m: 0 for m in range(1, 13)}
        qs_f = qs.filter(status__in=filter_statuses) if filter_statuses else qs
        rows = (
            qs_f.annotate(m=ExtractMonth("cheque_date"))
                .values("m")
                .annotate(total=Sum("amount"))
                .order_by("m")
        )
        for row in rows:
            result[row["m"]] = float(row["total"] or 0)
        return result

    received_m = monthly_agg([constants.CHEQUE_STATUS_CREDITED, constants.CHEQUE_STATUS_REALIZED])
    bounce_m   = monthly_agg([constants.CHEQUE_STATUS_BOUNCED])
    total_m    = monthly_agg()

    monthly = [
        {
            "month":           month_names[m - 1],
            "amount_received": received_m[m],
            "cheque_bounce":   bounce_m[m],
            "total_amount":    total_m[m],
        }
        for m in range(1, 13)
    ]

    return prepare_response(content={
        "summary": {
            "total_amount":    total_amount,
            "amount_received": received_amount,
            "pending_amount":  pending_amount,
        },
        "monthly": monthly,
    }, status=status.HTTP_200_OK)


@is_request_authenticated
@csrf_exempt
def property_analytics_view(request):
    """GET property/block/unit-wise revenue analytics.
    Always returns ALL properties/blocks/units (revenue = 0 when no transactions).
    """
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Sum, Q, Value
    from django.db.models.functions import Coalesce
    from property.models import Property, PropertyBlocks

    year        = request.GET.get("year", "").strip() or str(datetime.now().year)
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()

    if block_id:
        # All units in this block, each annotated with their total revenue
        # Unit -> Lease (related_name="leases") -> LeaseTransaction (related_name="lease_cheques")
        units = (
            Unit.objects
            .filter(property_block_tower_id=block_id)
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "leases__lease_cheques__amount",
                        filter=Q(leases__lease_cheques__cheque_date__year=year),
                    ),
                    Value(0),
                )
            )
            .order_by("unit_name")
        )
        chart = [
            {
                "key":     str(u.id),
                "name":    u.unit_name or u.code or f"Unit {u.id}",
                "revenue": float(u.revenue),
            }
            for u in units
        ]
        level = "unit"

    elif property_id:
        # All blocks in this property, each annotated with their total revenue
        # PropertyBlocks -> Unit (related_name="block_towers") -> Lease -> LeaseTransaction
        blocks = (
            PropertyBlocks.objects
            .filter(property_id=property_id)
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "block_towers__leases__lease_cheques__amount",
                        filter=Q(block_towers__leases__lease_cheques__cheque_date__year=year),
                    ),
                    Value(0),
                )
            )
            .order_by("block_name")
        )
        chart = [
            {
                "key":     str(b.id),
                "name":    b.block_name or f"Block {b.id}",
                "revenue": float(b.revenue),
            }
            for b in blocks
        ]
        level = "block"

    else:
        # All properties, each annotated with their total revenue
        # Property -> PropertyBlocks (related_name="property_blocks") -> Unit (related_name="block_towers") -> Lease -> LeaseTransaction
        properties = (
            Property.objects
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "property_blocks__block_towers__leases__lease_cheques__amount",
                        filter=Q(
                            property_blocks__block_towers__leases__lease_cheques__cheque_date__year=year
                        ),
                    ),
                    Value(0),
                )
            )
            .order_by("property_name")
        )
        chart = [
            {
                "key":     str(p.id),
                "name":    p.property_name or f"Property {p.id}",
                "revenue": float(p.revenue),
            }
            for p in properties
        ]
        level = "property"

    total_revenue = sum(item["revenue"] for item in chart)

    return prepare_response(content={
        "total_revenue": total_revenue,
        "chart":         chart,
        "level":         level,
    }, status=status.HTTP_200_OK)


@is_request_authenticated
@csrf_exempt
def property_comparison_view(request):
    """GET full detail for one property for the comparison card."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Sum, Count, Q
    from property.models import Property, PropertyBlocks

    property_id = request.GET.get("property_id", "").strip()
    if not property_id:
        return prepare_response(message="property_id is required", status=status.HTTP_400_BAD_REQUEST)

    try:
        prop = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        return prepare_response(message="Property not found", status=status.HTTP_404_NOT_FOUND)

    # Revenue: sum all LeaseTransaction amounts for this property
    revenue = float(
        LeaseTransaction.objects
        .filter(lease__unit__property_block_tower__property_id=property_id)
        .aggregate(t=Sum("amount"))["t"] or 0
    )

    # Rank: how many properties have strictly higher revenue
    all_revenues = (
        LeaseTransaction.objects
        .values("lease__unit__property_block_tower__property_id")
        .annotate(total=Sum("amount"))
    )
    higher_count = sum(1 for r in all_revenues if float(r["total"] or 0) > revenue)
    rank = higher_count + 1

    # Unit counts
    total_units    = Unit.objects.filter(property_block_tower__property_id=property_id).count()
    occupied_units = Unit.objects.filter(property_block_tower__property_id=property_id, is_occupied=True).count()
    available_units = total_units - occupied_units

    # Total parking across all blocks
    total_parking = (
        PropertyBlocks.objects
        .filter(property_id=property_id)
        .aggregate(t=Sum("no_of_parking"))["t"] or 0
    )

    # Built-up area: sum of unit sizes
    built_up_area = float(
        Unit.objects
        .filter(property_block_tower__property_id=property_id)
        .aggregate(t=Sum("unit_size"))["t"] or 0
    )

    return prepare_response(content={
        "id":              prop.id,
        "property_name":   prop.property_name,
        "thumbnail":       prop._get_thumbnail(),
        "revenue":         revenue,
        "rank":            rank,
        "land_area":       float(prop.land_area or 0),
        "land_area_unit":  prop.land_area_unit or "",
        "no_of_blocks":    prop.no_of_blocks,
        "total_units":     total_units,
        "occupied_units":  occupied_units,
        "available_units": available_units,
        "total_parking":   total_parking,
        "built_up_area":   built_up_area,
    }, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------------
# Functions moved from property_management/views.py
# ---------------------------------------------------------------------------

@is_request_authenticated
def lease_details_view(request):
    user_profile = request.user

    try:
        # ----------------------- GET -----------------------
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")
            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            lease = Lease.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(
                    message=constants.LEASE_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )


            return prepare_response(
                content=serialize_lease(lease),
                message=constants.LEASE_FETCHED,
                status=status.HTTP_200_OK
            )

        # ----------------------- POST -----------------------
        elif request.method == "POST":
            body = json.loads(request.body)

            # Required fields
            property_id = body.get("property_id")
            tenant_id = body.get("tenant_id")
            if not property_id or not tenant_id:
                return prepare_response(
                    message=constants.PROPERTY_AND_TENANT_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_obj = Unit.objects.filter(id=property_id).first()
            tenant_obj = UserProfile.objects.filter(id=tenant_id, user_role=constants.TENANT).first()
            if not property_obj or not tenant_obj:
                return prepare_response(message=constants.PROPERTY_TENANT_INVALID, status=status.HTTP_400_BAD_REQUEST)

            owner_obj = property_obj.owner
            if not owner_obj:
                return prepare_response(message=constants.THIS_OWNER_HAS_NO_PROPERTY, status=status.HTTP_400_BAD_REQUEST)

            # Convert datetime fields
            lease_start_date = safe_epoch_to_datetime(body.get("lease_start_date"))
            lease_end_date = safe_epoch_to_datetime(body.get("lease_end_date"))
            lease_grace_start_date = safe_epoch_to_datetime(body.get("lease_grace_start_date")) if body.get("lease_grace_start_date") else None
            lease_grace_end_date = safe_epoch_to_datetime(body.get("lease_grace_end_date")) if body.get("lease_grace_end_date") else None

            # ----------------- Create Lease with all fields -----------------
            lease = Lease.objects.create(
                created_by=user_profile.user,
                lease_property=property_obj,
                tenant=tenant_obj,
                owner=owner_obj,
                lease_number=body.get("lease_number"),
                lease_start_date=lease_start_date,
                lease_end_date=lease_end_date,
                lease_grace_start_date=lease_grace_start_date,
                lease_grace_end_date=lease_grace_end_date,
                lease_remarks=body.get("lease_remarks"),
                lease_stage=body.get("lease_stage", constants.BASIC_DETAILS),
                lease_status=body.get("lease_status", "DRAFT"),
                # approval_status=body.get("approval_status", "PENDING"),


                annual_amount=body.get("annual_amount"),
                actual_annual_amount=body.get("actual_annual_amount"),
                rent=body.get("rent"),
                booking_amount=body.get("booking_amount"),
                security_deposit=body.get("security_deposit"),
                maintenance_charges=body.get("maintenance_charges"),
                commission_percentage=body.get("commission_percentage"),
                notice_period=body.get("notice_period"),
                discount=body.get("discount"),
                contract_amount=body.get("contract_amount"),
                payment_count=body.get("payment_count"),
                shell=body.get("shell", False),
                core=body.get("core", False),
            )

            audit_logs(
                request,
                f"Added lease agreement for {property_obj.property.property_name} – Unit {property_obj.unit_name}",
                constants.CREATED
            )

            return prepare_response(
                message=constants.LEASE_CREATED,
                content={"id": lease.id},
                status=status.HTTP_201_CREATED
            )

        # ----------------------- PUT -----------------------
        elif request.method == "PUT":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            lease = Lease.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            # Update ForeignKeys
            if "tenant_id" in body:
                tenant_obj = UserProfile.objects.filter(id=body["tenant_id"], user_role=constants.TENANT).first()
                if not tenant_obj:
                    return prepare_response(message=constants.INVALID_TENANT, status=status.HTTP_400_BAD_REQUEST)
                lease.tenant = tenant_obj

            if "property_id" in body:
                property_obj = Unit.objects.filter(id=body["property_id"]).first()
                if not property_obj:
                    return prepare_response(message=constants.INVALID_PROPERTY, status=status.HTTP_400_BAD_REQUEST)
                lease.lease_property = property_obj
                lease.owner = property_obj.owner

            # Update datetime fields
            datetime_fields = ["lease_start_date", "lease_end_date", "lease_grace_start_date", "lease_grace_end_date"]
            for field in datetime_fields:
                if field in body and body[field]:
                    setattr(lease, field, safe_epoch_to_datetime(body[field]))

            # Update all other fields explicitly
            lease_fields = [
                "lease_number", "lease_remarks", "lease_stage", "lease_status",
                "approval_status", "pdf_path",
                "annual_amount", "actual_annual_amount", "rent", "booking_amount",
                "security_deposit", "maintenance_charges", "commission_percentage",
                "notice_period", "discount",
                "contract_amount", "payment_count", "shell", "core"
            ]
            for field in lease_fields:
                if field in body:
                    setattr(lease, field, body[field])

            lease.save()

            audit_logs(
                request,
                f"Updated lease agreement for {lease.lease_property.property.property_name} – Unit {lease.lease_property.unit_name}",
                constants.UPDATED
            )

            return prepare_response(
                message=constants.LEASE_UPDATED,
                content={"id": lease.id},
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@is_request_authenticated
def lease_documents(request):
    try:
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")
            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_LEASE_ID,
                    status=status.HTTP_404_NOT_FOUND
                )

            docs_qs = lease_obj.lease_documents.select_related("document").order_by("-id")
            final_docs = []

            for mapping in docs_qs:
                doc = mapping.document
                base64_data = fetch_s3_presigned_url(
                    doc.file_path,
                    file_name=doc.file_name
                )
                final_docs.append({
                    "id": mapping.id,
                    "file_name": doc.file_name,
                    "data": base64_data,
                    "type": mapping.document_choice
                })

            return prepare_response(
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                content={
                    "documents": final_docs,
                    "lease_id": lease_id,
                    "step_status": lease_obj.lease_stage
                },
                status=status.HTTP_200_OK
            )

        # -------------------- POST --------------------
        if request.method == "POST":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            documents = body.get("documents", [])

            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not isinstance(documents, list) or not documents:
                return prepare_response(
                    message=constants.DOCUMENTS_MUST_BE_LIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_LEASE_ID,
                    status=status.HTTP_404_NOT_FOUND
                )

            uploaded_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", constants.EJARI_CERTIFICATE).upper()

                if not file_name or not base64_data:
                    return prepare_response(
                        message=constants.MISSING_FILE_OR_DATA,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                object_name = f"lease_documents/{lease_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_obj = Documents.objects.create(
                    file_name=file_name,
                    file_path=file_url,
                    created_by=request.user.user
                )

                LeaseDocuments.objects.create(
                    lease=lease_obj,
                    document=doc_obj,
                    document_choice=doc_type,
                    created_by=request.user.user
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type
                })

            lease_obj.lease_stage = "UPLOAD_EJARI"
            lease_obj.save()

            audit_logs(
                request,
                f"Uploaded lease documents for unit '{lease_obj.lease_property.unit_name}'",
                constants.CREATED
            )

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"uploaded": uploaded_files},
                status=status.HTTP_201_CREATED
            )

        # -------------------- PUT --------------------
        if request.method == "PUT":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            documents = body.get("documents", [])

            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not isinstance(documents, list):
                return prepare_response(
                    message=constants.DOCUMENTS_MUST_BE_LIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_LEASE_ID,
                    status=status.HTTP_404_NOT_FOUND
                )

            updated_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", constants.EJARI_CERTIFICATE).upper()

                if not file_name or not base64_data:
                    return prepare_response(
                        message=constants.MISSING_FILE_OR_DATA,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                mapping_obj = LeaseDocuments.objects.filter(
                    lease=lease_obj,
                    document__file_name=file_name
                ).select_related("document").first()

                if mapping_obj:
                    doc_obj = mapping_obj.document
                    mapping_obj.document_choice = doc_type
                    status_text = "updated"
                else:
                    doc_obj = Documents.objects.create(
                        file_name=file_name,
                        file_path="",
                        created_by=request.user.user
                    )
                    mapping_obj = LeaseDocuments.objects.create(
                        lease=lease_obj,
                        document=doc_obj,
                        document_choice=doc_type,
                        created_by=request.user.user
                    )
                    status_text = "created"

                object_name = f"lease_documents/{lease_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_obj.file_path = file_url
                doc_obj.save()
                mapping_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": status_text
                })

            audit_logs(
                request,
                f"Updated lease documents for unit '{lease_obj.lease_property.unit_name}'",
                constants.UPDATED
            )

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )

        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def lease_tenancy(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        current_user = request.user
        lease_status_param = request.GET.get("lease_status")

        leases_qs = Lease.objects.select_related(
            "lease_property",
            "lease_property__company",
            "tenant",
            "tenant__user"
        )

        # ================= ROLE BASED FILTER (UNCHANGED) =================
        if current_user.user_role == constants.OWNER:
            leases_qs = leases_qs.filter(owner=current_user)

        elif current_user.user_role == constants.COMPANY_USER:
            leases_qs = leases_qs.filter(
                lease_property__company__company_user=current_user
            ).distinct()

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        # ================= LEASE STATUS FILTER (UNCHANGED) =================
        if lease_status_param:
            status_list = [status.strip().upper() for status in lease_status_param.split(",")]
            leases_qs = leases_qs.filter(lease_status__in=status_list)

        # ================= SEARCH FILTER (NEW - NON BREAKING) =================
        search = request.GET.get("search", "").strip()
        if search:
            leases_qs = leases_qs.filter(
                Q(id__icontains=search) |
                Q(lease_property__property_code__icontains=search) |
                Q(tenant__user__first_name__icontains=search) |
                Q(tenant__user__last_name__icontains=search) |
                Q(tenant__contact_number__icontains=search)
            ).distinct()

        # ================= PAGINATION (NEW - SAFE) =================
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))

        paginator = Paginator(leases_qs.order_by("-created"), limit)

        try:
            leases_page = paginator.page(page)
        except EmptyPage:
            leases_page = paginator.page(paginator.num_pages)

        table_data = []

        # ================= LOOP (UNCHANGED LOGIC) =================
        for lease in leases_page:
            tenant_profile = lease.tenant
            property_unit = lease.lease_property

            table_data.append({
                "lease_id": lease.id,
                "property_code": property_unit.property_code if property_unit else None,
                "tenant_name": (
                    tenant_profile.user.get_full_name()
                    if tenant_profile and tenant_profile.user
                    else None
                ),
                "tenant_profile_image": tenant_profile.profile_image if tenant_profile else None,
                "tenant_contact_number": tenant_profile.contact_number if tenant_profile else None,
                "lease_status": lease.lease_status,
                "agreement_start_date": datetime_to_epoch_millis(lease.lease_start_date),
                "agreement_end_date": datetime_to_epoch_millis(lease.lease_end_date),
            })

        return prepare_response(
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            content=table_data,

            pagination={
                "current_page": leases_page.number,
                "limit": limit,
                "total_pages": paginator.num_pages,
                "total_records": paginator.count
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def export_lease_tenancy_csv(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        current_user = request.user
        lease_status_param = request.GET.get("lease_status")

        leases_qs = Lease.objects.select_related(
            "lease_property",
            "lease_property__company",
            "tenant",
            "tenant__user"
        )
        if current_user.user_role == constants.OWNER:
            leases_qs = leases_qs.filter(owner=current_user)

        elif current_user.user_role == constants.COMPANY_USER:
            leases_qs = leases_qs.filter(
                lease_property__company__company_user=current_user
            ).distinct()
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )
        if lease_status_param:
            status_list = [s.strip().upper() for s in lease_status_param.split(",")]
            leases_qs = leases_qs.filter(lease_status__in=status_list)
        field_names = [
            "Property Code",
            "Agreement With",
            "Contact Number",
            "Agreement Start Date",
            "Agreement End Date",
            "Lease Status"
        ]

        data_list = []

        for lease in leases_qs.order_by("-created"):
            tenant = lease.tenant
            property_unit = lease.lease_property

            data_list.append({
                "Property Code": property_unit.property_code if property_unit else "",
                "Agreement With": tenant.user.get_full_name() if tenant and tenant.user else "",
                "Contact Number": tenant.contact_number if tenant else "",
                "Agreement Start Date": lease.lease_start_date.strftime("%Y-%m-%d") if lease.lease_start_date else "",
                "Agreement End Date": lease.lease_end_date.strftime("%Y-%m-%d") if lease.lease_end_date else "",
                "Lease Status": lease.lease_status
            })

        return export_to_csv(
            filename="lease_tenancy_export",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting lease CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def lease_pdf_view(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        lease_id = request.GET.get("lease_id")
        purpose = request.GET.get("purpose")

        if not lease_id:
            return prepare_response(
                message=constants.LEASE_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        lease = Lease.objects.filter(id=lease_id).first()
        if not lease:
            return prepare_response(
                message=constants.LEASE_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        if not lease.pdf_path:
            return prepare_response(
                message=constants.LEASE_PDF_NOT_AVAILABLE,
                status=status.HTTP_404_NOT_FOUND
            )

        file_name = f"lease_{lease.lease_number}.pdf"


        if purpose == "download":
            presigned_url = fetch_s3_presigned_url_for_download(
                file_url=lease.pdf_path,
                file_name=file_name
            )
        else:

            presigned_url = fetch_s3_presigned_url(
                file_url=lease.pdf_path,
                file_name=file_name
            )

        if not presigned_url:
            return prepare_response(
                message=constants.PDF_URL_GENERATION_FAILED,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return prepare_response(
            content={
                "lease_id": lease.id,
                "lease_number": lease.lease_number,
                "purpose": purpose or "preview",
                "pdf_url": presigned_url
            },
            message=constants.LEASE_PDF_URL_GENERATED_SUCCESS,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message={"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def lease_term_and_condition(request):
    try:
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")

            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_LEASE_ID,
                    status=status.HTTP_404_NOT_FOUND
                )

            # Fetch predefined terms (global) and user-defined terms for this lease
            predefined_terms = TermAndCondition.objects.filter(
                lease__isnull=True,
                is_predefined=True
            )

            user_defined_terms = TermAndCondition.objects.filter(
                lease=lease_obj,
                is_predefined=False
            )

            response_data = {
                "Predefined": [],
                "User defined": []
            }

            # Predefined terms
            for term in predefined_terms:
                response_data["Predefined"].append({
                 "id": term.id,
                 "description_en": term.description,
                "description_ar": translate_to_arabic(term.description),
                "term_type": term.term_type
                 })
            # User defined terms
            for term in user_defined_terms:
                response_data["User defined"].append({
                 "id": term.id,
                 "description_en": term.description,
                     "description_ar": translate_to_arabic(term.description),
                    "term_type": term.term_type
                        })

            return prepare_response(
                message=constants.DATA_FETCHED_SUCCESS,
                content=response_data,
                status=status.HTTP_200_OK
            )

        elif request.method == "POST":
            body = json.loads(request.body)
            lease_id = body.get("lease_id")
            descriptions = body.get("descriptions", [])

            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not isinstance(descriptions, list) or not descriptions:
                return prepare_response(
                    message=constants.TERMS_MUST_BE_LIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                return prepare_response(
                    message=constants.INVALID_LEASE_ID,
                    status=status.HTTP_404_NOT_FOUND
                )

            created_terms = []

            for item in descriptions:
                description = item.get("description")
                term_type = item.get("term_type", "ADDITIONAL")

                if not description:
                    return prepare_response(
                        message=constants.DESCRIPTION_REQUIRED,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                term_obj = TermAndCondition.objects.create(
                    lease=lease_obj,
                    description=description,
                    term_type=term_type,
                    is_predefined=False
                )

                created_terms.append({
                    "id": term_obj.id,
                    "description": term_obj.description,
                    "term_type": term_obj.term_type
                })

            return prepare_response(
                message=constants.TERMS_CREATED_SUCCESS,
                content={"created_terms": created_terms},
                status=status.HTTP_201_CREATED
            )


        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def property_owner_compny_lease(request):
    try:
        if request.method == "GET":
            property_unit_id = request.GET.get("property_unit_id")
            tenant_id = request.GET.get("tenant_id")

            tenant_data = None
            if tenant_id:

                tenant_data = get_tenant_detail_by_id(tenant_id)
                if not tenant_data:
                    return prepare_response(message="Invalid tenant_id",status=status.HTTP_404_NOT_FOUND)

                return prepare_response(message="tenant details fetched successfully", content=tenant_data,status=status.HTTP_200_OK)

            if not property_unit_id:
                return prepare_response(
                    message="Property unit id is required",
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                unit = Unit.objects.select_related(
                    "property_block_tower__property"
                ).get(id=property_unit_id)
            except Unit.DoesNotExist:
                return prepare_response(
                    message="Invalid property unit id",
                    status=status.HTTP_404_NOT_FOUND
                )

            # ---------------- Owner Details ----------------
            owner_data = [
                {
                    "name": o.name,
                    "email": o.email,
                    "contact_number": o.contact_number,
                    "emirates_id": o.emirates_id,
                    "owner_number": o.owner_number,
                    "trade_license_number": o.trade_license_number,
                    "license_number": o.license_number,
                    "license_expiry_date": o.license_expiry_date.strftime("%Y-%m-%d") if o.license_expiry_date else None,
                    "license_issuer": o.license_issuer,
                    "fax_number": o.fax_number,
                    "po_box_number": o.po_box_number,
                }
                for o in unit.unit_owners.all()
            ]

            # ---------------- Parent Property ----------------
            property_data = None
            if unit.property_block_tower and unit.property_block_tower.property:
                prop = unit.property_block_tower.property
                property_data = {
                    "property_id": prop.id,
                    "property_name": prop.property_name,
                    "property_code": prop.code,
                    "property_type": prop.property_type,
                    "total_units": prop.no_of_units,
                }

            # ---------------- Block / Tower ----------------
            block_data = None
            if unit.property_block_tower:
                block_data = {
                    "block_id": unit.property_block_tower.id,
                    "block_name": unit.property_block_tower.block_name,
                }

            # ---------------- Property Unit ----------------
            unit_data = {
                "property_unit_id": unit.id,
                "unit_name": unit.unit_name,
                "unit_size": str(unit.unit_size) if unit.unit_size is not None else None,
                "area": unit.area,
                "dm_no": unit.dm_no,
                "land_no": unit.land_no,
                "unit_usage": unit.unit_usage,
                "unit_type": unit.unit_type,
                "sub_type": unit.sub_type,
                "makani_no": unit.makani_no,
                "dewa_no": unit.dewa_no,
                "floor_no": unit.floor_no,
                "rent": unit.rent,
                "security_deposit": unit.security_deposit,
                "maintenance_charges": unit.maintenance_charges,
                "is_occupied": unit.is_occupied,
                "no_of_bedrooms": unit.no_of_bedrooms,
            }

            response_data = {
                "property_unit": unit_data,
                "block": block_data,
                "parent_property": property_data,
                "owners": owner_data,
            }

            return prepare_response(
                message="Property unit details fetched successfully",
                content=response_data,
                status=status.HTTP_200_OK
            )

        return prepare_response(
            message="Invalid request method",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def property_lease_payment(request):
    try:
        user = request.user
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")
            payment_id = request.GET.get("payment_id")

            if lease_id:
                transactions = LeaseTransaction.objects.filter(lease_id=lease_id)
            elif payment_id:
                transactions = LeaseTransaction.objects.filter(id=payment_id)
            else:
                return prepare_response(
                    message="lease_id or payment_id is required",
                    status=status.HTTP_400_BAD_REQUEST
                )
            data = []
            for t in transactions:
                data.append({
                    "id": t.id,
                    "lease_id": t.lease_id,
                    "amount": t.amount,
                    "cheque_type": t.cheque_type,
                    "payment_type": t.payment_type,
                    "status": t.status,
                    "cheque_number": t.cheque_number,
                    "origin_account_number": t.origin_account_number,
                    "settlement_account_number": t.settlement_account_number,
                    "cheque_date": int(t.cheque_date.timestamp()) if t.cheque_date else None,
                    "origin_bank": {
                        "id": t.origin_bank.id,
                        "name": t.origin_bank.name,
                        "branch_name": t.origin_bank.branch_name,
                        "ifsc_code": t.origin_bank.ifsc_code
                    } if t.origin_bank else None
                })

            return prepare_response(
                content=data if lease_id else (data[0] if data else {}),
                message="Payment data fetched",
                status=status.HTTP_200_OK
            )

        elif request.method == "POST":
            body = json.loads(request.body)

            lease_id = body.get("lease_id")
            if not lease_id:
                return prepare_response(
                    message="lease_id is required",
                    status=status.HTTP_400_BAD_REQUEST
                )

            lease = Lease.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(
                    message="Invalid lease_id",
                    status=status.HTTP_400_BAD_REQUEST
                )

            origin_bank = Bank.objects.filter(id=body.get("origin_bank_id")).first() if body.get("origin_bank_id") else None
            settlement_bank = Bank.objects.filter(id=body.get("settlement_bank_id")).first() if body.get("settlement_bank_id") else None

            transaction = LeaseTransaction.objects.create(
                created_by=user.user,
                lease=lease,
                origin_bank=origin_bank,
                selltlement_bank=settlement_bank,
                cheque_type=body.get("cheque_type", constants.RENT_CHEQUE),
                payment_type=body.get("payment_type", constants.PAYMENT_TYPE_CHEQUE),
                amount=body.get("amount", 0),
                origin_account_number=body.get("origin_account_number", 0),
                settlement_account_number=body.get("settlement_account_number", 0),
                cheque_number=body.get("cheque_number"),
                cheque_date=safe_epoch_to_datetime(body.get("cheque_date")) if body.get("cheque_date") else None,
                status=body.get("status", constants.CHEQUE_STATUS_BALANCE),
                start_date=safe_epoch_to_datetime(body.get("start_date")) if body.get("start_date") else None,
                end_date=safe_epoch_to_datetime(body.get("end_date")) if body.get("end_date") else None,
            )

            audit_logs(
                request,
                f"Created transaction of {transaction.amount} for Lease {lease.id}",
                constants.CREATED
            )

            return prepare_response(
                message="Payment created successfully",
                content={"payment_id": transaction.id},
                status=status.HTTP_201_CREATED
            )
        elif request.method == "PUT":
            body = json.loads(request.body)
            payment_id = body.get("payment_id")
            if not payment_id:
                return prepare_response(
                    message="payment_id is mandatory for update",
                    status=status.HTTP_400_BAD_REQUEST
                )

            transaction = LeaseTransaction.objects.filter(id=payment_id).first()
            if not transaction:
                return prepare_response(
                    message="Payment not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            if body.get("origin_bank_id"):
                bank = Bank.objects.filter(id=body.get("origin_bank_id")).first()
                if not bank:
                    return prepare_response(
                        message="Invalid origin_bank_id",
                        status=status.HTTP_400_BAD_REQUEST
                    )
                transaction.origin_bank = bank

            for field in [
                "cheque_type", "payment_type", "amount",
                "origin_account_number", "settlement_account_number",
                "cheque_number", "status"
            ]:
                if field in body:
                    setattr(transaction, field, body[field])

            if body.get("cheque_date"):
                transaction.cheque_date = safe_epoch_to_datetime(body.get("cheque_date"))

            transaction.save()

            audit_logs(
                request,
                f"Updated payment {transaction.id}",
                constants.UPDATED
            )

            return prepare_response(
                message="Payment updated successfully",
                content={"payment_id": transaction.id},
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message="Invalid request method",
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@is_request_authenticated
def invoice_view(request):
    """
    GET /api/lease/invoice?lease_id=X
    Returns all data needed to render an invoice for a lease:
      - tenant details, property/unit details
      - other charges (lease_charges), cheque rows, computed totals
    """
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    if not lease_id:
        return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    lease = (
        Lease.objects
        .filter(id=lease_id, is_active=True)
        .select_related("tenant__user", "unit__property_block_tower__property")
        .first()
    )
    if not lease:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    tenant_info = {
        "name":           f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else None,
        "code":           t.code if t else None,
        "email":          t.user.email if t and t.user else None,
        "contact":        t.contact_number if t else None,
        "address_line_1": t.address_line_1 if t else None,
        "address_line_2": t.address_line_2 if t else None,
    }

    property_info = {
        "property_name": prop.property_name if prop else None,
        "block_name":    pb.block_name if pb else None,
        "unit_name":     unit.unit_name if unit else None,
        "start_date":    str(lease.start_date)[:10] if lease.start_date else None,
        "end_date":      str(lease.end_date)[:10] if lease.end_date else None,
        "lease_code":    lease.code,
    }

    qs = lease.lease_cheques.select_related("charge", "origin_bank").filter(is_active=True).order_by("created")

    def _desc(ch):
        if ch.cheque_type == constants.OTHER_CHARGE:
            return ch.charge.description if ch.charge else "Other Charge"
        label = "Rent" if ch.cheque_type == constants.RENT_CHEQUE else "Additional Charge"
        if ch.start_date and ch.end_date:
            return f"{label} [{str(ch.start_date)[:7]} – {str(ch.end_date)[:7]}]"
        return label

    transactions = [
        {
            "id":                    ch.id,
            "code":                  ch.code,
            "cheque_type":           ch.cheque_type,
            "description":           _desc(ch),
            "cheque_date":           str(ch.cheque_date)[:10] if ch.cheque_date else None,
            "cheque_number":         ch.cheque_number,
            "payment_type":          ch.payment_type,
            "status":                ch.status,
            "amount":                ch.amount,
            "vat":                   ch.vat,
            "total":                 ch.total if ch.cheque_type == constants.OTHER_CHARGE else ch.amount,
            "tax_code":              ch.charge.tax_code if ch.charge else None,
            "origin_bank_name":      ch.origin_bank.name if ch.origin_bank else None,
            "origin_account_number": ch.origin_account_number,
        }
        for ch in qs
    ]

    subtotal    = sum((t["amount"] or 0) for t in transactions)
    vat_total   = sum(t["vat"]           for t in transactions)
    grand_total = round(sum(t["total"]   for t in transactions), 2)

    return prepare_response(content={
        "tenant":       tenant_info,
        "property":     property_info,
        "transactions": transactions,
        "totals": {
            "subtotal":    subtotal,
            "vat_total":   vat_total,
            "grand_total": grand_total,
        },
    })


# ── Invoice PDF ───────────────────────────────────────────────────────────────

@is_request_authenticated
@csrf_exempt
def invoice_pdf_view(request):
    """GET /api/lease/invoice-pdf?lease_id=X  — render invoice HTML → PDF → S3 → presigned URL."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    if not lease_id:
        return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    lease = (
        Lease.objects
        .filter(id=lease_id, is_active=True)
        .select_related("tenant__user", "unit__property_block_tower__property")
        .first()
    )
    if not lease:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else None

    qs = lease.lease_cheques.select_related("charge", "origin_bank").filter(is_active=True).order_by("created")

    def _desc(ch):
        if ch.cheque_type == constants.OTHER_CHARGE:
            return ch.charge.description if ch.charge else "Other Charge"
        label = "Rent" if ch.cheque_type == constants.RENT_CHEQUE else "Additional Charge"
        if ch.start_date and ch.end_date:
            return f"{label} [{str(ch.start_date)[:7]} \u2013 {str(ch.end_date)[:7]}]"
        return label

    def _type_label(ct):
        return {"RENT_CHEQUE": "Rent", "ADDITIONAL_CHEQUE": "Additional", "OTHER_CHARGE": "Other Charge"}.get(ct, ct or "—")

    transactions = [
        {
            "description":   _desc(ch),
            "cheque_number": ch.cheque_number or "—",
            "cheque_date":   str(ch.cheque_date)[:10] if ch.cheque_date else "—",
            "type_label":    _type_label(ch.cheque_type),
            "status":        ch.status or "—",
            "payment_type":  ch.payment_type or "—",
            "amount":        float(ch.amount or 0),
            "vat":           float(ch.vat or 0),
            "tax_code":      ch.charge.tax_code if ch.charge else None,
            "total":         float(ch.total if ch.cheque_type == constants.OTHER_CHARGE else (ch.amount or 0)),
        }
        for ch in qs
    ]

    subtotal    = sum(t["amount"] for t in transactions)
    vat_total   = sum(t["vat"]    for t in transactions)
    grand_total = round(sum(t["total"] for t in transactions), 2)

    html_content = _build_invoice_html(
        tenant={
            "name":           f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "—",
            "code":           t.code if t else "",
            "email":          t.user.email if t and t.user else "",
            "contact":        t.contact_number if t else "",
            "address_line_1": t.address_line_1 if t else "",
            "address_line_2": t.address_line_2 if t else "",
        },
        property_info={
            "property_name": prop.property_name if prop else "—",
            "block_name":    pb.block_name if pb else "",
            "unit_name":     unit.unit_name if unit else "",
            "start_date":    str(lease.start_date)[:10] if lease.start_date else "—",
            "end_date":      str(lease.end_date)[:10]   if lease.end_date   else "—",
            "lease_code":    lease.code or "—",
        },
        transactions=transactions,
        totals={"subtotal": subtotal, "vat_total": vat_total, "grand_total": grand_total},
    )

    try:
        pdf_bytes = WeasyprintHTML(string=html_content).write_pdf()
    except Exception as e:
        return prepare_response(message=f"PDF generation failed: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    timestamp    = datetime.now().strftime("%Y%m%d%H%M%S")
    pdf_filename = f"invoice_{lease.code}_{timestamp}.pdf"
    pdf_s3_url   = upload_file_to_s3_base64(pdf_bytes, f"invoices/{pdf_filename}")
    if not pdf_s3_url:
        return prepare_response(message="Failed to upload invoice PDF", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    download_url = fetch_s3_presigned_url_for_download(pdf_s3_url, file_name=pdf_filename)
    return prepare_response(
        content={"pdf_url": download_url, "file_name": pdf_filename},
        status=status.HTTP_200_OK,
    )


def _fmt(n):
    return f"{float(n or 0):,.2f}"


def _amount_in_words(amount):
    ones = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
            "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
            "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
    tens_w = ["", "", "Twenty", "Thirty", "Forty", "Fifty",
              "Sixty", "Seventy", "Eighty", "Ninety"]

    def chunk(n):
        if n == 0:  return ""
        if n < 20:  return ones[n]
        if n < 100: return tens_w[n // 10] + (" " + ones[n % 10] if n % 10 else "")
        return ones[n // 100] + " Hundred" + (" " + chunk(n % 100) if n % 100 else "")

    dirhams = int(amount)
    fils    = round((amount - dirhams) * 100)
    parts   = []
    n = dirhams
    if n >= 1_000_000: parts.append(chunk(n // 1_000_000) + " Million");  n %= 1_000_000
    if n >= 1_000:     parts.append(chunk(n // 1_000)     + " Thousand"); n %= 1_000
    if n > 0:          parts.append(chunk(n))
    dirham_words = " ".join(parts) if parts else "Zero"
    fils_words   = chunk(fils) if fils else "Zero"
    return f"{dirham_words} Dirhams And {fils_words} Fils"


def _status_badge_style(status_val):
    s = (status_val or "").lower()
    if any(k in s for k in ("credit", "paid", "realiz")):
        return "background:#dcfce7;color:#15803d;"
    if any(k in s for k in ("bounce", "reject")):
        return "background:#fee2e2;color:#dc2626;"
    if "pending" in s:
        return "background:#fef3c7;color:#b45309;"
    return "background:#f3f4f6;color:#6b7280;"


def _build_invoice_html(tenant, property_info, transactions, totals):
    today = datetime.now().strftime("%d %b %Y")
    grand = totals["grand_total"]

    # ── Transaction rows ──────────────────────────────
    rows_html = ""
    for i, t in enumerate(transactions):
        bg   = "#f9fafb" if i % 2 == 0 else "#ffffff"
        badge = _status_badge_style(t["status"])
        vat_cell = (f"{t['tax_code']}% / {_fmt(t['vat'])}" if t["tax_code"] is not None else f"— / {_fmt(t['vat'])}")
        rows_html += f"""
        <tr style="background:{bg};">
          <td style="{TD}">{i + 1}</td>
          <td style="{TD}">{t['description']}</td>
          <td style="{TD}">{t['cheque_number']}</td>
          <td style="{TD}">{t['cheque_date']}</td>
          <td style="{TD}">{t['type_label']}</td>
          <td style="{TD}"><span style="display:inline-block;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:600;{badge}">{t['status']}</span></td>
          <td style="{TD_R}">{_fmt(t['amount'])}</td>
          <td style="{TD_R}">{vat_cell}</td>
          <td style="{TD_R};font-weight:700;">{_fmt(t['total'])}</td>
        </tr>"""

    if not rows_html:
        rows_html = f'<tr><td colspan="9" style="text-align:center;padding:20px;color:#aaa;">No transactions found</td></tr>'

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 20mm 15mm; }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, Helvetica, sans-serif; font-size: 13px; color: #1f2937; background: #fff; }}
  .header-table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; border-bottom: 3px solid #0c6ce9; padding-bottom: 16px; }}
  .invoice-title {{ font-size: 30px; font-weight: 900; color: #0c6ce9; letter-spacing: 3px; }}
  .sub-text {{ font-size: 12px; color: #6b7280; margin-top: 4px; }}
  .parties-table {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; }}
  .party-box {{ background: #eff6ff; border-radius: 8px; padding: 16px 18px; vertical-align: top; width: 48%; }}
  .party-spacer {{ width: 4%; }}
  .section-label {{ font-size: 10px; font-weight: 700; color: #0c6ce9; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }}
  .party-name {{ font-size: 14px; font-weight: 700; color: #111; margin-bottom: 6px; }}
  .party-detail {{ font-size: 11px; color: #555; margin-bottom: 3px; }}
  .txn-table {{ width: 100%; border-collapse: collapse; font-size: 11.5px; margin-bottom: 24px; }}
  .txn-table thead tr {{ background: #0c6ce9; color: #fff; }}
  .txn-table thead th {{ padding: 9px 10px; font-weight: 600; white-space: nowrap; }}
  .totals-table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  .totals-right {{ width: 260px; vertical-align: top; }}
  .totals-row {{ display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f3f4f6; font-size: 12px; }}
  .grand-box {{ background: #0c6ce9; color: #fff; border-radius: 6px; padding: 10px 14px; margin-top: 10px; display: flex; justify-content: space-between; font-size: 13px; font-weight: 700; }}
  .footer {{ margin-top: 36px; padding-top: 12px; border-top: 1px solid #e5e7eb; text-align: center; font-size: 10px; color: #9ca3af; }}
</style>
</head>
<body>

<!-- Header -->
<table class="header-table" style="margin-bottom:0;border-bottom:none;">
  <tr>
    <td style="padding-bottom:16px;border-bottom:3px solid #0c6ce9;">
      <div class="invoice-title">INVOICE</div>
      <div class="sub-text">Lease No: <strong style="color:#111;">{property_info['lease_code']}</strong></div>
    </td>
    <td style="text-align:right;padding-bottom:16px;border-bottom:3px solid #0c6ce9;">
      <div class="sub-text">Date: <strong style="color:#111;">{today}</strong></div>
      <div class="sub-text" style="margin-top:4px;">Period: <strong style="color:#111;">{property_info['start_date']} &rarr; {property_info['end_date']}</strong></div>
    </td>
  </tr>
</table>
<div style="height:20px;"></div>

<!-- Parties -->
<table class="parties-table">
  <tr>
    <td class="party-box">
      <div class="section-label">Invoice To</div>
      <div class="party-name">{tenant['name']}</div>
      {'<div class="party-detail">&#9993; ' + tenant['email'] + '</div>'   if tenant.get('email')   else ''}
      {'<div class="party-detail">&#9742; ' + tenant['contact'] + '</div>' if tenant.get('contact') else ''}
      {'<div class="party-detail">'          + tenant['address_line_1'] + '</div>' if tenant.get('address_line_1') else ''}
      {'<div class="party-detail">'          + tenant['address_line_2'] + '</div>' if tenant.get('address_line_2') else ''}
      {'<div class="party-detail" style="margin-top:6px;color:#888;">Ref: <strong>' + tenant['code'] + '</strong></div>' if tenant.get('code') else ''}
    </td>
    <td class="party-spacer"></td>
    <td class="party-box">
      <div class="section-label">Property Details</div>
      <div class="party-name">{property_info['property_name']}{(' | ' + property_info['unit_name']) if property_info.get('unit_name') else ''}</div>
      {'<div class="party-detail">Block: ' + property_info['block_name'] + '</div>' if property_info.get('block_name') else ''}
    </td>
  </tr>
</table>

<!-- Transactions -->
<table class="txn-table">
  <thead>
    <tr>
      <th style="padding:9px 10px;text-align:left;">#</th>
      <th style="padding:9px 10px;text-align:left;">Description</th>
      <th style="padding:9px 10px;text-align:left;">Cheque No</th>
      <th style="padding:9px 10px;text-align:left;">Date</th>
      <th style="padding:9px 10px;text-align:left;">Type</th>
      <th style="padding:9px 10px;text-align:left;">Status</th>
      <th style="padding:9px 10px;text-align:right;">Amount</th>
      <th style="padding:9px 10px;text-align:right;">VAT %/Amt</th>
      <th style="padding:9px 10px;text-align:right;">Total</th>
    </tr>
  </thead>
  <tbody>{rows_html}</tbody>
</table>

<!-- Totals -->
<table class="totals-table">
  <tr>
    <td style="vertical-align:top;padding-right:20px;">
      <div style="font-size:11px;color:#9ca3af;margin-bottom:6px;">Amount in words:</div>
      <div style="font-size:13px;font-weight:700;color:#111;line-height:1.5;">{_amount_in_words(grand)}</div>
    </td>
    <td class="totals-right">
      <table style="width:100%;border-collapse:collapse;font-size:12px;">
        <tr><td style="padding:6px 0;border-bottom:1px solid #f3f4f6;color:#374151;">Sub Total</td>
            <td style="padding:6px 0;border-bottom:1px solid #f3f4f6;text-align:right;font-weight:600;">AED {_fmt(totals['subtotal'])}</td></tr>
        <tr><td style="padding:6px 0;border-bottom:1px solid #f3f4f6;color:#374151;">VAT Amount</td>
            <td style="padding:6px 0;border-bottom:1px solid #f3f4f6;text-align:right;font-weight:600;">AED {_fmt(totals['vat_total'])}</td></tr>
      </table>
      <table style="width:100%;border-collapse:collapse;margin-top:10px;background:#0c6ce9;border-radius:6px;">
        <tr>
          <td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:700;">Grand Total</td>
          <td style="padding:10px 14px;color:#fff;font-size:13px;font-weight:700;text-align:right;">AED {_fmt(grand)}</td>
        </tr>
      </table>
    </td>
  </tr>
</table>

<div class="footer">This is a computer-generated invoice and does not require a signature.</div>
</body>
</html>"""


# Shared cell style constants for invoice template
TD   = "padding:8px 10px;border-bottom:1px solid #f3f4f6;color:#374151;white-space:nowrap;"
TD_R = "padding:8px 10px;border-bottom:1px solid #f3f4f6;color:#374151;white-space:nowrap;text-align:right;"


@csrf_exempt
@is_request_authenticated
def manager_approval_view(request):
    """POST: Create a manager approval entry linked to the lease and update lease stage."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = json.loads(request.body)
    lease_id = data.get("lease_id")
    if not lease_id:
        return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

    lease = Lease.objects.select_related("tenant", "unit").filter(id=lease_id).first()
    if not lease:
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

    requested_rent = data.get("requested_rent") or (float(lease.annual_amount) if lease.annual_amount else 0)
    requested_tenure = data.get("requested_tenure") or ""

    existing = Approval.objects.filter(
        tenant=lease.tenant, unit=lease.unit, approved=False
    ).first()
    if existing:
        lease.lease_stage = constants.MANAGER_APPROVAL_REQUIRED
        lease.save(update_fields=["lease_stage"])
        return prepare_response(
            message="Approval request already pending",
            content={"approval_id": existing.id},
            status=status.HTTP_200_OK,
        )

    approval = Approval.objects.create(
        created_by=request.user.user,
        tenant=lease.tenant,
        unit=lease.unit,
        requested_rent=requested_rent,
        requested_tenure=requested_tenure,
    )

    lease.lease_stage = constants.MANAGER_APPROVAL_REQUIRED
    lease.save(update_fields=["lease_stage"])

    return prepare_response(
        message="Manager approval request created",
        content={"approval_id": approval.id},
        status=status.HTTP_201_CREATED,
    )
