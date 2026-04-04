import os
import json
import calendar
from datetime import timedelta, datetime, date
from calendar import monthrange
from dateutil.relativedelta import relativedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Prefetch, Sum
from django.db.models.functions import TruncMonth
from django.http import FileResponse
from django.utils import timezone
from django.utils.timezone import now
from django.utils.dateparse import parse_date

from user_service.models import Role, FAQ, Owner, Tenant, PropertyManager, DocumentType
from property.models import Unit, Property, PropertyManagmentCompany
from property_management.models import Country, State, City, AuditLog
from lease.models import Lease, Template
from payment.models import Payment, Bank
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import (
    prepare_response,
    safe_epoch_to_datetime,
    datetime_to_epoch_millis,
    export_to_csv
)
from utilities import status, constants
from property_management import settings
from property_management.utils import create_and_send_invitation, get_user_basic_info

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
                units = Unit.objects.none()
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
            companies = PropertyManagmentCompany.objects.filter(is_active=True)
            content["company_user"] = [{"key": c.id, "value": c.name or f"PropertyManagmentCompany #{c.id}"} for c in companies]
            
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
                    units = Unit.objects.filter(owner=user, lease_details__isnull=False).distinct()
                elif is_pm:
                    if not pm_profile.company:
                        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                    units = Unit.objects.filter(property_block_tower__property__pmc=pm_profile.company, lease_details__isnull=False).distinct()
                else:
                    units = Unit.objects.none()
            else:
                if is_owner:
                    units = Unit.objects.filter(property_block_tower__property_id=parent_property_id, lease_details__isnull=False).distinct()
                elif is_pm:
                    if not pm_profile.company:
                        return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                    units = Unit.objects.filter(property_block_tower__property_id=parent_property_id, property_block_tower__property__pmc=pm_profile.company, lease_details__isnull=False).distinct()
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
        if user.user_role == constants.OWNER:
            properties = Unit.objects.filter(owner=user)
        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            properties = Unit.objects.filter(company=company)
        else:
            properties = Unit.objects.none()

        if not property_id:  
            property_id = properties.values_list("property_id", flat=True).first()
        if property_id:
            filtered_units = Unit.objects.filter(property_id=property_id)
        else:
            filtered_units = Unit.objects.none()


        total_properties = properties.count()
        rented_count = properties.filter(is_occupied=True).count()
        vacant_count = properties.filter(is_occupied=False).count()
        lease_queryset = Lease.objects.filter(
            lease_property__in=properties
        )

        active_count = lease_queryset.filter(
            lease_start_date__lte=now,
            lease_end_date__gte=now
        ).count()

        upcoming_renewals_count = lease_queryset.filter(
            lease_end_date__gt=now,
            lease_end_date__lte=renewal_window
        ).count()

        negotiations_count = lease_queryset.filter(
            lease_end_date__lt=now
        ).count()
        property_stats = (
            properties
            .values("property_id", "property__property_name")
            .annotate(
                total_units=Count("id"),
                occupied_units=Count(
                    "id",
                    filter=Q(is_occupied=True)
                )
            )
        )
        top_properties = []
        index = 1
        for item in property_stats:
            total = item["total_units"]
            occupied = item["occupied_units"]
            occupancy_rate = round((occupied / total) * 100, 2) if total > 0 else 0
            top_properties.append({
                "rank": index,
                "property_id": item["property_id"],
                "name": item["property__property_name"],
                "occupancy_rate": occupancy_rate,
                "figures": f"{occupancy_rate}%",
                "total_units": total,
                "occupied_units": occupied
            })
            index += 1

        top_properties = sorted(top_properties, key=lambda x: x["occupancy_rate"], reverse=True)

        # ---- Occupancy Section ----
        total_units = filtered_units.count()
        occupied_units = filtered_units.filter(is_occupied=True).count()
        vacant_units = filtered_units.filter(is_occupied=False).count()
        occupied_percent = round((occupied_units / total_units) * 100, 2) if total_units > 0 else 0
        vacant_percent = round((vacant_units / total_units) * 100, 2) if total_units > 0 else 0
        occupancy_data = {
         "total_units": total_units,
         "occupied_units": occupied_units,
        "vacant_units": vacant_units,
        "occupied_percent": occupied_percent,
        "vacant_percent": vacant_percent
                        }
        content = {
            "properties": {
                "total": total_properties,
                "rented": rented_count,
                "vacant": vacant_count
            },
            "tenants": {
                "active": active_count,
                "upcoming_renewals": upcoming_renewals_count,
                "negotiations": negotiations_count
            },
            "top_properties": top_properties,
            "occupancy_data":occupancy_data,
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

        payments = Payment.objects.filter(
            status=constants.PAYMENT_SUCCESSFUL,
            reason_type=constants.RENT,
            is_active=True,
            created__date__range=[start_date, end_date]
        )

        leases = Lease.objects.filter(
            lease_status=constants.ACTIVE,
            is_active=True
        )

        # =========================
        # ROLE BASED FILTER
        # =========================
        if user.user_role == constants.OWNER:
            payments = payments.filter(
                rental_account__lease_property__owner=user
            )
        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            payments = payments.filter(
                rental_account__lease_property__company=company
            )
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        # =========================
        # OPTIONAL FILTERS
        # =========================
        if city_id:
            payments = payments.filter(
                rental_account__lease_property__property__city_id=city_id
            )

        if unit_id:
            payments = payments.filter(
                rental_account__lease_property__id=unit_id
            )

        # =========================
        # MONTHLY AGGREGATION (12 MONTHS ALWAYS)
        # =========================
        monthly_data = (
            payments
            .annotate(month=TruncMonth("created"))
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
        # MRR
        # =========================
        mrr = leases.aggregate(
            total_mrr=Sum("rent")
        )["total_mrr"] or 0

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
        city_id = request.GET.get("city_id")
        unit_id = request.GET.get("property_unit_id")
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")      

        # =========================
        # DEFAULT DATE RANGE = CURRENT MONTH
        # =========================
        today = datetime.now()
        if from_date and to_date:
            start_date = safe_epoch_to_datetime(int(from_date))
            end_date = safe_epoch_to_datetime(int(to_date))
            if start_date:
                start_date = start_date.date()
            if end_date:
                end_date = end_date.date()
        else:
            start_date = today.replace(day=1).date()  # first day of current month
            end_date = (today.replace(day=1) + relativedelta(months=1, days=-1)).date()  # last day of current month

        # =========================
        # ROLE BASED LEASES
        # =========================
        if user.user_role == constants.OWNER:
            leases = Lease.objects.filter(owner=user, is_active=True)
        elif user.user_role == constants.COMPANY_USER:
            companies = PropertyManagmentCompany.objects.filter(company_user=user)
            if not companies.exists():
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            leases = Lease.objects.filter(lease_property__company__in=companies, is_active=True)
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        # =========================
        # OPTIONAL FILTERS
        # =========================
        if city_id:
            leases = leases.filter(lease_property__property__city_id=city_id)
        if unit_id:
            leases = leases.filter(lease_property__id=unit_id)

        # =========================
        # APPLY DATE RANGE FILTER
        # =========================
        leases = leases.filter(
            created__date__range=[start_date, end_date]
        )

        leases = leases.prefetch_related(
            Prefetch(
                "payments",
                queryset=Payment.objects.filter(method=constants.CHEQUE, is_active=True),
                to_attr="cheque_payments"
            )
        ).select_related(
            "lease_property",
            "owner",
            "tenant"
        )

        # =========================
        # BUILD RESPONSE
        # =========================
        cheque_list = []
        for lease in leases:
            property_unit = lease.lease_property
            owner_name = f"{lease.owner.user.first_name} {lease.owner.user.last_name}".strip() if lease.owner else ""
            tenant_name = f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}".strip() if lease.tenant else ""

            if lease.cheque_payments:
                for p in lease.cheque_payments:
                    cheque_list.append({
                        "lease_number": lease.lease_number,
                        "unit_name": property_unit.unit_name if property_unit else "",
                        "owner_name": owner_name,
                        "tenant_name": tenant_name,
                        "cheque_number": p.cheque_number,
                        "status": p.get_status_display() if p.status else None,
                        "amount": round(p.amount, 2)
                    })
            else:
                cheque_list.append({
                    "lease_number": lease.lease_number,
                    "unit_name": property_unit.unit_name if property_unit else "",
                    "owner_name": owner_name,
                    "tenant_name": tenant_name,
                    "cheque_number": None,
                    "status": None,
                    "amount": 0
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
        property_unit_id = request.GET.get("property_unit_id")
        today = now().date()
        payments = Payment.objects.filter(
            method=constants.CHEQUE,
            is_active=True
        )
        if user.user_role == constants.OWNER:
            payments = payments.filter(rental_account__owner=user)

        elif user.user_role == constants.COMPANY_USER:
            companies = PropertyManagmentCompany.objects.filter(company_user=user)
            if not companies.exists():
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            payments = payments.filter(
                rental_account__lease_property__company__in=companies
            )
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )
        if property_unit_id:
            payments = payments.filter(
                rental_account__lease_property__id=property_unit_id
            )

        # ================= SUMMARY =================
        total_cheques = payments.count()

        realized_count = payments.filter(
            status=constants.PAYMENT_SUCCESSFUL
        ).count()

        bounced_payments = payments.filter(
            status=constants.PAYMENT_BOUNCED,
            cheque_date__isnull=False
        )

        bounced_count = bounced_payments.count()

        # ================= AGING =================
        aging_30 = aging_60 = aging_90 = aging_90_plus = 0

        for p in bounced_payments:
            age_days = (today - p.cheque_date.date()).days

            if age_days <= 30:
                aging_30 += 1
            elif age_days <= 60:
                aging_60 += 1
            elif age_days <= 90:
                aging_90 += 1
            else:
                aging_90_plus += 1

        data = {
            "property_unit_id": property_unit_id,
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
        payments = Payment.objects.filter(
            status=constants.PAYMENT_SUCCESSFUL,
            is_active=True,
            created__date__range=[year_start, year_end]
        )

        # ---------------- USER FILTER ----------------
        if user.user_role == constants.OWNER:
            payments = payments.filter(
                rental_account__lease_property__owner=user
            )

        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            payments = payments.filter(
                rental_account__lease_property__company=company
            )
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        # ---------------- PROPERTY UNIT FILTER ----------------
        if property_unit_id:
            payments = payments.filter(
                rental_account__lease_property__id=property_unit_id
            )

        # ---------------- MONTH + METHOD AGGREGATION (SAME) ----------------
        monthly_qs = (
            payments
            .annotate(month=TruncMonth("created"))
            .values("month")
            .annotate(
                credit_card=Sum("amount", filter=Q(method=constants.CREDIT_CARD)),
                debit_card=Sum("amount", filter=Q(method=constants.DEBIT_CARD)),
                net_banking=Sum("amount", filter=Q(method=constants.NET_BANKING)),
                total=Sum("amount")
            )
        )

        # ---------------- CONVERT TO MAP ----------------
        month_map = {}
        for row in monthly_qs:
            month_no = row["month"].month
            month_map[month_no] = row

        # ---------------- FORCE JAN → DEC ----------------
        monthly_data = []
        total_revenue = 0

        for month in range(1, 13):
            data = month_map.get(month, {})

            credit_card = float(data.get("credit_card", 0) or 0)
            debit_card = float(data.get("debit_card", 0) or 0)
            net_banking = float(data.get("net_banking", 0) or 0)
            total = float(data.get("total", 0) or 0)

            total_revenue += total

            month_date = datetime(year, month, 1)

            monthly_data.append({
                "period_epoch": datetime_to_epoch_millis(month_date),
                "month": month,
                "year": year,
                "credit_card": credit_card,
                "debit_card": debit_card,
                "net_banking": net_banking,
                "total": total
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
        # 1 BASE LEASE QUERY (Expected Rent)
        # ------------------------------------------------
        leases = Lease.objects.filter(
            lease_status=constants.ACTIVE,
            is_active=True,
            lease_start_date__lte=year_end,
            lease_end_date__gte=year_start
        )

        # ------------------------------------------------
        # 2 BASE PAYMENT QUERY (Actual Received)
        # ------------------------------------------------
        payments = Payment.objects.filter(
            status=constants.PAYMENT_SUCCESSFUL,
            reason_type=constants.RENT,
            is_active=True,
            created__date__range=[year_start, year_end]
        )

        # ------------------------------------------------
        # 3 USER WISE FILTER
        # ------------------------------------------------
        if user.user_role == constants.OWNER:
            leases = leases.filter(owner=user)
            payments = payments.filter(rental_account__owner=user)

        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            leases = leases.filter(lease_property__company=company)
            payments = payments.filter(
                rental_account__lease_property__company=company
            )
        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        # ------------------------------------------------
        # 4 PROPERTY UNIT FILTER ( ONLY ADDITION)
        # ------------------------------------------------
        if property_unit_id:
            leases = leases.filter(lease_property__id=property_unit_id)
            payments = payments.filter(
                rental_account__lease_property__id=property_unit_id
            )

        # ------------------------------------------------
        # 5 PAYMENT MONTHLY MAP → {month: received}
        # ------------------------------------------------
        payment_qs = (
            payments
            .annotate(month=TruncMonth("created"))
            .values("month")
            .annotate(total=Sum("amount"))
        )

        payment_map = {
            row["month"].month: float(row["total"] or 0)
            for row in payment_qs if row["month"]
        }

        # ------------------------------------------------
        # 6 MONTHLY CALCULATION (NO LOGIC CHANGE)
        # ------------------------------------------------
        monthly_data = []
        yearly_total = 0
        yearly_received = 0

        for month in range(1, 13):

            month_start = date(year, month, 1)
            month_end = date(year, month, monthrange(year, month)[1])

            active_leases = leases.filter(
                lease_start_date__lte=month_end,
                lease_end_date__gte=month_start
            )

            expected_amount = active_leases.aggregate(
                total=Sum("rent")
            )["total"] or 0

            received_amount = payment_map.get(month, 0)
            due_amount = max(expected_amount - received_amount, 0)

            yearly_total += expected_amount
            yearly_received += received_amount

            monthly_data.append({
                "month": month,
                "month_str": calendar.month_abbr[month],
                "total_amount": round(expected_amount, 2),
                "received_amount": round(received_amount, 2),
                "due_amount": round(due_amount, 2)
            })

        # ------------------------------------------------
        # 7 YEARLY SUMMARY
        # ------------------------------------------------
        yearly_due = max(yearly_total - yearly_received, 0)

        received_percent = (yearly_received / yearly_total * 100) if yearly_total else 0
        due_percent = (yearly_due / yearly_total * 100) if yearly_total else 0

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
    try:
        search = request.GET.get("search", "").strip()
        from_date = request.GET.get("from_date")
        to_date = request.GET.get("to_date")
        user_id = request.GET.get("user_id")
        section = request.GET.get("section")
        download = request.GET.get("download")
        if from_date and not to_date:
            to_date = from_date
        if to_date and not from_date:
            from_date = to_date

        logs = AuditLog.objects.select_related(
            "userprofile__user"
        ).order_by("-created")

        if search:
            logs = logs.filter(
                Q(userprofile__user__first_name__icontains=search) |
                Q(userprofile__user__last_name__icontains=search) |
                Q(userprofile__user__email__icontains=search) |
                Q(message__icontains=search) |
                Q(action_type__icontains=search)
            )

        if from_date:
            logs = logs.filter(created__date__gte=from_date)
        if to_date:
            logs = logs.filter(created__date__lte=to_date)
        if user_id:
            logs = logs.filter(userprofile__id=user_id)
        if section:
            logs = logs.filter(section=section.lower())
        if download == "csv":

            field_names = [
                "User Name",
                "Email",
                "Section",
                "Action Type",
                "Message", 
                "Created At"
            ]

            export_data = []

            for log in logs:
                export_data.append({
                    "User Name": log.userprofile.user.get_full_name() if log.userprofile else "",
                    "Email": log.userprofile.user.email if log.userprofile else "",
                    "Section": log.section if hasattr(log, "section") else "",
                    "Action Type": log.action_type,
                    "Message": log.message,
                    "Created At": log.created.strftime("%Y-%m-%d %H:%M:%S") if log.created else ""
                })
            return export_to_csv(
                filename="audit_logs",
                field_names=field_names,
                data_list=export_data
            )
        data = []

        for log in logs:
            data.append({
                "id": log.id,
                "user": get_user_basic_info(log.userprofile),
                "section": log.section if hasattr(log, "section") else "",
                "message": log.message,
                "action_type": log.action_type,
                "created": datetime_to_epoch_millis(log.created)
            })
 
        return prepare_response(
            content=data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return prepare_response(
            message=f"Error fetching audit logs: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )