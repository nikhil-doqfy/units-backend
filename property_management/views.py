import os
import datetime
import pdfkit
import json
import datetime
from user_service.models import UserProfile, Documents, PropertyUnitDetails,\
    Property, Company, PropertyImages ,PropertyDocumentsMapping, Country, State, City, Role
from property_management.models import LeasePropertyDetails,TemplateFields, TemplateValues,Template
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import (
    upload_file_to_s3_base64, 
    prepare_response, 
    safe_epoch_to_datetime ,
    replace_placeholders,
    fetch_s3_presigned_url,
    export_to_csv,
    datetime_to_epoch_millis,
    get_pdfkit_config,
    generate_property_code,
)
from utilities import status, constants
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models import Count
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
    get_lease_status
)
from django.db.models import Count, Q
from django.utils import timezone




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
            properties = Property.objects.all()
            content["property"] = [
                          {"key": p.id , "value": p.property_name}for p in properties]
        elif option_type == "PROPERTY_TYPE":
            content["property_type"] = [
                {"key": key, "value": value }
                for key, value in constants.PROPERTY_TYPE_CHOICES]
            
        elif option_type == "PROPERTY_UNIT":
            if user.user_role == constants.OWNER:
                units = PropertyUnitDetails.objects.filter(owner=user)
            elif user.user_role == constants.COMPANY_USER:
                units = PropertyUnitDetails.objects.filter(company=user.company)
            else:
                units = PropertyUnitDetails.objects.none()
            content["property_unit"] = [
        {"key": u.id, "value": u.property_unit_name or "Unnamed Unit"} for u in units
    ]
        elif option_type == "TENANTS":
            tenants = UserProfile.objects.filter(user_role=constants.TENANT)
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
        elif option_type == "ROLE":
            company = Company.objects.filter(company_user=user,is_active=True).first()
            if not company:
                content["role"] = []
               
            else:
                roles = Role.objects.filter(company=company,is_active=True)
                content["role"] = [{"key": r.id, "value": r.name}for r in roles]
                
        # ---------- Fetched rental accoubt lease ----------
        elif option_type == "RENTAL_ACCOUNT_LEASE":
            leases = LeasePropertyDetails.objects.filter(lease_status=constants.ACTIVE)
            content["lease_data"] = [
                {
                    "key": lease.id,
                    "value": lease.lease_number
                }
                for lease in leases
            ]          
        else:
            content[option_type] = []
            
    return prepare_response(
        content=content,
        message=constants.DROPDOWN_DATA_FETCHED_SUCEESS,
        status=status.HTTP_200_OK
    )


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
        LeasePropertyDetails.objects
        .filter(tenant=user)
        .values_list("lease_property_id", flat=True)
        .first()
    )
        if not lease_property_id:
            return prepare_response(
            message="No property assigned to this tenant",
            status=status.HTTP_404_NOT_FOUND
        )
        full_data, error = get_full_property_data(lease_property_id)
        if error:
            return prepare_response(message=error, status=status.HTTP_404_NOT_FOUND)
        return prepare_response(
        content=full_data,
        message="Property details fetched successfully",
        status=status.HTTP_200_OK
    )
    if property_id:
        full_data, error = get_full_property_data(property_id)
        if error:
            return prepare_response(message=error, status=status.HTTP_404_NOT_FOUND)
        return prepare_response(content=full_data, message="Property details fetched successfully", status=status.HTTP_200_OK)
    if user.user_role == constants.OWNER:
        properties_qs = PropertyUnitDetails.objects.filter(owner=user)

    elif user.user_role == constants.COMPANY_USER:
        companies_qs = Company.objects.filter(company_user=user)
      
        if not companies_qs.exists():
            return prepare_response(
            message=constants.COMPANY_NOT_FOUND,
            status=status.HTTP_400_BAD_REQUEST
        )
        properties_qs = PropertyUnitDetails.objects.filter(
        company__in=companies_qs
    )

    elif user.user_role == constants.TENANT:
        properties_qs = PropertyUnitDetails.objects.filter(lease_details__tenant=user)
    else:
        return prepare_response(message="Unauthorized user role", status=status.HTTP_403_FORBIDDEN)
    properties_qs = properties_qs.select_related("owner__user", "company", "property").prefetch_related(
        Prefetch("lease_details", queryset=LeasePropertyDetails.objects.select_related("tenant__user"))
    ).distinct()
    if tenancy_status == constants.VACANT:
        properties_qs = properties_qs.filter(is_occupied=False)
    elif tenancy_status == constants.OCCUPIED:
        properties_qs = properties_qs.filter(is_occupied=True)
    if search:
        properties_qs = properties_qs.filter(
            Q(property_unit_name__icontains=search) |
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
            "property_unit_name": prop.property_unit_name,
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
        message="Properties fetched successfully",
        pagination=pagination_meta,
        status=status.HTTP_200_OK
    )


@is_request_authenticated
def save_property(request):
    user_profile = request.user
    if request.method == "GET":
        try:
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            prop = PropertyUnitDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            parent_property = prop.property
            property_type_options = dict(constants.PROPERTY_TYPE_CHOICES)

            property_data = None
            if parent_property:
                property_data = {
                    "id": parent_property.id,
                    "property_name": parent_property.property_name,
                    "property_code": parent_property.Property_code,
                    "additional_address": parent_property.additional_address,
                    "locality": parent_property.locality,
                    "postal_code": parent_property.postal_code,
                    "city_id": parent_property.city.id if parent_property.city else None,
                    "property_type": {
                        "key": parent_property.property_type_options,
                        "value": property_type_options.get(parent_property.property_type_options)
                    }
                }
            content = {
                "id": prop.id,
                "property_unit_name": prop.property_unit_name,
                "land_dm_no": prop.land_dm_no,
                "area_of_property": prop.area_of_property,
                "no_of_parking": prop.no_of_parking,
                "bedrooms": prop.bedrooms,
                "balcony": prop.balcony,
                "plot_no": prop.plot_no,
                "area_unit": prop.area_unit,
                "land_area_unit": prop.land_area_unit,
                "dimension": prop.dimension,
                "property_code": prop.property_code,
                "address": prop.address,
                "apartment_no": prop.apartment_no,
                "apartment_floor_no": prop.apartment_floor_no,
                "no_of_floors": prop.no_of_floors,
                "step_status": prop.step_status,
                "rent": prop.rent,
                "security_deposit": prop.security_deposit,
                "booking_amount": prop.booking_amount,
                "maintenance_charges": prop.maintenance_charges,
                "cycle": prop.cycle,
                "notice_period": prop.notice_period,
                "commission_percent": prop.commission_percent,

                "owner_id": prop.owner.id if prop.owner else None,
                "property": property_data
            }

            return prepare_response(content=content, status=status.HTTP_200_OK)

        except Exception as e:
            return prepare_response(
                message={"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "PUT":
        try:
            current_user = request.user
            data = json.loads(request.body)

            property_id = data.get("property_id")
            if not property_id:
                return prepare_response(
                    message=constants.PROPERTY_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            prop = PropertyUnitDetails.objects.filter(id=property_id).first()
            if not prop:
                return prepare_response(
                    message=constants.PROPERTY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            parent_property = prop.property
            if parent_property:
                parent_fields = [
                    "property_name",
                    "additional_address",
                    "locality",
                    "postal_code",
                    "property_type_options",
                    "city"
                ]
                for field in parent_fields:
                    if field in data and data[field] is not None:
                        setattr(parent_property, field, data[field])
                parent_property.save()

            basic_fields = [
                "property_unit_name", "land_dm_no", "area_of_property",
                "no_of_parking", "makani_no", "dewa_no",
                "land_area", "apartment_no", "bedrooms", "balcony",
                "plot_no", "area_unit", "land_area_unit",
                "apartment_floor_no", "no_of_floors",
                "dimension", "address"
            ]

            for field in basic_fields:
                if field in data and data[field] is not None:
                    setattr(prop, field, data[field])

            commercial_fields = [
                "rent", "security_deposit", "booking_amount",
                "maintenance_charges", "cycle",
                "notice_period", "commission_percent"
            ]

            for field in commercial_fields:
                if field in data:
                    setattr(prop, field, data[field])
                    if prop.step_status == constants.BASIC_DETAILS:
                        prop.step_status = constants.COMMERCIALS_DETAILS

            if current_user.user_role == constants.COMPANY_USER:
                owner_id = data.get("owner_id")
                if owner_id:
                    owner_obj = UserProfile.objects.filter(
                        id=owner_id, user_role=constants.OWNER
                    ).first()
                    if owner_obj:
                        prop.owner = owner_obj

                if hasattr(current_user, "company"):
                    prop.company = current_user.company

            elif current_user.user_role == constants.OWNER:
                company_id = data.get("company_id")
                if company_id:
                    company_obj = Company.objects.filter(id=company_id).first()
                    if company_obj:
                        prop.company = company_obj
                prop.owner = current_user

            prop.save()

            return prepare_response(
                message=constants.PROPERTY_UPDATE_SUCCESS,
                content={"property_id": prop.id},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message={"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    elif request.method == "POST":
        try:
            data = json.loads(request.body)
            property_code = generate_property_code()

            if user_profile.user_role == constants.OWNER:
                owner = user_profile
                company = None

            elif user_profile.user_role == constants.COMPANY_USER:
                company = Company.objects.filter(company_user=user_profile).first()
                if not company:
                    return prepare_response(
                        message=constants.COMPANY_NOT_FOUND,
                        status=status.HTTP_400_BAD_REQUEST
                    )
                owner = None
            else:
                return prepare_response(
                    message=constants.UNAUTHORIZED_TO_CREATE_PROPERTY,
                    status=status.HTTP_403_FORBIDDEN
                )

            parent_property_id = data.get("parent_property_id")

            if parent_property_id:
                parent_property = Property.objects.filter(id=parent_property_id).first()
                if not parent_property:
                    return prepare_response(
                        message="Invalid parent property id",
                        status=status.HTTP_404_NOT_FOUND
                    )
            else:
                parent_property = Property.objects.create(
                    property_name=data.get("property_unit_name"),
                    Property_code=property_code,
                    additional_address=data.get("additional_address"),
                    locality=data.get("locality"),
                    postal_code=data.get("postal_code"),
                    property_type_options=data.get("property_type_options"),
                    city_id=data.get("city_id"),
                    created_by=user_profile.user
                )
            new_property_unit = PropertyUnitDetails.objects.create(
                created_by=user_profile.user,
                property_unit_name=data.get("property_unit_name"),
                land_dm_no=data.get("land_dm_no"),
                area_of_property=data.get("area_of_property"),
                no_of_parking=data.get("no_of_parking"),
                makani_no=data.get("makani_no"),
                dewa_no=data.get("dewa_no"),
                property_type=data.get("property_type"),
                land_area=data.get("land_area"),
                apartment_no=data.get("apartment_no"),
                bedrooms=data.get("bedrooms"),
                balcony=data.get("balcony"),
                plot_no=data.get("plot_no"),
                area_unit=data.get("area_unit"),
                land_area_unit=data.get("land_area_unit"),
                apartment_floor_no=data.get("apartment_floor_no"),
                no_of_floors=data.get("no_of_floors"),
                dimension=data.get("dimension"),
                address=data.get("address"),
                property_code=property_code,
                owner=owner,
                company=company,
                property=parent_property,
                step_status=constants.BASIC_DETAILS,
            )

            return prepare_response(
                message=constants.PROPERTY_ADDED,
                content={"id": new_property_unit.id},
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return prepare_response(
                message={"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



# @is_request_authenticated
# def save_property(request):
#     user_profile = request.user
#     if request.method == "GET":
#         try:
#             property_id = request.GET.get("property_id")
#             if not property_id:
#                 return prepare_response(
#                     message=constants.PROPERTY_ID_REQUIRED,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             prop = PropertyUnitDetails.objects.filter(id=property_id).first()
#             if not prop:
#                 return prepare_response(
#                     message=constants.PROPERTY_NOT_FOUND,
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             property_type_options = dict(constants.PROPERTY_TYPE_CHOICES)
#             property_type_data = {
#                 "key": prop.property_type_options,
#                 "value": property_type_options.get(prop.property_type_options)
#             }
#             parent_property = prop.property


#             property_data = None
#             if parent_property:
#                 property_data = {"id": parent_property.id,
#         "property_name": parent_property.property_name,
#         "property_code": parent_property.Property_code,
#         "address": parent_property.address,
#         "additional_address": parent_property.additional_address,
    
#     }
#             content = {
#                 "id": prop.id,
#                 "property_unit_name": prop.property_unit_name,
#                 "land_dm_no": prop.land_dm_no,
#                 "area_of_property": prop.area_of_property,
#                 "no_of_parking": prop.no_of_parking,
#                 "bedrooms": prop.bedrooms,
#                 "balcony": prop.balcony,
#                 "plot_no": prop.plot_no,
#                 "area_unit": prop.area_unit,
#                 "property_code": prop.property_code,
#                 "property_type": property_type_data,
#                 "land_area": prop.land_area,
#                 "makani_no": prop.makani_no,
#                 "dewa_no": prop.dewa_no,
#                 "apartment_no": prop.apartment_no,
#                 "apartment_floor_no": prop.apartment_floor_no,
#                 "no_of_floors": prop.no_of_floors,
#                 "step_status": prop.step_status,
#                 "commercial_details": {
#                     "rent": prop.rent,
#                     "security_deposit": prop.security_deposit,
#                     "booking_amount": prop.booking_amount,
#                     "maintenance_charges": prop.maintenance_charges,
#                     "cycle": prop.cycle,
#                     "notice_period": prop.notice_period,
#                     "commission_percent": prop.commission_percent,
#                 },
#                 "owner_id": prop.owner.id if prop.owner else None,
#                  "property": property_data
#             }

#             return prepare_response(content=content, status=status.HTTP_200_OK)
#         except Exception as e:
#             return prepare_response(
#                 message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
#     elif request.method == "PUT":
#         try:
#             current_user = request.user
#             data = json.loads(request.body)
#             property_id = data.get("property_id")
#             if not property_id:
#                 return prepare_response(
#                     message=constants.PROPERTY_ID_REQUIRED,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
            

#             prop = PropertyUnitDetails.objects.filter(id=property_id).first()
#             if not prop:
#                  return prepare_response(
#                 message=constants.PROPERTY_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )
#             parent_property = prop.property
#             updated = False
#             if parent_property:
#                 parent_fields = ["property_name", "address", "additional_address"]
#                 for field in parent_fields:
#                     if field in data and data[field] is not None:
#                         setattr(parent_property, field, data[field])
#                         updated = True
#                 if updated:
#                     parent_property.save()
                        
#             basic_fields = [
#             "property_unit_name", "land_dm_no", "area_of_property",
#             "no_of_parking", "makani_no", "dewa_no",
#             "land_area", "apartment_no", "bedrooms", "balcony",
#             "plot_no", "area_unit", "land_area_unit",
#             "apartment_floor_no", "no_of_floors", "property_type_options"
#              ]

#             for field in basic_fields:
#                 if field in data:
#                     value = data.get(field)
#                     if value is not None:
#                         setattr(prop, field, value)
                    
#             if "property_type" in data and data["property_type"]:
#                 prop.property_type = data["property_type"]
                  
#             commercial_fields = [
#                 "rent", "security_deposit", "booking_amount",
#                 "maintenance_charges", "cycle", "notice_period", "commission_percent"
#             ]

#             for field in commercial_fields:
#                 if field in data:
#                     setattr(prop, field, data[field])
#                     if prop.step_status == constants.BASIC_DETAILS:
#                         prop.step_status = constants.COMMERCIALS_DETAILS

            
#             if current_user.user_role == constants.COMPANY_USER:
#                 owner_id = data.get("owner_id")
#                 if owner_id:
#                     owner_obj = UserProfile.objects.filter(
#                     id=owner_id, user_role=constants.OWNER
#                 ).first()
#                     if owner_obj:
#                         prop.owner = owner_obj

#                 if hasattr(current_user, "company"):
#                     prop.company = current_user.company
            
#             elif current_user.user_role == constants.OWNER:
#                  company_id = data.get("company_id")
#                  if company_id:
#                      company_obj = Company.objects.filter(id=company_id).first()
#                      if company_obj:
#                          prop.company = company_obj
#                  prop.owner = current_user
#             prop.save()
#             return prepare_response(
#                 message=constants.PROPERTY_UPDATE_SUCCESS,
#                 content={"property_id": prop.id},
#                 status=status.HTTP_200_OK
#             )

#         except Exception as e:
#             return prepare_response(
#                 message={"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#     elif request.method == "POST":
#         try:
#             data = json.loads(request.body)
#             property_unit_name = data.get("property_unit_name")
#             land_dm_no = data.get("land_dm_no")
#             area_of_property = data.get("area_of_property")
#             no_of_parking = data.get("no_of_parking")
#             makani_no = data.get("makani_no")
#             dewa_no = data.get("dewa_no")
#             property_type = data.get("property_type")
#             land_area = data.get("land_area")
#             apartment_no = data.get("apartment_no")
#             bedrooms = data.get("bedrooms")
#             balcony = data.get("balcony")
#             plot_no = data.get("plot_no")
#             area_unit = data.get("area_unit")
#             land_area_unit = data.get("land_area_unit")
#             apartment_floor_no = data.get("apartment_floor_no")
#             no_of_floors = data.get("no_of_floors")
#             parent_property_id = data.get("parent_property_id")
#             address = data.get("address")
#             additional_address = data.get("additional_address")
#             locality = data.get("locality")
#             postal_code = data.get("postal_code")
#             city_id = data.get("city_id")
#             property_code = generate_property_code()
#             if user_profile.user_role == constants.OWNER:
#                 owner = user_profile
#                 company = None
#             elif user_profile.user_role == constants.COMPANY_USER:
#                 company = Company.objects.filter(company_user=user_profile).first()
#                 if not company:
#                     return prepare_response(
#                         message=constants.COMPANY_NOT_FOUND,
#                         status=status.HTTP_400_BAD_REQUEST
#                     )
#                 owner = None
#             else:
#                 return prepare_response(
#                     message=constants.UNAUTHORIZED_TO_CREATE_PROPERTY,
#                     status=status.HTTP_403_FORBIDDEN
#                 )
#             if parent_property_id:
#                 parent_property = Property.objects.filter(id=parent_property_id).first()
#                 if not parent_property:
#                     return prepare_response(
#                     message="Invalid parent property id",
#                     status=status.HTTP_404_NOT_FOUND
#                 )
#             else:
#                 parent_property = Property.objects.create(
#                 property_name=property_unit_name,
#                 Property_code=property_code,
#                 additional_address=additional_address,
#                 address=address,
#                 created_by=user_profile.user
#             )
#             city = None
#             if city_id:
#                 city = City.objects.filter(id=city_id).first()
#             new_property_unit = PropertyUnitDetails.objects.create(
#                 created_by=user_profile.user,
#                 property_unit_name=property_unit_name,
#                 land_dm_no=land_dm_no,
#                 area_of_property=area_of_property,
#                 no_of_parking=no_of_parking,
#                 makani_no=makani_no,
#                 dewa_no=dewa_no,
#                 property_type=property_type,
#                 land_area=land_area,
#                 apartment_no=apartment_no,
#                 bedrooms=bedrooms,
#                 balcony=balcony,
#                 plot_no=plot_no,
#                 area_unit=area_unit,
#                 land_area_unit=land_area_unit,
#                 apartment_floor_no=apartment_floor_no,
#                 no_of_floors=no_of_floors,
#                 property_code=property_code,
#                 owner=owner,
#                 company=company,
#                 property=parent_property,
#                 step_status="BASIC_DETAILS",
#                 locality=locality,
#                 postal_code=postal_code,
#                 city=city,
#             )
#             return prepare_response(
#                 message=constants.PROPERTY_ADDED,
#                 content={"id": new_property_unit.id},
#                 status=status.HTTP_201_CREATED
#             )
#         except Exception as e:
#             return prepare_response(
#                 message={"error": str(e)},
#                 status=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )
#     else:
#         return prepare_response(
#             message=constants.INVALID_REQUEST_METHOD,
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )


@is_request_authenticated
def property_images(request):
    try:
        if request.method == "GET":
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=status.HTTP_404_NOT_FOUND)

            images_qs = PropertyImages.objects.filter(property=property_obj).order_by("-id")
            final_images = []

            for img in images_qs:
                base64_data = fetch_s3_presigned_url(img.image_path, file_name=img.file_name)
                final_images.append({
                    "id": img.id,
                    "file_name": img.file_name,
                    "data": base64_data,
                    "type": img.image_type
                })

            return prepare_response(
                message=constants.DATA_FETCHED_SUCCESSFULLY,
                content={
                    "images": final_images,
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=status.HTTP_200_OK
            )
        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(images, list) or not images:
                return prepare_response(message="Images must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            uploaded_files = []
            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=status.HTTP_400_BAD_REQUEST)

                object_name = f"property_images/{property_id}/{file_name}"
                image_url = upload_file_to_s3_base64(base64_data, object_name)

                PropertyImages.objects.create(
                    property=property_obj,
                    file_name=file_name,
                    image_path=image_url,
                    image_type=img_type,
                    created_by = request.user.user

                )

                uploaded_files.append({
                    "file_name": file_name,
                    "image_url": image_url,
                    "image_type": img_type
                })
            property_obj.step_status = "PROPERTY_IMAGES_DETAILS"
            property_obj.save()

            return prepare_response(
                message=constants.IMAGE_UPLOADED_SUCCESS,
                content={"uploaded": uploaded_files},
                status=status.HTTP_201_CREATED
            )
        
        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            images = body.get("images", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(images, list):
                return prepare_response(message="Images must be a list", status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            updated_files = []
            for img in images:
                file_name = img.get("file_name")
                base64_data = img.get("data")
                img_type = img.get("type", "INTERIOR").upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=status.HTTP_400_BAD_REQUEST)

                img_obj, created = PropertyImages.objects.update_or_create(
                    property=property_obj,
                    file_name=file_name,
                    defaults={"image_type": img_type}
                )

                object_name = f"property_images/{property_id}/{file_name}"
                image_url = upload_file_to_s3_base64(base64_data, object_name)
                img_obj.image_path = image_url
                img_obj.save()

                updated_files.append({
                    "file_name": file_name,
                    "image_url": image_url,
                    "image_type": img_type,
                    "status": "created" if created else "updated"
                })

            return prepare_response(
                message=constants.IMAGE_UPLOADED_SUCCESS,
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )
    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)



@is_request_authenticated
def property_documents(request):
    try:
    
        if request.method == "GET":
            property_id = request.GET.get("property_id")
            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.INVALID_PROPERTY_ID, status=status.HTTP_404_NOT_FOUND)

            docs_qs = property_obj.property_documents.select_related('document').order_by("-id")
            final_docs = []

            for mapping in docs_qs:
                doc = mapping.document
                base64_data = fetch_s3_presigned_url(doc.file_path, file_name=doc.file_name)
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
                    "property_id": property_id,
                    "step_choice": property_obj.step_status
                },
                status=status.HTTP_200_OK
            )

   
        if request.method == "POST":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(documents, list) or not documents:
                return prepare_response(message=constants.DOCUMENTS_MUST_BE_LIST, status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            uploaded_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
            
                doc_type = doc.get("type", constants.FLOOR_PLAN).upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=status.HTTP_400_BAD_REQUEST)

                object_name = f"property_documents/{property_id}/{file_name}"
                file_url = upload_file_to_s3_base64(base64_data, object_name)

         
                doc_obj = Documents.objects.create(
                    file_name=file_name,
                    file_path=file_url,
                    created_by=request.user.user
                )

                PropertyDocumentsMapping.objects.create(
                    property=property_obj,
                    document=doc_obj,
                    document_choice=doc_type,
                    created_by=request.user.user
                )

                uploaded_files.append({
                    "file_name": file_name,
                    "file_url": file_url,
                    "type": doc_type
                })

            property_obj.step_status = "DOCUMENTS_DETAILS"
            property_obj.save()

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"uploaded": uploaded_files},
                status=status.HTTP_201_CREATED
            )

        if request.method == "PUT":
            body = json.loads(request.body)
            property_id = body.get("property_id")
            documents = body.get("documents", [])

            if not property_id:
                return prepare_response(message=constants.PROPERTY_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            if not isinstance(documents, list):
                return prepare_response(message=constants.DOCUMENTS_MUST_BE_LIST, status=status.HTTP_400_BAD_REQUEST)

            try:
                property_obj = PropertyUnitDetails.objects.get(id=property_id)
            except PropertyUnitDetails.DoesNotExist:
                return prepare_response(message=constants.PROPERTY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            updated_files = []

            for doc in documents:
                file_name = doc.get("file_name")
                base64_data = doc.get("data")
                doc_type = doc.get("type", constants.FLOOR_PLAN).upper()

                if not file_name or not base64_data:
                    return prepare_response(message=constants.MISSING_FILE_OR_DATA, status=status.HTTP_400_BAD_REQUEST)

                mapping_obj = PropertyDocumentsMapping.objects.filter(
                    property=property_obj,
                    document__file_name=file_name
                ).select_related('document').first()

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
                    mapping_obj = PropertyDocumentsMapping.objects.create(
                        property=property_obj,
                        document=doc_obj,
                        document_choice=doc_type,
                        created_by=request.user.user
                    )
                    status_text = "created"

                object_name = f"property_documents/{property_id}/{file_name}"
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

            return prepare_response(
                message=constants.DOCUMENTS_UPLOAD_SUCCESS,
                content={"updated": updated_files},
                status=status.HTTP_200_OK
            )

        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)





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
                "city": tenant_obj.city,
                "address": tenant_obj.address,
                "emirate_id": tenant_obj.emirate_id,
            }

            lease_qs = LeasePropertyDetails.objects.filter(tenant=tenant_obj).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )

        elif user.user_role == constants.OWNER:
            lease_qs = LeasePropertyDetails.objects.filter(owner=user).select_related(
                "tenant", "lease_property", "lease_property__owner", "lease_property__company"
            )

        elif user.user_role == constants.COMPANY_USER:
            company = Company.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            lease_qs = LeasePropertyDetails.objects.filter(
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
                Q(lease_property__property_unit_name__icontains=search)
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
                "tenant_id": tenant.id if tenant else None,
                "tenant_name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant.user else None,
                "tenant_profile_image": tenant.profile_image if tenant else None,
                "contact_number": tenant.contact_number,
                "property_assigned": prop_unit.property_unit_name if prop_unit else None,
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




# This view is for a logged-in Company User(PMC).
# It fetches all Owners under the company of the logged-in user
@is_request_authenticated
def company_owners_view(request):
    user = request.user 
    search = request.GET.get("search", "").strip()
    owner_id = request.GET.get("owner_id")
    page = int(request.GET.get("page", 1))
    limit = int(request.GET.get("limit", 10))

    try:
        company = Company.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
        if owner_id:
            owner = UserProfile.objects.filter(id=owner_id, user_role="OWNER").first()
            if not owner:
                return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)
            lease_qs = LeasePropertyDetails.objects.filter(
                lease_property__owner=owner,
                lease_property__company=company
            ).select_related(
                "tenant", "lease_property"
            )

            if search:
                lease_qs = lease_qs.filter(
                    Q(tenant__user__first_name__icontains=search) |
                    Q(tenant__user__last_name__icontains=search) |
                    Q(lease_property__property_unit_name__icontains=search) |
                    Q(tenant__contact_number__icontains=search)
                )

            lease_qs = lease_qs.order_by("-id")

            paginator = Paginator(lease_qs, limit)
            try:
                lease_page = paginator.page(page)
            except EmptyPage:
                lease_page = paginator.page(paginator.num_pages)

            data = []
            for lease in lease_page:
                tenant = lease.tenant
                prop_unit = lease.lease_property
                data.append({
                    "tenant_id": tenant.id,
                    "tenant_name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant.user else "",
                    "contact_number": tenant.contact_number,
                    "property_name": prop_unit.property_unit_name if prop_unit else None,
                    "tenancy_status": lease.lease_status,
                    "agreement": lease.pdf_path if lease.pdf_path else None,
                })

            pagination_meta = {
                "current_page": lease_page.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            return prepare_response(
                content=data,
                message=f"Tenant details for owner {owner.user.email if owner.user else owner.id}",
                pagination=pagination_meta,
                status=status.HTTP_200_OK
            )

        owners_qs = UserProfile.objects.filter(
            user_role="OWNER",
            owner_properties__company=company
        ).distinct().prefetch_related(
            Prefetch(
                'owner_properties',
                queryset=PropertyUnitDetails.objects.filter(company=company)
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
                "properties": [{"id": prop.id, "name": prop.property_unit_name,"image": (
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
            message="Owners fetched successfully",
            pagination=pagination_meta,
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=f"Error fetching data: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    


# This view is for the logged-in user with role "OWNER".  
# It provides details of PMC (Property Management Company) associated with the owner's properties.
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

                properties = PropertyUnitDetails.objects.filter(owner=user)
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
                        owner_props = PropertyUnitDetails.objects.filter(owner=user, company=comp)
                        leased_count = LeasePropertyDetails.objects.filter(
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
                            "compnay_code":"comp_110",
                        })

                pagination_meta = {
                    "current_page": pmc_page.number,
                    "limit": limit,
                    "total_records": paginator.count,
                    "total_pages": paginator.num_pages
                }

                return prepare_response(
                    content=data,
                    message="PMC list fetched successfully",
                    pagination=pagination_meta,
                    status=status.HTTP_200_OK
                )

            elif company_id:
                if user.user_role != constants.OWNER:
                    return prepare_response(message="Only owner can access this data",status=status.HTTP_403_FORBIDDEN)
                company = Company.objects.select_related("company_user__user").filter(id=company_id).first()
                if not company:
                    return prepare_response(message="Company not found", status=status.HTTP_404_NOT_FOUND)
                properties_qs = PropertyUnitDetails.objects.filter(owner=user,company=company ).select_related("property" ).prefetch_related( "lease_details__tenant__user")

                if search:
                    properties_qs = properties_qs.filter(Q(property_unit_name__icontains=search) | Q(property__property_name__icontains=search))
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
                    properties_data.append({"property_unit_id": prop.id,"property_name": prop.property_unit_name or (
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
                          "total_properties_handled": PropertyUnitDetails.objects.filter(
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
                    message="PMC profile & property details fetched successfully",
                    pagination=pagination_meta,
                    status=status.HTTP_200_OK)
                 
            
                    


                

            else:
                return prepare_response(message="Unauthorized access or missing parameters", status=status.HTTP_403_FORBIDDEN)

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
        return prepare_response(message="Invalid request", status=status.HTTP_405_METHOD_NOT_ALLOWED)

    try:
        user_profile = request.user  
        data = json.loads(request.body)
        email = data.get("email")
        invite_type = data.get("invitation_type") 
        property_unit_id = data.get("property_unit_id")

        if not email:
            return prepare_response(message="Email is required", status=status.HTTP_400_BAD_REQUEST)
        
        if not property_unit_id:
            return prepare_response(message="Property unit id is required", status=status.HTTP_400_BAD_REQUEST)
        

        if invite_type not in ["OWNER_TO_PMC", "PMC_TO_OWNER", "PMC_TO_TENANT"]:
            return prepare_response(message="Invalid invitation type", status=status.HTTP_400_BAD_REQUEST)

      
        if invite_type == "OWNER_TO_PMC" and user_profile.user_role != constants.OWNER:
            return prepare_response(message="Only owners can invite PMC", status=status.HTTP_403_FORBIDDEN)

        if invite_type in ["PMC_TO_OWNER", "PMC_TO_TENANT"] and user_profile.user_role != constants.COMPANY_USER:
            return prepare_response(message="Only PMC can send this invitation", status=status.HTTP_403_FORBIDDEN)
        property_unit_qs = PropertyUnitDetails.objects.filter(id=property_unit_id)
        if not property_unit_qs.exists():
            return prepare_response(
        message="Invalid property unit id",
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
            message="Invitation sent successfully",
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
    if request.method == "GET":
        try:
            lease_id = request.GET.get("lease_id")

            if not lease_id:
                return prepare_response(
                    message=constants.LEASE_ID_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST,
                )

            lease = LeasePropertyDetails.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(
                    message=constants.LEASE_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND,
                )

            return prepare_response(
                content=serialize_lease(lease),
                message="Lease fetched",
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

 
    elif request.method == "POST":
        try:
            body = json.loads(request.body)

            property_id = body.get("property_id")
            tenant_id = body.get("tenant_id")
            

            if not property_id or not tenant_id:
                return prepare_response(
                    message="property_id and tenant_id are required",
                    status=status.HTTP_400_BAD_REQUEST
                )

            property_obj = PropertyUnitDetails.objects.filter(id=property_id).first()
            tenant_obj = UserProfile.objects.filter(id=tenant_id, user_role="TENANT").first()

            if not property_obj or not tenant_obj:
                return prepare_response(message="Invalid property or tenant", status=status.HTTP_400_BAD_REQUEST)
            owner_obj = property_obj.owner
            if not owner_obj:
                return prepare_response(message=constants.THIS_OWNER_HAS_NO_PROPERTY, status=status.HTTP_400_BAD_REQUEST)
            
            lease_start_date = safe_epoch_to_datetime(body.get("lease_start_date"))
            lease_end_date = safe_epoch_to_datetime(body.get("lease_end_date"))
            if not lease_start_date or not lease_end_date:
                return prepare_response(message="Invalid lease dates", status=status.HTTP_400_BAD_REQUEST)
            lease_grace_start_date = safe_epoch_to_datetime(body.get("lease_grace_start_date")) if body.get("lease_grace_start_date") else None
            lease_grace_end_date = safe_epoch_to_datetime(body.get("lease_grace_end_date")) if body.get("lease_grace_end_date") else None
            lease = LeasePropertyDetails.objects.create(
             created_by=user_profile.user,
            lease_property=property_obj,
            tenant=tenant_obj,
            owner=owner_obj,
            lease_start_date=lease_start_date,
            lease_end_date=lease_end_date,
            lease_grace_start_date=lease_grace_start_date,
            lease_grace_end_date=lease_grace_end_date,
            lease_remarks=body.get("lease_remarks"),
            step_status="LEASE_DETAILS",  
            )

            return prepare_response(
                message="Lease created successfully",
                content={"lease_id": lease.id},
                status=status.HTTP_201_CREATED,
            )

        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == "PUT":
      
        try:
            body = json.loads(request.body)
            lease_id = body.get("lease_id")

            if not lease_id:
                return prepare_response(message=constants.LEASE_ID_REQUIRED , status=status.HTTP_400_BAD_REQUEST)

            lease = LeasePropertyDetails.objects.filter(id=lease_id).first()
            if not lease:
                return prepare_response(message=constants.LEASE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            basic_fields = [
                "lease_remarks",
                "step_status",
            ]
            for field in basic_fields:
                if field in body and body[field] is not None:
                    setattr(lease, field, body[field])
            if "lease_start_date" in body:
                lease.lease_start_date = safe_epoch_to_datetime(body["lease_start_date"])

            if "lease_end_date" in body:
                lease.lease_end_date = safe_epoch_to_datetime(body["lease_end_date"])

            if "lease_grace_start_date" in body:
                lease.lease_grace_start_date = safe_epoch_to_datetime(body["lease_grace_start_date"])

            if "lease_grace_end_date" in body:
                lease.lease_grace_end_date = safe_epoch_to_datetime(body["lease_grace_end_date"])

            commercial_fields = [
                "annual_amount", "actual_annual_amount", "rent",
                "booking_amount", "security_deposit", "maintenance_charges",
                "commission_percentage", "notice_period", "discount"
            ]
            commercial_updated = False
            for field in commercial_fields:
                if field in body:
                    setattr(lease, field, body[field])
                    commercial_updated = True
            if commercial_updated and lease.step_status == "LEASE_DETAILS":
                lease.step_status = "LEASE_COMMERCIALS"

            if "tenant_id" in body:
                tenant_obj = UserProfile.objects.filter(
                    id=body["tenant_id"], user_role="TENANT").first()
                if not tenant_obj:
                    return prepare_response(message="Invalid tenant_id", status=status.HTTP_400_BAD_REQUEST)
                lease.tenant = tenant_obj
            
            if "property_id" in body:
                property_obj = PropertyUnitDetails.objects.filter(id=body["property_id"]).first()
                if not property_obj:
                    return prepare_response(message="Invalid property", status=status.HTTP_400_BAD_REQUEST)
                    
                lease.lease_property = property_obj
                lease.owner = property_obj.owner

            lease.save()

            return prepare_response(
                message=constants.LEASE_UPDATED,
                content={"lease_id": lease.id},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)


@is_request_authenticated
def lease_tenancy(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message="Method not allowed",
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        current_user = request.user

        leases_qs = LeasePropertyDetails.objects.select_related(
            "lease_property",
            "tenant",
            "tenant__user"
        )

        if current_user.user_role == constants.OWNER:
            leases_qs = leases_qs.filter(
                owner=current_user
            )

        elif current_user.user_role == constants.COMPANY_USER:
            leases_qs = leases_qs.filter(
                lease_property__assigned_staff__staff=current_user
            ).distinct()

        else:
            return prepare_response(
                message="Unauthorized role",
                status=status.HTTP_403_FORBIDDEN
            )

        table_data = []

        for lease in leases_qs.order_by("-created"):
            tenant_profile = lease.tenant

            table_data.append({
                "lease_id":lease.id,
                "property_code": lease.lease_property.property_code,
                "tenant_name": tenant_profile.user.get_full_name(),
                "tenant_profile_image": tenant_profile.profile_image,
                "tenant_contact_number": tenant_profile.contact_number,
                "lease_status": lease.lease_status,
                "agreement_start_date": datetime_to_epoch_millis(lease.lease_start_date),
                "agreement_end_date": datetime_to_epoch_millis(lease.lease_end_date),
            })

        return prepare_response(
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            content={
                "count": len(table_data),
                "results": table_data
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



# -----------------------------------All Exports API--------------------------------------------------------------

# /lease/export/csv/
@is_request_authenticated
def export_lease_tenancy_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        current_user = request.user

        leases_qs = LeasePropertyDetails.objects.select_related(
            "lease_property",
            "tenant",
            "tenant__user"
        )

        if current_user.user_role == constants.OWNER:
            leases_qs = leases_qs.filter(owner=current_user)

        elif current_user.user_role == constants.COMPANY_USER:
            leases_qs = leases_qs.filter(
                lease_property__assigned_staff__staff=current_user
            ).distinct()

        else:
            return prepare_response(
                message="Unauthorized role",
                status=status.HTTP_403_FORBIDDEN
            )
        field_names = [
            "Lease ID",
            "Property Code",
            "Tenant Name",
            "Tenant Contact",
            "Lease Status",
            "Agreement Start Date",
            "Agreement End Date",
        ]

        export_data = []

        for lease in leases_qs.order_by("-created"):
            tenant = lease.tenant
            tenant_name = tenant.user.get_full_name()

            export_data.append({
                "Lease ID": lease.id,
                "Property Code": lease.lease_property.property_code,
                "Tenant Name": tenant_name,
                "Tenant Contact": tenant.contact_number,
                "Lease Status": lease.lease_status,
                "Agreement Start Date": lease.lease_start_date.strftime("%d-%m-%Y"),
                "Agreement End Date": lease.lease_end_date.strftime("%d-%m-%Y"),
            })

        return export_to_csv(
            file_name="lease_tenancy",
            field_names=field_names,
            export_data=export_data
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
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
        search = request.GET.get("search", "").strip()

        if user.user_role != "OWNER":
            return prepare_response(
                message="Unauthorized",
                status=status.HTTP_403_FORBIDDEN
            )

        properties = PropertyUnitDetails.objects.filter(owner=user)
        pmc_ids = properties.values_list('company__company_user', flat=True).distinct()

        pmc_qs = UserProfile.objects.filter(
            id__in=pmc_ids,
            user_role="COMPANY_USER"
        ).prefetch_related("company_user")

        if search:
            pmc_qs = pmc_qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search)
            )

        field_names = [
            "Company ID",
            "Company Name",
            "Company Address",
            "Owner Property Count",
            "Tenancy Ratio"
        ]

        export_data = []

        for pmc in pmc_qs:
            for comp in pmc.company_user.all():
                owner_props = PropertyUnitDetails.objects.filter(owner=user, company=comp)
                leased_count = LeasePropertyDetails.objects.filter(
                    lease_property__in=owner_props
                ).count()
                total_count = owner_props.count()
                tenancy_ratio = f"{leased_count}/{total_count}" if total_count else "0/0"

                export_data.append({
                    "Company ID": comp.id,
                    "Company Name": comp.company_name,
                    "Company Address": comp.company_address,
                    "Owner Property Count": total_count,
                    "Tenancy Ratio": tenancy_ratio
                })

        return export_to_csv(
            filename="owner_pmc_list",
            field_names=field_names,
            data_list=export_data
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



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
            properties_qs = PropertyUnitDetails.objects.filter(owner=user)

        elif user.user_role == constants.COMPANY_USER:
            company = Company.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)
            properties_qs = PropertyUnitDetails.objects.filter(company=company)

        elif user.user_role == constants.TENANT:
            properties_qs = PropertyUnitDetails.objects.filter(
                lease_details__tenant=user
            )

        else:
            return prepare_response(
                message="Unauthorized user role",
                status=status.HTTP_403_FORBIDDEN
            )

        properties_qs = properties_qs.select_related(
            "owner__user", "company", "property"
        ).prefetch_related(
            Prefetch(
                "lease_details",
                queryset=LeasePropertyDetails.objects.select_related("tenant__user")
            )
        ).distinct()
        if search:
            properties_qs = properties_qs.filter(
                Q(property_unit_name__icontains=search) |
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
                "Company Name"
            ]

            for prop in properties_qs:
                lease = prop.lease_details.first()
                export_data.append({
                    "Property Name": prop.property.property_name if prop.property else "",
                    "Tenant Name": lease.tenant.user.get_full_name() if lease else "",
                    "Agreement Expiration": get_lease_status(lease),
                    "Dimension": prop.area_of_property,
                    "Company Name": prop.company.company_name if prop.company else ""
                })

        # 🔹 COMPANY USER CSV
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

        # 🔹 TENANT CSV
        elif user.user_role == constants.TENANT:
            field_names = [
                "Property Name",
                "Owner Name",
                "Tenancy Status",
                "Dimension",
                "Company Name"
            ]

            for prop in properties_qs:
                export_data.append({
                    "Property Name": prop.property.property_name if prop.property else "",
                    "Owner Name": prop.owner.user.get_full_name() if prop.owner else "",
                    "Tenancy Status": "Occupied" if prop.is_occupied else "Available",
                    "Dimension": prop.area_of_property,
                    "Company Name": prop.company.company_name if prop.company else ""
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
def export_company_owners_csv(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        user = request.user
        search = request.GET.get("search", "").strip()
        owner_id = request.GET.get("owner_id")
        company = Company.objects.filter(company_user=user).first()
        if not company:
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_400_BAD_REQUEST)

        export_data = []
        if owner_id:
            owner = UserProfile.objects.filter(
                id=owner_id,
                user_role="OWNER"
            ).first()

            if not owner:
                return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)
            lease_qs = LeasePropertyDetails.objects.filter(
                lease_property__owner=owner,
                lease_property__company=company
            ).select_related("tenant", "lease_property")
            if search:
                lease_qs = lease_qs.filter(
                    Q(tenant__user__first_name__icontains=search) |
                    Q(tenant__user__last_name__icontains=search) |
                    Q(lease_property__property_unit_name__icontains=search) |
                    Q(tenant__contact_number__icontains=search)
                )

            lease_qs = lease_qs.order_by("-id")

            field_names = [
                "Tenant ID",
                "Tenant Name",
                "Contact Number",
                "Property Name",
                "Tenancy Status",
                "Agreement"
            ]

            for lease in lease_qs:
                tenant = lease.tenant
                prop = lease.lease_property

                export_data.append({
                    "Tenant ID": tenant.id if tenant else "",
                    "Tenant Name": f"{tenant.user.first_name} {tenant.user.last_name}" if tenant and tenant.user else "",
                    "Contact Number": tenant.contact_number if tenant else "",
                    "Property Name": prop.property_unit_name if prop else "",
                    "Tenancy Status": lease.lease_status,
                    "Agreement": lease.pdf_path if lease.pdf_path else ""
                })

            return export_to_csv(
                filename="company_owner_tenants",
                field_names=field_names,
                data_list=export_data
            )

        owners_qs = UserProfile.objects.filter(
            user_role="OWNER",
            owner_properties__company=company
        ).distinct().prefetch_related(
            Prefetch(
                "owner_properties",
                queryset=PropertyUnitDetails.objects.filter(company=company)
            )
        )

        if search:
            owners_qs = owners_qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(contact_number__icontains=search)
            )

        owners_qs = owners_qs.annotate(property_count=Count("owner_properties"))

        field_names = [
            "Owner ID",
            "First Name",
            "Last Name",
            "Email",
            "Contact Number",
            "Property Count",
            "Properties"
        ]

        for owner in owners_qs:
            properties = owner.owner_properties.all()
            property_names = ", ".join(
                [prop.property_unit_name for prop in properties]
            )

            export_data.append({
                "Owner ID": owner.id,
                "First Name": owner.user.first_name if owner.user else "",
                "Last Name": owner.user.last_name if owner.user else "",
                "Email": owner.user.email if owner.user else "",
                "Contact Number": owner.contact_number,
                "Property Count": owner.property_count,
                "Properties": property_names
            })

        return export_to_csv(
            filename="company_owners",
            field_names=field_names,
            data_list=export_data
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
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
        if user.user_role == constants.OWNER:
            properties = PropertyUnitDetails.objects.filter(owner=user)
        elif user.user_role == constants.COMPANY_USER:
            company = Company.objects.filter(company_user=user).first()
            if not company:
                return prepare_response(
                    message="Company not found for user",
                    status=status.HTTP_404_NOT_FOUND
                )
            properties = PropertyUnitDetails.objects.filter(company=company)
        else:
            properties = PropertyUnitDetails.objects.none()
        total_properties = properties.count()
        rented_count = properties.filter(is_occupied=True).count()
        vacant_count = properties.filter(is_occupied=False).count()
        lease_queryset = LeasePropertyDetails.objects.filter(
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
            "top_properties": top_properties
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




@is_request_authenticated
def most_revenue_generating_properties(request):
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    try:
        user = request.user
        if user.user_role == constants.OWNER:
            units = PropertyUnitDetails.objects.filter(owner=user)

        elif user.user_role == constants.COMPANY_USER:
            units = PropertyUnitDetails.objects.filter(company=user.company)

        else:
            return prepare_response(
                message=constants.UNAUTHORIZED,
                status=status.HTTP_403_FORBIDDEN
            )

        property_stats = (
            units
            .values("property_id", "property__property_name")
            .annotate(
                total_units=Count("id"),
                occupied_units=Count(
                    "id",
                    filter=Q(is_occupied=True)
                )
            )
        )
        result = []
        index = 1
        for item in property_stats:
            total = item["total_units"]
            occupied = item["occupied_units"]
            occupancy_rate = round((occupied / total) * 100, 2) if total > 0 else 0
            result.append({
                "rank": index,
                "property_id": item["property_id"],
                "name": item["property__property_name"],
                "occupancy_rate": occupancy_rate,
                "figures": f"{occupancy_rate}%",
                "total_units": total,
                "occupied_units": occupied
            })
            index += 1

        result = sorted(result, key=lambda x: x["occupancy_rate"], reverse=True)

        return prepare_response(
            content=result,
            message="Most revenue generating properties fetched successfully",
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message={"error": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@is_request_authenticated
def generate_contract(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        body = json.loads(request.body)
        template_id = body.get("template_id")
        lease_id = body.get("lease_id")
        values_dict = body.get("values")

        if not template_id or not lease_id or not values_dict:
            return prepare_response(
                message=constants.TEMPLATE_LEASE_VALUES_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        template = Template.objects.filter(id=template_id, is_active=True).first()
        if not template:
            return prepare_response(
                message=constants.INVALID_TEMPLATE_ID,
                status=status.HTTP_404_NOT_FOUND
            )
        lease = LeasePropertyDetails.objects.filter(id=lease_id).first()
        if not lease:
            return prepare_response(
                message=constants.INVALID_LAESE_ID,
                status=status.HTTP_404_NOT_FOUND
            )
        TemplateValues.objects.create(
            document_template=template,
            lease=lease,
            value=values_dict,
            created_by=request.user.user 
        )

        template_path = template.template_path

        if not template_path or not os.path.exists(template_path):
            return prepare_response(
                message=f"Template not found: {template_path}",
                status=status.HTTP_404_NOT_FOUND
            )

        if os.path.isdir(template_path):
            return prepare_response(
                message="Template path must be a file",
                status=status.HTTP_400_BAD_REQUEST
            )

        with open(template_path, "r", encoding="utf-8") as f:
            html_content = f.read()
        mapping = {}
        fields = TemplateFields.objects.filter(document_template=template, is_active=True)

        for field in fields:
            key = field.id_attribute or field.name_attribute
            if key and key in values_dict:
                mapping[key] = values_dict[key]

        html_content = replace_placeholders(html_content, mapping)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        filename = f"lease_{timestamp}.html"

        save_dir = os.path.join(settings.MEDIA_ROOT, "generated_templates")
        os.makedirs(save_dir, exist_ok=True)

        save_path = os.path.join(save_dir, filename)

        with open(save_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        pdf_filename = f"lease_{timestamp}.pdf"
        config = get_pdfkit_config()

        pdf_bytes = pdfkit.from_string(
            html_content,
            False,
            configuration=config
        )

        s3_object_name = f"generated_templates/{pdf_filename}"
        pdf_s3_url = upload_file_to_s3_base64(pdf_bytes, s3_object_name)

        lease.pdf_path = pdf_s3_url
        lease.save(update_fields=["pdf_path"])

        return prepare_response(
            message=constants.CONTRACT_GENERATED_SUCCESS,
            content={
                "file_name": filename,
                "pdf_url": pdf_s3_url
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )




def get_template_fields(request):
    try:
        template_id = request.GET.get("template_id")
        if not template_id:
            return prepare_response(
                message=constants.TEMPLATE_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        template = Template.objects.get(id=template_id)
        fields = TemplateFields.objects.filter(document_template=template)

        field_list = []
        for field in fields:
            field_list.append({
                "id_attribute": field.id_attribute,
                "name_attribute": field.name_attribute,
                "label": field.label_attribute,
                "html_tag": field.html_tag,
                "required": field.required,
                "min_value": field.min_value,
                "max_value": field.max_value,
                "min_length": field.min_length,
                "max_length": field.max_length,
                "pattern": field.pattern,
                "predefined_value": field.predefined_value,
            })

        return prepare_response(
            content={
                "template_id": template.id,
                "template_name": template.name,
                "template_path": template.template_path,
                "fields": field_list
            },
            message=constants.TEMPLATE_FIELDS_FETCHED,
            status=status.HTTP_200_OK
        )

    except Template.DoesNotExist:
        return prepare_response(
            message=constants.INVALID_TEMPLATE_ID,
            status=status.HTTP_404_NOT_FOUND
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



