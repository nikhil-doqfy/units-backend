import os
import datetime
import json
import datetime
from user_service.models import UserProfile, Documents, Role, FAQ, Owner, Tenant, PropertyManager, DocumentType
from property.models import Unit, Property, PropertyManagmentCompany, PropertyImages, PropertyInterest, UnitImages, PropertyDocuments
from property_management.models import TermAndCondition, Country, State, City, AuditLog
from lease.models import Template, TemplateField, TemplateValue, Lease, LeaseDocuments
from payment.models import Payment, Bank
from complaint.models import Complaint
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import (
    upload_file_to_s3_base64, 
    prepare_response, 
    safe_epoch_to_datetime ,
    replace_placeholders,
    fetch_s3_presigned_url,
    export_to_csv,
    datetime_to_epoch_millis,
    generate_property_code,
    fetch_s3_presigned_url_for_download,translate_to_arabic,
    base64_to_image,

)
from utilities import status, constants
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Prefetch
from datetime import timedelta, datetime
from django.core.paginator import Paginator, EmptyPage
from property_management import settings
from django.http import FileResponse
from property_management.utils import (
    get_full_property_data,
    create_and_send_invitation,
    serialize_lease, 
    get_property_images,
    get_lease_status,
    get_location_kv,
    get_full_user_data ,
    get_tenant_detail_by_id,
    audit_logs
)
from django.db.models import Count, Q
from django.utils import timezone
from django.db import transaction
from django.utils.timezone import now
from django.utils.dateparse import parse_date
from django.db.models.functions import TruncMonth
from django.db.models import Sum
import calendar
from datetime import datetime, date
from calendar import monthrange
from dateutil.relativedelta import relativedelta
import base64
import uuid
from django.core.files.base import ContentFile


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
            content["user_role"] = [ {"key": constants.OWNER, "value": "Owner"}, {"key": constants.TENANT, "value": "Tenant"},]
        
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
            banks = Bank.objects.all()
            content["bank"] = [{"key": bank.id, "value": f"{bank.name} ({bank.branch_code}) - {bank.city.name}"}for bank in banks]

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

            
        else:   
            content[option_type] = []  
    return prepare_response(
        content=content,
        message=constants.DROPDOWN_DATA_FETCHED_SUCEESS,
        status=status.HTTP_200_OK )


@is_request_authenticated
def property_table_view(request):
    user = request.user
    search = request.GET.get("search", "").strip()
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))
    property_id = request.GET.get("property_id")
    my_property = request.GET.get("MY_PROPERTY", "").lower() == "true"
    tenancy_status = request.GET.get("tenancy_status")
    agreement_expiration = request.GET.get("agreement_expiration")

    if my_property and user.user_role == constants.TENANT:
        lease_property_id = (
        Lease.objects
        .filter(tenant=user)
        .values_list("lease_property_id", flat=True)
        .first()
    )
        if not lease_property_id:
            return prepare_response(
            message=constants.NO_PROPERTY_ASSIGNED_TO_TENANAT,
            status=status.HTTP_404_NOT_FOUND
        )
        full_data, error = get_full_property_data(lease_property_id)
        if error:
            return prepare_response(message=error, status=status.HTTP_404_NOT_FOUND)
        return prepare_response(
        content=full_data,
        message=constants.PROPERTIES_FETCHED,
        status=status.HTTP_200_OK
    )
    if property_id:
        full_data, error = get_full_property_data(property_id)
        if error:
            return prepare_response(message=error, status=status.HTTP_404_NOT_FOUND)
        return prepare_response(content=full_data, message=constants.PROPERTIES_FETCHED, status=status.HTTP_200_OK)
    if user.user_role == constants.OWNER:
        properties_qs = Unit.objects.filter(owner=user)

    elif user.user_role == constants.COMPANY_USER:
        companies_qs = PropertyManagmentCompany.objects.filter(company_user=user)
      
        if not companies_qs.exists():
            return prepare_response(
            message=constants.COMPANY_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )
        properties_qs = Unit.objects.filter(
        company__in=companies_qs
    )

    elif user.user_role == constants.TENANT:
        # properties_qs = PropertyUnit.objects.filter(lease_details__tenant=user)
        properties_qs = Unit.objects.filter(is_occupied=False)
    else:
        return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)
    properties_qs = properties_qs.select_related("owner__user", "company", "property").prefetch_related(
        Prefetch("lease_details", queryset=Lease.objects.select_related("tenant__user"))
    ).distinct()
    if tenancy_status == constants.VACANT:
        properties_qs = properties_qs.filter(is_occupied=False)
    elif tenancy_status == constants.OCCUPIED:
        properties_qs = properties_qs.filter(is_occupied=True)
    if search:
        properties_qs = properties_qs.filter(
            Q(unit_name__icontains=search) |
            Q(property__property_name__icontains=search) |
            Q(owner__user__first_name__icontains=search) |
            Q(owner__user__last_name__icontains=search) |
            Q(company__company_name__icontains=search) |
            Q(lease_details__tenant__user__first_name__icontains=search) |
            Q(lease_details__tenant__user__last_name__icontains=search)
        ).distinct()

    now = timezone.now()
    if agreement_expiration == constants.EXPIRED:
        properties_qs = properties_qs.filter(
            lease_details__lease_end_date__lt=now
        )
    elif agreement_expiration == constants.ABOUT_TO_EXPIRE:
        properties_qs = properties_qs.filter(
            lease_details__lease_end_date__gte=now,
            lease_details__lease_end_date__lte=now + timedelta(days=30)
        )
    elif agreement_expiration == constants.ONGOING:
        properties_qs = properties_qs.filter(
            lease_details__lease_end_date__gt=now + timedelta(days=30)
        )
    
    paginator = Paginator(properties_qs, limit)
    try:
        properties_page = paginator.page(page)
    except EmptyPage:
        properties_page = paginator.page(paginator.num_pages)
    data = []
    for prop in properties_page:
        lease_obj = prop.lease_details.first() 
        tenant_name = lease_obj.tenant.user.get_full_name() if lease_obj else None
        owner_name = prop.owner.user.get_full_name() if prop.owner else None
        lease_status = get_lease_status(lease_obj)
        image_data = get_property_images(prop.id, single=True)
        property_image = image_data["images"][0]["data"] if image_data["images"] else None
        tenant_profile_image = lease_obj.tenant.profile_image if lease_obj else None

        data.append({
            "property_unit_id": prop.id,
            "property_name": prop.property.property_name if prop.property else None,
            "unit_name": prop.unit_name,
            "property_code":prop.property.Property_code if prop.property else None,
            "tenant_name": tenant_name,
            "tenant_profile_image": tenant_profile_image, 
            "owner_name": owner_name,
            "company_name": prop.company.company_name if prop.company else None,
            "tenancy_status": "occupied" if prop.is_occupied else "vacant",
            "dimension":prop.dimension,
            "agreement_expiration":lease_status,
             "property_image": property_image,

        })

    pagination_meta = {
        "current_page": properties_page.number,
        "limit": limit,
        "total_records": paginator.count,
        "total_pages": paginator.num_pages
    }
   
    return prepare_response(
        content=data,
        message=constants.PROPERTIES_FETCHED,
        pagination=pagination_meta,
        status=status.HTTP_200_OK
    )



@is_request_authenticated
def create_property_unit(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST_METHOD,status=status.HTTP_405_METHOD_NOT_ALLOWED)

    data = request.data

    parent_property_id = data.get("parent_property_id")
    if not parent_property_id:
        return prepare_response(
            message=constants.PROPERTY_ID_REQUIRED,
            status=status.HTTP_400_BAD_REQUEST
        )

    parent_property = Property.objects.filter(id=parent_property_id).first()
    if not parent_property:
        return prepare_response(
            message=constants.INVALID_PROPERTY_ID,
            status=status.HTTP_404_NOT_FOUND
        )

    try:
        user_profile = request.user_profile
        company = user_profile.company

        with transaction.atomic():
            new_property_unit = Unit.objects.create(
                created_by=user_profile.user,
                property=parent_property,
                owner=None,
                company=company,
                property_code=data.get("property_code"),

                property_block=data.get("property_block"),
                property_unit_name=data.get("property_unit_name"),
                property_type=data.get("property_type"),

                land_area=data.get("land_area"),
                land_area_unit=data.get("land_area_unit"),
                land_dm_no=data.get("land_dm_no"),

                bedrooms=data.get("bedrooms"),
                area_of_property=data.get("area_of_property"),
                area_unit=data.get("area_unit"),

                apartment_floor_no=data.get("apartment_floor_no"),
                no_of_parking=data.get("no_of_parking"),
                balcony=data.get("balcony"),

                plot_no=data.get("plot_no"),
                makani_no=data.get("makani_no"),
                dewa_no=data.get("dewa_no"),

                step_status=constants.BASIC_DETAILS
            )

        audit_logs(
            request,
            f"Property unit '{new_property_unit.property_unit_name}' created",constants.CREATED
        )

        return prepare_response(
            message=constants.PROPERTY_ADDED,
            content={"property_unit_id": new_property_unit.id},
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
def save_local_base64(base64_data, original_name):
    try:
        if "," in base64_data:
            base64_str = base64_data.split(",")[1]
        else:
            base64_str = base64_data

        
        decoded_file = base64.b64decode(base64_str)
        extension = original_name.split('.')[-1] if '.' in original_name else 'jpg'
        unique_name = f"{uuid.uuid4()}.{extension}"
        return ContentFile(decoded_file, name=unique_name)
    except:
        return None

def handle_image_upload(images_data, object_id, model_class, id_field, user):   #Generic function to handle image uploads for both property and property unit

    uploaded = []

    for img in images_data:
        image_data = img.get("data")
        file_name = img.get("file_name")
        image_type = img.get("type", "INTERIOR").upper()

        if not image_data or not file_name:
            continue

        image_file = save_local_base64(image_data, file_name)
        if not image_file:
            continue

        kwargs = {
            id_field: object_id,
            "image": image_file,
            "file_name": file_name,
            "image_type": image_type,
            "created_by": user
        }

        instance = model_class.objects.create(**kwargs)
        uploaded.append({"image_id": instance.id, "url": instance.image.url})

    return uploaded

@is_request_authenticated
def property_images(request):
    if request.method == "GET":
        property_id = request.GET.get("property_id")
        if not property_id:
            return prepare_response(
                message="Property ID is required",
                status=400
            )

        images = PropertyImages.objects.filter(property_id=property_id).order_by("-id")
        final_images = [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": img.image.url if img.image else None,
                "type": img.image_type
            } for img in images
        ]
        return prepare_response(message="Success", content={"images": final_images}, status=200)

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return prepare_response(message="Invalid JSON", status=400)

        property_id = body.get("property_unit_id") or body.get("property_id")
        if not property_id:
            return prepare_response(message="Property ID is required", status=400)

        images_data = body.get("images", [])
        if not images_data:
            return prepare_response(message="No images provided", status=400)

        uploaded = handle_image_upload(images_data, property_id, PropertyImages, "property_id", request.user.user)

        if not uploaded:
            return prepare_response(message="No valid images uploaded", status=400)

        return prepare_response(message="Uploaded Successfully", content={"uploaded": uploaded}, status=201)


@is_request_authenticated
def property_unit_images(request):
    if request.method == "GET":
        unit_id = request.GET.get("property_unit_id")
        if not unit_id:
            return prepare_response(message="Property Unit ID is required", status=400)

        images = UnitImages.objects.filter(property_unit_id=unit_id).order_by("-id")
        final_images = [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": img.image.url if img.image else None,
                "type": img.image_type
            } for img in images
        ]
        return prepare_response(message="Success", content={"images": final_images}, status=200)

    elif request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return prepare_response(message="Invalid JSON", status=400)

        unit_id = body.get("property_unit_id")
        if not unit_id:
            return prepare_response(message="Property Unit ID is required", status=400)

        images_data = body.get("images", [])
        if not images_data:
            return prepare_response(message="No images provided", status=400)

        uploaded = handle_image_upload(images_data, unit_id, UnitImages, "property_unit_id", request.user.user)

        if not uploaded:
            return prepare_response(message="No valid images uploaded", status=400)

        return prepare_response(message="Uploaded Successfully", content={"uploaded": uploaded}, status=201)
    
@is_request_authenticated
def property_documents(request):
    if request.method == "GET":
        property_id = request.GET.get("property_unit_id")
        if not property_id:
            return prepare_response(message=constants.PROPERTY_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)

        property_obj = Unit.objects.filter(id=property_id).first()
        if not property_obj:
            return prepare_response(message=constants.INVALID_PROPERTY_ID,status=status.HTTP_404_NOT_FOUND)

        docs_qs = property_obj.property_documents.select_related("document").order_by("-id")

        final_docs = [
            {
                "id": mapping.id,
                "file_name": mapping.document.file_name,
                "data": fetch_s3_presigned_url(
                    mapping.document.file_path,
                    file_name=mapping.document.file_name
                ),
                "type": mapping.document_choice
            }
            for mapping in docs_qs
        ]

        property_obj.step_status = "DOCUMENTS_DETAILS"
        property_obj.save(update_fields=["step_status"])

        audit_logs(
            request,
            f"Documents fetched for property unit '{property_obj.property_unit_name}'",
            constants.VIEWED
        )

        return prepare_response(
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            content={
                "documents": final_docs,
                "property_id": property_id,
                "step_status": property_obj.step_status
            },
            status=status.HTTP_200_OK
        )
    elif request.method in ["POST", "PUT"]:
        body = request.data 

        property_id = body.get("property_unit_id")
        documents = body.get("documents", [])

        if not property_id:
            return prepare_response(message=constants.PROPERTY_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(documents, list) or (request.method == "POST" and not documents):
            return prepare_response(message=constants.DOCUMENTS_MUST_BE_LIST,status=status.HTTP_400_BAD_REQUEST)
        property_obj = Unit.objects.filter(id=property_id).first()
        if not property_obj:
            return prepare_response(message=constants.PROPERTY_NOT_FOUND,status=status.HTTP_404_NOT_FOUND)

        updated_files = []

        with transaction.atomic():
            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", constants.FLOOR_PLAN).upper()

                if not file_name or not base64_data:
                    return prepare_response(
                        message=constants.MISSING_FILE_OR_DATA,
                        status=status.HTTP_400_BAD_REQUEST
                    )

                mapping_obj = PropertyDocuments.objects.filter(
                    property=property_obj,
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
                        created_by=request.user
                    )
                    mapping_obj = PropertyDocuments.objects.create(
                        property=property_obj,
                        document=doc_obj,
                        document_choice=doc_type,
                        created_by=request.user
                    )
                    status_text = "created"

                try:
                    object_name = f"property_documents/{property_id}/{file_name}"
                    file_url = upload_file_to_s3_base64(base64_data, object_name)
                except Exception as e:
                    return prepare_response(message=f"Failed to upload {file_name}: {str(e)}",status=status.HTTP_500_INTERNAL_SERVER_ERROR)

                doc_obj.file_path = file_url
                doc_obj.save(update_fields=["file_path"])
                mapping_obj.save(update_fields=["document_choice"])

                updated_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type,
                    "status": status_text
                })

        audit_logs(
            request,
            f"Documents updated for property '{property_obj.property.property_name}' unit '{property_obj.property_unit_name}'",
            constants.UPDATED
        )

        property_obj.step_status = "DOCUMENTS_DETAILS"
        property_obj.save(update_fields=["step_status"])

        return prepare_response(
            message=constants.DOCUMENTS_UPLOAD_SUCCESS,
            content={"files": updated_files},
            status=status.HTTP_201_CREATED if request.method == "POST" else status.HTTP_200_OK
        )

    return prepare_response(message=constants.INVALID_REQUEST_METHOD,status=status.HTTP_405_METHOD_NOT_ALLOWED)
# - If `tenant_id` is provided, returns detailed info for that specific tenant along with their leases.
# - If logged-in user is an OWNER, returns leases for properties owned by them.
# - If logged-in user is a COMPANY_USER(pmc), returns leases for properties under their company.

@is_request_authenticated
def tenant_table_view(request):

    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user = request.user 
    search = request.GET.get("search", "").strip()
    tenant_id = request.GET.get("tenant_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    try:
        data = []

        if tenant_id:
            tenant_obj = UserProfile.objects.select_related('user').get(id=tenant_id, user_role=constants.TENANT)
            tenant_data = {
                "tenant_id": tenant_obj.id,
                "first_name": tenant_obj.user.first_name if tenant_obj.user else "",
                "last_name": tenant_obj.user.last_name if tenant_obj.user else "",
                "email": tenant_obj.user.email if tenant_obj.user else "",
                "contact_number": tenant_obj.contact_number,
                "city": tenant_obj.city.name if tenant_obj.city else "" ,
                "address": tenant_obj.address,
                "emirate_id": tenant_obj.emirate_id,
                "additional_address":tenant_obj.additional_address,
                "locality":tenant_obj.locality,
                "postal_code":tenant_obj.pin_code,
                "profile_image":tenant_obj.profile_image,


            }
            lease_qs = Lease.objects.filter(tenant=tenant_obj).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )
            return prepare_response(content= tenant_data, message=constants.TENANT_DETAIL_FETCHED, status=status.HTTP_200_OK)
               

            

        elif user.user_role == constants.OWNER:
            lease_qs = Lease.objects.filter(owner=user).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )

        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            lease_qs = Lease.objects.filter(
                lease_property__company=company
            ).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )
        else:
            return prepare_response(message=constants.UNAUTHORIZED_ROLE, status=status.HTTP_403_FORBIDDEN)

        if search:
            lease_qs = lease_qs.filter(
                Q(tenant__user__email__icontains=search) |
                Q(tenant__contact_number__icontains=search) |
                Q(lease_property__unit_name__icontains=search)
            )

        lease_qs = lease_qs.order_by("-id")

        paginator = Paginator(lease_qs, limit)
        try:
            lease_page = paginator.page(page)
        except EmptyPage:
            lease_page = paginator.page(paginator.num_pages)

        for lease in lease_page:
            tenant = lease.tenant
            prop_unit = lease.lease_property
            data.append({
                "lease_id": lease.id,
                "user_code":tenant.user_code if tenant else None,
                "tenant_id": tenant.id if tenant else None,
                "tenant_name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant.user else None,
                "tenant_profile_image": tenant.profile_image if tenant else None,
                "contact_number": tenant.contact_number,
                "property_assigned": prop_unit.unit_name if prop_unit else None,
                "property_id": prop_unit.id if prop_unit else None,
               "owner_name": f"{prop_unit.owner.user.first_name} {prop_unit.owner.user.last_name}" if prop_unit and prop_unit.owner else None,
                "company_name": prop_unit.company.company_name if prop_unit and prop_unit.company else None,
                "lease_start_date": lease.lease_start_date,
                "lease_end_date": lease.lease_end_date,
            })

        response_content =  data
        if tenant_id:
            response_content["tenant"] = tenant_data

        pagination_meta = {
            "current_page": lease_page.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }

        return prepare_response(
            content=response_content,
            message=constants.TENANT_DETAIL_FETCHED,
            pagination=pagination_meta,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching tenant data: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

# This view is for a logged-in PropertyManagmentCompany User(PMC).
# It fetches all Owners under the company of the logged-in user
@is_request_authenticated
def company_owners_view(request):
    user = request.user 
    search = request.GET.get("search", "").strip()
    owner_id = request.GET.get("owner_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))
    tenancy_status = request.GET.get("tenancy_status") 

    try:
        company = PropertyManagmentCompany.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
        if owner_id:
            owner = UserProfile.objects.filter(
                id=owner_id,
                user_role=constants.OWNER
            ).first()
           
            if not owner:
                return prepare_response(message=constants.OWNER_DETAILS_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            units_qs = Unit.objects.filter(
                owner=owner,
                company=company
            ).prefetch_related("lease_details", "lease_details__tenant")
            table_data = []
            for unit in units_qs:
                lease = unit.lease_details.filter(
                    lease_status="ACTIVE"
                ).first()
                is_occupied = True if lease else False
                if tenancy_status:
                    if tenancy_status == "OCCUPIED" and not is_occupied:
                        pass
                    if tenancy_status == "VACANT" and is_occupied:
                        pass
                table_data.append({
                    "property_unit_id": unit.id,
                    "property_name": unit.unit_name,
                    "owner_name": f"{owner.user.first_name} {owner.user.last_name}",
                    "tenant_name": (
                        f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}"
                        if lease and lease.tenant else None
                    ),
                    
                    "tenancy_status": "Occupied" if is_occupied else "Vacant",
                    "lease_id": lease.id if lease else None,
                    "tenant_profile_image":lease.tenant.profile_image if lease and lease.tenant else None ,
                    
                })
            return prepare_response(
                content={
                    "owner_details": {
                        "owner_id": owner.id,
                        "name": f"{owner.user.first_name} {owner.user.last_name}",
                        "email": owner.user.email,
                        "contact_number": owner.contact_number,
                        "owner_code": owner.user_code,
                        "emirate_id":owner.emirate_id,
                        "uae_residence_visa":owner.uae_residence_visa,
                        "trade_license_number":owner.trade_license_number,
                        "role":owner.user_role,

                        "owner_profile_image":owner.profile_image,
                    },
                    "table": table_data
                },
                message=constants.OWNER_TENANCY_FETCH_SUCCESS,
                status=status.HTTP_200_OK
            )
        owners_qs = UserProfile.objects.filter(
            user_role="OWNER",
            owner_properties__company=company
        ).distinct().prefetch_related(
            Prefetch(
                'owner_properties',
                queryset=Unit.objects.filter(company=company)
            )
        )

        if search:
            owners_qs = owners_qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(contact_number__icontains=search)
            )

        owners_qs = owners_qs.annotate(property_count=Count('owner_properties'))

        paginator = Paginator(owners_qs, limit)
        try:
            owners_page = paginator.page(page)
        except EmptyPage:
            owners_page = paginator.page(paginator.num_pages)

        data = []
        for owner in owners_page:
            properties = owner.owner_properties.all()
            data.append({
                "owner_id": owner.id,
                "first_name": owner.user.first_name if owner.user else "",
                "last_name": owner.user.last_name if owner.user else "",
                "email": owner.user.email if owner.user else "",
                "contact_number": owner.contact_number,
                "property_count": owner.property_count,
                "owner_code":owner.user_code,
                "properties": [{"id": prop.id, "name": prop.unit_name,"image": (
            get_property_images(prop.id, single=True).get("images")[0]
            if get_property_images(prop.id, single=True).get("images")
            else None
        )} for prop in properties]
            })

        pagination_meta = {
            "current_page": owners_page.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }

        return prepare_response(
            content=data,
            message=constants.OWNER_DETAILS_FETCHED_SUCCESS,
            pagination=pagination_meta,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching data: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    


# This view is for the logged-in user with role "OWNER".  
# It provides details of all PMC (Property Management PropertyManagmentCompany) associated with the owner's properties.
@is_request_authenticated
def owner_pmc_view(request):
    if request.method == "GET":  
        user = request.user
        company_id = request.GET.get("company_id")
        search = request.GET.get("search", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        try:
            if user.user_role == "OWNER" and not company_id:

                properties = Unit.objects.filter(owner=user)
                pmc_ids = properties.values_list('company__company_user', flat=True).distinct()
                pmc_qs = UserProfile.objects.filter(
                      id__in=pmc_ids,
                     user_role="COMPANY_USER"
                     ).prefetch_related(
                 'company_user'  
                        )

                if search:
                    pmc_qs = pmc_qs.filter(
                        Q(user__first_name__icontains=search) |
                        Q(user__last_name__icontains=search) |
                        Q(user__email__icontains=search)
                    )

                paginator = Paginator(pmc_qs, limit)
                try:
                    pmc_page = paginator.page(page)
                except EmptyPage:
                    pmc_page = paginator.page(paginator.num_pages)

                data = []
                for pmc in pmc_page:
                    companies = pmc.company_user.all()
                    for comp in companies:
                        owner_props = Unit.objects.filter(owner=user, company=comp)
                        leased_count = Lease.objects.filter(
                            lease_property__in=owner_props
                        ).count()
                        total_count = owner_props.count()
                        tenancy_ratio = f"{leased_count}:{total_count}" if total_count else "0:0"
                        data.append({
                            "company_id": comp.id,
                            "company_name": comp.company_name,
                            "company_address": comp.company_address,
                            "property_handling": f"{total_count} property",
                            "tenancy_ratio": tenancy_ratio,
                            "compnay_code":comp.company_code,
                        })

                pagination_meta = {
                    "current_page": pmc_page.number,
                    "limit": limit,
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages
                }

                return prepare_response(
                    content=data,
                    message=constants.PROPERTY_MANAGER_COMPANY_DETAILS_SUCCESS,
                    pagination=pagination_meta,
                    status=status.HTTP_200_OK
                )

            elif company_id:
                if user.user_role != constants.OWNER:
                    return prepare_response(message="Only owner can access this data",status=status.HTTP_403_FORBIDDEN)
                company = PropertyManagmentCompany.objects.select_related("company_user__user").filter(id=company_id).first()
                if not company:
                    return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                properties_qs = Unit.objects.filter(owner=user,company=company ).select_related("property" ).prefetch_related( "lease_details__tenant__user")

                if search:
                    properties_qs = properties_qs.filter(Q(unit_name__icontains=search) | Q(property__property_name__icontains=search))
                paginator = Paginator(properties_qs, limit)
                try:
                    property_page = paginator.page(page)
                except EmptyPage:
                    property_page = paginator.page(paginator.num_pages)
                properties_data = []
                for prop in property_page:
                    lease = prop.lease_details.first()
                    tenant_name = None
                    lease_id = None
                    tenancy_status = "Vacant"
                    if lease and lease.tenant:
                        tenant_user = lease.tenant.user
                        tenant_name = f"{tenant_user.first_name} {tenant_user.last_name}".strip()
                        lease_id = lease.id
                        tenancy_status = "Occupied"
                    properties_data.append({"property_unit_id": prop.id,"property_name": prop.unit_name or (
                                  prop.property.property_name if prop.property else None
                                   ),"tenant_name": tenant_name,
                                   "tenancy_status": tenancy_status,
                                    "dimension": prop.dimension,
                                    "lease_id": lease_id,
                                          })
                pmc_user = company.company_user
                pmc_profile = {
                          "company_id": company.id,
                           "company_code": company.company_code,
                         "company_name": company.company_name,
                        "email": pmc_user.user.email,
                       "first_name": pmc_user.user.first_name,
                       "last_name": pmc_user.user.last_name,
                        "postal_code": pmc_user.pin_code,
                        "profile_image": pmc_user.profile_image,
                          "total_properties_handled": Unit.objects.filter(
                          owner=user,
                          company=company
                             ).count()
                                    }
                pagination_meta = {
                    "current_page": property_page.number,
                    "limit": limit,
                    "total_records": paginator.count,
                     "total_pages": paginator.num_pages
                            }
                return prepare_response(
                    content={"company_profile": pmc_profile, "properties": properties_data},
                    message=constants.PMC_PROFILE_PROPERTY_SUCCESS,
                    pagination=pagination_meta,
                    status=status.HTTP_200_OK)

            else:
                return prepare_response(message=constants.UNAUTHORIZED_OR_MISSING_PARAMETERS, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            return prepare_response(
                message=f"Error fetching data: {str(e)}",
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    else:
        return prepare_response(
            message=f"Invalid HTTP method: {request.method}",
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


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
                step_status=body.get("step_status", "LEASE_DETAILS"),
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
                "lease_number", "lease_remarks", "step_status", "lease_status",
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
                    "step_status": lease_obj.step_status
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

            lease_obj.step_status = "UPLOAD_EJARI"
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






# def parent_property_view(request):
#     if request.method == "GET":
#         property_id = request.GET.get("id")

#         if not property_id:
#             return prepare_response(
#                 message=constants.PROPERTY_ID_REQUIRED,
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#         prop = Property.objects.select_related("city").filter(id=property_id).first()

#         if not prop:
#             return prepare_response(
#                 message=constants.PROPERTY_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )

#         data = {
#             "id": prop.id,
#             "property_name": prop.property_name,
#             "total_floors": prop.total_floors,
#             "total_units": prop.total_units,
#             "additional_address": prop.additional_address,
#             "locality": prop.locality,
#             "postal_code": prop.postal_code,
#             "property_code": prop.Property_code,
#              "property_type": {
#              "key": prop.property_type_options,
#              "value": prop.get_property_type_options_display()},
#             "city": {
#                 "key": prop.city.id if prop.city else None,
#                 "value": prop.city.name if prop.city else None
#             },
#             "state":{
#                 "key": prop.city.state.id if prop.city.state else None,
#                 "value": prop.city.state.name if prop.city.state else None
#             },
#             "country":{
#                 "key": prop.city.state.country.id if prop.city.state.country else None,
#                 "value": prop.city.state.country.name if prop.city.state.country else None
#             }
#         }

#         return prepare_response(
#             content=data,
#             message=constants.PROPERTY_FETCH_SUCCESS,
#             status=status.HTTP_200_OK
#         )

#     else:
#         return prepare_response(
#             message=constants.INVALID_REQUEST_METHOD,
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )

def parent_property_view(request):
    if request.method == "GET":
        property_id = request.GET.get("id")

        if not property_id:
            return prepare_response(
                message=constants.PROPERTY_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        prop = Property.objects.filter(id=property_id).first()

        if not prop:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            "id": prop.id,
            "property_name": prop.property_name,
            "no_of_blocks": prop.no_of_blocks,
            "no_of_units": prop.no_of_units,
            "property_type": {
                "key": prop.property_type,
                "value": prop.get_property_type_display()
            },
            "land_area": prop.land_area,
            "land_area_unit": prop.land_area_unit,
            "land_dm_no": prop.land_dm_no,
            "plot_no": prop.plot_no,
            "makani_no": prop.makani_no,
            "dewa_no": prop.dewa_no,
            "address_line_1": prop.address_line_1,
            "address_line_2": prop.address_line_2,
            "landmark": prop.landmark,
            "pincode": prop.pincode,
            "latitude": prop.latitude,
            "longitude": prop.longitude,
            "map_address": prop.map_address,
            "property_pmc": {
                "id": prop.property_pmc.id if prop.property_pmc else None,
                "name": prop.property_pmc.company_name if prop.property_pmc else None,
            }
        }

        return prepare_response(
            content=data,
            message=constants.PROPERTY_FETCH_SUCCESS,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )




# -----------------------------------All Exports API--------------------------------------------------------------



@is_request_authenticated
def export_property_table_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        search = request.GET.get("search", "").strip()
        if user.user_role == constants.OWNER:
            properties_qs = Unit.objects.filter(owner=user)

        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            properties_qs = Unit.objects.filter(company=company)

        elif user.user_role == constants.TENANT:
            properties_qs = Unit.objects.filter(
                lease_details__tenant=user
            )

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_USER_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )

        properties_qs = properties_qs.select_related(
            "owner__user", "company", "property"
        ).prefetch_related(
            Prefetch(
                "lease_details",
                queryset=Lease.objects.select_related("tenant__user")
            )
        ).distinct()
        if search:
            properties_qs = properties_qs.filter(
                Q(unit_name__icontains=search) |
                Q(property__property_name__icontains=search) |
                Q(owner__user__first_name__icontains=search) |
                Q(owner__user__last_name__icontains=search) |
                Q(company__company_name__icontains=search) |
                Q(lease_details__tenant__user__first_name__icontains=search) |
                Q(lease_details__tenant__user__last_name__icontains=search)
            ).distinct()

        export_data = []

 
        if user.user_role == constants.OWNER:
            field_names = [
                "Property Name",
                "Tenant Name",
                "Agreement Expiration",
                "Dimension",
                "PropertyManagmentCompany Name"
            ]

            for prop in properties_qs:
                lease = prop.lease_details.first()
                export_data.append({
                    "Property Name": prop.property.property_name if prop.property else "",
                    "Tenant Name": lease.tenant.user.get_full_name() if lease else "",
                    "Agreement Expiration": get_lease_status(lease),
                    "Dimension": prop.area_of_property,
                    "PropertyManagmentCompany Name": prop.company.company_name if prop.company else ""
                })

   
        elif user.user_role == constants.COMPANY_USER:
            field_names = [
                "Property ID",
                "Property Name",
                "Tenant Name",
                "Owner Name",
                "Tenancy Status"
            ]

            for prop in properties_qs:
                lease = prop.lease_details.first()
                export_data.append({
                    "Property ID": prop.id,
                    "Property Name": prop.property.property_name if prop.property else "",
                    "Tenant Name": lease.tenant.user.get_full_name() if lease else "",
                    "Owner Name": prop.owner.user.get_full_name() if prop.owner else "",
                    "Tenancy Status": "Occupied" if prop.is_occupied else "Available"
                })

   
        elif user.user_role == constants.TENANT:
            field_names = [
                "Property Name",
                "Owner Name",
                "Tenancy Status",
                "Dimension",
                "PropertyManagmentCompany Name"
            ]

            for prop in properties_qs:
                export_data.append({
                    "Property Name": prop.property.property_name if prop.property else "",
                    "Owner Name": prop.owner.user.get_full_name() if prop.owner else "",
                    "Tenancy Status": "Occupied" if prop.is_occupied else "Available",
                    "Dimension": prop.area_of_property,
                    "PropertyManagmentCompany Name": prop.company.company_name if prop.company else ""
                })

        return export_to_csv(
            filename="property_table",
            field_names=field_names,
            data_list=export_data
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def complaint(request):
    user_profile = request.user

    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message")

            if not message:
                return prepare_response(
                    message=constants.MESSAGE_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            complaint = Complaint.objects.create(
                user=user_profile,
                message=message,
                created_by=request.user.user
            )

            return prepare_response(
                message=constants.COMPLAINT_RAISED_SUCCESS,
                status=status.HTTP_201_CREATED,
                content={
                    "id": complaint.id,
                    "message": complaint.message
                }
            )

        except Exception as e:
            return prepare_response(
                message=str(e),
                status=status.HTTP_400_BAD_REQUEST
            )

    elif request.method == "GET":
        login_user = request.user
        complaints_qs = Complaint.objects.none()

        # ================= ROLE BASED FILTER (UNCHANGED) =================
        if login_user.user_role == constants.TENANT:
            complaints_qs = Complaint.objects.filter(user=login_user)

        elif login_user.user_role == constants.OWNER:
            complaints_qs = Complaint.objects.filter(
                user__tenant_leases__lease_property__owner=login_user
            ).distinct()

        elif login_user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=login_user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            complaints_qs = Complaint.objects.filter(
                user__tenant_leases__lease_property__company=company
            ).distinct()

        else:
            return prepare_response(
                message="Invalid user role",
                status=status.HTTP_400_BAD_REQUEST
            )

        # ================= STATUS FILTER (UNCHANGED) =================
        status_param = request.GET.get("status")
        if status_param:
            status_list = [s.strip() for s in status_param.split(",")]

            VALID_STATUSES = {
                constants.IN_PROGRESS,
                constants.COMPLETED,
                constants.ASSIGNED_ENGINEER,
                constants.REJECTED,
            }

            invalid_status = set(status_list) - VALID_STATUSES
            if invalid_status:
                return prepare_response(
                    message=f"Invalid status value(s): {', '.join(invalid_status)}",
                    status=status.HTTP_400_BAD_REQUEST
                )

            complaints_qs = complaints_qs.filter(status__in=status_list)
        property_unit_id = request.GET.get("property_unit_id")
        if property_unit_id:
            if not property_unit_id.isdigit():
                return prepare_response(message="Invalid property_unit_id",status=status.HTTP_400_BAD_REQUEST)
            complaints_qs = complaints_qs.filter(user__tenant_leases__lease_property__id=property_unit_id).distinct()
        

        # ================= SEARCH FILTER (NEW) =================
        search = request.GET.get("search", "").strip()
        if search:
            complaints_qs = complaints_qs.filter(
                Q(id__icontains=search) |
                Q(user__user__first_name__icontains=search) |
                Q(user__user__last_name__icontains=search) |
                Q(user__tenant_leases__lease_property__unit_name__icontains=search)
            ).distinct()

        complaints_qs = complaints_qs.select_related(
            "user", "user__user"
        ).order_by("-created")

        # ================= SUMMARY COUNTS (UNCHANGED) =================
        total_complaints = complaints_qs.count()
        total_completed = complaints_qs.filter(status=constants.COMPLETED).count()
        total_in_progress = complaints_qs.filter(status=constants.IN_PROGRESS).count()
        total_rejected = complaints_qs.filter(status=constants.REJECTED).count()

        # ================= PAGINATION (NEW) =================
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))

        paginator = Paginator(complaints_qs, limit)
        try:
            complaints_page = paginator.page(page)
        except EmptyPage:
            complaints_page = paginator.page(paginator.num_pages)

        complaint_list = []

        for complaint_obj in complaints_page:
            tenant = complaint_obj.user

            lease = Lease.objects.filter(
                tenant=tenant
            ).select_related("lease_property").first()

            unit_name = None
            property_image = None

            if lease and lease.lease_property:
                property_obj = lease.lease_property
                unit_name = property_obj.unit_name

                image_data = get_property_images(
                    property_id=property_obj.id,
                    single=True
                )
                if not image_data.get("error") and image_data.get("images"):
                    property_image = image_data["images"][0]["data"]

            complaint_list.append({
                "complaint_id": complaint_obj.id,
                "unit_name": unit_name,
                "property_unit_id":property_obj.id,
                "description": complaint_obj.message,
                "raised_by_email": tenant.user.email,
                "raised_by_name": tenant.user.first_name,
                "status": {
                    "key": complaint_obj.status,
                    "value": complaint_obj.get_status_display()
                },
                "raised_date": datetime_to_epoch_millis(complaint_obj.created),
                "property_image": property_image,

                "raised_by_image": tenant.profile_image
            })

        return prepare_response(
            content={
                "summary": {
                    "total_complaints": total_complaints,
                    "total_completed": total_completed,
                    "total_in_progress": total_in_progress,
                    "total_rejected": total_rejected,
                },
                "complaints": complaint_list
            },
            pagination={
                "current_page": complaints_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            },
            message="Complaints fetched successfully",
            status=status.HTTP_200_OK
        )

    elif request.method == "PUT":
        pass

    elif request.method == "DELETE":
        pass

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
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





@is_request_authenticated
def export_tenant_csv(request):
    """
    Export simple tenant table as CSV:
    Columns: Tenant Name, User Code, Contact Number, Property Assigned
    Works for OWNER and COMPANY_USER
    """
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        search = request.GET.get("search", "").strip()
        lease_qs = Lease.objects.select_related(
            "tenant",
            "tenant__user",
            "lease_property",
        )
        if user.user_role == constants.OWNER:
            lease_qs = lease_qs.filter(owner=user)

        elif user.user_role == constants.COMPANY_USER:
            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_400_BAD_REQUEST
                )
            lease_qs = lease_qs.filter(lease_property__company=company)

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ROLE,
                status=status.HTTP_403_FORBIDDEN
            )
        if search:
            lease_qs = lease_qs.filter(
                Q(tenant__user__email__icontains=search) |
                Q(tenant__contact_number__icontains=search) |
                Q(lease_property__unit_name__icontains=search)
            )

        lease_qs = lease_qs.order_by("-id")
        field_names = [
            "Tenant Name",
            "User Code",
            "Contact Number",
            "Property Assigned",
        ]

        export_data = []

        for lease in lease_qs:
            tenant = lease.tenant
            prop = lease.lease_property

            export_data.append({
                "Tenant Name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant and tenant.user else "",
                "User Code": tenant.user_code if tenant else "",
                "Contact Number": tenant.contact_number if tenant else "",
                "Property Assigned": prop.unit_name if prop else "",
            })
        return export_to_csv(
            filename="tenant_simple_export",
            field_names=field_names,
            data_list=export_data
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting tenant CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




@is_request_authenticated
def export_owner_pmc_csv(request):

    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        company_id = request.GET.get("company_id")
        search = request.GET.get("search", "").strip()


        if user.user_role == constants.OWNER and not company_id:

            properties = Unit.objects.filter(owner=user)
            pmc_ids = properties.values_list(
                'company__company_user', flat=True
            ).distinct()

            pmc_qs = UserProfile.objects.filter(
                id__in=pmc_ids,
                user_role=constants.COMPANY_USER
            ).prefetch_related("company_user")

            if search:
                pmc_qs = pmc_qs.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search)
                )

            field_names = [
                "PropertyManagmentCompany Code",
                "PropertyManagmentCompany Name",
                "PropertyManagmentCompany Address",
                "Property Handling Count",
                "Tenancy Ratio",
            ]

            data_list = []

            for pmc in pmc_qs:
                for comp in pmc.company_user.all():
                    owner_props = Unit.objects.filter(
                        owner=user,
                        company=comp
                    )

                    total_props = owner_props.count()
                    leased_props = Lease.objects.filter(
                        lease_property__in=owner_props
                    ).count()

                    tenancy_ratio = f"{leased_props}:{total_props}" if total_props else "0:0"

                    data_list.append({
                        "PropertyManagmentCompany Code": comp.company_code,
                        "PropertyManagmentCompany Name": comp.company_name,
                        "PropertyManagmentCompany Address": comp.company_address,
                        "Property Handling Count": total_props,
                        "Tenancy Ratio": tenancy_ratio,
                    })

            return export_to_csv(
                filename="pmc_company_table",
                field_names=field_names,
                data_list=data_list
            )

        # -------------------------------
        # CASE 2: PROPERTY LIST (company_id present)
        # -------------------------------
        elif user.user_role == constants.OWNER and company_id:

            company = PropertyManagmentCompany.objects.filter(id=company_id).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            properties_qs = Unit.objects.filter(
                owner=user,
                company=company
            ).select_related("property").prefetch_related(
                "lease_details__tenant__user"
            )

            if search:
                properties_qs = properties_qs.filter(
                    Q(unit_name__icontains=search) |
                    Q(property__property_name__icontains=search)
                )

            field_names = [
                "Property Code",
                "Property Name",
                "Tenant Name",
                "Tenancy Status",
                "Dimension / Bedroom",
            ]

            data_list = []

            for prop in properties_qs:
                lease = prop.lease_details.first()

                tenant_name = ""
                tenancy_status = "Vacant"

                if lease and lease.tenant and lease.tenant.user:
                    tenant_user = lease.tenant.user
                    tenant_name = f"{tenant_user.first_name} {tenant_user.last_name}".strip()
                    tenancy_status = "Occupied"

                data_list.append({
                    "Property Code": prop.property_code,
                    "Property Name": prop.unit_name or (
                        prop.property.property_name if prop.property else ""
                    ),
                    "Tenant Name": tenant_name,
                    "Tenancy Status": tenancy_status,
                    "Dimension / Bedroom": prop.dimension,
                })

            return export_to_csv(
                filename="pmc_property_table",
                field_names=field_names,
                data_list=data_list
            )

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED_ACCESS,
                status=status.HTTP_403_FORBIDDEN
            )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
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






@is_request_authenticated
def export_company_owners_csv(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        user = request.user
        owner_id = request.GET.get("owner_id")
        search = request.GET.get("search", "").strip()
        tenancy_status = request.GET.get("tenancy_status")

        company = PropertyManagmentCompany.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )


        if not owner_id:
            owners_qs = UserProfile.objects.filter(
                user_role=constants.OWNER,
                owner_properties__company=company
            ).distinct().annotate(
                property_count=Count("owner_properties")
            )

            if search:
                owners_qs = owners_qs.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(contact_number__icontains=search)
                )

            field_names = [
                "Owner Name",
                "Code",
                "Contact Number",
                "Properties",
                "Email Address"
            ]

            data_list = []

            for owner in owners_qs:
                data_list.append({
                    "Owner Name": f"{owner.user.first_name} {owner.user.last_name}".strip(),
                    "Code": owner.user_code,
                    "Contact Number": owner.contact_number,
                    "Properties": owner.property_count,
                    "Email Address": owner.user.email if owner.user else ""
                })

            return export_to_csv(
                filename="company_owners",
                field_names=field_names,
                data_list=data_list
            )

        owner = UserProfile.objects.filter(
            id=owner_id,
            user_role=constants.OWNER
        ).first()

        if not owner:
            return prepare_response(
                message=constants.OWNER_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        units_qs = Unit.objects.filter(
            owner=owner,
            company=company
        ).prefetch_related("lease_details", "lease_details__tenant__user")

        field_names = [
            "Code",
            "Property Name",
            "Tenant Name",
            "Tenancy Status",
            "Agreement"
        ]

        data_list = []

        for unit in units_qs:
            lease = unit.lease_details.filter(lease_status="ACTIVE").first()
            is_occupied = True if lease else False

            if tenancy_status:
                if tenancy_status == "OCCUPIED" and not is_occupied:
                    continue
                if tenancy_status == "VACANT" and is_occupied:
                    continue

            data_list.append({
                "Code": unit.property_code,
                "Property Name": unit.unit_name,
                "Tenant Name": (
                    f"{lease.tenant.user.first_name} {lease.tenant.user.last_name}"
                    if lease and lease.tenant and lease.tenant.user
                    else ""
                ),
                "Tenancy Status": "Occupied" if is_occupied else "Vacant",
                "Agreement": lease.id if lease else ""
            })

        return export_to_csv(
            filename="owner_properties",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting owner CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@is_request_authenticated
def toggle_property_interest(request):
    if request.method != "PUT":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        data = json.loads(request.body)

        property_unit_id = data.get("property_unit_id")
        is_interested = data.get("is_interested")

        if property_unit_id  is None or is_interested is None:
            return prepare_response(
                message=constants.INVALID_DATA,
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant = request.user 

        if tenant.user_role != constants.TENANT:
            return prepare_response(
                message=constants.ONLY_TENANT_ALLOWED,
                status=status.HTTP_403_FORBIDDEN
            )

        property_unit = Unit.objects.filter(
            id=property_unit_id,
            is_active=True
        ).first()

        if not property_unit:
            return prepare_response(
                message=constants.PROPERTY_UNIT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        with transaction.atomic():
            interest_obj, created = PropertyInterest.objects.update_or_create(
                property_unit=property_unit,
                tenant=tenant,
                defaults={
                    "is_active": is_interested,
                    "created_by": tenant.user
                }
            )
            if is_interested:
                PropertyInterest.objects.filter(
                    id=interest_obj.id
                ).update(created=timezone.now())

        return prepare_response(
            message=constants.INTEREST_UPDATED_SUCCESS,
            status=status.HTTP_200_OK,
            content={
                "property_unit": property_unit.unit_name,
                "is_interested": is_interested
            }
        )

    except Exception as e:
        print("Interest API Error:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def company_tenants(request):
    user = request.user
    tenant_status = request.GET.get("tenant_status", constants.PENDING)


    if user.user_role != constants.COMPANY_USER:
        return prepare_response(
            message=constants.ONLY_COMPANY_USER_ALLOWED,
            status=status.HTTP_403_FORBIDDEN
        )

    try:
        if request.method == "GET":

            tenant_id = request.GET.get("tenant_id")

            company = PropertyManagmentCompany.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            if tenant_id:
                data = get_full_user_data(tenant_id)
                return prepare_response(
                    content=data,
                    message=constants.DATA_FETCHED_SUCCESSFULLY,
                    status=status.HTTP_200_OK
                )

           
            tenants_created = UserProfile.objects.filter(
                created_by=user.user,
                user_role=constants.TENANT,
                is_active=True,
                tenant_status=tenant_status
            )

           
            tenants_interested = UserProfile.objects.filter(
                interested_properties__property_unit__company=company,
                interested_properties__is_active=True,
                user_role=constants.TENANT,
                tenant_status=tenant_status
            )

            tenants = (tenants_created | tenants_interested).distinct().select_related(
                "city", "city__state", "city__state__country"
            )

            tenant_list = [
                {
                    "tenant_id": t.id,
                    "name": f"{t.user.first_name} {t.user.last_name}",
                    "email": t.user.email,
                    "contact_number": t.contact_number,
                    "emirates_id": t.emirate_id,
                    "profile_image": t.profile_image,
                    "user_code": t.user_code,
                    "locality": t.locality,
                    "role": t.user_role,
                    "tenant_status": t.tenant_status,
                    "city": t.city.name if t.city else None,
                    "state": t.city.state.name if t.city and t.city.state else None,
                    "country": (
                        t.city.state.country.name
                        if t.city and t.city.state and t.city.state.country
                        else None
                    ),
                }
                for t in tenants
            ]

            return prepare_response(
                message=constants.TENANT_DETAILS_FETCHED_SUCCESS,
                content={"tenants": tenant_list},
                status=status.HTTP_200_OK
            )
        elif request.method == "PUT":

            data = json.loads(request.body)
            tenant_id = data.get("tenant_id")
            tenant_status = data.get("tenant_status") 

            # if not tenant_id or tenant_status not in [
            #     constants.APPROVED,
            #     constants.REJECTED
            # ]:
            #     return prepare_response(
            #         message="data not found ",
            #         status=status.HTTP_400_BAD_REQUEST
            #     )

            tenant = UserProfile.objects.filter(
                id=tenant_id,
                user_role=constants.TENANT,
                is_active=True
            ).first()

            if not tenant:
                return prepare_response(
                    message=constants.TENANT_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            tenant.tenant_status = tenant_status
            tenant.save(update_fields=["tenant_status", "modified"])

            return prepare_response(
                message=constants.TENANT_DETAILS_UPDATED_SUCCESSFULLY,
                content={
                    "tenant_id": tenant.id,
                    "tenant_status": tenant.tenant_status
                },
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message=constants.INVALID_REQUEST,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        print("PropertyManagmentCompany Tenants API Error:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
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
                payments = Payment.objects.filter(rental_account_id=lease_id)
            elif payment_id:
                payments = Payment.objects.filter(id=payment_id)
            else:
                return prepare_response(
                    message="lease_id or payment_id is required",
                    status=status.HTTP_400_BAD_REQUEST
                )
            data = []
            for p in payments:
                data.append({
                    "id": p.id,
                    "lease_id": p.rental_account.id if p.rental_account else None,
                    "amount": p.amount,
                    "method": p.method,
                    "reason_type": p.reason_type,
                    "status": p.status,
                    "payee_name": p.payee_name,
                    "payee_email": p.payee_email,
                    "payee_contact": p.payee_contact,
                    "account_number": p.account_number,
                    "cheque_number": p.cheque_number,
                    "cheque_date": int(p.cheque_date.timestamp()) if p.cheque_date else None,
                    "bank": {
                        "id": p.bank.id,
                        "name": p.bank.name,
                        "branch_name": p.bank.branch_name,
                        "swift_code": p.bank.swift_code
                    } if p.bank else None
                })

            return prepare_response(
                content=data if lease_id else data[0],
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

            bank = None
            if body.get("bank_id"):
                bank = Bank.objects.filter(id=body.get("bank_id")).first()
            scanned_image = None
            if body.get("scanned_image_base64"):
                scanned_image = base64_to_image(body.get("scanned_image_base64"))

            payment = Payment.objects.create(
                created_by=user.user,
                rental_account=lease,
                bank=bank,
                method=body.get("method"),
                reason_type=body.get("reason_type"),
                amount=body.get("amount", 0),
                payee_name=body.get("payee_name"),
                payee_email=body.get("payee_email"),
                payee_contact=body.get("payee_contact"),
                account_number=body.get("account_number"),
                cheque_number=body.get("cheque_number"),
                cheque_date=safe_epoch_to_datetime(body.get("cheque_date"))
                if body.get("cheque_date") else None,
                scanned_image=scanned_image,
                status=body.get("status")
            )

            audit_logs(
                request,
                f"Created payment of {payment.amount} for Lease {lease.id}", 
                constants.CREATED
            )

            return prepare_response(
                message="Payment created successfully",
                content={"payment_id": payment.id},
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

            payment = Payment.objects.filter(id=payment_id).first()
            if not payment:
                return prepare_response(
                    message="Payment not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            if body.get("bank_id"):
                bank = Bank.objects.filter(id=body.get("bank_id")).first()
                if not bank:
                    return prepare_response(
                        message="Invalid bank_id",
                        status=status.HTTP_400_BAD_REQUEST
                    )
                payment.bank = bank

            for field in [
                "method", "reason_type", "amount", "payee_name",
                "payee_email", "payee_contact", "account_number",
                "cheque_number", "status"
            ]:
                if field in body:
                    setattr(payment, field, body[field])

            if body.get("cheque_date"):
                payment.cheque_date = safe_epoch_to_datetime(body.get("cheque_date"))

            payment.save()

            audit_logs(
               request,
                f"Updated payment {payment.id}",
               constants.UPDATED
            )

            return prepare_response(
                message="Payment updated successfully",
                content={"payment_id": payment.id},
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

@is_request_authenticated
def audit_log(request):

    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    logs = AuditLog.objects.select_related("userprofile__user").order_by("-created")

    data = []

    for log in logs:
        data.append({
            "id": log.id,
            "user": log.userprofile.get_user_basic_info() if log.userprofile else None,
            "message": log.message,
            "action_type": log.action_type,
            "created": datetime_to_epoch_millis(log.created)
        })

    return prepare_response(
        content=data,
        message=constants.DATA_FETCHED_SUCCESSFULLY,
        status=status.HTTP_200_OK
    )

def company_list(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    search = request.GET.get("search", "").strip()
    companies = PropertyManagmentCompany.objects.filter(is_active=True).order_by("name")
    if search:
        companies = companies.filter(name__icontains=search)
    content = [{"key": c.id, "value": c.name, "code": c.code} for c in companies]
    return prepare_response(content=content, status=status.HTTP_200_OK)
