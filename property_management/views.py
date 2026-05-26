import os
import json
import calendar
from datetime import timedelta, datetime, date
from calendar import monthrange
from dateutil.relativedelta import relativedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Prefetch, Sum, F
from django.db.models.functions import TruncMonth
from django.http import FileResponse
from django.utils import timezone
from django.utils.timezone import now
from django.utils.dateparse import parse_date

from user_service.models import Role, FAQ, Owner, Tenant, PropertyManager, DocumentType
from property.models import Unit, Property, PropertyManagmentCompany, UnitOwner
from property_management.models import Country, State, City, AuditLog
from lease.models import Lease, Template, LeaseTransaction
from lead.models import Lead
from complaint.models import Complaint
from payment.models import Bank
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import (
    prepare_response,
    safe_epoch_to_datetime,
    datetime_to_epoch_millis,
    export_to_csv,
)
from utilities import status, constants
from property_management import settings
from property_management.utils import create_and_send_invitation
from django.http import FileResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@is_request_authenticated
def serve_media(request, path):
    file_path = os.path.join(settings.MEDIA_ROOT, path)
    response = FileResponse(open(file_path, 'rb'))
    return response


@is_request_authenticated
def options(request):
    if request.method != "GET":
        return prepare_response(
            content={},
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    option_types = request.GET.get("option_type")
    if not option_types:    
        return prepare_response(
            message=constants.QUERY_PARAMETER,
            status=status.HTTP_400_BAD_REQUEST
        )
    option_types = [t.strip() for t in option_types.split(",")]   
    content = {}
    user = request.user
    is_owner = Owner.objects.filter(pk=user.pk).exists()
    pm_profile = PropertyManager.objects.filter(pk=user.pk).select_related('company').first()
    is_pm = pm_profile is not None
    for option_type in option_types:
        if option_type == "COUNTRY":
            countries = Country.objects.all()
            content["country"] = [{"key": c.id, "value": c.name} for c in countries]
        elif option_type == "STATE":
            country_id = request.GET.get("country_id")
            if not country_id:
                content["state"] = []
            else:
                states = State.objects.filter(country_id=country_id)
                content["state"] = [{"key": s.id, "value": s.name} for s in states]
        elif option_type == "CITY":
            state_id = request.GET.get("state_id")
            if not state_id:
                content["city"] = []
            else:
                cities = City.objects.filter(state_id=state_id)
                content["city"] = [{"key": c.id, "value": c.name} for c in cities]

        elif option_type == "PARENT_PROPERTY":
            properties = Property.objects.none()
            if is_owner:
                property_ids = Unit.objects.filter(owner=user).values_list('property_id', flat=True).distinct()
                properties = Property.objects.filter(id__in=property_ids)
            elif is_pm and pm_profile.company:
                properties = Property.objects.filter(pmc=pm_profile.company)
            content["property"] = [{"key": prop.id, "value": prop.property_name}for prop in properties]
        elif option_type == "PROPERTY_TYPE":
            content["property_type"] = [
                {"key": key, "value": value }
                for key, value in constants.PROPERTY_TYPE_CHOICES]

        elif option_type == "BLOCKS_COUNT":
            content["blocks_count"] = [
                {"key": key, "value": value}
                for key, value in constants.BLOCKS_CHOICES]

        elif option_type == "UNITS_COUNT":
            content["units_count"] = [
                {"key": key, "value": value}
                for key, value in constants.UNITS_CHOICES]

        elif option_type == "AREA_UNIT":
            content["area_unit"] = [
                {"key": key, "value": value}
                for key, value in constants.AREA_UNIT_CHOICES]

        elif option_type == "FLOOR_COUNT":
            content["floor_count"] = [
                {"key": key, "value": value}
                for key, value in constants.FLOOR_CHOICES]

        elif option_type == "PARKING_COUNT":
            content["parking_count"] = [
                {"key": key, "value": value}
                for key, value in constants.PARKING_CHOICES]

        elif option_type == "PROPERTY_UNIT":
            if is_owner:
                units = Unit.objects.filter(owner=user)
            elif is_pm:
                if not pm_profile.company:
                    return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                units = Unit.objects.filter(property_block_tower__property__pmc=pm_profile.company)
            else:
                company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()
                units = Unit.objects.filter(property_block_tower__property__pmc=company) if company else Unit.objects.none()
            content["property_unit"] = [{"key": u.id, "value": u.unit_name or "Unnamed Unit"} for u in units]
        


        elif option_type == "TENANTS":
            tenants = Tenant.objects.select_related('user').all()
            content["tenants"] = [{"key": t.id, "value": t.user.get_full_name() or t.user.email} for t in tenants]
        
        elif option_type == "PREDEFINED_TEMPLATES":
            templates = Template.objects.filter( is_predefined=True,is_active=True)
            content["predefined_templates"] = [{"key": t.id,"value": t.name,"description": t.description}for t in templates]
        
        elif option_type == "TENANCY_STATUS":
            content["tenancy_status"] = [
                {"key": constants.VACANT, "value": "Vacant"},
                {"key": constants.OCCUPIED, "value": "Occupied"},
                ]
            
        elif option_type == "Agreement_Expiration":
            content["Agreement_Expiration"] = [
        {"key": constants.ONGOING, "value": "Ongoing"},
        {"key": constants.ABOUT_TO_EXPIRE, "value": "About to Expire"},
        {"key": constants.EXPIRED, "value": "Expired"},
    ]
            
        elif option_type == "USER_ROLE":
            content["user_role"] = [
                {"key": constants.OWNER, "value": "Owner"},
                {"key": constants.TENANT, "value": "Tenant"},
                {"key": constants.COMPANY_USER, "value": "Property Manager"},
            ]
        
        elif option_type == "PROPERTY_DOCUMENT_CHOICE":
             content["Property_Document"] = [
        {"key": constants.FLOOR_PLAN, "value": "Floor Plan"},
        {"key": constants.EJARI_CERTIFICATE, "value": "Ejari Certificate"},
        {"key": constants.PMC_DOCUMENT, "value": "PMC Document"},
        {"key": constants.CHEQUE_DOCUMENT, "value": "Cheque Document"},
        {"key": constants.OWNER_DOCUMENT, "value": "Owner Document"},
        {"key": constants.TENANT_DOCUMENT, "value": "Tenant Document"},
             ]
        
        elif option_type == "PROPERTY_IMAGE_CHOICE":
            content["Property_Image"] = [
                {"key": key, "value": value} for key, value in constants.IMAGE_TYPE_CHOICES]

        elif option_type == "ROLE":
            company = pm_profile.company if pm_profile else None
            if not company:
                company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()
            if not company or not company.is_active:
                content["role"] = []
            else:
                roles = Role.objects.filter(company=company, is_active=True)
                content["role"] = [{"key": r.id, "value": r.name} for r in roles]
                
        # ---------- Fetched rental accoubt lease ----------
        elif option_type == "RENTAL_ACCOUNT_LEASE":
            leases = Lease.objects.filter(lease_status=constants.ACTIVE)
            content["lease_data"] = [
                {
                    "key": lease.id,
                    "value": lease.lease_number
                }
                for lease in leases
            ]    
        elif option_type == "OWNER_COMPANY_USER":
            if pm_profile and pm_profile.company:
                companies = PropertyManagmentCompany.objects.filter(
                    id=pm_profile.company.id,
                    is_active=True
                )
            else:
                own_company = PropertyManagmentCompany.objects.filter(
                    created_by=user.user,
                    is_active=True
                ).first()
                companies = PropertyManagmentCompany.objects.filter(
                    id=own_company.id,
                    is_active=True
                ) if own_company else PropertyManagmentCompany.objects.none()

            content["company_user"] = [
                {"key": c.id, "value": c.name or f"Company #{c.id}"}
                for c in companies
            ]
        elif option_type == "LEASE_STATUS":
            content["lease_status"] = [{"key": status_key,"value": status_value}for status_key, status_value in constants.LEASE_STATUS_CHOICES]
        elif option_type == "OWNER_DETAILS":
            owners = Owner.objects.select_related('user').filter(user__is_active=True)
            content["owners"] = [{"key": owner.id, "value": f"{owner.user.first_name} {owner.user.last_name}"} for owner in owners]

        elif option_type == "PMC_OWNERS":
            owners = Owner.objects.select_related('user').filter(user__is_active=True)
            content["pmc_owners"] = [
                {
                    "key": owner.id,
                    "value": f"{owner.user.first_name} {owner.user.last_name} ({owner.code})" if owner.code else f"{owner.user.first_name} {owner.user.last_name}",
                    "name": f"{owner.user.first_name} {owner.user.last_name}",
                    "email": owner.email or owner.user.email,
                    "contact_number": owner.contact_number,
                    "emirates_id": owner.emirate_id,
                    "owner_number": owner.owner_number,
                    "trade_license_number": owner.trade_license_number,
                    "license_number": owner.license_number,
                    "license_expiry_date": owner.license_expiry_date.isoformat() if owner.license_expiry_date else None,
                    "license_issuer": owner.license_issuer,
                    "fax_number": owner.fax_number,
                    "po_box_number": owner.po_box_number,
                }
                for owner in owners
            ]
            
        elif option_type == "PROPERTY_UNIT_WITH_LEASE":
            if is_owner:
                units = Unit.objects.filter(owner=user, lease_details__isnull=False).distinct()
            elif is_pm:
                if not pm_profile.company:
                    return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                units = Unit.objects.filter(property_block_tower__property__pmc=pm_profile.company, lease_details__isnull=False).distinct()
            else:
                units = Unit.objects.none()
            content["property_unit_with_lease"] = [{"key": u.id, "value": u.unit_name or "Unnamed Unit"} for u in units]

        elif option_type == "PARENT_PROPERTY_WITH_LEASE":
            if is_owner:
                properties = Property.objects.filter(property_blocks__block_towers__owner=user, property_blocks__block_towers__lease_details__isnull=False).distinct()
            elif is_pm:
                if not pm_profile.company:
                    return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                properties = Property.objects.filter(pmc=pm_profile.company, property_blocks__block_towers__lease_details__isnull=False).distinct()
            else:
                properties = Property.objects.none()
            content["property_with_lease"] = [{"key": p.id, "value": p.property_name or "Unnamed Property"} for p in properties]
        
         # Fetch all leased property units under selected parent property (user-specific)
        elif option_type == "PROPERTY_UNIT_BY_LEASE":
            parent_property_id = request.GET.get("parent_property_id")
            if not parent_property_id:
                if is_owner:
                    units = Unit.objects.filter(owner=user, leases__isnull=False).distinct()
                elif is_pm:
                    if not pm_profile.company:
                        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                    units = Unit.objects.filter(property_block_tower__property__pmc=pm_profile.company, leases__isnull=False).distinct()
                else:
                    units = Unit.objects.none()
            else:
                if is_owner:
                    units = Unit.objects.filter(property_block_tower__property_id=parent_property_id, leases__isnull=False).distinct()
                elif is_pm:
                    if not pm_profile.company:
                        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                    units = Unit.objects.filter(property_block_tower__property_id=parent_property_id, property_block_tower__property__pmc=pm_profile.company, leases__isnull=False).distinct()
                else:
                    units = Unit.objects.none()
            content["property_unit_with_lease"] = [{"key": u.id, "value": u.unit_name or "Unnamed Unit"} for u in units]

        elif option_type == "LEASE_DOCUMENT_CHOICES":
            content["lease_document_choices"] = [{"key": key, "value": value}for key, value in constants.LEASE_DOCUMENT_CHOICES]

        elif option_type == "PAYMENT_METHOD":
            content["payment_method"] = [
            {"key": constants.CASH, "value": "Cash"},
            {"key": constants.CHEQUE, "value": "Cheque"},
            {"key": constants.CREDIT_CARD, "value": "Credit Card"},
            {"key": constants.DEBIT_CARD, "value": "Debit Card"},
            {"key": constants.NET_BANKING, "value": "Net Banking"},
        ]
        elif option_type == "BANK_WITH_BRANCH":
            banks = Bank.objects.select_related("city").all()
            content["bank"] = [
                {
                    "key":       bank.id,
                    "value":     f"{bank.name} ({bank.branch_code}) - {bank.city.name}",
                    "ifsc_code": bank.ifsc_code or "",
                }
                for bank in banks
            ]

        elif option_type == "PROPERTY_UNIT_BY_PROPERTY":
            property_id = request.GET.get("property_id")
            if not property_id:
                content["property_unit"] = []
            else:
                units = Unit.objects.filter(property_block_tower__property_id=property_id)
                content["property_unit"] = [{ "key": unit.id,"value": unit.unit_name or f"Unit #{unit.id}"}for unit in units]

        elif option_type == "PROPERTY_BLOCK_BY_PROPERTY":
            property_id = request.GET.get("property_id")
            if not property_id:
                content["property_block"] = []
            else:
                from property.models import PropertyBlocks
                blocks = PropertyBlocks.objects.filter(property_id=property_id)
                content["property_block"] = [{"key": b.id, "value": b.block_name} for b in blocks]

        elif option_type == "PROPERTY_UNIT_BY_BLOCK":
            block_id = request.GET.get("block_id")
            if not block_id:
                content["property_unit"] = []
            else:
                units = Unit.objects.filter(property_block_tower_id=block_id)
                content["property_unit"] = [{"key": unit.id, "value": unit.unit_name or f"Unit #{unit.id}"} for unit in units]

        elif option_type == "COMPLAINT_STATUS":
            content["complaint_status"] = [{"key": constants.IN_PROGRESS, "value": "In Progress"},
        {"key": constants.COMPLETED, "value": "Completed"},
        {"key": constants.ASSIGNED_ENGINEER, "value": "Assigned to Engineer"},
        {"key": constants.REJECTED, "value": "Rejected"},]
        
        elif option_type == "TENANT_DOCUMENT_TYPE":
            doc_types = DocumentType.objects.filter(section=constants.TENANT).order_by("id")
            content["tenant_document_type"] = [{"key": dt.id, "value": dt.name} for dt in doc_types]

        elif option_type == "TENANT_BY_COMPANY": #for creating lease we get that tenants
            if not is_pm or not pm_profile.company:
                content["tenant"] = []
                continue
            company = pm_profile.company
            tenant_status = request.GET.get("tenant_status", constants.APPROVED)
            tenants_created = Tenant.objects.filter(created_by=user.user, is_active=True, tenant_status=tenant_status)
            tenants_interested = Tenant.objects.filter(interested_properties__property_unit__company=company, interested_properties__is_active=True, tenant_status=tenant_status)
            tenants = (tenants_created | tenants_interested).distinct()
            content["tenant"] = [{"key": t.id, "value": f"{t.user.first_name} {t.user.last_name}"} for t in tenants]

            
        elif option_type == "TIMEZONE":
            content["timezone"] = [{"key": key, "value": value} for key, value in constants.TIMEZONE_CHOICES]

        else:
            content[option_type] = []
    return prepare_response(
        content=content,
        message=constants.DROPDOWN_DATA_FETCHED_SUCEESS,
        status=status.HTTP_200_OK )


# property_table_view moved to property/views.py

# owner_pmc_view moved to user_service/views.py


@is_request_authenticated
def send_invitation(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_profile = request.user  
        data = json.loads(request.body)
        email = data.get("email")
        invite_type = data.get("invitation_type") 
        property_unit_id = data.get("property_unit_id")

        if not email:
            return prepare_response(message=constants.EMAIL_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
        
        if not property_unit_id:
            return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
        
        if invite_type not in ["OWNER_TO_PMC", "PMC_TO_OWNER", "PMC_TO_TENANT"]:
            return prepare_response(message=constants.INVALID_INVITATION_TYPE, status=status.HTTP_400_BAD_REQUEST)
      
        if invite_type == "OWNER_TO_PMC" and user_profile.user_role != constants.OWNER:
            return prepare_response(message=constants.ONLY_OWNER_CAN_INVITE_PMC, status=status.HTTP_403_FORBIDDEN)

        if invite_type in ["PMC_TO_OWNER", "PMC_TO_TENANT"] and user_profile.user_role != constants.COMPANY_USER:
            return prepare_response(message=constants.ONLY_PMC_CAN_SEND_INVITATION, status=status.HTTP_403_FORBIDDEN)
        property_unit_qs = Unit.objects.filter(id=property_unit_id)
        if not property_unit_qs.exists():
            return prepare_response(
        message=constants.INVALID_PROPERTY_ID,
        status=status.HTTP_404_NOT_FOUND
    )
        property_unit = property_unit_qs.first()
        template_map = {
            "OWNER_TO_PMC": "email_templates/invite_owner_to_pmc.html",
            "PMC_TO_OWNER": "email_templates/invite_pmc_to_owner.html",
            "PMC_TO_TENANT": "email_templates/invite_tenant_by_pmc.html",
        }

        template_name = template_map[invite_type]
        invitation, error = create_and_send_invitation(
            invited_by_profile=user_profile,
            email=email,
            invitation_type=invite_type,
            template_name=template_name,
            property_unit=property_unit
        )
        if error:
            return prepare_response(message=error, status=status.HTTP_400_BAD_REQUEST)

        return prepare_response(
            content={
                "email": invitation.email,
                "token": invitation.token,
                "status": invitation.status,
                "invitation_type": invitation.invitation_type
            },
            message=constants.INVITATION_SENT_SUCCESS,
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def dashboard_overview(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user = request.user
        now = timezone.now()
        renewal_window = now + timedelta(days=30)
        property_id = request.GET.get("property_id")

        # ── Resolve unit queryset by checking which subclass user is ─
        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        if pm_instance:
            company = pm_instance.company
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            units_qs = Unit.objects.filter(property_block_tower__property__pmc=company)
        elif owner_instance:
            units_qs = Unit.objects.filter(unit_owners__owner=owner_instance)
        else:
            units_qs = Unit.objects.none()

        # ── Properties summary: unit-level counts for the logged-in user ─
        if pm_instance:
            properties_qs = Property.objects.filter(pmc=company)
        elif owner_instance:
            owned_prop_ids = units_qs.values_list(
                "property_block_tower__property_id", flat=True
            ).distinct()
            properties_qs = Property.objects.filter(id__in=owned_prop_ids)
        else:
            properties_qs = Property.objects.none()

        total_units = units_qs.count()
        rented_unit_ids = (
            Lease.objects.filter(unit__in=units_qs, lease_status=constants.ACTIVE)
            .values_list("unit_id", flat=True)
            .distinct()
        )
        rented_count = rented_unit_ids.count()
        vacant_count = total_units - rented_count

        # ── Tenants stats ────────────────────────────────────────────
        lease_queryset = Lease.objects.filter(unit__in=units_qs)
        active_count = lease_queryset.filter(lease_status=constants.ACTIVE).count()
        upcoming_renewals_count = lease_queryset.filter(
            lease_status=constants.ACTIVE,
            end_date__gte=now,
            end_date__lte=renewal_window,
        ).count()
        negotiations_count = lease_queryset.filter(
            lease_stage=constants.NEGOTIATION_SENT,
        ).count()

        # ── Top properties by occupancy rate (all properties, not just those with units)
        property_stats = properties_qs.annotate(
            total_units=Count("property_blocks__block_towers", distinct=True),
        )
        rented_per_prop = {
            r["unit__property_block_tower__property_id"]: r["rented"]
            for r in (
                Lease.objects.filter(
                    unit__property_block_tower__property__in=properties_qs,
                    lease_status=constants.ACTIVE,
                )
                .values("unit__property_block_tower__property_id")
                .annotate(rented=Count("unit_id", distinct=True))
            )
        }
        top_properties = []
        for idx, prop in enumerate(property_stats, start=1):
            total = prop.total_units
            occupied = rented_per_prop.get(prop.id, 0)
            occupancy_rate = round((occupied / total) * 100, 2) if total > 0 else 0
            top_properties.append({
                "rank": idx,
                "property_id": prop.id,
                "name": prop.property_name,
                "occupancy_rate": occupancy_rate,
                "figures": f"{occupancy_rate}%",
                "total_units": total,
                "occupied_units": occupied,
            })
        top_properties = sorted(top_properties, key=lambda x: x["occupancy_rate"], reverse=True)[:5]

        # ── Occupancy data (per property_id if given, else all) ──────
        filtered_units = units_qs.filter(
            property_block_tower__property_id=property_id
        ) if property_id else units_qs

        f_total = filtered_units.count()
        f_occupied = (
            Lease.objects.filter(unit__in=filtered_units, lease_status=constants.ACTIVE)
            .values_list("unit_id", flat=True)
            .distinct()
            .count()
        )
        f_vacant = f_total - f_occupied
        occupied_percent = round((f_occupied / f_total) * 100, 2) if f_total > 0 else 0
        vacant_percent = round((f_vacant / f_total) * 100, 2) if f_total > 0 else 0

        # ── Top revenue-generating properties ────────────────────────
        revenue_rows = (
            LeaseTransaction.objects.filter(
                lease__unit__in=units_qs,
                status=constants.CHEQUE_STATUS_REALIZED,
                is_active=True,
            )
            .values(
                prop_id=F("lease__unit__property_block_tower__property_id"),
                prop_name=F("lease__unit__property_block_tower__property__property_name"),
            )
            .annotate(total_revenue=Sum("amount"))
            .order_by("-total_revenue")
        )
        max_revenue = revenue_rows[0]["total_revenue"] if revenue_rows else 1
        top_revenue_properties = [
            {
                "rank": idx,
                "property_id": r["prop_id"],
                "name": r["prop_name"],
                "total_revenue": round(r["total_revenue"], 2),
                "revenue_percent": round((r["total_revenue"] / max_revenue) * 100, 2),
            }
            for idx, r in enumerate(revenue_rows, start=1)
        ]

        # ── Leads & Complaints counts ────────────────────────────────
        if pm_instance:
            active_leads_count = Lead.objects.filter(pmc=company).count()
            active_complaints_count = Complaint.objects.filter(company=company, is_active=True).count()
        elif owner_instance:
            active_leads_count = 0
            active_complaints_count = Complaint.objects.filter(unit__in=units_qs, is_active=True).count()
        else:
            active_leads_count = 0
            active_complaints_count = 0

        content = {
            "properties": {
                "total": total_units,
                "rented": rented_count,
                "vacant": vacant_count,
            },
            "tenants": {
                "active": active_count,
                "upcoming_renewals": upcoming_renewals_count,
                "negotiations": negotiations_count,
            },
            "top_properties": top_properties,
            "top_revenue_properties": top_revenue_properties,
            "occupancy_data": {
                "total_units": f_total,
                "occupied_units": f_occupied,
                "vacant_units": f_vacant,
                "occupied_percent": occupied_percent,
                "vacant_percent": vacant_percent,
            },
            "active_leads_count": active_leads_count,
            "active_complaints_count": active_complaints_count,
        }

        return prepare_response(
            content=content,
            message="Dashboard overview fetched successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message={"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def faq_api(request):

    if request.method == "GET":
        faqs = FAQ.objects.all()
        data = [
            {
                "id": faq.id,
                "question": faq.question,
                "answer": faq.answer
            }
            for faq in faqs
        ]
        return prepare_response(
            content=data
        )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


#--------------------------------------------> Dashboard API<------------------------------------------------------------------

@is_request_authenticated
def dashboard_monthly_revenue(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user

        city_id = request.GET.get("city_id")
        unit_id = request.GET.get("property_unit_id")
        from_date = request.GET.get("from_date")   # epoch in ms
        to_date = request.GET.get("to_date")       # epoch in ms
        year = int(request.GET.get("year", datetime.now().year))

        # =========================
        # DATE RANGE FILTER LOGIC
        # =========================
        if from_date and to_date:
            start_date = safe_epoch_to_datetime(int(from_date))
            end_date = safe_epoch_to_datetime(int(to_date))
            if start_date:
                start_date = start_date.date()
            if end_date:
                end_date = end_date.date()
        else:
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)

        transactions = LeaseTransaction.objects.filter(
            status=constants.CHEQUE_STATUS_REALIZED,
            is_active=True,
            cheque_date__date__range=[start_date, end_date]
        )

        leases = Lease.objects.filter(
            lease_status=constants.ACTIVE,
            is_active=True
        )

        # =========================
        # ROLE BASED FILTER
        # =========================
        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        if pm_instance:
            company = pm_instance.company
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
            leases = leases.filter(
                unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            transactions = transactions.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
            leases = leases.filter(
                unit__unit_owners__owner=owner_instance
            )
        else:
            transactions = transactions.none()
            leases = leases.none()

        # =========================
        # OPTIONAL FILTERS
        # =========================
        if city_id:
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__city_id=city_id
            )

        if unit_id:
            transactions = transactions.filter(
                lease__unit__id=unit_id
            )

        # =========================
        # MONTHLY AGGREGATION (12 MONTHS ALWAYS)
        # =========================
        monthly_data = (
            transactions
            .annotate(month=TruncMonth("cheque_date"))
            .values("month")
            .annotate(total_amount=Sum("amount"))
            .order_by("month")
        )

        # Create a dict for quick lookup
        monthly_dict = {item["month"].month: float(item["total_amount"] or 0) for item in monthly_data}

        revenue_list = []
        total_revenue = 0

        for m in range(1, 13):  # Always loop Jan (1) to Dec (12)
            amount = monthly_dict.get(m, 0)  # 0 if no payments
            total_revenue += amount

            revenue_list.append({
                "period_epoch": datetime_to_epoch_millis(datetime(year, m, 1)),
                "month": m,
                "month_str": calendar.month_abbr[m],
                "year": year,
                "amount": round(amount, 2)
            })

        # =========================
        # MRR — total of all realized lease transactions for the company (no date filter)
        # =========================
        mrr_qs = LeaseTransaction.objects.filter(
            status=constants.CHEQUE_STATUS_REALIZED,
            is_active=True
        )
        if pm_instance:
            mrr_qs = mrr_qs.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            mrr_qs = mrr_qs.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
        else:
            mrr_qs = mrr_qs.none()

        mrr = mrr_qs.aggregate(total_mrr=Sum("amount"))["total_mrr"] or 0

        return prepare_response(
            message=constants.MONTHLY_REVENUE_FETCH_SUCCESS,
            status=status.HTTP_200_OK,
            content={
                "total_revenue": round(total_revenue, 2),
                "MRR": round(mrr, 2),
                "monthly_revenue": revenue_list
            }
        )

    except Exception as e:
        print("Dashboard Revenue Error:", e)
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# dasassa

from datetime import datetime

from django.utils.dateparse import parse_date

@is_request_authenticated
def dashboard_cheque_visibility(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        city_id        = request.GET.get("city_id")
        unit_id        = request.GET.get("property_unit_id")
        property_id    = request.GET.get("property_id")
        cheque_status  = request.GET.get("cheque_status")
        from_date      = request.GET.get("from_date")
        to_date        = request.GET.get("to_date")      

        # =========================
        # DEFAULT DATE RANGE = CURRENT MONTH
        # =========================
        start_date = None
        end_date   = None
        if from_date and to_date:
            start_date = safe_epoch_to_datetime(int(from_date))
            end_date   = safe_epoch_to_datetime(int(to_date))
            if start_date:
                start_date = start_date.date()
            if end_date:
                end_date = end_date.date()

        # =========================
        # ROLE BASED FILTER
        # =========================
        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        transactions = LeaseTransaction.objects.filter(is_active=True)

        if pm_instance:
            company = pm_instance.company
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            transactions = transactions.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
        else:
            transactions = transactions.none()

        # =========================
        # OPTIONAL FILTERS
        # =========================
        if city_id:
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__city_id=city_id
            )
        if property_id:
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__id=property_id
            )
        if unit_id:
            transactions = transactions.filter(lease__unit__id=unit_id)
        if cheque_status:
            transactions = transactions.filter(status=cheque_status)

        # =========================
        # APPLY DATE RANGE FILTER
        # =========================
        if start_date and end_date:
            transactions = transactions.filter(
                cheque_date__date__range=[start_date, end_date]
            )

        transactions = transactions.select_related(
            "lease__unit__property_block_tower__property",
            "lease__tenant__user"
        )

        # =========================
        # BUILD RESPONSE
        # =========================
        cheque_list = []
        for t in transactions:
            lease  = t.lease
            unit   = lease.unit if lease else None
            prop   = unit.property_block_tower.property if unit and unit.property_block_tower_id else None
            tenant = lease.tenant if lease else None
            tenant_name = f"{tenant.user.first_name} {tenant.user.last_name}".strip() if tenant and tenant.user else ""

            cheque_list.append({
                "lease_number":       lease.code if lease else "",
                "property_unit_name": unit.unit_name if unit else "",
                "property_name":      prop.property_name if prop else "",
                "tenant_name":        tenant_name,
                "cheque_number":      t.cheque_number,
                "cheque_date":        t.cheque_date.strftime("%d %b %Y") if t.cheque_date else "",
                "status":             t.status or "",
                "status_display":     t.get_status_display() if t.status else "",
                "amount":             round(t.amount, 2),
            })

        return prepare_response(
            message=constants.CHEQUE_VISIBILITY_FETCH_SUCCESS,
            status=status.HTTP_200_OK,
            content={"cheques": cheque_list}
        )

    except Exception as e:
        print("Cheque Visibility Error:", e)
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def dashboard_cheque_aging(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user = request.user
        property_id = request.GET.get("property_id")
        today = now().date()

        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        transactions = LeaseTransaction.objects.filter(is_active=True)

        if pm_instance:
            company = pm_instance.company
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            transactions = transactions.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
        else:
            transactions = transactions.none()

        if property_id:
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__id=property_id
            )

        # ================= SUMMARY =================
        total_cheques = transactions.count()

        realized_count = transactions.filter(
            status=constants.CHEQUE_STATUS_REALIZED
        ).count()

        bounced_payments = transactions.filter(
            status=constants.CHEQUE_STATUS_BOUNCED,
        )

        bounced_count = bounced_payments.count()

        # ================= AGING =================
        aging_30 = aging_60 = aging_90 = aging_90_plus = 0

        for p in bounced_payments:
            ref_date = p.cheque_date or p.created
            age_days = (today - ref_date.date()).days
            if age_days <= 30:
                aging_30 += 1
            elif age_days <= 60:
                aging_60 += 1
            elif age_days <= 90:
                aging_90 += 1
            else:
                aging_90_plus += 1

        data = {
            "property_id": property_id,
            "summary": {
                "total_cheques": total_cheques,
                "realized_cheques": {
                    "count": realized_count,
                    "text": f"{realized_count} / {total_cheques}"
                },
                "bounced_cheques": {
                    "count": bounced_count,
                    "text": f"{bounced_count} / {total_cheques}"
                }
            },
            "aging_breakup": {
                "30_days": aging_30,
                "60_days": aging_60,
                "90_days": aging_90,
                "above_90_days": aging_90_plus
            }
        }

        return prepare_response(
            message=constants.CHEQUE_AGING_FETCH_SUCCESS,
            status=status.HTTP_200_OK,
            content=data
        )

    except Exception as e:
        print("Cheque Aging Error:", e)
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def dashboard_other_type_payments(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        year = int(request.GET.get("year", datetime.now().year))
        property_unit_id = request.GET.get("property_unit_id")
        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)
        transactions = LeaseTransaction.objects.filter(
            status=constants.CHEQUE_STATUS_REALIZED,
            is_active=True,
            cheque_date__date__range=[year_start, year_end]
        )

        # ---------------- USER FILTER ----------------
        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        if pm_instance:
            company = pm_instance.company
            transactions = transactions.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            transactions = transactions.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
        else:
            transactions = transactions.none()

        # ---------------- PROPERTY UNIT FILTER ----------------
        if property_unit_id:
            transactions = transactions.filter(lease__unit__id=property_unit_id)

        # ---------------- MONTH + PAYMENT TYPE AGGREGATION ----------------
        monthly_qs = (
            transactions
            .annotate(month=TruncMonth("cheque_date"))
            .values("month")
            .annotate(
                cheque=Sum("amount", filter=Q(payment_type=constants.PAYMENT_TYPE_CHEQUE)),
                cash=Sum("amount", filter=Q(payment_type=constants.PAYMENT_TYPE_CASH)),
                bank_transfer=Sum("amount", filter=Q(payment_type=constants.PAYMENT_TYPE_BANK_TRANSFER)),
                pdc=Sum("amount", filter=Q(payment_type=constants.PAYMENT_TYPE_PDC)),
                total=Sum("amount")
            )
        )

        # ---------------- CONVERT TO MAP ----------------
        month_map = {}
        for row in monthly_qs:
            if row["month"]:
                month_map[row["month"].month] = row

        # ---------------- FORCE JAN → DEC ----------------
        monthly_data = []
        total_revenue = 0

        for month in range(1, 13):
            data = month_map.get(month, {})

            cheque       = float(data.get("cheque",       0) or 0)
            cash         = float(data.get("cash",         0) or 0)
            bank_transfer = float(data.get("bank_transfer", 0) or 0)
            pdc          = float(data.get("pdc",          0) or 0)
            total        = float(data.get("total",        0) or 0)

            total_revenue += total

            monthly_data.append({
                "month":         month,
                "month_str":     calendar.month_abbr[month],
                "year":          year,
                "cheque":        cheque,
                "cash":          cash,
                "bank_transfer": bank_transfer,
                "pdc":           pdc,
                "total":         total,
            })

        return prepare_response(
            message=constants.OTHER_TYPE_PAYMENTS_FETCH_SUCCESS,
            status=status.HTTP_200_OK,
            content={
                "total_revenue": round(total_revenue, 2),
                "monthly_data": monthly_data
            }
        )

    except Exception as e:
        print("Other Payment Dashboard Error:", e)
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# Total Amount → lease se (expected rent)

# Received Amount → payments se (successful rent payments)

# Due Amount → Total − Received

# """
# LOGIC USED:

# 1. LeasePropertyDetails:
#    - rent field represents expected MONTHLY rent
#    - Same rent amount is applicable for every month
#    - Lease duration (start/end) is NOT considered here

# 2. Payment:
#    - Represents actual rent paid by user
#    - Grouped month-wise using created date

# 3. Monthly Due:
#    - Due = Total Expected Rent - Received Rent

# 4. Yearly Calculation:
#    - Yearly Total = Monthly Rent * 12
#    - Percentages calculated on yearly totals
# """


@is_request_authenticated
def dashboard_yearly_dues(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        year = int(request.GET.get("year", datetime.now().year))
        property_unit_id = request.GET.get("property_unit_id")  #  ADDED

        year_start = date(year, 1, 1)
        year_end = date(year, 12, 31)

        # ------------------------------------------------
        # 1 ROLE BASED COMPANY FILTER
        # ------------------------------------------------
        pm_instance = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
        owner_instance = Owner.objects.filter(pk=user.pk).first()

        base_qs = LeaseTransaction.objects.filter(is_active=True)

        if pm_instance:
            company = pm_instance.company
            base_qs = base_qs.filter(
                lease__unit__property_block_tower__property__pmc=company
            )
        elif owner_instance:
            base_qs = base_qs.filter(
                lease__unit__unit_owners__owner=owner_instance
            )
        else:
            base_qs = base_qs.none()

        base_qs = base_qs.filter(cheque_date__year=year)

        # ------------------------------------------------
        # 2 PROPERTY UNIT FILTER
        # ------------------------------------------------
        if property_unit_id:
            base_qs = base_qs.filter(lease__unit__id=property_unit_id)

        # ------------------------------------------------
        # 3 BUILD MONTHLY MAPS FROM LeaseTransaction
        # ------------------------------------------------
        def _monthly_map(qs):
            rows = (
                qs.annotate(month=TruncMonth("cheque_date"))
                .values("month")
                .annotate(total=Sum("amount"))
            )
            return {row["month"].month: float(row["total"] or 0) for row in rows if row["month"]}

        total_map    = _monthly_map(base_qs)
        received_map = _monthly_map(base_qs.filter(status=constants.CHEQUE_STATUS_REALIZED))

        # ------------------------------------------------
        # 4 MONTHLY CALCULATION
        # ------------------------------------------------
        monthly_data = []
        yearly_total = 0
        yearly_received = 0

        for month in range(1, 13):
            total_amount    = total_map.get(month, 0)
            received_amount = received_map.get(month, 0)
            due_amount      = max(total_amount - received_amount, 0)

            yearly_total    += total_amount
            yearly_received += received_amount

            received_pct = round((received_amount / total_amount * 100), 1) if total_amount else 0
            due_pct      = round(100 - received_pct, 1) if total_amount else 0

            monthly_data.append({
                "month":             month,
                "month_str":         calendar.month_abbr[month],
                "total_amount":      round(total_amount, 2),
                "received_amount":   round(received_amount, 2),
                "due_amount":        round(due_amount, 2),
                "received_percent":  received_pct,
                "due_percent":       due_pct,
            })

        # ------------------------------------------------
        # 7 YEARLY SUMMARY
        # ------------------------------------------------
        yearly_due = max(yearly_total - yearly_received, 0)

        received_percent = round((yearly_received / yearly_total * 100), 1) if yearly_total else 0
        due_percent = round(100 - received_percent, 1) if yearly_total else 0

        return prepare_response(
            message="Yearly dues fetched successfully",
            status=status.HTTP_200_OK,
            content={
                "year": year,
                "overall": {
                    "total_amount": round(yearly_total, 2),
                    "received_amount": round(yearly_received, 2),
                    "due_amount": round(yearly_due, 2),
                    "total_percent": 100,
                    "received_percent": round(received_percent, 2),
                    "due_percent": round(due_percent, 2)
                },
                "monthly_data": monthly_data
            }
        )

    except Exception as e:
        print("Yearly Dues Error:", e)
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def audit_log(request):

    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    from django.utils import timezone
    from datetime import timedelta
    from django.core.paginator import Paginator, EmptyPage

    user_id    = request.GET.get("user_id")
    search     = request.GET.get("search", "").strip()
    time_range = request.GET.get("time_range")   # today | 7days | 30days
    page       = int(request.GET.get("page", 1))
    page_size  = int(request.GET.get("page_size", 20))
    export     = request.GET.get("export") == "true"

    logs_qs = AuditLog.objects.select_related("userprofile__user").order_by("-created")

    if user_id:
        logs_qs = logs_qs.filter(userprofile_id=user_id)

    if search:
        from django.db.models import Q
        logs_qs = logs_qs.filter(
            Q(message__icontains=search) |
            Q(action_type__icontains=search) |
            Q(userprofile__user__first_name__icontains=search) |
            Q(userprofile__user__last_name__icontains=search)
        )

    if time_range:
        now = timezone.now()
        if time_range == "today":
            logs_qs = logs_qs.filter(created__date=now.date())
        elif time_range == "7days":
            logs_qs = logs_qs.filter(created__gte=now - timedelta(days=7))
        elif time_range == "30days":
            logs_qs = logs_qs.filter(created__gte=now - timedelta(days=30))

    if export:
        field_names = ["ID", "User", "Email", "Message", "Action Type", "Created"]
        data_list = []
        for log in logs_qs:
            user_info = log.userprofile.get_user_basic_info() if log.userprofile else {}
            data_list.append({
                "ID":          log.id,
                "User":        user_info.get("name", ""),
                "Email":       user_info.get("email", ""),
                "Message":     log.message,
                "Action Type": log.action_type,
                "Created":     log.created.strftime("%Y-%m-%d %H:%M:%S") if log.created else "",
            })
        return export_to_csv(filename="audit_logs", field_names=field_names, data_list=data_list)

    total_records = logs_qs.count()
    paginator = Paginator(logs_qs, page_size)
    try:
        page_obj = paginator.page(page)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    data = []
    for log in page_obj:
        data.append({
            "id":          log.id,
            "user":        log.userprofile.get_user_basic_info() if log.userprofile else None,
            "message":     log.message,
            "action_type": log.action_type,
            "created":     datetime_to_epoch_millis(log.created),
        })

    return prepare_response(
        content=data,
        pagination={
            "total_records": total_records,
            "page":          page,
            "page_size":     page_size,
            "total_pages":   paginator.num_pages,
        },
        message=constants.DATA_FETCHED_SUCCESSFULLY,
        status=status.HTTP_200_OK
    )


@is_request_authenticated
def global_search(request):
    if request.method != "GET":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    search = request.GET.get("search", "").strip()
    if not search or len(search) < 2:
        return prepare_response(content={"results": []}, message="OK", status=status.HTTP_200_OK)

    user = request.user
    results = []

    pm_profile = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
    company = pm_profile.company if pm_profile else None
    if not company:
        company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()

    if company:
        props = Property.objects.filter(
            pmc=company, is_active=True
        ).filter(
            Q(property_name__icontains=search) | Q(code__icontains=search)
        )[:5]
        for p in props:
            results.append({
                "type": "property",
                "id": p.id,
                "label": p.property_name,
                "sub_label": p.code or "",
            })

        units = Unit.objects.filter(
            property_block_tower__property__pmc=company,
            is_active=True,
        ).filter(
            Q(unit_name__icontains=search) | Q(code__icontains=search)
        ).select_related("property_block_tower__property")[:5]
        for u in units:
            prop_name = u.property_block_tower.property.property_name
            results.append({
                "type": "unit",
                "id": u.id,
                "label": u.unit_name,
                "sub_label": f"{u.property_block_tower.block_name} — {prop_name}",
            })

    owners = Owner.objects.filter(
        Q(user__first_name__icontains=search) |
        Q(user__last_name__icontains=search) |
        Q(user__email__icontains=search) |
        Q(contact_number__icontains=search) |
        Q(owner_number__icontains=search)
    ).select_related("user")[:5]
    for o in owners:
        results.append({
            "type": "owner",
            "id": o.id,
            "label": o.user.get_full_name() or o.user.email,
            "sub_label": o.user.email,
        })

    tenants = Tenant.objects.filter(
        Q(user__first_name__icontains=search) |
        Q(user__last_name__icontains=search) |
        Q(user__email__icontains=search) |
        Q(contact_number__icontains=search)
    ).select_related("user")[:5]
    for t in tenants:
        results.append({
            "type": "tenant",
            "id": t.id,
            "label": t.user.get_full_name() or t.user.email,
            "sub_label": t.user.email,
        })

    return prepare_response(content={"results": results}, message="OK", status=status.HTTP_200_OK)

@staff_member_required
def admin_report_file(request, filename):
    safe_filename = os.path.basename(filename)
    file_path = os.path.join(settings.MEDIA_ROOT, "reports", safe_filename)

    if not os.path.exists(file_path):
        raise Http404("Report not found")

    return FileResponse(open(file_path, "rb"))

@staff_member_required 
def reports_view(request):
    reports_path = os.path.join(settings.MEDIA_ROOT, "reports")

    files = []
    if os.path.exists(reports_path):
        files = os.listdir(reports_path)

    return render(
        request,
        "email_templates/report_list.html",
        {"files": files}
    )