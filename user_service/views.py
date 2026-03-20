import json
from utilities import status, constants
from utilities.helper_functions import prepare_response, datetime_to_epoch_millis, safe_epoch_to_datetime,get_extension_from_base64,export_to_csv
from user_service.models import UserProfile, Documents, OwnerDocuments, TenantDocuments, Role, Owner, Tenant, PropertyManager
from property.models import PropertyManagerDocuments, Unit, Property, PropertyManagmentCompany
from django.db import transaction
from utilities.decorator import is_request_authenticated
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.contrib.auth.models import User
from django.db import transaction
from property_management.utils import get_staff_details, get_property_images
from user_service.utils import upload_document

EMIRATES_VISA_DOC_SPECS = [
    ("emirates_id_doc", "emirates_id", "emirates_id_doc_type"),
    ("uae_residence_visa_doc", "uae_residence_visa", "visa_doc_type"),
]


def user_sign_up(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    data = json.loads(request.body)
    email = data.get("email")
    password = data.get("password")
    user_role = data.get("user_role")

    if not all([email, password, data.get("confirm_password"), user_role]):
        return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
    if password != data.get("confirm_password"):
        return prepare_response(message=constants.PASSWORD_MISMATCH, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=email).exists():
        return prepare_response(message=constants.EMAIL_ALREADY_REGISTERED, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        user = User.objects.create_user(
            username=email,
            email=email,
            password=password,
            first_name=data.get("first_name"),
            last_name=data.get("last_name")
        )

        common_profile_kwargs = dict(
            user=user,
            created_by=user,
            pin_code=data.get("pin_code"),
            address_line_1=data.get("address_line_1"),
            address_line_2=data.get("address_line_2"),
            emirate_id=data.get("emirate_id"),
            visa_number=data.get("visa_number"),
            contact_number=data.get("contact_number"),
        )

        if user_role == constants.OWNER:
            profile = Owner.objects.create(**common_profile_kwargs, trade_license_number=data.get("trade_license_number") or "")
        elif user_role == constants.TENANT:
            profile = Tenant.objects.create(**common_profile_kwargs)
        elif user_role == constants.COMPANY_USER:
            company_id = data.get("company_id")
            if not company_id:
                return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            profile = PropertyManager.objects.create(
                **common_profile_kwargs,
                company_id=company_id
            )
        else:
            return prepare_response(message=constants.INVALID_USER_ROLE, status=status.HTTP_400_BAD_REQUEST)

        folder_name = f"{user_role.lower()}_documents/{profile.id}"

        if user_role == constants.OWNER:
            doc_specs = [*EMIRATES_VISA_DOC_SPECS, ("dld_certificate_doc", "dld_certificate", "dld_doc_type")]
            for data_key, prefix, type_key in doc_specs:
                upload_document(data.get(data_key), prefix, data.get(type_key), OwnerDocuments, {"owner": profile}, folder_name, user)
        elif user_role == constants.TENANT:
            for data_key, prefix, type_key in EMIRATES_VISA_DOC_SPECS:
                upload_document(data.get(data_key), prefix, data.get(type_key), TenantDocuments, {"tenant": profile}, folder_name, user)
        elif user_role == constants.COMPANY_USER:
            for data_key, prefix, type_key in EMIRATES_VISA_DOC_SPECS:
                doc = upload_document(data.get(data_key), prefix, data.get(type_key), Documents, {}, folder_name, user)
                if doc:
                    PropertyManagerDocuments.objects.create(company_user=profile, document=doc, created_by=user)

    return prepare_response(
        message=constants.SIGNUP_SUCCESS,
        content={"user_id": user.id, "profile_id": profile.id, "email": email, "role": user_role},
        status=status.HTTP_201_CREATED
    )




@is_request_authenticated
def userprofile_view(request):
    user_profile = request.user  
    if request.method == "GET":
        try:
            user = user_profile.user
            city = user_profile.city
            state = city.state if city else None
            country = state.country if state else None

            data = {
                "id": user_profile.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_role": user_profile.user_role,
                "profile_image": user_profile.profile_image,
                "city": {
                    "key": city.id if city else None,
                    "value": city.name if city else None,
                },
                "state": {
                    "key": state.id if state else None,
                    "value": state.name if state else None,
                },
                "country": {
                    "key": country.id if country else None,
                    "value": country.name if country else None,
                },
                "locality": user_profile.locality,
                "postal_code": user_profile.pin_code,
                "address": user_profile.address,
                "additional_address": user_profile.additional_address,
                "contact_number": user_profile.contact_number,
                "emirate_id": user_profile.emirate_id,
                "uae_residence_visa": user_profile.uae_residence_visa,
                "trade_license_number": user_profile.trade_license_number,
                "time_zone": user_profile.time_zone,
                "utc": user_profile.utc,
                "manage_through": user_profile.manage_through,
            }

            return prepare_response(
                content=data,
                message=constants.USER_PROFILE_FETCHED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            user = user_profile.user

            restricted_fields = ["email", "user_role", "password"]
            for field in restricted_fields:
                body.pop(field, None)

            if "first_name" in body:
                user.first_name = body.get("first_name")
            if "last_name" in body:
                user.last_name = body.get("last_name")
            user.save()

            if "city" in body:
                city_id = body["city"]
                if city_id:
                    user_profile.city = City.objects.filter(id=city_id).first()
                else:
                    user_profile.city = None

            simple_fields = [
                "profile_image",
                "locality",
                "pin_code",
                "address",
                "additional_address",
                "contact_number",
                "emirate_id",
                "uae_residence_visa",
                "trade_license_number",
                "time_zone",
                "utc",
                "manage_through",
            ]
            for field in simple_fields:
                if field in body:
                    setattr(user_profile, field, body[field])
            user_profile.save()
               
                    
            return prepare_response(
                message=constants.USER_PROFILE_UPDATED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )



@is_request_authenticated
def user_management(request):
    user = request.user 
    try:
        if request.method == "POST":
            body = json.loads(request.body)
            first_name = body.get("first_name")
            last_name = body.get("last_name")
            email = body.get("email")
            password = body.get("password")
            phone = body.get("phone")
            role = body.get("role")
            city_id = body.get("city_id")
       
            if not all([first_name, last_name, email, password, role]):
                return prepare_response(
                    message=constants.ALL_FIELD_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if role not in [constants.OWNER, constants.TENANT]:
                return prepare_response(
                    message=constants.UNAUTHORIZED_USER_ROLE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if User.objects.filter(email=email).exists():
                return prepare_response(
                    message=constants.EMAIL_ALREADY_REGISTERED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            django_user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            city_instance = None
            if city_id:
                city_instance = City.objects.filter(id=city_id).first()

            profile = UserProfile.objects.create(
                user=django_user,
                user_role=role,
                contact_number=phone,
                address=body.get("address"),
                locality=body.get("locality"),
                pin_code=body.get("pin_code"),
                profile_image=body.get("profile_image"),
                city=city_instance,
                created_by=user.user
            )

            return prepare_response(
                message=constants.USER_CREATED,
                content={
                    "user_id": profile.id,
                    "email": django_user.email,
                    "role": profile.user_role
                },
                status=status.HTTP_201_CREATED
            )
        elif request.method == "GET":
            is_active_param = request.GET.get("is_active", "true").lower()
            is_active = is_active_param == "true"
            role = request.GET.get("role")
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            start_epoch = request.GET.get("start_date")
            end_epoch = request.GET.get("end_date")
            user_id = request.GET.get("user_id")
            users_qs = UserProfile.objects.select_related("user").filter( is_active=is_active,created_by=user.user,is_staff=False)
            if role:
                users_qs = users_qs.filter(user_role=role)
            if user_id:
                users_qs = users_qs.filter(id=user_id)
            if start_epoch and end_epoch:
                s = safe_epoch_to_datetime(int(start_epoch))
                e = safe_epoch_to_datetime(int(end_epoch))
                users_qs = users_qs.filter(created__range=(s, e))
            if search:
                users_qs = users_qs.filter(
                    Q(user__email__icontains=search) |
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(contact_number__icontains=search)
                )

            users_qs = users_qs.order_by("-created")
            paginator = Paginator(users_qs, limit)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)
            data = []
            for profile in page_obj:
                role_key = profile.user_role
                role_value = role_key.replace("_", " ").title()
                data.append({
                    "id": profile.id,
                    "email": profile.user.email,
                    "first_name": profile.user.first_name,
                    "last_name": profile.user.last_name,
                    "contact_number": profile.contact_number,
                    "address": profile.address,
                    "locality": profile.locality,
                    "pin_code": profile.pin_code,
                    "profile_image": profile.profile_image,
                    "is_active": profile.is_active,
                    "created_on": datetime_to_epoch_millis(profile.created),
                    "last_login": datetime_to_epoch_millis(profile.user.last_login) if profile.user.last_login else None,
                    "role": {
                        "key": role_key,
                        "value": role_value
                    }
                })

            pagination_meta = {
                "current_page": page_obj.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }

            return prepare_response(
                message=constants.USER_FETCHED_SUCCESS,
                content=data,
                pagination=pagination_meta,
                status=status.HTTP_200_OK
            )
        elif request.method == "PUT":
            return prepare_response(
                message="Update user API will be added later",
                status=status.HTTP_501_NOT_IMPLEMENTED
            )
        elif request.method == "DELETE":
            user_id = request.GET.get("user_id")
            if not user_id:
                return prepare_response(message=constants.USER_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)
            
            profile = UserProfile.objects.select_related("user").filter(
                          id=user_id,
                          created_by=user.user).first()
            if not profile:
                return prepare_response( message=constants.USER_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            if profile.is_active: 
                profile.is_active = False
                profile.save(update_fields=["is_active"])
                return prepare_response(message="User deactivated successfully",content={"user_id": profile.id,"is_active": profile.is_active},status=status.HTTP_200_OK)
            django_user = profile.user
            profile.delete()
            django_user.delete()
            return prepare_response(
                message=constants.USER_PERMANENTLY_DELETED,
                 status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message=constants.INVALID_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def create_role(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        body = json.loads(request.body)
        role_name = body.get("name")
        if not role_name:
            return prepare_response(
                message=constants.ROLE_IS_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        user_profile = request.user 
        django_user = user_profile.user
        company = PropertyManagmentCompany.objects.filter(company_user=user_profile, is_active=True).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )
        if Role.objects.filter(
            name__iexact=role_name,
            company=company,
            is_active=True
        ).exists():
            return prepare_response(
                message=constants.ROLE_ALREADY_EXISTS_IN_COMPANY,
                status=status.HTTP_400_BAD_REQUEST
            )

        role = Role.objects.create(
            name=role_name,
            company=company,
            created_by=django_user
        )
        return prepare_response(
            content={
                "id": role.id,
                "name": role.name,
                "company": company.company_name
            },
            message=constants.ROLE_CREATED_SUCCESS,
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        print("Create Role Error:", e)
        return prepare_response(
            message=constants.SOMETHING_WENT_WRONG,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



@is_request_authenticated
def staff_view(request):
    user = request.user 
    if request.method == "POST":
        try:
            body = json.loads(request.body)
            staff_name = body.get("staff_name")
            email = body.get("email")
            contact = body.get("contact_number")
            role_ids = body.get("roles", [])              
            property_ids = body.get("properties", [])     
            password = body.get("password")
            confirm_password = body.get("confirm_password")
            emirate_id = body.get("emirate_id")
            city_id = body.get("city")  
            locality = body.get("locality")
            address = body.get("address")
            additional_address = body.get("additional_address")
            pin_code = body.get("postal_code")

            if not all([staff_name, email, contact, password, confirm_password]):
                return prepare_response(
                    message=constants.ALL_FIELD_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if password != confirm_password:
                return prepare_response(
                    message=constants.PASSWORD_MISMATCH,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if User.objects.filter(username=email).exists():
                return prepare_response(
                    message=constants.USER_ALREADY_EXISTS_EMAIL,
                    status=status.HTTP_400_BAD_REQUEST
                )

            company = PropertyManagmentCompany.objects.filter(
                company_user=user,
                is_active=True
            ).first()

            if not company:
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            city = City.objects.filter(id=city_id).first() if city_id else None

            django_user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=staff_name
            )
            staff_profile = UserProfile.objects.create(
                user=django_user,
                user_role=constants.COMPANY_USER,
                contact_number=contact,
                is_staff=True,
                emirate_id=emirate_id,
                city=city,
                locality=locality,
                address=address,
                additional_address=additional_address,
                pin_code=pin_code,
                created_by=user.user
            )
            company_staff = CompanyStaff.objects.create(
                staff=staff_profile,
                company=company,
                created_by=user.user
            )
            if role_ids:
                roles = Role.objects.filter(id__in=role_ids, company=company)
                company_staff.roles.set(roles)

            if property_ids:
                properties = Unit.objects.filter(
                    id__in=property_ids,
                    company=company
                )
                for prop in properties:
                    prop.assigned_staff.add(company_staff)

            return prepare_response(
                message=constants.STAFF_CREATION_SUCCESS,
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return prepare_response(
                message=constants.SOMETHING_WENT_WRONG,
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
            staff_id = body.get("staff_id")
            if not staff_id:
                return prepare_response(message=constants.STAFF_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)
            company = PropertyManagmentCompany.objects.filter(company_user=user, is_active=True).first()
            if not company:
                return prepare_response(message=constants.COMPANY_NOT_FOUND,status=status.HTTP_404_NOT_FOUND)
            company_staff = CompanyStaff.objects.filter(id=staff_id, company=company).first()
            if not company_staff:
                return prepare_response(message=constants.STAFF_NOT_FOUND,status=status.HTTP_404_NOT_FOUND)
            staff_profile = company_staff.staff
            django_user = staff_profile.user
            if "staff_name" in body:
                django_user.first_name = body["staff_name"]
            if "email" in body:
                email = body["email"]
                if User.objects.filter(username=email).exclude(id=django_user.id).exists():
                    return prepare_response(message=constants.EMAIL_ALREADY_REGISTERED,status=status.HTTP_400_BAD_REQUEST)
                django_user.username = email
                django_user.email = email
            django_user.save()

            if "contact" in body:
                staff_profile.contact_number = body["contact"]
            if "emirate_id" in body:
                staff_profile.emirate_id = body["emirate_id"]
            if "city_id" in body:
                city = City.objects.filter(id=body["city_id"]).first()
                staff_profile.city = city
            if "locality" in body:
                staff_profile.locality = body["locality"]
            if "address" in body:
                staff_profile.address = body["address"]
            if "additional_address" in body:
                staff_profile.additional_address = body["additional_address"]
            if "postal_code" in body:
                staff_profile.pin_code = body["postal_code"]
            staff_profile.save()
            if "roles" in body:
                role_ids = body["roles"]
                roles = Role.objects.filter(id__in=role_ids, company=company)
                company_staff.roles.set(roles)
            if "properties" in body:
                property_ids = body["properties"]
                properties = Unit.objects.filter(id__in=property_ids, company=company)
                for prop in company_staff.assigned_properties.exclude(id__in=property_ids):
                    prop.assigned_staff.remove(company_staff)
                for prop in properties:
                    prop.assigned_staff.add(company_staff)
            return prepare_response(
                message=constants.STAFF_DETAILS_UPDATED_SUCCESS,status=status.HTTP_200_OK)
        except Exception as e:
            return prepare_response(message=constants.SOMETHING_WENT_WRONG,status=status.HTTP_500_INTERNAL_SERVER_ERROR)


    elif request.method == "GET":
        search = request.GET.get("search", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        role_id = request.GET.get("role_id")
        staff_id = request.GET.get("staff_id")

        company = PropertyManagmentCompany.objects.filter(
            company_user=user,
            is_active=True
        ).first()

        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        staff_qs = CompanyStaff.objects.filter(
            company=company,
            staff__is_active=True
        ).select_related(
            "staff__user"
        ).prefetch_related(
            "roles",
            "assigned_properties"
        )

        if staff_id:
            company_staff = CompanyStaff.objects.filter(
                              id=staff_id,
                             company=company
                              ).select_related(
                             "staff__user",
                             "staff__city"
                             ).prefetch_related(
                              "roles",
                              "assigned_properties",
                            "assigned_properties__property",
                             "assigned_properties__lease_details",
                              "assigned_properties__owner"
                            ).first()


            if not company_staff:
                return prepare_response(
                    message=constants.STAFF_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND)
            staff_data = get_staff_details(company_staff, include_password=True)
            properties_table = []
            for unit in company_staff.assigned_properties.all():
                lease = unit.lease_details.first()
                property_image = None
                image_response = get_property_images(unit.id, single=True)
                if not image_response.get("error") and image_response.get("images"):
                    property_image = image_response["images"][0]

                properties_table.append({
            "property_name": unit.property.property_name if unit.property else None,
            "property_code": unit.property_code,
            "property_image": property_image,
            "tenant_name": (
                lease.tenant.user.get_full_name()
                if lease and lease.tenant and lease.tenant.user
                else None
            ),
            "tenant_profile_image":lease.tenant.profile_image,
            
            
            "owner_name": (
                unit.owner.user.get_full_name()
                if unit.owner and unit.owner.user
                else None
            ),
            "lease_id": lease.id if lease else None
        })
                
            staff_data["assigned_properties"] = properties_table
            return prepare_response(
        content=staff_data,
        message=constants.STAFF_DETAILS_FETCH_SUCCESS,
        status=status.HTTP_200_OK
    )
        if search:
            staff_qs = staff_qs.filter(
                Q(staff__user__first_name__icontains=search) |
                Q(staff__user__email__icontains=search) |
                Q(staff__contact_number__icontains=search)
            )
        if role_id:
            staff_qs = staff_qs.filter(roles__id=role_id)

        paginator = Paginator(staff_qs, limit)
        try:
            staff_page = paginator.page(page)
        except EmptyPage:
            staff_page = paginator.page(paginator.num_pages)

        data = []
        for staff in staff_page:
            total_properties = staff.assigned_properties.count()
            occupied = staff.assigned_properties.filter(is_occupied=True).count()
            tenancy_ratio = f"{occupied}:{total_properties}" if total_properties else "0:0"
            data.append({
                "staff_id": staff.id,
                "staff_name": staff.staff.user.get_full_name(),
                "email": staff.staff.user.email,
                "contact_number": staff.staff.contact_number,
                "roles": [r.name for r in staff.roles.all()],
                "property_count": total_properties,
                "tenancy_ratio": tenancy_ratio
            })
        pagination_meta = {
            "current_page": staff_page.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }
        return prepare_response(
            content=data,
            pagination=pagination_meta,
            message=constants.STAFF_DETAILS_FETCH_SUCCESS,
            status=status.HTTP_200_OK
        )
    elif request.method == "DELETE":
        pass
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def role_table_view(request):
    user = request.user
    if request.method != "GET":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        search = request.GET.get("search", "").strip()
        page = int(request.GET.get("page", 1))
        limit = int(request.GET.get("limit", 10))
        start_epoch = request.GET.get("start_date")
        end_epoch = request.GET.get("end_date")
        is_active_param = request.GET.get("is_active", "true").lower()
        is_active = is_active_param == "true"
        company = PropertyManagmentCompany.objects.filter(company_user=user, is_active=True).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )
        roles_qs = Role.objects.filter(company=company, is_active=is_active)
        if search:
            roles_qs = roles_qs.filter(name__icontains=search)
        if start_epoch and end_epoch:
            start_dt = safe_epoch_to_datetime(int(start_epoch))
            end_dt = safe_epoch_to_datetime(int(end_epoch))
            roles_qs = roles_qs.filter(created__range=(start_dt, end_dt))
        roles_qs = roles_qs.order_by("-created")
        paginator = Paginator(roles_qs, limit)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        data = []
        for role in page_obj:
            data.append({
                "role_id": role.id,
                "role_name": role.name,
                "created_on": datetime_to_epoch_millis(role.created)
            })
        pagination_meta = {
            "current_page": page_obj.number,
            "limit": limit,
            "total_records": paginator.count,
            "total_pages": paginator.num_pages
        }
        return prepare_response(
            message=constants.ROLES_FETCH_SUCCESS,
            content=data,
            pagination=pagination_meta,
            status=status.HTTP_200_OK
        )
    except Exception as e:
        print("Role Table Error:", e)
        return prepare_response(
            message=constants.SOMETHING_WENT_WRONG,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def export_users_csv(request):
    try:
        if request.method != "GET":
            return prepare_response(message=constants.INVALID_REQUEST_METHOD,status=status.HTTP_405_METHOD_NOT_ALLOWED)
        user = request.user

        is_active_param = request.GET.get("is_active", "true").lower()
        is_active = is_active_param == "true"
        role = request.GET.get("role")
        search = request.GET.get("search", "").strip()
        start_epoch = request.GET.get("start_date")
        end_epoch = request.GET.get("end_date")
        user_id = request.GET.get("user_id")
        users_qs = UserProfile.objects.select_related("user").filter(
            is_active=is_active,
            created_by=user.user)
        if role:
            users_qs = users_qs.filter(user_role=role)
        if user_id:
            users_qs = users_qs.filter(id=user_id)
        if start_epoch and end_epoch:
            s = safe_epoch_to_datetime(int(start_epoch))
            e = safe_epoch_to_datetime(int(end_epoch))
            users_qs = users_qs.filter(created__range=(s, e))
        if search:
            users_qs = users_qs.filter(
                Q(user__email__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(contact_number__icontains=search)
            )
        users_qs = users_qs.order_by("-created")

        field_names = [
            "User Name",
            "Phone",
            "Role",
            "Email",
            "Created On",
            "Last Login",
            "Status"
        ]

        data_list = []

        for profile in users_qs:
            role_value = profile.user_role.replace("_", " ").title()

            data_list.append({
                "User Name": f"{profile.user.first_name} {profile.user.last_name}".strip(),
                "Phone": profile.contact_number,
                "Role": role_value,
                "Email": profile.user.email,
                "Created On": profile.created.strftime("%d-%m-%Y %H:%M"),
                "Last Login": (
                    profile.user.last_login.strftime("%d-%m-%Y %H:%M")
                    if profile.user.last_login else ""
                ),
                "Status": "Active" if profile.is_active else "Inactive"
            })

        return export_to_csv(
            filename="users_export",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting users CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@is_request_authenticated
def export_staff_csv(request):
    try:
        if request.method != "GET":
            return prepare_response(
                message=constants.INVALID_REQUEST_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

        user = request.user
        search = request.GET.get("search", "").strip()
        role_id = request.GET.get("role_id")
        staff_id = request.GET.get("staff_id")

        company = PropertyManagmentCompany.objects.filter(
            company_user=user,
            is_active=True
        ).first()

        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

 
        if staff_id:
            staff = CompanyStaff.objects.filter(
                id=staff_id,
                company=company
            ).select_related(
                "staff__user"
            ).prefetch_related(
                "assigned_properties",
                "assigned_properties__property",
                "assigned_properties__lease_details",
                "assigned_properties__owner"
            ).first()

            if not staff:
                return prepare_response(
                    message=constants.STAFF_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            field_names = [
                "Code",
                "Property Name",
                "Tenant Name",
                "Assigned Staff",
                "Owner Name",
                "Document"
            ]

            data_list = []

            for unit in staff.assigned_properties.all():
                lease = unit.lease_details.first()

                data_list.append({
                    "Code": unit.property_code,
                    "Property Name": unit.property.property_name if unit.property else "",
                    "Tenant Name": (
                        lease.tenant.user.get_full_name()
                        if lease and lease.tenant and lease.tenant.user else ""
                    ),
                    "Assigned Staff": staff.staff.user.get_full_name(),
                    "Owner Name": (
                        unit.owner.user.get_full_name()
                        if unit.owner and unit.owner.user else ""
                    ),
                    "Document": ""  
                })

            return export_to_csv(
                filename="staff_property_details",
                field_names=field_names,
                data_list=data_list
            )


        staff_qs = CompanyStaff.objects.filter(
            company=company,
            staff__is_active=True
        ).select_related(
            "staff__user"
        ).prefetch_related(
            "roles",
            "assigned_properties"
        )

        if search:
            staff_qs = staff_qs.filter(
                Q(staff__user__first_name__icontains=search) |
                Q(staff__user__email__icontains=search) |
                Q(staff__contact_number__icontains=search)
            )

        if role_id:
            staff_qs = staff_qs.filter(roles__id=role_id)

        field_names = [
            "Staff Name",
            "Code",
            "Contact Number",
            "Properties",
            "Tenancy Ratio",
            "Staff Role"
        ]

        data_list = []

        for staff in staff_qs:
            total_properties = staff.assigned_properties.count()
            occupied = staff.assigned_properties.filter(is_occupied=True).count()
            tenancy_ratio = f"{occupied}:{total_properties}" if total_properties else "0:0"

            data_list.append({
                "Staff Name": staff.staff.user.get_full_name(),
                "Code": staff.staff.user_code,
                "Contact Number": staff.staff.contact_number,
                "Properties": total_properties,
                "Tenancy Ratio": tenancy_ratio,
                "Staff Role": ", ".join([r.name for r in staff.roles.all()])
            })

        return export_to_csv(
            filename="staff_list",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        return prepare_response(
            message=f"Error exporting staff CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def contact_list_view(request):

    if request.method == "GET":

        search = request.GET.get("search")
        logged_in_profile = request.user
        role_filter = logged_in_profile.user_role

        profiles = UserProfile.objects.select_related("user")

        if role_filter and role_filter.upper() != "ALL":
            profiles = profiles.filter(user_role=role_filter.upper())

        if search:
            profiles = profiles.filter(
                Q(user__first_name__istartswith=search) |
                Q(user__last_name__istartswith=search) |
                Q(user__email__istartswith=search) |
                Q(contact_number__icontains=search)
            )

        results = [
            {
                "id": profile.id,
                "full_name": f"{profile.user.first_name} {profile.user.last_name}",
                "email": profile.user.email,
                "phone": profile.contact_number
            }
            for profile in profiles
        ]

        return prepare_response(
            content=results,
            message=constants.CONTACTS_FETCH_SUCCESS
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )

# ─────────────────────────────────────────────────────────────
#  Owner CRUD
# ─────────────────────────────────────────────────────────────

def _serialize_owner(owner):
    return {
        "id": owner.id,
        "code": owner.code or "",
        "name": f"{owner.user.first_name} {owner.user.last_name}".strip(),
        "first_name": owner.user.first_name or "",
        "last_name": owner.user.last_name or "",
        "email": owner.email or owner.user.email or "",
        "contact_number": owner.contact_number or "",
        "emirates_id": owner.emirate_id or "",
        "nationality": owner.nationality or "",
        "address_line_1": owner.address_line_1 or "",
        "address_line_2": owner.address_line_2 or "",
        "pin_code": owner.pin_code or "",
        "passport_number": owner.passport_number or "",
        "passport_expiry_date": owner.passport_expiry_datetime.strftime("%Y-%m-%d") if owner.passport_expiry_datetime else "",
        "visa_number": owner.visa_number or "",
        "visa_expiry_date": owner.visa_expiry_datetime.strftime("%Y-%m-%d") if owner.visa_expiry_datetime else "",
        "owner_number": owner.owner_number or "",
        "trade_license_number": owner.trade_license_number or "",
        "license_number": owner.license_number or "",
        "license_expiry_date": owner.license_expiry_date.strftime("%Y-%m-%d") if owner.license_expiry_date else "",
        "license_issuer": owner.license_issuer or "",
        "fax_number": owner.fax_number or "",
        "po_box_number": owner.po_box_number or "",
        "profile_image": owner.profile_image or "",
    }


@is_request_authenticated
def owner_crud(request):
    if request.method == "GET":
        owner_id = request.GET.get("owner_id", "").strip()

        if owner_id:
            owner = Owner.objects.select_related("user").filter(id=owner_id, user__is_active=True).first()
            if not owner:
                return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)
            return prepare_response(content=_serialize_owner(owner), message="Owner fetched", status=status.HTTP_200_OK)

        search = request.GET.get("search", "").strip()
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        export = request.GET.get("export", "").strip()

        # Filter owners created by any staff member of the logged-in user's PMC
        user_profile = request.user
        pm = PropertyManager.objects.filter(id=user_profile.id).select_related("company").first()
        company = pm.company if pm else None
        if company:
            pmc_staff_user_ids = PropertyManager.objects.filter(
                company=company
            ).values_list("user_id", flat=True)
            owners = Owner.objects.select_related("user").filter(
                user__is_active=True,
                created_by__in=pmc_staff_user_ids,
            ).order_by("-id")
        else:
            owners = Owner.objects.select_related("user").filter(user__is_active=True).order_by("-id")

        if search:
            owners = owners.filter(
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(email__icontains=search) |
                Q(user__email__icontains=search) |
                Q(contact_number__icontains=search) |
                Q(owner_number__icontains=search) |
                Q(code__icontains=search)
            )

        if export == "csv":
            rows = [_serialize_owner(o) for o in owners]
            fields = ["code", "name", "owner_number", "email", "contact_number", "emirates_id",
                      "trade_license_number", "license_number", "license_expiry_date",
                      "license_issuer", "fax_number", "po_box_number"]
            return export_to_csv("owners", fields, rows)

        paginator = Paginator(owners, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)

        return prepare_response(
            content=[_serialize_owner(o) for o in page_obj.object_list],
            message="Owners fetched",
            status=status.HTTP_200_OK,
            pagination={
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
                "current_page": page,
                "page_size": page_size,
            }
        )

    elif request.method == "POST":
        from datetime import datetime as dt
        data = json.loads(request.body)
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        email = data.get("email", "").strip()

        if not email:
            return prepare_response(message="Email is required", status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=email).exists():
            return prepare_response(message="Email already registered", status=status.HTTP_400_BAD_REQUEST)

        expiry_raw = data.get("license_expiry_date")
        expiry_date = None
        if expiry_raw:
            try:
                expiry_date = dt.strptime(expiry_raw[:10], "%Y-%m-%d")
            except ValueError:
                pass

        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email,
                first_name=first_name, last_name=last_name,
                password=User.objects.make_random_password()
            )
            def _parse_dt(val):
                if not val:
                    return None
                try:
                    return dt.strptime(str(val)[:10], "%Y-%m-%d")
                except ValueError:
                    return None

            owner = Owner.objects.create(
                user=user,
                created_by=request.user.user,
                email=email,
                contact_number=data.get("contact_number", ""),
                emirate_id=data.get("emirates_id", ""),
                nationality=data.get("nationality", ""),
                address_line_1=data.get("address_line_1", ""),
                address_line_2=data.get("address_line_2", ""),
                pin_code=data.get("pin_code", ""),
                passport_number=data.get("passport_number", ""),
                passport_expiry_datetime=_parse_dt(data.get("passport_expiry_date")),
                visa_number=data.get("visa_number", ""),
                visa_expiry_datetime=_parse_dt(data.get("visa_expiry_date")),
                trade_license_number=data.get("trade_license_number", ""),
                owner_number=data.get("owner_number", ""),
                license_number=data.get("license_number", ""),
                license_expiry_date=expiry_date,
                license_issuer=data.get("license_issuer", ""),
                fax_number=data.get("fax_number", ""),
                po_box_number=data.get("po_box_number", ""),
            )

        return prepare_response(content=_serialize_owner(owner), message="Owner created", status=status.HTTP_201_CREATED)

    elif request.method == "PUT":
        from datetime import datetime as dt
        data = json.loads(request.body)
        owner_id = data.get("owner_id")
        if not owner_id:
            return prepare_response(message="owner_id is required", status=status.HTTP_400_BAD_REQUEST)

        owner = Owner.objects.select_related("user").filter(id=owner_id).first()
        if not owner:
            return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)

        user = owner.user
        if "first_name" in data:
            user.first_name = data["first_name"]
        if "last_name" in data:
            user.last_name = data["last_name"]
        user.save()

        simple_fields = {
            "contact_number": "contact_number",
            "emirates_id": "emirate_id",
            "nationality": "nationality",
            "address_line_1": "address_line_1",
            "address_line_2": "address_line_2",
            "pin_code": "pin_code",
            "passport_number": "passport_number",
            "visa_number": "visa_number",
            "trade_license_number": "trade_license_number",
            "owner_number": "owner_number",
            "license_number": "license_number",
            "license_issuer": "license_issuer",
            "fax_number": "fax_number",
            "po_box_number": "po_box_number",
        }
        for src, dest in simple_fields.items():
            if src in data:
                setattr(owner, dest, data[src] or "")

        def _parse_dt(val):
            if not val:
                return None
            try:
                return dt.strptime(str(val)[:10], "%Y-%m-%d")
            except ValueError:
                return None

        if "license_expiry_date" in data:
            owner.license_expiry_date = _parse_dt(data["license_expiry_date"])
        if "passport_expiry_date" in data:
            owner.passport_expiry_datetime = _parse_dt(data["passport_expiry_date"])
        if "visa_expiry_date" in data:
            owner.visa_expiry_datetime = _parse_dt(data["visa_expiry_date"])

        owner.save()
        return prepare_response(content=_serialize_owner(owner), message="Owner updated", status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        owner_id = request.GET.get("owner_id", "").strip()
        if not owner_id:
            return prepare_response(message="owner_id is required", status=status.HTTP_400_BAD_REQUEST)

        owner = Owner.objects.select_related("user").filter(id=owner_id).first()
        if not owner:
            return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)

        owner.user.is_active = False
        owner.user.save()
        return prepare_response(message="Owner deleted", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def _serialize_tenant(tenant):
    return {
        "id": tenant.id,
        "code": tenant.code or "",
        "name": f"{tenant.user.first_name} {tenant.user.last_name}".strip(),
        "first_name": tenant.user.first_name or "",
        "last_name": tenant.user.last_name or "",
        "email": tenant.email or tenant.user.email or "",
        "contact_number": tenant.contact_number or "",
        "emirates_id": tenant.emirate_id or "",
        "nationality": tenant.nationality or "",
        "address_line_1": tenant.address_line_1 or "",
        "address_line_2": tenant.address_line_2 or "",
        "pin_code": tenant.pin_code or "",
        "passport_number": tenant.passport_number or "",
        "passport_expiry_date": tenant.passport_expiry_datetime.strftime("%Y-%m-%d") if tenant.passport_expiry_datetime else "",
        "visa_number": tenant.visa_number or "",
        "visa_expiry_date": tenant.visa_expiry_datetime.strftime("%Y-%m-%d") if tenant.visa_expiry_datetime else "",
    }


@is_request_authenticated
def tenant_crud(request):
    from datetime import datetime as dt

    def _parse_dt(val):
        if not val:
            return None
        try:
            return dt.strptime(str(val)[:10], "%Y-%m-%d")
        except ValueError:
            return None

    def _apply_tenant_fields(tenant, data):
        user = tenant.user
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        if not first_name and not last_name:
            name = data.get("name", "").strip()
            if name:
                first_name, _, last_name = name.partition(" ")
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name
        user.save()

        for src, dest in [
            ("contact_number", "contact_number"),
            ("emirates_id", "emirate_id"),
            ("nationality", "nationality"),
            ("address_line_1", "address_line_1"),
            ("address_line_2", "address_line_2"),
            ("pin_code", "pin_code"),
            ("passport_number", "passport_number"),
            ("visa_number", "visa_number"),
        ]:
            if src in data:
                setattr(tenant, dest, data[src] or "")

        if "passport_expiry_date" in data:
            tenant.passport_expiry_datetime = _parse_dt(data["passport_expiry_date"])
        if "visa_expiry_date" in data:
            tenant.visa_expiry_datetime = _parse_dt(data["visa_expiry_date"])

        tenant.save()
        return tenant

    # ── GET ──────────────────────────────────────────────────────────────────
    if request.method == "GET":
        tenant_id = request.GET.get("tenant_id", "").strip()
        email = request.GET.get("email", "").strip()

        if tenant_id:
            tenant = Tenant.objects.select_related("user").filter(id=tenant_id, user__is_active=True).first()
            if not tenant:
                return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)
            return prepare_response(content=_serialize_tenant(tenant))

        if email:
            tenant = Tenant.objects.select_related("user").filter(
                Q(email__iexact=email) | Q(user__email__iexact=email),
                user__is_active=True,
            ).first()
            if not tenant:
                return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)
            return prepare_response(content=_serialize_tenant(tenant))

        return prepare_response(message="tenant_id or email is required", status=status.HTTP_400_BAD_REQUEST)

    # ── POST (create or find-and-update by email) ─────────────────────────────
    elif request.method == "POST":
        data = json.loads(request.body)
        email = (data.get("email") or "").strip()

        if not email:
            return prepare_response(message="email is required", status=status.HTTP_400_BAD_REQUEST)

        # Check if tenant with this email already exists
        existing = Tenant.objects.select_related("user").filter(
            Q(email__iexact=email) | Q(user__email__iexact=email),
            user__is_active=True,
        ).first()

        if existing:
            _apply_tenant_fields(existing, data)
            return prepare_response(content=_serialize_tenant(existing), message="Tenant updated")

        # Create new tenant
        name = data.get("name", "").strip()
        first_name = data.get("first_name", "") or (name.partition(" ")[0] if name else "")
        last_name = data.get("last_name", "") or (name.partition(" ")[2] if name else "")

        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email,
                first_name=first_name, last_name=last_name,
                password=User.objects.make_random_password(),
            )
            tenant = Tenant.objects.create(
                user=user,
                created_by=request.user.user,
                email=email,
                contact_number=data.get("contact_number", ""),
                emirate_id=data.get("emirates_id", ""),
                nationality=data.get("nationality", ""),
                address_line_1=data.get("address_line_1", ""),
                address_line_2=data.get("address_line_2", ""),
                pin_code=data.get("pin_code", ""),
                passport_number=data.get("passport_number", ""),
                passport_expiry_datetime=_parse_dt(data.get("passport_expiry_date")),
                visa_number=data.get("visa_number", ""),
                visa_expiry_datetime=_parse_dt(data.get("visa_expiry_date")),
            )

        return prepare_response(content=_serialize_tenant(tenant), message="Tenant created", status=status.HTTP_201_CREATED)

    # ── PUT ───────────────────────────────────────────────────────────────────
    elif request.method == "PUT":
        data = json.loads(request.body)
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            return prepare_response(message="tenant_id is required", status=status.HTTP_400_BAD_REQUEST)

        tenant = Tenant.objects.select_related("user").filter(id=tenant_id, user__is_active=True).first()
        if not tenant:
            return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)

        _apply_tenant_fields(tenant, data)
        return prepare_response(content=_serialize_tenant(tenant), message="Tenant updated")

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)
