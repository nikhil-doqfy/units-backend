import csv
import json
import os
import uuid
from weasyprint import HTML as WeasyprintHTML
from datetime import datetime, date

from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

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
from property.models import Unit, PropertyManagmentCompany, PMCPMMapping
from user_service.models import Tenant, TenantDocuments, DocumentType, UserProfile, Documents, Approval, PropertyManager, Owner
from property_management import settings
from property_management.utils import audit_logs, get_tenant_detail_by_id
from property_management.models import TermAndCondition, AuditLog
from payment.models import Bank
from .models import Lease, LeaseDocuments, LeaseTransaction, LeaseSignature
from charges.models import Charge
from .serializers import group_lease_cheques, serialize_lease_cheque, serialize_cheque_list_row, LeaseSerializer, _lease_cheque_description
from .services import get_active_lease_for_tenant
from .cheque_scheduling import generate_cheque_schedule

from rest_framework.decorators import api_view
from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import NotFound, ValidationError, PermissionDenied
from utilities.authentication import JWTAuthentication

from .swagger import (
    lease_onboarding_documents_get,
    lease_onboarding_documents_post,
    lease_onboarding_documents_delete,
    lease_cheque_get,
    lease_cheque_post,
    lease_cheque_put,
    lease_cheque_delete,
    cheque_summary_get,
    all_cheques_get,
    cheque_monthly_get,
    rent_analytics_get,
    activate_lease_post,
)
from django.db.models import Q, Sum
from plugins.logger_plugin import get_logger
from utilities.org_scope import get_pmc_ids_for_user

logger = get_logger(__name__)


def _get_pmc_ids_for_user(user_profile):
    """Return the PMCs the logged-in property manager is allowed to access."""
    pm_profile = PropertyManager.objects.filter(
        pk=user_profile.pk
    ).select_related("company").first()
    if pm_profile:
        pmc_ids = list(
            PMCPMMapping.objects.filter(pm=pm_profile).values_list("pmc_id", flat=True)
        )
        if not pmc_ids and pm_profile.company_id:
            pmc_ids = [pm_profile.company_id]
        return pmc_ids

    own_company = PropertyManagmentCompany.objects.filter(
        created_by=user_profile.user,
        is_active=True,
    ).first()
    return [own_company.id] if own_company else []

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


def _create_tenant(email, data, created_by, pmc):
    name = data.get("tenant_name") or data.get("name") or ""
    first_name, _, last_name = name.partition(" ")
    with transaction.atomic():
        django_user = User.objects.create_user(
            username=email, email=email,
            first_name=first_name, last_name=last_name,
            password=get_random_string(12),
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
        tenant_obj.pmc.add(pmc)
    return tenant_obj

class LeaseViewSet(viewsets.ViewSet):
    """First lease/lead endpoint converted to real DRF (see the DRF
    migration plan) -- JWTAuthentication + IsAuthenticated instead of
    is_request_authenticated, LeaseSerializer instead of serialize_lease
    called by hand, DRF's Response instead of prepare_response's
    {content, message, status} envelope. Business logic (tenant
    resolution, VAT/commission computation, other-charges reconciliation)
    is unchanged from the previous function-based lease_view.

    No partial_update() defined on purpose: the router only wires up PATCH
    when the method exists, so PATCH still 405s exactly as it did before.
    """
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def list(self, request):
        user = request.user
        qs = Lease.objects.for_user(user).select_related("unit__property_block_tower__property", "tenant__user").filter(is_active=True)

        property_id = request.query_params.get("property_id")
        unit_id = request.query_params.get("unit_id")
        tenant_id = request.query_params.get("tenant_id")
        lease_status = request.query_params.get("lease_status")
        search = request.query_params.get("search", "").strip()
        pmc_id = request.query_params.get("pmc_id", "").strip()

        if pmc_id:
            if int(pmc_id) not in get_pmc_ids_for_user(user):
                raise PermissionDenied("You are not allowed to access this PMC")
            qs = qs.filter(
                Q(unit__parent_property__pmc_id=pmc_id) |
                Q(unit__property_block_tower__property__pmc_id=pmc_id)
            )

        if property_id:
            qs = qs.filter(
                Q(unit__parent_property_id=property_id) |
                Q(unit__property_block_tower__property_id=property_id)
            )
        if unit_id:
            qs = qs.filter(unit_id=unit_id)
        if tenant_id:
            qs = qs.filter(tenant_id=tenant_id)
        if lease_status:
            qs = qs.filter(lease_status=lease_status)
        lease_stage = request.query_params.get("lease_stage")
        if lease_stage:
            qs = qs.filter(lease_stage=lease_stage)
        if search:
            qs = qs.filter(code__icontains=search)

        qs = qs.order_by("-created")

        page = int(request.query_params.get("page", 1))
        page_size = int(request.query_params.get("page_size", 20))
        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(page)
        logger.info(
            "LEASE_LIST_FETCHED | user_id=%d | total=%d", request.user.id, paginator.count)
        return Response({
            "results": LeaseSerializer(page_obj, many=True).data,
            "pagination": {
                "has_previous": page_obj.has_previous(),
                "has_next": page_obj.has_next(),
                "page_number": page_obj.number,
                "total_records": paginator.count,
            },
        })

    def retrieve(self, request, pk=None):
        user = request.user
        lease = (
            Lease.objects
            .for_user(user)
            .select_related("unit__property_block_tower__property", "tenant__user")
            .prefetch_related("unit__unit_owners__owner__user")
            .filter(id=pk, is_active=True)
            .first()
        )
        if not lease:
            logger.warning(
                "LEASE_FETCH_FAILED | user_id=%d | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, pk)
            raise NotFound("Lease not found")
        logger.info(
            "LEASE_FETCHED | user_id=%d | lease_id=%d", request.user.id, lease.id)
        return Response(LeaseSerializer(lease).data)

    def create(self, request):
        user = request.user
        body = request.data

        unit_id = body.get("unit_id") or body.get("property_id")
        tenant_id = body.get("tenant_id")
        email = (body.get("email") or "").strip()

        if not unit_id:
            logger.warning(
                "LEASE_CREATE_FAILED | user_id=%d | reason=UNIT_ID_MISSING", request.user.id)
            raise ValidationError({"detail": "unit_id is required"})

        unit_obj = Unit.objects.select_related("property_block_tower__property", "parent_property").filter(id=unit_id).first()
        if not unit_obj:
            logger.warning(
                "LEASE_CREATE_FAILED | user_id=%d | unit_id=%s | reason=UNIT_NOT_FOUND",
                request.user.id, unit_id)
            raise ValidationError({"detail": "Unit not found"})
        pmc = (
            unit_obj.property_block_tower.property.pmc
            if unit_obj.property_block_tower
            else unit_obj.parent_property.pmc
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
            tenant_obj.pmc.add(pmc)
            tenant_obj.save()
        elif email:
            tenant_obj = _create_tenant(email, body, user, pmc)
        else:
            logger.warning(
                "LEASE_CREATE_FAILED | user_id=%d | reason=TENANT_ID_OR_EMAIL_REQUIRED",
                request.user.id)
            raise ValidationError({"detail": "tenant_id or email is required"})

        # Block if tenant already has an active lease
        active_lease = get_active_lease_for_tenant(tenant_obj)
        if active_lease:
            logger.warning(
                "LEASE_CREATE_FAILED | user_id=%d | tenant_id=%d | reason=ACTIVE_LEASE_EXISTS_ALREADY",
                request.user.id, tenant_obj.id)
            raise ValidationError({
                "detail": f"Tenant already has an active lease ({active_lease.code}). A new lease cannot be created while an active lease exists."
            })

        # Phase 4: VAT/commission computed at creation time.
        _annual_amount = body.get("annual_amount") or None
        _contract_amount = body.get("contract_amount") or None
        _vat_base = _contract_amount or _annual_amount
        _vat_amount = round(float(_vat_base) * constants.UAE_VAT_RATE, 2) if _vat_base else None

        _commission = body.get("commission")
        if _commission is None and unit_obj.commission_percent and body.get("rent"):
            _commission = round(float(body.get("rent")) * float(unit_obj.commission_percent) / 100, 2)
        else:
            _commission = _commission or None

        lease = Lease.objects.create(
            created_by=user.user,
            unit=unit_obj,
            tenant=tenant_obj,
            start_date=_parse_date(body.get("start_date")),
            end_date=_parse_date(body.get("end_date")),
            grace_start_date=_parse_date(body.get("grace_start_date")),
            grace_end_date=_parse_date(body.get("grace_end_date")),
            annual_amount=_annual_amount,
            actual_annual_amount=body.get("actual_annual_amount") or None,
            booking_amount=body.get("booking_amount") or None,
            maintenance_charges=body.get("maintenance_charges") or None,
            rent=body.get("rent") or None,
            security_deposit=body.get("security_deposit") or None,
            commission=_commission,
            notice_period=body.get("notice_period") or None,
            discount=body.get("discount") or None,
            contract_amount=_contract_amount,
            payment_count=body.get("payment_count") or None,
            payment_frequency=body.get("payment_frequency") or None,
            vat_amount=_vat_amount,
            shell_and_core=bool(body.get("shell_and_core", False)),
            remarks=body.get("remarks") or "",
            lease_status=body.get("lease_status") or constants.LEASE_STATUS_CHOICES[0][0],
            lease_stage=body.get("lease_stage") or constants.INVITE,
            platform=body.get("platform") or None,
        )
        unit_obj.status = constants.UNIT_CONTRACT_IN_PROGRESS
        unit_obj.save(update_fields=["status"])
        logger.info(
            "LEASE_CREATED_SUCCESSFULLY | user_id=%d | lease_id=%d | tenant_id=%d | unit_id=%d",
            request.user.id, lease.id, tenant_obj.id, unit_obj.id)
        return Response(LeaseSerializer(lease).data, status=status.HTTP_201_CREATED)

    def update(self, request, pk=None):
        user = request.user
        body = request.data

        lease = Lease.objects.for_user(user).filter(id=pk, is_active=True).first()
        if not lease:
            logger.warning("LEASE_UPDATE_FAILED | user_id=%d | lease_id=%s | reason=NOT_FOUND",
                request.user.id, pk)
            raise NotFound("Lease not found")

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
            "payment_frequency": body.get("payment_frequency"),
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

        # Phase 4: recompute VAT whenever annual/contract amount changed
        # (safe to just always recompute off whatever the lease currently
        # holds post-merge, since it's idempotent). Commission is
        # deliberately NOT re-derived here -- only ever auto-computed
        # once at creation, so a PM's manual override on an unrelated
        # field-edit is never silently clobbered.
        _vat_base = lease.contract_amount or lease.annual_amount
        lease.vat_amount = round(float(_vat_base) * constants.UAE_VAT_RATE, 2) if _vat_base else None

        lease.save()
        logger.info(
            "LEASE_UPDATED_SUCCESSFULLY | user_id=%d | lease_id=%d | lease_status=%s | lease_stage=%s",
            request.user.id, lease.id, lease.lease_status, lease.lease_stage)

        other_charges = body.get("other_charges")
        if other_charges is not None:
            lease_cheque_doc_type = (
                DocumentType.objects.filter(section=constants.LEASE_CHEQUE).first()
                or DocumentType.objects.first()
            )

            # Each item is either an existing Charge (from the Charges
            # section, referenced by charge_id) or a commercial-details
            # field surfaced as a charge line (Security/Booking Amount,
            # Maintenance Charges, Security Deposit, Commission --
            # identified by description only). Field-derived items are
            # NEVER turned into a Charge record in Settings > Charges --
            # they're stored directly on the transaction's own
            # description, at the flat UAE VAT rate (LeaseTransaction.save()).
            resolved_charges = []
            for item in other_charges:
                amount = item.get("amount")
                if amount is None:
                    continue
                charge_id = item.get("charge_id")
                description = item.get("description")
                if charge_id:
                    charge = Charge.objects.filter(id=charge_id).first()
                    if not charge:
                        continue
                    resolved_charges.append({"charge": charge, "description": None, "amount": amount})
                elif description:
                    resolved_charges.append({"charge": None, "description": description, "amount": amount})

            incoming_charge_ids = {r["charge"].id for r in resolved_charges if r["charge"]}
            incoming_descriptions = {r["description"] for r in resolved_charges if r["description"]}

            existing_other_charges = lease.lease_cheques.filter(cheque_type=constants.OTHER_CHARGE)
            # Delete removed other-charge transactions -- matched by
            # charge_id for Charges-list items, by description for
            # field-derived ones (which have no charge_id at all).
            existing_other_charges.exclude(
                Q(charge_id__in=incoming_charge_ids) |
                Q(charge__isnull=True, description__in=incoming_descriptions)
            ).delete()

            for r in resolved_charges:
                if r["charge"]:
                    existing = existing_other_charges.filter(charge_id=r["charge"].id).first()
                else:
                    existing = existing_other_charges.filter(charge__isnull=True, description=r["description"]).first()

                if existing:
                    existing.amount = float(r["amount"])
                    existing.save()
                else:
                    LeaseTransaction.objects.create(
                        lease=lease,
                        cheque_type=constants.OTHER_CHARGE,
                        charge=r["charge"],
                        description=r["description"] or "",
                        amount=float(r["amount"]),
                        document_type=lease_cheque_doc_type,
                        file_name='',
                        file_path='',
                        created_by=user.user,
                    )

        return Response(LeaseSerializer(lease).data)

    def destroy(self, request, pk=None):
        user = request.user
        lease = Lease.objects.for_user(user).filter(id=pk, is_active=True).first()
        if not lease:
            logger.warning(
                "LEASE_DELETE_FAILED | user_id=%d | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, pk)
            raise NotFound("Lease not found")

        lease.is_active = False
        lease.save(update_fields=["is_active"])
        logger.info(
            "LEASE_DELETED_SUCCESSFULLY | user_id=%d | lease_id=%d",
            request.user.id, lease.id)

        return Response(status=status.HTTP_204_NO_CONTENT)


@lease_onboarding_documents_get
@lease_onboarding_documents_post
@lease_onboarding_documents_delete
@api_view(['GET', 'POST', 'DELETE'])
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
            logger.warning(
                "LEASE_DOCUMENT_FETCH_FAILED | user_id=%d | reason=LEASE_ID_MISSING", request.user.id)
            return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.for_user(user).filter(id=lease_id, is_active=True).select_related("tenant").first()
        if not lease:
            logger.warning(
                "LEASE_DOCUMENT_FETCH_FAILED | user_id=%d | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id )
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
        logger.info(
            "LEASE_DOCUMENT_FETCHED | user_id=%d | lease_id=%s",
            request.user.id, lease_id)
        return prepare_response(content={
            "tenant_documents": [_doc(d, "tenant") for d in tenant_docs],
            "lease_documents":  [_doc(d, "lease")  for d in lease_docs],
        })

    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except Exception:
            logger.warning(
                "LEASE_DOCUMENT_UPLOAD_FAILED | user_id=%d | reason=INVALID_JSON",
                request.user.id)
            return prepare_response(message="Invalid JSON", status=status.HTTP_400_BAD_REQUEST)

        lease_id       = data.get("lease_id")
        documents_data = data.get("documents") or []

        if not lease_id:
            logger.warning(
                "LEASE_DOCUMENT_UPLOAD_FAILED | user_id=%d | reason=LEASE_ID_MISSING",request.user.id)
            return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.for_user(user).filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "LEASE_DOCUMENT_UPLOAD_FAILED | user_id=%d | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id )
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
        logger.info(
            "LEASE_DOCUMENT_UPLOADED | user_id=%d | lease_id=%d | documents_count=%d",
            request.user.id, lease.id, len(created_ids) )
        return prepare_response(
            message="Documents uploaded successfully",
            content={"ids": created_ids},
            status=status.HTTP_201_CREATED,
        )

    elif request.method == "DELETE":
        document_id = request.GET.get("document_id")
        if not document_id:
            logger.warning(
                "LEASE_DOCUMENT_DELETE_FAILED | user_id=%d | reason=DOCUMENT_ID_MISSING",
                request.user.id)
            return prepare_response(message="document_id is required", status=status.HTTP_400_BAD_REQUEST)
        LeaseDocuments.objects.filter(id=document_id).delete()
        logger.info(
            "LEASE_DOCUMENT_DELETED | user_id=%d | document_id=%s",
            request.user.id, document_id )
        return prepare_response(message="Document deleted successfully")

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_405_METHOD_NOT_ALLOWED,
    )


# ── Cheque auto-generation (Dubai Leasing Management Flow, Phase 3) ───────────
# Sits alongside lease_cheque_view below, which remains the one-at-a-time
# edit/adjust surface -- this is purely the bulk "generate the standard N
# cheques" convenience action.

@is_request_authenticated
def generate_cheque_schedule_view(request):
    """POST: bulk-generate rent cheques from Lease.contract_amount / payment_frequency."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body = json.loads(request.body)
        lease_id = body.get("lease_id")
        frequency = body.get("payment_frequency")
        start_date = _parse_date(body.get("start_date"))
        regenerate = bool(body.get("regenerate", False))

        if not lease_id or not frequency or not start_date:
            logger.warning(
                "CHEQUE_SCHEDULE_GENERATION_FAILED | user_id=%s | reason=MISSING_REQUIRED_FIELDS",
                request.user.id)
            return prepare_response(
                message="lease_id, payment_frequency and start_date are required",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lease = Lease.objects.filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "CHEQUE_SCHEDULE_GENERATION_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id)
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        if regenerate:
            lease.lease_cheques.filter(cheque_type=constants.RENT_CHEQUE).delete()
        elif lease.lease_cheques.filter(cheque_type=constants.RENT_CHEQUE).exists():
            return prepare_response(
                message="Rent cheques already exist for this lease. Pass regenerate=true to replace them.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lease.payment_frequency = frequency
        lease.save(update_fields=["payment_frequency"])

        try:
            created = generate_cheque_schedule(lease, frequency, start_date, request.user.user)
        except ValueError as e:
            return prepare_response(message=str(e), status=status.HTTP_400_BAD_REQUEST)

        logger.info(
            "CHEQUE_SCHEDULE_GENERATED | user_id=%s | lease_id=%s | count=%s",
            request.user.id, lease_id, len(created))
        audit_logs(
            request,
            f"Generated {len(created)} rent cheques ({frequency}) for lease '{lease.code}'",
            constants.CREATED,
        )

        return prepare_response(
            content=[serialize_lease_cheque(c) for c in created],
            message=f"Generated {len(created)} rent cheques.",
            status=status.HTTP_201_CREATED,
        )
    except Exception as e:
        logger.exception(
            "CHEQUE_SCHEDULE_GENERATION_ERROR | user_id=%s | error=%s",
            request.user.id, str(e))
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@lease_cheque_get
@lease_cheque_post
@lease_cheque_put
@lease_cheque_delete
@api_view(['GET', 'POST', 'PUT', 'DELETE'])
@csrf_exempt
@is_request_authenticated
def lease_cheque_view(request):
    """CRUD for LeaseTransaction. GET ?lease_id=X, POST/PUT body JSON, DELETE ?cheque_id=X"""

    if request.method == "GET":

        user_profile = request.user

        pm_profile = PropertyManager.objects.filter(
            pk=user_profile.pk
        ).select_related("company").first()
        owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
        pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
        if not pmc_ids and not owner_profile:
            logger.warning(
                "LEASE_CHEQUE_FETCH_FAILED | user_id=%d | reason=UNAUTHORIZED_ROLE", request.user.id)
            return prepare_response(message=constants.UNAUTHORIZED_ROLE,status=status.HTTP_403_FORBIDDEN)

        # ── Single cheque ──────────────────────────────────────
        cheque_id = request.GET.get("cheque_id")

        if cheque_id:
            try:
                if pmc_ids:
                    cheque = LeaseTransaction.objects.select_related(
                        "origin_bank",
                        "selltlement_bank",
                        "document_type",
                        "lease__unit__property_block_tower__property"
                    ).get(
                        Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
                        Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids),
                        id=cheque_id,
                    )
                else:
                    cheque = LeaseTransaction.objects.select_related(
                        "origin_bank",
                        "selltlement_bank",
                        "document_type",
                        "lease__unit__property_block_tower__property"
                    ).get(
                        lease__unit__unit_owners__owner=owner_profile,
                        id=cheque_id,
                    )

            except LeaseTransaction.DoesNotExist:
                logger.warning(
                    "LEASE_CHEQUE_FETCH_FAILED | user_id=%d | cheque_id=%s | reason=CHEQUE_NOT_FOUND",
                    request.user.id, cheque_id )
                return prepare_response(message="Cheque not found",status=status.HTTP_404_NOT_FOUND)
            logger.info(
                "LEASE_CHEQUE_FETCHED | user_id=%d | cheque_id=%d",
                request.user.id, cheque.id )
            return prepare_response(
                content=serialize_lease_cheque(cheque),
                status=status.HTTP_200_OK
            )

        # ── Lease cheque list ──────────────────────────────────
        lease_id = request.GET.get("lease_id")

        if not lease_id:
            logger.warning(
                "LEASE_CHEQUE_FETCH_FAILED | user_id=%d | reason=LEASE_ID_MISSING",
                request.user.id)
            return prepare_response(
                message="lease_id or cheque_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        search = request.GET.get("search", "").strip()
        payment_type = request.GET.get("payment_type")
        cheque_status = request.GET.get("status")
        if pmc_ids:
            cheques = LeaseTransaction.objects.filter(
                lease_id=lease_id,
            ).filter(
                Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
                Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
            ).select_related(
                "origin_bank",
                "selltlement_bank",
                "document_type",
                "lease__unit__property_block_tower__property",
                "lease__unit__parent_property",
            )
        else:
            cheques = LeaseTransaction.objects.filter(
                lease_id=lease_id,
                lease__unit__unit_owners__owner=owner_profile,
            ).select_related(
                "origin_bank",
                "selltlement_bank",
                "document_type",
                "lease__unit__property_block_tower__property",
                "lease__unit__parent_property",
            ).distinct()
        # ── Search ─────────────────────────────────────────────
        if search:
            cheques = cheques.filter(
                Q(cheque_number__icontains=search) |
                Q(code__icontains=search) |
                Q(origin_bank__name__icontains=search) |
                Q(selltlement_bank__name__icontains=search)
            )
        #filters
        if payment_type:
            cheques = cheques.filter(payment_type=payment_type)
            
        if cheque_status:
            cheques = cheques.filter(status=cheque_status)
        logger.info(
            "LEASE_CHEQUE_LIST_FETCHED | user_id=%d | lease_id=%s | count=%d",
            request.user.id, lease_id, cheques.count() )

        # Pagination is opt-in (only applied when page/page_size are sent)
        # so the Collect Cheque page's existing "show everything" callers
        # keep working unchanged.
        raw_page = request.GET.get("page")
        raw_page_size = request.GET.get("page_size")
        if raw_page or raw_page_size:
            page = int(raw_page or 1)
            page_size = int(raw_page_size or 10)
            paginator = Paginator(cheques.order_by("-cheque_date", "-created"), page_size)
            page_obj = paginator.get_page(page)
            return prepare_response(
                content=group_lease_cheques(list(page_obj)),
                pagination={
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages,
                    "current_page": page,
                    "page_size": page_size,
                },
                status=status.HTTP_200_OK,
            )

        return prepare_response(content=group_lease_cheques(cheques),status=status.HTTP_200_OK)
    # ── POST create ───────────────────────────────────────────────────────────
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            logger.warning(
                "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | reason=INVALID_JSON",request.user.id )
            return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)

        lease_id = data.get("lease_id")
        if not lease_id:
            logger.warning(
                        "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | reason=LEASE_ID_MISSING", request.user.id )
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            # lease = Lease.objects.get(id=lease_id)
            pmc_ids = _get_pmc_ids_for_user(request.user)
            if not pmc_ids:
                logger.warning(
                    "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | reason=COMPANY_NOT_FOUND",
                    request.user.id)
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            lease = Lease.objects.filter(id=lease_id).filter(
                Q(unit__parent_property__pmc_id__in=pmc_ids) |
                Q(unit__property_block_tower__property__pmc_id__in=pmc_ids)
            ).first()
            if not lease:
                raise Lease.DoesNotExist
        except Lease.DoesNotExist:
            logger.warning(
                "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id)
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        from user_service.models import DocumentType
        document_type_id = data.get("document_type_id")
        try:
            doc_type = DocumentType.objects.get(id=document_type_id) if document_type_id else DocumentType.objects.first()
        except DocumentType.DoesNotExist:
            logger.warning(
                "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | lease_id=%s | reason=DOCUMENT_TYPE_NOT_FOUND",
                request.user.id, lease_id)
            return prepare_response(message="Document type not found", status=status.HTTP_404_NOT_FOUND)

        from payment.models import Bank
        origin_bank_id      = data.get("origin_bank_id")
        settlement_bank_id  = data.get("settlement_bank_id")
        try:
            origin_bank     = Bank.objects.get(id=origin_bank_id)     if origin_bank_id     else None
            settlement_bank = Bank.objects.get(id=settlement_bank_id) if settlement_bank_id else None
        except Bank.DoesNotExist:
            logger.warning(
                "LEASE_CHEQUE_CREATE_FAILED | user_id=%d | lease_id=%s | reason=BANK_NOT_FOUND",
                request.user.id, lease_id )
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
            payment_type=data.get("payment_type", constants.PAYMENT_TYPE_PDC),
            cheque_number=data.get("cheque_number") or "",
            description=data.get("description") or "",
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
        logger.info(
            "LEASE_CHEQUE_CREATED | user_id=%d | lease_id=%d | cheque_id=%d",
            request.user.id, lease.id, cheque.id )
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
            logger.warning(
                        "LEASE_CHEQUE_UPDATE_FAILED | user_id=%d | reason=INVALID_JSON", request.user.id)
            return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)

        cheque_id = data.get("cheque_id")
        if not cheque_id:
            logger.warning(
                        "LEASE_CHEQUE_UPDATE_FAILED | user_id=%d | reason=CHEQUE_ID_MISSING",
                        request.user.id)
            return prepare_response(message="cheque_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            pmc_ids = _get_pmc_ids_for_user(request.user)
            if not pmc_ids:
                logger.warning(
                    "LEASE_CHEQUE_UPDATE_FAILED | user_id=%d | reason=COMPANY_NOT_FOUND", 
                    request.user.id)
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            # cheque = LeaseTransaction.objects.get(id=cheque_id)
            cheque = LeaseTransaction.objects.filter(id=cheque_id).filter(
               Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
               Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
            ).first()
            if not cheque:
                raise LeaseTransaction.DoesNotExist
        except LeaseTransaction.DoesNotExist:
            logger.warning(
                "LEASE_CHEQUE_UPDATE_FAILED | user_id=%d | cheque_id=%s | reason=CHEQUE_NOT_FOUND",
                request.user.id, cheque_id)
            return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)

        from payment.models import Bank
        updatable = ["cheque_type", "payment_type", "origin_account_number",
                     "settlement_account_number", "amount", "status", "cheque_number",
                     "description"]
        integer_fields = {"origin_account_number", "settlement_account_number"}
        for field in updatable:
            if field in data:
                value = data[field]
                if field in integer_fields and value in ("", None):
                    value = None
                setattr(cheque, field, value)

        for date_field in ["start_date", "end_date", "cheque_date"]:
            if date_field in data:
                setattr(cheque, date_field, _parse_date(data[date_field]))

        for bank_field, attr in [("origin_bank_id", "origin_bank"), ("settlement_bank_id", "selltlement_bank")]:
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
        logger.info(
            "LEASE_CHEQUE_UPDATED | user_id=%d | cheque_id=%d | status=%s",
            request.user.id, cheque.id, cheque.status)
        from notification.utils import (
            notify_cheque_bounced,
            notify_cheque_realized,
        )

        tenant_user_profile = cheque.lease.tenant
        print("Logged in user:", request.user)
        print("Tenant user:", tenant_user_profile)

        if cheque.status == "BOUNCED":
            logger.info(
                "LEASE_CHEQUE_BOUNCED_NOTIFICATION | cheque_id=%d", cheque.id)
            notify_cheque_bounced(tenant_user_profile, cheque)

        elif cheque.status == "REALIZED":
            logger.info(
                    "LEASE_CHEQUE_REALIZED_NOTIFICATION | cheque_id=%d", cheque.id )
            notify_cheque_realized(tenant_user_profile, cheque)

            if not cheque.invoice_pdf_path:
                try:
                    invoice_pdf_bytes = _build_cheque_invoice_pdf_bytes(cheque)
                    invoice_url = upload_file_to_s3_base64(
                        invoice_pdf_bytes, f"invoices/{cheque.lease_id}/invoice_{cheque.code}.pdf",
                    )
                    if invoice_url:
                        cheque.invoice_pdf_path = invoice_url
                        cheque.save(update_fields=["invoice_pdf_path"])
                        logger.info("CHEQUE_INVOICE_GENERATED | cheque_id=%d", cheque.id)
                except Exception as e:
                    logger.exception(
                        "CHEQUE_INVOICE_GENERATION_FAILED | cheque_id=%d | error=%s",
                        cheque.id, str(e))
        return prepare_response(message="Cheque updated successfully", status=status.HTTP_200_OK)

    # ── DELETE ────────────────────────────────────────────────────────────────
    elif request.method == "DELETE":
        cheque_id = request.GET.get("cheque_id")
        if not cheque_id:
            logger.warning(
                        "LEASE_CHEQUE_DELETE_FAILED | user_id=%d | reason=CHEQUE_ID_MISSING",
                        request.user.id)
            return prepare_response(message="cheque_id is required", status=status.HTTP_400_BAD_REQUEST)
        try:
            # LeaseTransaction.objects.get(id=cheque_id).delete()
            pmc_ids = _get_pmc_ids_for_user(request.user)
            if not pmc_ids:
                logger.warning(
                    "LEASE_CHEQUE_DELETE_FAILED | user_id=%d | reason=COMPANY_NOT_FOUND",
                    request.user.id)
                return prepare_response( message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND )
            deleted_count, _ = LeaseTransaction.objects.filter(id=cheque_id).filter(
                Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
                Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
            ).delete()
            if not deleted_count:
                raise LeaseTransaction.DoesNotExist
            logger.info(
                "LEASE_CHEQUE_DELETED | user_id=%d | cheque_id=%s", 
                request.user.id, cheque_id )
        except LeaseTransaction.DoesNotExist:
            logger.warning(
                        "LEASE_CHEQUE_DELETE_FAILED | user_id=%d | cheque_id=%s | reason=CHEQUE_NOT_FOUND",
                        request.user.id, cheque_id)
            return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)
        return prepare_response(message="Cheque deleted successfully", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def lease_cheque_status(request):
    """Legacy — kept for backward compat. Delegates to lease_cheque_view."""
    return lease_cheque_view(request)


def _receipt_status_style(status_val):
    s = (status_val or "").lower()
    if any(k in s for k in ("credit", "paid", "realiz")):
        return "background:#dcfce7;color:#15803d;"
    if any(k in s for k in ("bounce", "reject")):
        return "background:#fee2e2;color:#dc2626;"
    if "pending" in s:
        return "background:#fef3c7;color:#b45309;"
    return "background:#f3f4f6;color:#6b7280;"


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


def _build_cheque_invoice_pdf_bytes(cheque):
    """Renders the Tax Invoice template for a single realized cheque/
    transaction -- one invoice per cheque, generated once the moment its
    status first becomes REALIZED (see lease_cheque_view's PUT handler)."""
    lease = cheque.lease
    t     = lease.tenant
    unit  = lease.unit
    pb    = unit.property_block_tower if unit else None
    prop  = pb.property if pb else (unit.parent_property if unit else None)

    tax_code = cheque.charge.tax_code if cheque.charge else constants.UAE_VAT_RATE * 100
    amount   = float(cheque.amount or 0)
    vat      = float(cheque.vat or 0)
    total    = float(cheque.total or 0)

    html_content = render_to_string("pdf_templates/invoice.html", {
        "trn": "",
        "tenant": {
            "name":    f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "—",
            "address": f"{t.address_line_1 or ''} {t.address_line_2 or ''}".strip() if t else "",
            "phone":   t.contact_number if t else "",
            "trn":     "",
        },
        "property_info": {
            "property_name": prop.property_name if prop else "—",
            "unit_name":     unit.unit_name if unit else "",
            "period_start":  str(cheque.start_date)[:10] if cheque.start_date else str(lease.start_date)[:10] if lease.start_date else "—",
            "period_end":    str(cheque.end_date)[:10] if cheque.end_date else str(lease.end_date)[:10] if lease.end_date else "—",
            "lease_code":    lease.code or "—",
            "ref_no":        cheque.code or "—",
        },
        "invoice_no":      f"INV-{cheque.code}",
        "prepared_by":     f"{cheque.created_by.first_name} {cheque.created_by.last_name}".strip() if cheque.created_by else "—",
        "signatory_name":  f"{cheque.created_by.first_name} {cheque.created_by.last_name}".strip() if cheque.created_by else "—",
        "invoice_date":  datetime.now().strftime("%d-%b-%Y"),
        "due_date":      str(cheque.cheque_date)[:10] if cheque.cheque_date else datetime.now().strftime("%d-%b-%Y"),
        "items": [{
            "description": _lease_cheque_description(cheque),
            "quantity":    1,
            "rate":        f"{amount:,.2f}",
            "amount":      f"{amount:,.2f}",
            "tax_code":    tax_code,
            "vat":         f"{vat:,.2f}",
            "total":       f"{total:,.2f}",
        }],
        "amount_in_words": _amount_in_words(total),
        "subtotal":        f"{amount:,.2f}",
        "vat_total":       f"{vat:,.2f}",
        "grand_total":     f"{total:,.2f}",
        "payment_type":    cheque.payment_type or "—",
        "cheque_number":   cheque.cheque_number or "",
        "transaction_id":  cheque.code or "—",
    })
    # base_url lets the template's untouched <img src="logo.png"> (a plain
    # relative path, per the original template file) resolve against the
    # local logo.png placed alongside it.
    pdf_templates_dir = os.path.join(settings.BASE_DIR, "templates", "pdf_templates")
    return WeasyprintHTML(string=html_content, base_url=pdf_templates_dir).write_pdf()


@is_request_authenticated
@csrf_exempt
def rent_receipt_months_view(request):
    """GET /api/lease/rent-receipt-months?lease_id=X — distinct months (by
    cheque_date) that have a rent cheque, for the Rental receipt picker."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    if not lease_id:
        return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    user_profile = request.user
    pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
    if not pmc_ids and not owner_profile:
        return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)

    if pmc_ids:
        cheques = LeaseTransaction.objects.filter(
            lease_id=lease_id, cheque_type=constants.RENT_CHEQUE, is_active=True,
        ).filter(
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
        )
    else:
        cheques = LeaseTransaction.objects.filter(
            lease_id=lease_id, cheque_type=constants.RENT_CHEQUE, is_active=True,
            lease__unit__unit_owners__owner=owner_profile,
        ).distinct()

    months = sorted({
        ch.cheque_date.strftime("%Y-%m") for ch in cheques if ch.cheque_date
    })
    content = [
        {"key": m, "label": datetime.strptime(m, "%Y-%m").strftime("%b %Y")}
        for m in months
    ]
    return prepare_response(content=content, status=status.HTTP_200_OK)


@is_request_authenticated
@csrf_exempt
def lease_activity_history_view(request):
    """GET /api/lease/activity-history?lease_id=X — recent audit-log
    entries mentioning this lease's code. AuditLog isn't lease-scoped by a
    foreign key (it's a flat, org-wide log), so this matches on the
    lease's own code, which every lease-related audit_logs() call already
    includes in its message."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    if not lease_id:
        return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    user_profile = request.user
    pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
    if not pmc_ids and not owner_profile:
        return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)

    lease_qs = Lease.objects.filter(id=lease_id, is_active=True)
    if pmc_ids:
        lease = lease_qs.filter(
            Q(unit__parent_property__pmc_id__in=pmc_ids) |
            Q(unit__property_block_tower__property__pmc_id__in=pmc_ids)
        ).first()
    else:
        lease = lease_qs.filter(unit__unit_owners__owner=owner_profile).first()

    if not lease:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    logs = AuditLog.objects.filter(
        message__icontains=lease.code,
    ).select_related("userprofile__user").order_by("-created")[:50]

    content = [
        {
            "id":            log.id,
            "message":       log.message,
            "action_type":   log.action_type,
            "created":       log.created.isoformat(),
            "user_name":     f"{log.userprofile.user.first_name} {log.userprofile.user.last_name}".strip()
                              if log.userprofile and log.userprofile.user else "",
        }
        for log in logs
    ]
    return prepare_response(content=content, status=status.HTTP_200_OK)


@is_request_authenticated
def cheque_file_proxy_view(request):
    """GET /api/lease/cheque-file-proxy?cheque_id=X&type=receipt|invoice
    Streams the cheque's receipt (uploaded file) or auto-generated invoice
    through our own backend instead of the frontend fetching S3 directly
    -- the S3 bucket has no CORS policy configured, which silently blocks
    the browser's own fetch() calls needed to preview these in-page via
    ng2-pdf-viewer (a raw <img>/<a> tag doesn't need CORS, but reading the
    bytes into a blob for the PDF viewer does)."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    cheque_id = request.GET.get("cheque_id")
    file_type = (request.GET.get("type") or "receipt").lower()
    if not cheque_id:
        return prepare_response(message="cheque_id is required", status=status.HTTP_400_BAD_REQUEST)

    user_profile = request.user
    pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
    if not pmc_ids and not owner_profile:
        return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)

    if pmc_ids:
        cheque = LeaseTransaction.objects.filter(id=cheque_id).filter(
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
        ).first()
    else:
        cheque = LeaseTransaction.objects.filter(
            id=cheque_id, lease__unit__unit_owners__owner=owner_profile,
        ).first()

    if not cheque:
        return prepare_response(message="Cheque not found", status=status.HTTP_404_NOT_FOUND)

    s3_url = cheque.invoice_pdf_path if file_type == "invoice" else cheque.file_path
    if not s3_url:
        return prepare_response(message="File not found", status=status.HTTP_404_NOT_FOUND)

    try:
        from utilities.helper_functions import _s3_client
        from utilities.config import S3_BUCKET_NAME
        key = s3_url.split(".amazonaws.com/")[1]
        s3_client = _s3_client()
        obj = s3_client.get_object(Bucket=S3_BUCKET_NAME, Key=key)
        content_type = obj.get("ContentType") or "application/octet-stream"
        return HttpResponse(obj["Body"].read(), content_type=content_type)
    except Exception as e:
        logger.exception(
            "CHEQUE_FILE_PROXY_FAILED | cheque_id=%s | type=%s | error=%s",
            cheque_id, file_type, str(e))
        return prepare_response(message="Failed to fetch file", status=status.HTTP_502_BAD_GATEWAY)


@is_request_authenticated
@csrf_exempt
def cheque_receipt_pdf_view(request):
    """GET /api/lease/cheque-receipt-pdf?lease_id=X — render one PDF with one
    page per cheque/transaction entry, for handover to the tenant.
    Optional receipt_type=RENTAL|OTHER_CHARGES|COMBINED narrows which
    cheques are included (default: all, matching the Collect Cheque
    page's plain "Download Receipt" button); months=YYYY-MM,YYYY-MM
    further narrows RENTAL to the selected months."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    if not lease_id:
        logger.warning(
            "CHEQUE_RECEIPT_PDF_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
            request.user.id)
        return prepare_response(message=constants.LEASE_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

    user_profile = request.user
    pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
    if not pmc_ids and not owner_profile:
        logger.warning(
            "CHEQUE_RECEIPT_PDF_FAILED | user_id=%d | reason=UNAUTHORIZED_ROLE", request.user.id)
        return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)

    lease_qs = Lease.objects.select_related(
        "tenant__user", "unit__property_block_tower__property", "unit__parent_property",
    )
    if pmc_ids:
        lease = lease_qs.filter(
            Q(unit__parent_property__pmc_id__in=pmc_ids) |
            Q(unit__property_block_tower__property__pmc_id__in=pmc_ids),
            id=lease_id,
        ).first()
    else:
        lease = lease_qs.filter(unit__unit_owners__owner=owner_profile, id=lease_id).first()

    if not lease:
        logger.warning(
            "CHEQUE_RECEIPT_PDF_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
            request.user.id, lease_id)
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else (unit.parent_property if unit else None)

    receipt_type = (request.GET.get("receipt_type") or "").strip().upper()
    months = [m for m in (request.GET.get("months") or "").split(",") if m]

    cheques = lease.lease_cheques.select_related(
        "charge", "origin_bank", "selltlement_bank",
    ).filter(is_active=True)

    if receipt_type == "RENTAL":
        if not months:
            return prepare_response(message="Select at least one month.", status=status.HTTP_400_BAD_REQUEST)
        cheques = cheques.filter(cheque_type=constants.RENT_CHEQUE)
        cheques = [ch for ch in cheques if ch.cheque_date and ch.cheque_date.strftime("%Y-%m") in months]
    elif receipt_type == "OTHER_CHARGES":
        cheques = cheques.filter(cheque_type=constants.OTHER_CHARGE)
    # COMBINED and the default (no receipt_type -- Collect Cheque's plain
    # "Download Receipt" button) include every cheque type, unfiltered.

    if not isinstance(cheques, list):
        cheques = list(cheques.order_by("cheque_date", "created"))
    else:
        # cheque_date/created are both tz-aware -- avoid mixing in a naive
        # fallback (e.g. datetime.min), which would raise on comparison.
        cheques.sort(key=lambda ch: (ch.cheque_date is None, ch.cheque_date or ch.created, ch.created))

    entries = [
        {
            "code":            ch.code or "—",
            "description":     _lease_cheque_description(ch),
            "payment_type":    ch.payment_type or "—",
            "cheque_number":   ch.cheque_number or "",
            "cheque_date":     str(ch.cheque_date)[:10] if ch.cheque_date else "—",
            "drawn_bank":      ch.origin_bank.name if ch.origin_bank else "",
            "settlement_bank": ch.selltlement_bank.name if ch.selltlement_bank else "",
            "amount":          f"{float(ch.amount or 0):,.2f}",
            "tax_code":        ch.charge.tax_code if ch.charge else constants.UAE_VAT_RATE * 100,
            "vat":             f"{float(ch.vat or 0):,.2f}",
            "total":           f"{float(ch.total or 0):,.2f}",
            "status":          ch.status or "—",
            "status_style":    _receipt_status_style(ch.status),
        }
        for ch in cheques
    ]

    if not entries:
        logger.warning(
            "CHEQUE_RECEIPT_PDF_FAILED | user_id=%s | lease_id=%s | receipt_type=%s | reason=NO_CHEQUES",
            request.user.id, lease_id, receipt_type)
        return prepare_response(message="No cheques found for this selection", status=status.HTTP_400_BAD_REQUEST)

    html_content = render_to_string("pdf_templates/cheque_receipt.html", {
        "today": datetime.now().strftime("%d %b %Y"),
        "tenant": {
            "name":    f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "—",
            "code":    t.code if t else "",
            "email":   t.user.email if t and t.user else "",
            "contact": t.contact_number if t else "",
        },
        "property_info": {
            "property_name": prop.property_name if prop else "—",
            "block_name":    pb.block_name if pb else "",
            "unit_name":     unit.unit_name if unit else "",
            "start_date":    str(lease.start_date)[:10] if lease.start_date else "—",
            "end_date":      str(lease.end_date)[:10] if lease.end_date else "—",
            "lease_code":    lease.code or "—",
        },
        "entries": entries,
    })

    try:
        pdf_bytes = WeasyprintHTML(string=html_content).write_pdf()
    except Exception as e:
        logger.exception(
            "CHEQUE_RECEIPT_PDF_FAILED | user_id=%s | lease_id=%s | error=%s",
            request.user.id, lease_id, str(e))
        return prepare_response(message=f"PDF generation failed: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    timestamp    = datetime.now().strftime("%Y%m%d%H%M%S")
    prefix       = {"RENTAL": "rent_receipt", "OTHER_CHARGES": "other_charges_receipt", "COMBINED": "combined_receipt"}.get(receipt_type, "cheque_receipt")
    pdf_filename = f"{prefix}_{lease.code}_{timestamp}.pdf"
    pdf_s3_url   = upload_file_to_s3_base64(pdf_bytes, f"cheque_receipts/{pdf_filename}")
    if not pdf_s3_url:
        logger.error(
            "CHEQUE_RECEIPT_PDF_UPLOAD_FAILED | user_id=%s | lease_id=%s",
            request.user.id, lease_id)
        return prepare_response(message="Failed to upload receipt PDF", status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    download_url = fetch_s3_presigned_url_for_download(pdf_s3_url, file_name=pdf_filename)
    logger.info(
        "CHEQUE_RECEIPT_PDF_GENERATED | user_id=%s | lease_id=%s | file_name=%s",
        request.user.id, lease_id, pdf_filename)
    return prepare_response(
        content={"pdf_url": download_url, "file_name": pdf_filename},
        status=status.HTTP_200_OK,
    )


def _scope_transactions_to_user(qs, user, pmc_id=None):
    """Filter LeaseTransaction queryset to the logged-in user's company or
    owner scope. `pmc_id`, when given, narrows further (navbar PMC
    selector) -- for a PM it must be one of their already-authorized
    pmc_ids (raises otherwise), for an Owner it just filters their units
    down to that PMC."""
    from user_service.models import PropertyManager, Owner
    pm = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
    owner = Owner.objects.filter(pk=user.pk).first()
    if pm:
        pmc_ids = _get_pmc_ids_for_user(user)
        if pmc_id:
            if int(pmc_id) not in pmc_ids:
                raise PermissionError("You are not allowed to access this PMC")
            pmc_ids = [int(pmc_id)]
        return qs.filter(
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids) |
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids)
        )
    elif owner:
        qs = qs.filter(lease__unit__unit_owners__owner=owner)
        if pmc_id:
            qs = qs.filter(
                Q(lease__unit__property_block_tower__property__pmc_id=pmc_id) |
                Q(lease__unit__parent_property__pmc_id=pmc_id)
            )
        return qs
    return qs.none()


@cheque_summary_get
@api_view(['GET'])
@is_request_authenticated
@csrf_exempt
def cheque_summary_view(request):
    """GET summary counts and totals grouped by cheque status."""
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    from django.db.models import Count, Sum

    pmc_id = request.GET.get("pmc_id", "").strip()
    try:
        qs = _scope_transactions_to_user(LeaseTransaction.objects.all(), request.user, pmc_id=pmc_id)
    except PermissionError as e:
        return prepare_response(message=str(e), status=status.HTTP_403_FORBIDDEN)

    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()
    year        = request.GET.get("year", "").strip()

    if property_id:
        qs = qs.filter(
            Q(lease__unit__parent_property_id=property_id) |
            Q(lease__unit__property_block_tower__property_id=property_id)
        )
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
    logger.info(
            "CHEQUE_SUMMARY_SUCCESS | user_id=%s | total_count=%s | total_amount=%s",
            request.user.id, total_count, total_amount )
    return prepare_response(content=summary, status=status.HTTP_200_OK)


@all_cheques_get
@api_view(['GET'])
@is_request_authenticated
@csrf_exempt
def all_cheques_view(request):
    """GET all cheques (company scoped) with pagination and search."""

    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD,status=status.HTTP_405_METHOD_NOT_ALLOWED)
    logger.info(
            "ALL_CHEQUES_REQUEST | user_id=%s | page=%s | page_size=%s",
            request.user.id, request.GET.get("page", 1), request.GET.get("page_size", 10))
    user_profile = request.user

    # ── Get logged-in user's company ─────────────────────
    pm_profile = PropertyManager.objects.filter(
        pk=user_profile.pk
    ).select_related("company").first()

    # company = pm_profile.company if pm_profile else None
    # if not company:
    #     company = PropertyManagmentCompany.objects.filter(
    #         created_by=user_profile.user, is_active=True
    #     ).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile)
    if not pmc_ids:
        logger.warning(
                "ALL_CHEQUES_COMPANY_NOT_FOUND | user_id=%s", request.user.id )
        return prepare_response(
            message=constants.COMPANY_NOT_FOUND,
            status=status.HTTP_404_NOT_FOUND
        )

    pmc_id = request.GET.get("pmc_id", "").strip()
    if pmc_id:
        if int(pmc_id) not in pmc_ids:
            return prepare_response(message="You are not allowed to access this PMC", status=status.HTTP_403_FORBIDDEN)
        pmc_ids = [int(pmc_id)]

    page        = int(request.GET.get("page", 1))
    page_size   = int(request.GET.get("page_size", 10))
    search      = request.GET.get("search", "").strip()
    cheque_status_filter = request.GET.get("status", "").strip()
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
    unit_id     = request.GET.get("unit_id", "").strip()
    year        = request.GET.get("year", "").strip()
    from django.db.models import Q
    qs = LeaseTransaction.objects.select_related(
        "lease__unit__parent_property",
        "lease__unit__property_block_tower__property",
        "lease__tenant__user",
        "selltlement_bank",
    ).filter(    
        Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
        Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
    ).order_by("-id")

    if cheque_status_filter:
        qs = qs.filter(status=cheque_status_filter)
    if property_id:
        qs = qs.filter(
                Q(lease__unit__parent_property_id=property_id) |
                Q(lease__unit__property_block_tower__property_id=property_id)
            )
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
            Q(lease__unit__parent_property__property_name__icontains=search) | Q(lease__unit__property_block_tower__property__property_name__icontains=search)
        )
        logger.info(
            "ALL_CHEQUES_SEARCH | user_id=%s | search=%s | records=%s",
            request.user.id, search, qs.count() )

    from django.core.paginator import Paginator
    paginator = Paginator(qs, page_size)
    page_obj  = paginator.get_page(page)

    rows = [serialize_cheque_list_row(c) for c in page_obj]

    logger.info(
            "ALL_CHEQUES_SUCCESS | user_id=%s | records_returned=%s",
            request.user.id, len(rows))
    return prepare_response(
        content=rows,
        pagination={
            "total_records": paginator.count,
            "total_pages": paginator.num_pages,
            "current_page": page,
            "page_size": page_size,
        },
        status=status.HTTP_200_OK,
    )

@cheque_monthly_get
@api_view(['GET'])
@is_request_authenticated
@csrf_exempt
def cheque_monthly_view(request):

    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    from django.db.models import Sum
    from django.db.models.functions import ExtractMonth
    from datetime import datetime

    user_profile = request.user

    # ── Role detection: PMC → Owner ───────────────────────
    pm_profile = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()

    year = request.GET.get("year", "").strip() or str(datetime.now().year)
    property_id = request.GET.get("property_id", "").strip()
    block_id = request.GET.get("block_id", "").strip()
    unit_id = request.GET.get("unit_id", "").strip()
    pmc_id = request.GET.get("pmc_id", "").strip()

    if pm_profile and pm_profile.company:
        pmc_ids = _get_pmc_ids_for_user(user_profile)
        if pmc_id:
            if int(pmc_id) not in pmc_ids:
                return prepare_response(message="You are not allowed to access this PMC", status=status.HTTP_403_FORBIDDEN)
            pmc_ids = [int(pmc_id)]
        qs = LeaseTransaction.objects.filter(
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids) |
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids),
            cheque_date__year=year
        )

    elif owner_profile:
        qs = LeaseTransaction.objects.filter(
            lease__unit__unit_owners__owner=owner_profile,
            cheque_date__year=year
        ).distinct()
        if pmc_id:
            qs = qs.filter(
                Q(lease__unit__property_block_tower__property__pmc_id=pmc_id) |
                Q(lease__unit__parent_property__pmc_id=pmc_id)
            )
    else:
        logger.warning(
                    "CHEQUE_MONTHLY_FAILED | user_id=%s | reason=UNAUTHORIZED", request.user.id )
        return prepare_response(
            message=constants.UNAUTHORIZED_ROLE,
            status=status.HTTP_403_FORBIDDEN
        )

    if property_id:
        qs = qs.filter(
            Q(lease__unit__parent_property_id=property_id) |
            Q(lease__unit__property_block_tower__property_id=property_id)
        )
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

    data = [{"month": month_names[m - 1], "amount": result[m]}for m in range(1, 13)]
    logger.info(
        "CHEQUE_MONTHLY_SUCCESS | user_id=%s | year=%s",
        request.user.id, year )
    return prepare_response(content=data, status=status.HTTP_200_OK)

@rent_analytics_get
@api_view(['GET'])
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
    pmc_id      = request.GET.get("pmc_id", "").strip()

    user_profile = request.user
    pm_profile = PropertyManager.objects.select_related("company").filter(pk=user_profile.pk).first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []

    if pm_profile and pm_profile.company:
        if pmc_id:
            if int(pmc_id) not in pmc_ids:
                return prepare_response(message="You are not allowed to access this PMC", status=status.HTTP_403_FORBIDDEN)
            pmc_ids = [int(pmc_id)]
        qs = LeaseTransaction.objects.filter(
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids) |
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids),
            cheque_date__year=year
        )

    elif owner_profile:
        qs = LeaseTransaction.objects.filter(
            cheque_date__year=year,
            lease__unit__unit_owners__owner=owner_profile
        ).distinct()
        if pmc_id:
            qs = qs.filter(
                Q(lease__unit__property_block_tower__property__pmc_id=pmc_id) |
                Q(lease__unit__parent_property__pmc_id=pmc_id)
            )

    else:
        return prepare_response(message=constants.UNAUTHORIZED_ROLE,status=status.HTTP_403_FORBIDDEN)
    if lease_id:
        qs = qs.filter(lease_id=lease_id)
    if property_id:
        qs = qs.filter(
            Q(lease__unit__property_block_tower__property_id=property_id) |
            Q(lease__unit__parent_property_id=property_id)
        )
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
    logger.info(
        "RENT_ANALYTICS_FETCH_SUCCESS | user_id=%s | year=%s | total_amount=%s",
        request.user.id, year, total_amount )
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

    from django.db.models import Sum, Q, Value, FloatField
    from django.db.models.functions import Coalesce
    from property.models import Property, PropertyBlocks

    year        = request.GET.get("year", "").strip() or str(datetime.now().year)
    property_id = request.GET.get("property_id", "").strip()
    block_id    = request.GET.get("block_id", "").strip()
 
    user_profile = request.user
    pm_profile = PropertyManager.objects.select_related("company").filter(pk=user_profile.pk).first()
    owner_profile = Owner.objects.filter(pk=user_profile.pk).first()
    pmc_ids = _get_pmc_ids_for_user(user_profile) if pm_profile else []
 
    if block_id:
        # All units in this block, each annotated with their total revenue
        # Unit -> Lease (related_name="leases") -> LeaseTransaction (related_name="lease_cheques")
        # units_qs = Unit.objects.filter(property_block_tower_id=block_id)
        units_qs = Unit.objects.filter(property_block_tower_id=block_id)
        if pm_profile:
            units_qs = units_qs.filter(
                property_block_tower__property__pmc_id__in=pmc_ids,
            )
        if owner_profile:
            units_qs = units_qs.filter(
                unit_owners__owner=owner_profile
            ).distinct()
        units = (
            units_qs
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "leases__lease_cheques__amount",
                        filter=Q(leases__lease_cheques__cheque_date__year=year),
                    ),
                    Value(0, output_field=FloatField())
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
        # blocks_qs = PropertyBlocks.objects.filter(property_id=property_id)
        blocks_qs = PropertyBlocks.objects.filter(property_id=property_id)
        if pm_profile:
            blocks_qs = blocks_qs.filter(property__pmc_id__in=pmc_ids)
        if owner_profile:
            blocks_qs = blocks_qs.filter(
                block_towers__unit_owners__owner=owner_profile
            ).distinct()
        blocks = (
            blocks_qs
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "block_towers__leases__lease_cheques__amount",
                        filter=Q(block_towers__leases__lease_cheques__cheque_date__year=year),
                    ),
                    Value(0, output_field=FloatField())
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
        direct_units = Unit.objects.filter(
            parent_property_id=property_id,
            property_block_tower__isnull=True,
        )
        if pm_profile:
            direct_units = direct_units.filter(parent_property__pmc_id__in=pmc_ids)
        chart.extend({
            "key": f"unit-{unit.id}",
            "name": unit.unit_name or unit.code or f"Unit {unit.id}",
            "revenue": float(unit.revenue or 0),
        } for unit in direct_units.annotate(revenue=Coalesce(
            Sum("leases__lease_cheques__amount", filter=Q(leases__lease_cheques__cheque_date__year=year)),
            Value(0, output_field=FloatField()),
        )))
        level = "block"

    else:
        # All properties, each annotated with their total revenue
        properties = Property.objects.filter(is_active=True)
        if pm_profile and pm_profile.company:
            properties = properties.filter(pmc_id__in=pmc_ids)
 
        elif owner_profile:
            properties = properties.filter(
                property_blocks__block_towers__unit_owners__owner=owner_profile
            ).distinct()

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )
        properties = (
            properties
            .annotate(
                revenue=Coalesce(
                    Sum(
                        "property_blocks__block_towers__leases__lease_cheques__amount",
                        filter=Q(
                            property_blocks__block_towers__leases__lease_cheques__cheque_date__year=year
                        ),
                    ),
                    Value(0, output_field=FloatField()),
                )
            )
            .order_by("property_name")
        )
        direct_revenue = {
            row["lease__unit__parent_property_id"]: float(row["total"] or 0)
            for row in LeaseTransaction.objects.filter(
                lease__unit__parent_property__isnull=False,
                lease__unit__property_block_tower__isnull=True,
                cheque_date__year=year,
            ).values("lease__unit__parent_property_id").annotate(total=Sum("amount"))
        }
        chart = [
            {
                "key":     str(p.id),
                "name":    p.property_name or f"Property {p.id}",
                "revenue": float(p.revenue or 0) + direct_revenue.get(p.id, 0),
            }
            for p in properties
        ]
        level = "property"

    total_revenue = sum(item["revenue"] for item in chart)
    logger.info(
        "PROPERTY_ANALYTICS_SUCCESS | user_id=%s | year=%s | level=%s | total_revenue=%s",
        request.user.id, year, level, total_revenue )
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
        logger.warning(
                    "PROPERTY_COMPARISON_FAILED | user_id=%s | reason=PROPERTY_ID_MISSING",request.user.id)
        return prepare_response(message="property_id is required", status=status.HTTP_400_BAD_REQUEST)

    try:
        prop = Property.objects.get(id=property_id)
    except Property.DoesNotExist:
        logger.warning(
                    "PROPERTY_COMPARISON_FAILED | user_id=%s | property_id=%s | reason=PROPERTY_NOT_FOUND", property_id, request.user.id)
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
    occupied_units = Unit.objects.filter(property_block_tower__property_id=property_id, status=constants.UNIT_ACTIVE).count()
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
    logger.info(
            "PROPERTY_COMPARISON_SUCCESS | property_id=%s | revenue=%s | rank=%s",
            property_id, revenue, rank )
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
def lease_documents(request):
    try:
        if request.method == "GET":
            lease_id = request.GET.get("lease_id")
            if not lease_id:
                logger.warning(
                    "LEASE_DOCUMENTS_FETCH_FAILED | user_id=%s | reason=LEASE_ID_MISSING", request.user.id)
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                logger.warning(
                    "LEASE_DOCUMENTS_FETCH_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                    request.user.id, lease_id )
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
            logger.info(
                    "LEASE_DOCUMENTS_FETCHED | user_id=%s | lease_id=%s | document_count=%s",
                    request.user.id, lease_id, len(final_docs))
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
                logger.warning(
                    "LEASE_DOCUMENT_UPLOAD_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                    request.user.id )
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if not isinstance(documents, list) or not documents:
                logger.warning(
                    "LEASE_DOCUMENT_UPLOAD_FAILED | user_id=%s | lease_id=%s | reason=INVALID_DOCUMENT_LIST",
                    request.user.id, lease_id )
                return prepare_response(
                    message=constants.DOCUMENTS_MUST_BE_LIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            try:
                lease_obj = Lease.objects.get(id=lease_id)
            except Lease.DoesNotExist:
                logger.warning(
                    "LEASE_DOCUMENT_UPLOAD_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND", lease_id )
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
                    logger.warning(
                        "LEASE_DOCUMENT_UPLOAD_FAILED | lease_id=%s | reason=MISSING_FILE_OR_DATA", lease_id )
                    return prepare_response(
                        message=constants.MISSING_FILE_OR_DATA,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                object_name = f"lease_documents/{lease_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                doc_type_obj, _ = DocumentType.objects.get_or_create(
                    name=doc_type, section=constants.LEASE_CHEQUE,
                    defaults={"created_by": request.user.user},
                )
                LeaseDocuments.objects.create(
                    lease=lease_obj,
                    document_type=doc_type_obj,
                    file_name=file_name,
                    file_path=file_url,
                    document_choice=doc_type,
                    created_by=request.user.user,
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type
                })

            # Phase 3 validation gate: rent-cheque total must match the
            # contract amount before Ejari document upload can proceed.
            rent_cheque_total = lease_obj.lease_cheques.filter(
                cheque_type=constants.RENT_CHEQUE
            ).aggregate(total=Sum("amount"))["total"] or 0
            if lease_obj.contract_amount and abs(rent_cheque_total - lease_obj.contract_amount) > 0.01:
                return prepare_response(
                    message=(
                        f"Cheque total ({rent_cheque_total}) does not match "
                        f"contract amount ({lease_obj.contract_amount})."
                    ),
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease_obj.lease_stage = constants.EJARI_DOCUMENT_UPLOAD
            lease_obj.save()
            lease_obj.unit.status = constants.UNIT_EJARI_PENDING
            lease_obj.unit.save(update_fields=["status"])
            logger.info(
                "LEASE_DOCUMENTS_UPLOADED | user_id=%s | lease_id=%s | files_uploaded=%s",
                request.user.id, lease_id, len(uploaded_files))
            audit_logs(
                request,
                f"Uploaded lease documents for unit '{lease_obj.unit.unit_name}'",
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
                logger.warning(
                    "LEASE_DOCUMENT_UPDATE_FAILED | reason=LEASE_ID_MISSING")
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
                logger.warning(
                    "LEASE_DOCUMENT_UPDATE_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND", lease_id )
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
                    logger.warning(
                        "LEASE_DOCUMENT_UPDATE_FAILED | lease_id=%s | reason=MISSING_FILE_OR_DATA", lease_id )
                    return prepare_response(
                        message=constants.MISSING_FILE_OR_DATA,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                mapping_obj = LeaseDocuments.objects.filter(
                    lease=lease_obj,
                    file_name=file_name
                ).first()

                if mapping_obj:
                    mapping_obj.document_choice = doc_type
                    status_text = "updated"
                else:
                    doc_type_obj, _ = DocumentType.objects.get_or_create(
                        name=doc_type, section=constants.LEASE_CHEQUE,
                        defaults={"created_by": request.user.user},
                    )
                    mapping_obj = LeaseDocuments.objects.create(
                        lease=lease_obj,
                        document_type=doc_type_obj,
                        file_name=file_name,
                        file_path="",
                        document_choice=doc_type,
                        created_by=request.user.user,
                    )
                    status_text = "created"

                object_name = f"lease_documents/{lease_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

                mapping_obj.file_path = file_url
                mapping_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": status_text
                })
            logger.info(
                "LEASE_DOCUMENTS_UPDATED | user_id=%s | lease_id=%s | files_updated=%s",
                request.user.id, lease_id, len(updated_files) )
            audit_logs(
                request,
                f"Updated lease documents for unit '{lease_obj.unit.unit_name}'",
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
        logger.exception(
                    "LEASE_DOCUMENTS_ERROR | user_id=%s | error=%s",
                    request.user.id if request.user else None, str(e) )
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@csrf_exempt
@is_request_authenticated
def manager_approval_view(request):
    """POST: Create a manager approval entry linked to the lease and update lease stage."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = json.loads(request.body)
    lease_id = data.get("lease_id")
    if not lease_id:
        logger.warning(
            "MANAGER_APPROVAL_CREATE_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
            request.user.id )
        return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

    lease = Lease.objects.select_related("tenant", "unit").filter(id=lease_id).first()
    if not lease:
        logger.warning(
            "MANAGER_APPROVAL_CREATE_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
            request.user.id, lease_id )
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

    requested_rent = data.get("requested_rent") or (float(lease.annual_amount) if lease.annual_amount else 0)
    requested_tenure = data.get("requested_tenure") or ""

    existing = Approval.objects.filter(
        tenant=lease.tenant, unit=lease.unit, approved=False
    ).first()
    if existing:
        lease.lease_stage = constants.MANAGER_APPROVAL_REQUIRED
        lease.save(update_fields=["lease_stage"])
        logger.info(
            "MANAGER_APPROVAL_ALREADY_PENDING | user_id=%s | lease_id=%s | approval_id=%s",
            request.user.id, lease_id, existing.id )
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
    logger.info(
        "MANAGER_APPROVAL_CREATED | user_id=%s | lease_id=%s | approval_id=%s",
        request.user.id, lease_id, approval.id )
    return prepare_response(
        message="Manager approval request created",
        content={"approval_id": approval.id},
        status=status.HTTP_201_CREATED,
    )


# ── Step 11: Verify cheque documents ──────────────────────────────────────────

@is_request_authenticated
def verify_cheque_view(request):
    """POST: PM confirms cheque documents are valid → CHEQUE_VERIFIED."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        if not lease_id:
            logger.warning(
                "CHEQUE_VERIFICATION_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                request.user.id )
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "CHEQUE_VERIFICATION_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id )
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        if lease.lease_stage != constants.CHEQUE_COLLECTED:
            logger.warning(
                "CHEQUE_VERIFICATION_FAILED | lease_id=%s | current_stage=%s",
                lease_id, lease.lease_stage )
            return prepare_response(
                message=f"Cannot verify cheque: lease is in '{lease.lease_stage}' stage, expected CHEQUE_COLLECTED.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lease.lease_stage = constants.CHEQUE_VERIFIED
        lease.save(update_fields=["lease_stage"])
        logger.info(
            "CHEQUE_VERIFIED | user_id=%s | lease_id=%s",
            request.user.id, lease_id )
        audit_logs(request, f"Cheque documents verified for lease '{lease.code}'", constants.UPDATED)

        return prepare_response(
            message="Cheque documents verified. Lease can now proceed to Agreement.",
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.exception(
            "CHEQUE_VERIFICATION_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Step 13b: Approve Ejari submission ────────────────────────────────────────
# Dubai Leasing Management Flow, Phase 2: today submit_ejari_signature jumped
# straight from EJARI_DOCUMENT_UPLOAD to full ACTIVATED with no approval gate
# -- this is the missing EJARI_PENDING -> EJARI_APPROVED step the diagram
# requires. Mirrors verify_cheque_view's guard-then-flip shape exactly.

@is_request_authenticated
def approve_ejari_submission(request):
    """POST: PM confirms the (simulated) Ejari submission is approved → EJARI_APPROVED."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        if not lease_id:
            logger.warning(
                "EJARI_APPROVAL_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                request.user.id )
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related("unit").filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "EJARI_APPROVAL_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id )
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        if lease.lease_stage != constants.EJARI_DOCUMENT_UPLOAD:
            logger.warning(
                "EJARI_APPROVAL_FAILED | lease_id=%s | current_stage=%s",
                lease_id, lease.lease_stage )
            return prepare_response(
                message=f"Cannot approve Ejari submission: lease is in '{lease.lease_stage}' stage, expected EJARI_DOCUMENT_UPLOAD.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lease.lease_stage = constants.EJARI_APPROVED
        lease.save(update_fields=["lease_stage"])
        if lease.unit:
            lease.unit.status = constants.UNIT_EJARI_APPROVED
            lease.unit.save(update_fields=["status"])
        logger.info(
            "EJARI_APPROVED | user_id=%s | lease_id=%s",
            request.user.id, lease_id )
        audit_logs(request, f"Ejari submission approved for lease '{lease.code}'", constants.UPDATED)

        return prepare_response(
            message="Ejari submission approved. Lease can now proceed to signature.",
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.exception(
            "EJARI_APPROVAL_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Step 14: Send Ejari for signature ─────────────────────────────────────────

@is_request_authenticated
def send_ejari_for_signature(request):
    """POST: PM triggers Ejari signature request → EJARI_SIGNING. Emails
    both the tenant and the owner their own signing link -- activation
    requires both to sign (see esign_callback_view)."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        if not lease_id:
            logger.warning(
                "EJARI_SIGNATURE_REQUEST_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                request.user.id )
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related(
            "tenant__user", "unit__property_block_tower__property"
        ).filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "EJARI_SIGNATURE_REQUEST_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND",
                lease_id )
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        if lease.lease_stage not in (constants.EJARI_DOCUMENT_UPLOAD, constants.EJARI_APPROVED, constants.EJARI):
            logger.warning(
                "EJARI_SIGNATURE_REQUEST_FAILED | lease_id=%s | current_stage=%s | reason=INVALID_STAGE",
                lease_id, lease.lease_stage )
            if lease.lease_stage == constants.EJARI_SIGNING:
                message = "Ejari has already been sent for signature. Waiting for signatures."
            elif lease.lease_stage == constants.EJARI_SIGNED:
                message = "Ejari has already been signed."
            else:
                message = "Cannot send Ejari for signature at this stage. Please refresh and try again."
            return prepare_response(message=message, status=status.HTTP_400_BAD_REQUEST)

        tenant_email = lease.tenant.user.email if lease.tenant and lease.tenant.user else None
        if not tenant_email:
            logger.warning(
                        "EJARI_SIGNATURE_REQUEST_FAILED | lease_id=%s | reason=TENANT_EMAIL_MISSING",
                        lease_id )
            return prepare_response(message="Tenant email not found", status=status.HTTP_400_BAD_REQUEST)

        owner_link = lease.unit.unit_owners.select_related("owner").first() if lease.unit else None
        owner = owner_link.owner if owner_link else None
        owner_email = owner.email if owner else None
        if not owner_email:
            logger.warning(
                        "EJARI_SIGNATURE_REQUEST_FAILED | lease_id=%s | reason=OWNER_EMAIL_MISSING",
                        lease_id )
            return prepare_response(message="Owner email not found for this unit.", status=status.HTTP_400_BAD_REQUEST)

        if lease.unit:
            lease.unit.status = constants.UNIT_ESIGN_PENDING
            lease.unit.save(update_fields=["status"])

        from utilities.config import FRONTEND_URL
        prop = lease.unit.property_block_tower.property if lease.unit and lease.unit.property_block_tower else None

        for role, recipient_email, recipient_name in (
            (LeaseSignature.ROLE_TENANT, tenant_email, f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}".strip()),
            (LeaseSignature.ROLE_OWNER, owner_email, f"{owner.user.first_name} {owner.user.last_name}".strip() if owner.user else owner_email),
        ):
            LeaseSignature.objects.update_or_create(
                lease=lease, role=role,
                defaults={"signer_email": recipient_email, "created_by": request.user.user},
            )
            sign_url = f"{FRONTEND_URL}/ejari-sign?lease_id={lease.id}&role={role.lower()}&email={recipient_email}"
            ctx = {
                "tenant_name":   recipient_name,
                "lease_code":    lease.code,
                "property_name": prop.property_name if prop else "",
                "unit_name":     lease.unit.unit_name if lease.unit else "",
                "sign_url":      sign_url,
            }
            subject   = f"Ejari Signature Required – {lease.code}"
            body_text = f"Please sign the Ejari document for lease {lease.code}: {sign_url}"
            body_html = render_to_string("email_templates/ejari_signature_required.html", ctx)
            send_ses_email(recipient_email, subject, body_text, body_html)

        lease.lease_stage = constants.EJARI_SIGNING
        lease.save(update_fields=["lease_stage"])
        logger.info(
                "EJARI_SENT_FOR_SIGNATURE | user_id=%s | lease_id=%s ",
                request.user.id, lease_id )
        audit_logs(request, f"Ejari sent for signature (tenant + owner) for lease '{lease.code}'", constants.UPDATED)

        return prepare_response(message="Ejari sent for signature successfully.", status=status.HTTP_200_OK)
    except Exception as e:
        logger.exception(
            "EJARI_SIGNATURE_REQUEST_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def ejari_signature_otp(request):
    """POST: Send OTP to tenant for Ejari signing. No auth required."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from user_service.utils import request_otp_sent
        from django.core.cache import cache

        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        email    = (body.get("email") or "").strip().lower()
        if not lease_id or not email:
            logger.warning(
                "EJARI_OTP_SEND_FAILED | reason=MISSING_REQUIRED_FIELDS" )
            return prepare_response(message="lease_id and email are required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related("tenant__user").get(id=lease_id)

        expected = lease.tenant.user.email.strip().lower() if lease.tenant and lease.tenant.user else None
        if not expected or expected != email:
            logger.warning(
                        "EJARI_OTP_SEND_FAILED | lease_id=%s | email=%s | reason=EMAIL_MISMATCH",
                        lease_id, email )
            return prepare_response(message="Email does not match the tenant for this lease.", status=status.HTTP_403_FORBIDDEN)

        otp       = request_otp_sent()
        cache_key = f"otp_ejari_signature_{lease_id}_{email}"
        cache.set(cache_key, otp, timeout=600)

        subject   = f"Ejari Signing OTP – {lease.code}"
        body_text = f"Your OTP for Ejari signing ({lease.code}) is: {otp}. Expires in 10 minutes."
        body_html = render_to_string("email_templates/lease_approval_otp.html", {
            "otp": otp, "lease_code": lease.code,
            "recipient_name": email, "role_label": "Tenant", "role_label_ar": "المستأجر",
        })
        send_ses_email(email, subject, body_text, body_html)
        logger.info(
            "EJARI_OTP_SENT | lease_id=%s ",
            lease_id )
        return prepare_response(message="OTP sent successfully", status=status.HTTP_200_OK)
    except Lease.DoesNotExist:
        logger.warning(
            "EJARI_OTP_SEND_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND",
            lease_id )
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(
            "EJARI_OTP_SEND_ERROR | lease_id=%s | error=%s",
            lease_id if 'lease_id' in locals() else None, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def ejari_signature_verify_otp(request):
    """POST: Verify OTP for Ejari signing. No auth required."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from django.core.cache import cache

        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        email    = (body.get("email") or "").strip().lower()
        otp      = body.get("otp")
        if not lease_id or not email or not otp:
            logger.warning(
                "EJARI_OTP_VERIFY_FAILED | reason=MISSING_REQUIRED_FIELDS" )
            return prepare_response(message="lease_id, email and otp are required", status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"otp_ejari_signature_{lease_id}_{email}"
        stored    = cache.get(cache_key)
        if not stored or str(stored) != str(otp):
            logger.warning(
                "EJARI_OTP_VERIFY_FAILED | lease_id=%s | reason=INVALID_OTP",
                lease_id)
            return prepare_response(message="Invalid or expired OTP", status=status.HTTP_400_BAD_REQUEST)

        verified_key = f"otp_ejari_signature_verified_{lease_id}_{email}"
        cache.set(verified_key, True, timeout=600)

        lease = Lease.objects.select_related(
            "tenant__user", "unit__property_block_tower__property"
        ).get(id=lease_id)
        unit = lease.unit
        prop = unit.property_block_tower.property if unit and unit.property_block_tower else None

        ejari_docs = lease.lease_documents.filter(
            document_choice=constants.EJARI_CERTIFICATE
        ).order_by("-id")
        first_ejari_doc = ejari_docs.first()
        ejari_url = (
            fetch_s3_presigned_url(first_ejari_doc.file_path, file_name=first_ejari_doc.file_name)
            if first_ejari_doc else ""
        )
        logger.info(
            "EJARI_OTP_VERIFIED | lease_id=%s ",
            lease_id )
        return prepare_response(
            message="OTP verified",
            content={
                "ejari_url":     ejari_url,
                "lease_code":    lease.code,
                "tenant_name":   f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}".strip() if lease.tenant and lease.tenant.user else "",
                "property_name": prop.property_name if prop else "",
                "unit_name":     unit.unit_name if unit else "",
            },
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        logger.warning(
                "EJARI_OTP_VERIFY_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND",
                lease_id if 'lease_id' in locals() else None )
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(
            "EJARI_OTP_VERIFY_ERROR | lease_id=%s | error=%s",
            lease_id if 'lease_id' in locals() else None, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
def submit_ejari_signature(request):
    """POST: Tenant submits Ejari signature → lease ACTIVATED. No auth required."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        from django.core.cache import cache

        body           = json.loads(request.body)
        lease_id       = body.get("lease_id")
        email          = (body.get("email") or "").strip().lower()
        signature_data = body.get("signature_data", "")

        if not lease_id or not email or not signature_data:
            logger.warning(
                "EJARI_SIGNATURE_SUBMIT_FAILED | reason=MISSING_REQUIRED_FIELDS" )
            return prepare_response(message="lease_id, email and signature_data are required", status=status.HTTP_400_BAD_REQUEST)

        verified_key = f"otp_ejari_signature_verified_{lease_id}_{email}"
        if not cache.get(verified_key):
            logger.warning(
                        "EJARI_SIGNATURE_SUBMIT_FAILED | lease_id=%s | reason=OTP_NOT_VERIFIED",
                        lease_id)
            return prepare_response(message="OTP not verified. Please verify OTP first.", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related("unit").get(id=lease_id)

        # Phase 5 gate: handover must be confirmed before final activation.
        if not lease.handover_completed_at:
            logger.warning(
                "EJARI_SIGNATURE_SUBMIT_FAILED | lease_id=%s | reason=HANDOVER_NOT_CONFIRMED",
                lease_id)
            return prepare_response(
                message="Handover must be confirmed before activation.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Store signature record directly on LeaseDocuments (it inherits
        # Documents' file_name/file_path fields -- no separate Documents row).
        sig_obj_name = f"lease_documents/{lease_id}/ejari_signature_{email}.png"
        sig_url = upload_file_to_s3_base64(signature_data, sig_obj_name)
        # Base.created_by is a required, non-nullable FK -- no request.user
        # exists here (tenant-facing, no-auth endpoint), so this falls back
        # to the lease's own creator when the tenant relation is missing.
        signer = lease.tenant.user if lease.tenant and lease.tenant.user else lease.created_by
        sig_doc_type, _ = DocumentType.objects.get_or_create(
            name=constants.EJARI_SIGNATURE, section=constants.LEASE_CHEQUE,
            defaults={"created_by": signer},
        )
        LeaseDocuments.objects.create(
            lease=lease,
            document_type=sig_doc_type,
            file_name=f"ejari_signature_{email}.png",
            file_path=sig_url,
            document_choice=constants.EJARI_SIGNATURE,
            created_by=signer,
        )

        cache.delete(verified_key)

        # Activate the lease
        lease.lease_stage  = constants.ACTIVATED
        lease.lease_status = "ACTIVE"
        lease.save(update_fields=["lease_stage", "lease_status"])
        if lease.unit:
            lease.unit.status = constants.UNIT_ACTIVE
            lease.unit.save(update_fields=["status"])
        logger.info(
            "EJARI_SIGNATURE_SUBMITTED | lease_id=%s | lease_status=%s",
            lease.id, lease.lease_status )
        return prepare_response(
            message="Ejari signed successfully. Lease is now active.",
            content={"lease_id": lease.id, "lease_stage": lease.lease_stage},
            status=status.HTTP_200_OK,
        )
    except Lease.DoesNotExist:
        logger.warning(
            "EJARI_SIGNATURE_SUBMIT_FAILED | lease_id=%s | reason=LEASE_NOT_FOUND", lease_id )
        return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(
            "EJARI_SIGNATURE_SUBMIT_ERROR | lease_id=%s | error=%s",
            lease_id if 'lease_id' in locals() else None, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── E-signature (tenant-facing, no auth) ──────────────────────────────────────
# Provider-pluggable -- see lease/esign/. Applies a real digital signature
# to a generated Ejari document. This does NOT activate the lease (that
# still goes through the existing handover/activation gate, same as
# submit_ejari_signature) -- it just records that the signature step is
# done, advancing lease_stage to EJARI_SIGNED.

def _build_ejari_pdf_bytes(lease):
    """Render a one-page Ejari contract summary to sign -- there's no real
    Ejari certificate generation elsewhere in the app yet, so this stands
    in for the actual document that would be submitted for signature."""
    t    = lease.tenant
    unit = lease.unit
    pb   = unit.property_block_tower if unit else None
    prop = pb.property if pb else (unit.parent_property if unit else None)

    html_content = render_to_string("pdf_templates/ejari_document.html", {
        "today": datetime.now().strftime("%d %b %Y"),
        "tenant": {
            "name":    f"{t.user.first_name} {t.user.last_name}".strip() if t and t.user else "—",
            "code":    t.code if t else "",
            "email":   t.user.email if t and t.user else "",
            "contact": t.contact_number if t else "",
        },
        "property_info": {
            "property_name": prop.property_name if prop else "—",
            "block_name":    pb.block_name if pb else "",
            "unit_name":     unit.unit_name if unit else "",
            "start_date":    str(lease.start_date)[:10] if lease.start_date else "—",
            "end_date":      str(lease.end_date)[:10] if lease.end_date else "—",
            "lease_code":    lease.code or "—",
            "rent":          f"{float(lease.rent or 0):,.2f}",
        },
    })
    return WeasyprintHTML(string=html_content).write_pdf()


def _expected_signer_email(lease, role):
    """The email that must match for `role` to start/complete a signature
    on `lease` -- tenant's own email, or the unit's first registered
    owner's email."""
    if role == LeaseSignature.ROLE_TENANT:
        return lease.tenant.user.email.strip().lower() if lease.tenant and lease.tenant.user else None
    if role == LeaseSignature.ROLE_OWNER:
        owner_link = lease.unit.unit_owners.select_related("owner").first() if lease.unit else None
        return owner_link.owner.email.strip().lower() if owner_link and owner_link.owner and owner_link.owner.email else None
    return None


@csrf_exempt
def esign_start_view(request):
    """GET: starts a signature process with the configured provider and
    returns the URL to redirect the signer's browser to. No auth required
    -- the signer (tenant or owner) reaches this from their emailed
    sign_url link, identified by lease_id + role + their own email."""
    from lease.esign import get_signature_provider
    from lease.esign.state import sign_state
    from utilities import config as esign_config

    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    lease_id = request.GET.get("lease_id")
    email    = (request.GET.get("email") or "").strip().lower()
    role     = (request.GET.get("role") or "").strip().upper()
    if not lease_id or not email or role not in (LeaseSignature.ROLE_TENANT, LeaseSignature.ROLE_OWNER):
        return prepare_response(message="lease_id, email and a valid role (tenant/owner) are required", status=status.HTTP_400_BAD_REQUEST)

    lease = Lease.objects.select_related(
        "tenant__user", "unit__property_block_tower__property", "unit__parent_property",
    ).filter(id=lease_id, is_active=True).first()
    if not lease:
        return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

    expected = _expected_signer_email(lease, role)
    if not expected or expected != email:
        logger.warning(
            "ESIGN_START_FAILED | lease_id=%s | role=%s | email=%s | reason=EMAIL_MISMATCH",
            lease_id, role, email)
        return prepare_response(message="Email does not match this signer for this lease.", status=status.HTTP_403_FORBIDDEN)

    signature_request = LeaseSignature.objects.filter(lease=lease, role=role).first()
    if signature_request and signature_request.signed_at:
        return prepare_response(message="This signature has already been completed.", status=status.HTTP_400_BAD_REQUEST)

    if not esign_config.UAE_PASS_SIGN_CLIENT_ID or not esign_config.UAE_PASS_SIGN_CLIENT_SECRET:
        logger.error("ESIGN_NOT_CONFIGURED | lease_id=%s | role=%s", lease_id, role)
        return prepare_response(
            message="E-signature is not configured yet (UAE_PASS_SIGN_CLIENT_ID/SECRET missing).",
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    provider = get_signature_provider()
    ui_locale = request.GET.get("ui_locale", "en")
    callback_url = f"{esign_config.UAE_PASS_SIGN_CALLBACK_URL}?state={sign_state(lease_id, provider.name, role)}"

    try:
        pdf_bytes = _build_ejari_pdf_bytes(lease)
        process = provider.create_sign_process(
            pdf_bytes=pdf_bytes,
            filename=f"ejari_{lease.code}_{role.lower()}.pdf",
            callback_url=callback_url,
            ui_locale=ui_locale,
        )
    except Exception as e:
        logger.exception("ESIGN_START_FAILED | lease_id=%s | role=%s | provider=%s | error=%s", lease_id, role, provider.name, str(e))
        return prepare_response(message=f"Failed to start signature: {str(e)}", status=status.HTTP_502_BAD_GATEWAY)

    LeaseSignature.objects.update_or_create(
        lease=lease, role=role,
        defaults={
            "signer_email": email,
            "esign_provider": provider.name,
            "esign_process_id": process.process_id,
            "esign_document_ref": process.document_ref,
            "created_by": lease.created_by,
        },
    )

    logger.info("ESIGN_STARTED | lease_id=%s | role=%s | provider=%s | process_id=%s", lease_id, role, provider.name, process.process_id)
    return prepare_response(content={"authorize_url": process.redirect_url}, status=status.HTTP_200_OK)


@csrf_exempt
def esign_callback_view(request):
    """GET: the signature provider redirects the signer's browser back
    here once they've authenticated and approved (or canceled/failed) the
    signature. Not JWT-protected -- the provider calls this directly.
    Activation requires both the tenant's and the owner's signature to be
    complete (plus the existing handover gate) -- see
    submit_ejari_signature for the same handover check. Redirects on to
    the frontend sign page with a result indicator."""
    from django.http import HttpResponseRedirect
    from lease.esign import get_signature_provider
    from lease.esign.state import verify_state
    from utilities import config as esign_config

    redirect_base = f"{esign_config.FRONTEND_URL}/ejari-sign"

    state = request.GET.get("state")
    lease_id, provider_name, role = verify_state(state) if state else (None, None, None)
    if not lease_id or role not in (LeaseSignature.ROLE_TENANT, LeaseSignature.ROLE_OWNER):
        logger.warning("ESIGN_CALLBACK_INVALID | reason=INVALID_STATE")
        return HttpResponseRedirect(f"{redirect_base}?uaepass=failed&reason=invalid_state")

    lease = Lease.objects.filter(id=lease_id, is_active=True).first()
    signature_request = LeaseSignature.objects.filter(lease=lease, role=role).first() if lease else None
    if not lease or not signature_request or not signature_request.esign_process_id:
        logger.warning("ESIGN_CALLBACK_NOT_FOUND | lease_id=%s | role=%s", lease_id, role)
        return HttpResponseRedirect(f"{redirect_base}?lease_id={lease_id}&role={role}&uaepass=failed&reason=lease_not_found")

    provider = get_signature_provider(signature_request.esign_provider or provider_name)

    try:
        result_status = provider.get_result_status(signature_request.esign_process_id)
    except Exception as e:
        logger.exception("ESIGN_CALLBACK_STATUS_FAILED | lease_id=%s | role=%s | error=%s", lease_id, role, str(e))
        return HttpResponseRedirect(f"{redirect_base}?lease_id={lease_id}&role={role}&uaepass=failed&reason=status_check_failed")

    if result_status != "finished":
        logger.warning("ESIGN_CALLBACK_NOT_FINISHED | lease_id=%s | role=%s | status=%s", lease_id, role, result_status)
        return HttpResponseRedirect(f"{redirect_base}?lease_id={lease_id}&role={role}&uaepass=failed&reason={result_status}")

    try:
        signed_pdf = provider.fetch_signed_document(signature_request.esign_document_ref)
        signed_url = upload_file_to_s3_base64(
            signed_pdf, f"ejari_signed/{lease.id}/ejari_{lease.code}_{role.lower()}_signed.pdf",
        )
    except Exception as e:
        logger.exception("ESIGN_CALLBACK_FETCH_FAILED | lease_id=%s | role=%s | error=%s", lease_id, role, str(e))
        return HttpResponseRedirect(f"{redirect_base}?lease_id={lease_id}&role={role}&uaepass=failed&reason=fetch_signed_document_failed")

    signature_request.signed_at = datetime.now()
    signature_request.esign_signed_document_path = signed_url or ""
    signature_request.save(update_fields=["signed_at", "esign_signed_document_path"])
    provider.cleanup(signature_request.esign_process_id)

    # Activation requires BOTH tenant and owner to have signed.
    all_signed = not LeaseSignature.objects.filter(
        lease=lease, role__in=(LeaseSignature.ROLE_TENANT, LeaseSignature.ROLE_OWNER), signed_at__isnull=True,
    ).exists() and LeaseSignature.objects.filter(lease=lease).count() >= 2

    if all_signed:
        if lease.handover_completed_at:
            lease.lease_stage = constants.ACTIVATED
            lease.lease_status = "ACTIVE"
            lease.save(update_fields=["lease_stage", "lease_status"])
            if lease.unit:
                lease.unit.status = constants.UNIT_ACTIVE
                lease.unit.save(update_fields=["status"])
            logger.info("EJARI_FULLY_SIGNED_AND_ACTIVATED | lease_id=%s", lease_id)
        else:
            lease.lease_stage = constants.EJARI_SIGNED
            lease.save(update_fields=["lease_stage"])
            logger.info("EJARI_FULLY_SIGNED_AWAITING_HANDOVER | lease_id=%s", lease_id)
    else:
        logger.info("ESIGN_SIGNATURE_COMPLETE | lease_id=%s | role=%s | waiting_on_other_party=True", lease_id, role)

    return HttpResponseRedirect(f"{redirect_base}?lease_id={lease_id}&role={role}&uaepass=success")


# ── Step 15: Confirm handover (Dubai Leasing Management Flow, Phase 5) ────────
# A separate prerequisite gate, not folded into activation -- lets the
# frontend show "handover done, awaiting signature" vs. "signed, awaiting
# handover" as independently-trackable checklist states, matching the
# diagram's own separate step boxes. submit_ejari_signature and
# activate_lease_view both check handover_completed_at before activating.

@is_request_authenticated
def confirm_handover(request):
    """POST: PM confirms property handover complete -- prerequisite gate before final activation."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body = json.loads(request.body)
        lease_id = body.get("lease_id")
        handover_documents = body.get("handover_documents", [])

        if not lease_id:
            logger.warning(
                "HANDOVER_CONFIRMATION_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                request.user.id)
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "HANDOVER_CONFIRMATION_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id)
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        allowed_stages = (
            constants.EJARI_APPROVED,
            constants.EJARI_SIGNING,
            constants.ACTIVATED,
        )
        if lease.lease_stage not in allowed_stages:
            logger.warning(
                "HANDOVER_CONFIRMATION_FAILED | lease_id=%s | current_stage=%s",
                lease_id, lease.lease_stage)
            return prepare_response(
                message=f"Cannot confirm handover: lease is in '{lease.lease_stage}' stage, expected at/after EJARI_APPROVED.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        for doc in handover_documents:
            file_name = doc.get("file_name")
            base64_data = doc.get("data")
            doc_type = (doc.get("type") or constants.HANDOVER_DOCUMENT).upper()
            if not file_name or not base64_data:
                continue
            object_name = f"lease_documents/{lease_id}/handover/{file_name}"
            file_url = upload_file_to_s3_base64(base64_data, object_name)
            doc_type_obj, _ = DocumentType.objects.get_or_create(
                name=doc_type, section=constants.LEASE_CHEQUE,
                defaults={"created_by": request.user.user},
            )
            LeaseDocuments.objects.create(
                lease=lease,
                document_type=doc_type_obj,
                file_name=file_name,
                file_path=file_url,
                document_choice=doc_type,
                created_by=request.user.user,
            )

        lease.handover_completed_at = timezone.now()
        lease.save(update_fields=["handover_completed_at"])
        logger.info(
            "HANDOVER_CONFIRMED | user_id=%s | lease_id=%s",
            request.user.id, lease_id)
        audit_logs(request, f"Handover confirmed for lease '{lease.code}'", constants.UPDATED)

        return prepare_response(
            message="Handover confirmed.",
            content={"lease_id": lease.id, "handover_completed_at": lease.handover_completed_at},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.exception(
            "HANDOVER_CONFIRMATION_ERROR | user_id=%s | error=%s",
            request.user.id, str(e))
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ── Step 16: Activate lease (admin-triggered fallback) ────────────────────────
@activate_lease_post
@api_view(['POST'])
@is_request_authenticated
def activate_lease_view(request):
    """POST: Manually activate a lease (e.g. after all steps are complete)."""
    if request.method != "POST":
        return prepare_response(message="Method not allowed", status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        body     = json.loads(request.body)
        lease_id = body.get("lease_id")
        if not lease_id:
            logger.warning(
                "LEASE_ACTIVATION_FAILED | user_id=%s | reason=LEASE_ID_MISSING",
                request.user.id )
            return prepare_response(message="lease_id is required", status=status.HTTP_400_BAD_REQUEST)

        lease = Lease.objects.select_related("unit").filter(id=lease_id, is_active=True).first()
        if not lease:
            logger.warning(
                "LEASE_ACTIVATION_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                request.user.id, lease_id )
            return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)

        # Phase 5 gate: handover must be confirmed before final activation.
        if not lease.handover_completed_at:
            logger.warning(
                "LEASE_ACTIVATION_FAILED | user_id=%s | lease_id=%s | reason=HANDOVER_NOT_CONFIRMED",
                request.user.id, lease_id )
            return prepare_response(
                message="Handover must be confirmed before activation.",
                status=status.HTTP_400_BAD_REQUEST,
            )

        lease.lease_stage  = constants.ACTIVATED
        lease.lease_status = "ACTIVE"
        lease.save(update_fields=["lease_stage", "lease_status"])
        if lease.unit:
            lease.unit.status = constants.UNIT_ACTIVE
            lease.unit.save(update_fields=["status"])
        logger.info(
            "LEASE_ACTIVATED | user_id=%s | lease_id=%s",
            request.user.id, lease_id )
        audit_logs(request, f"Lease '{lease.code}' manually activated", constants.UPDATED)

        return prepare_response(
            message="Lease activated successfully.",
            content={"lease_id": lease.id, "lease_stage": constants.ACTIVATED},
            status=status.HTTP_200_OK,
        )
    except Exception as e:
        logger.exception(
            "LEASE_ACTIVATION_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

