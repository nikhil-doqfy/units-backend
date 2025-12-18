import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response ,upload_file_to_s3_base64 ,datetime_to_epoch,epoch_to_datetime,datetime_to_epoch_millis,safe_epoch_to_datetime ,generate_unique_code ,get_extension_from_base64
from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,StaffDocumentsMapping,CompanyUserDocumentsMapping,TenantDocumentsMapping , Company,Country, State, City , Role
# from property_management.models import OwnerDetails , TenantDetails
from user_service.utils import request_otp_sent
from django.db import transaction
from utilities.decorator import is_request_authenticated
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.utils import timezone
from django.utils.timezone import make_aware
import random
import time
from django.contrib.auth.models import User
from django.db import transaction


def user_sign_up(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    try:
        data = json.loads(request.body)

        with transaction.atomic():  
            email = data.get("email")
            password = data.get("password")
            confirm_password = data.get("confirm_password")
            user_role = data.get("user_role")
            first_name = data.get("first_name")
            last_name = data.get("last_name")
            if not all([email, password, confirm_password, user_role]):
                prepare_response(message="All fields are required")
            if password != confirm_password:
                prepare_response(message="Password mismatch")
            if User.objects.filter(username=email).exists():
                prepare_response(message="Email already registered")

            user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            profile = UserProfile.objects.create(
                user=user,
                user_role=user_role,
                created_by=user,
                time_zone=data.get("time_zone"),
                utc=data.get("utc"),
                locality=data.get("locality"),
                pin_code=data.get("pin_code"),
                address=data.get("address"),
                additional_address=data.get("additional_address"),
                emirate_id=data.get("emirate_id"),
                uae_residence_visa=data.get("uae_residence_visa"),
                contact_number=data.get("contact_number"),
                trade_license_number=data.get("trade_license_number"),
                manage_through=data.get("manage_through") or constants.choices[0][0]
            )

            folder_name = f"{user_role.lower()}_documents/{profile.id}"

            def upload_document(base64_data, file_prefix):
                if not base64_data:
                    return None

                extension = get_extension_from_base64(base64_data) or ".png"
                filename = f"{file_prefix}{extension}"
                object_name = f"{folder_name}/{filename}"

                uploaded_url = upload_file_to_s3_base64(base64_data, object_name)
                if not uploaded_url:
                    prepare_response(message="Document upload failed")

                return Documents.objects.create(
                    file_name=filename,
                    file_path=uploaded_url,
                    created_by=user
                )

            emirates_doc = upload_document(data.get("emirates_id_doc"), "emirates_id")
            visa_doc = upload_document(data.get("uae_residence_visa_doc"), "uae_residence_visa")
            dld_doc = upload_document(data.get("dld_certificate_doc"), "dld_certificate")

            def create_mappings(mapping_model, profile, docs, attr_name):
                for doc in docs:
                    if doc:
                        mapping_model.objects.create(
                            **{attr_name: profile, "document": doc, "created_by": user}
                        )

            if user_role == constants.OWNER:
                create_mappings(OwnerDocumentsMapping, profile, [emirates_doc, visa_doc, dld_doc], "owner")

            if user_role == constants.TENANT:
                create_mappings(TenantDocumentsMapping, profile, [emirates_doc, visa_doc], "tenant")

            if user_role == constants.COMPANY_USER:
                create_mappings(CompanyUserDocumentsMapping, profile, [emirates_doc, visa_doc], "company_user")

                Company.objects.create(
                    company_user=profile,
                    company_code=data.get("company_code"),
                    company_name=data.get("company_name"),
                    company_address=data.get("company_address"),
                    created_by=user
                )

    
        return prepare_response(
            message="Signup successful",
            content={
                "user_id": user.id,
                "profile_id": profile.id,
                "email": email,
                "role": user_role
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        return prepare_response(
            message=str(e),
            status=status.HTTP_400_BAD_REQUEST
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
                "pin_code": user_profile.pin_code,
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
                message="User profile fetched successfully",
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

            updatable_fields = [
                "profile_image",
                "city",
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

            for field in updatable_fields:
                if field in body:
               
                    if field in ["country", "state", "city"]:
                        model_class = {"country": Country, "state": State, "city": City}[field]
                        try:
                            obj = model_class.objects.get(id=body[field])
                            setattr(user_profile, field, obj)
                        except model_class.DoesNotExist:
                            setattr(user_profile, field, None)
                    else:
                        setattr(user_profile, field, body[field])

            user_profile.save()

            return prepare_response(
                message="User profile updated successfully",
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
                    message="Required fields missing",
                    status=status.HTTP_400_BAD_REQUEST
                )

            if role not in [constants.OWNER, constants.TENANT]:
                return prepare_response(
                    message="Invalid role",
                    status=status.HTTP_400_BAD_REQUEST
                )

            if User.objects.filter(email=email).exists():
                return prepare_response(
                    message="User already exists",
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
                message="User created successfully",
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

         
            users_qs = UserProfile.objects.select_related("user").filter(
                     is_active=is_active,
                  created_by=user.user 
                    )

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
                status=501
            )
        elif request.method == "DELETE":
            user_id = request.GET.get("user_id")
            if not user_id:
                return prepare_response(message="user_id is required",status=status.HTTP_400_BAD_REQUEST)
            
            profile = UserProfile.objects.select_related("user").filter(
                          id=user_id,
                          created_by=user.user).first()
            if not profile:
                return prepare_response( message="User not found", status=status.HTTP_404_NOT_FOUND)
            if profile.is_active: 
                profile.is_active = False
                profile.save(update_fields=["is_active"])
                return prepare_response(message="User deactivated successfully",content={"user_id": profile.id,"is_active": profile.is_active},status=status.HTTP_200_OK)
            django_user = profile.user
            profile.delete()
            django_user.delete()
            return prepare_response(
                message="User permanently deleted successfully",
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
                message="Role name is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        user_profile = request.user 
        django_user = user_profile.user
        company = Company.objects.filter(company_user=user_profile, is_active=True).first()
        if not company:
            return prepare_response(
                message="Company not found for logged in user",
                status=status.HTTP_404_NOT_FOUND
            )
        if Role.objects.filter(
            name__iexact=role_name,
            company=company,
            is_active=True
        ).exists():
            return prepare_response(
                message="Role already exists in this company",
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
            message="Role created successfully",
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        print("Create Role Error:", e)
        return prepare_response(
            message="Something went wrong",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
