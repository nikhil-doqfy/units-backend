import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response ,upload_file_to_s3_base64 ,datetime_to_epoch,epoch_to_datetime,datetime_to_epoch_millis,safe_epoch_to_datetime ,generate_unique_code ,get_extension_from_base64
from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,StaffDocumentsMapping,CompanyUserDocumentsMapping,TenantDocumentsMapping , Company,Country, State, City
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
            message="Invalid request method",
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
                raise ValueError("All fields are required")

            if password != confirm_password:
                raise ValueError("Password mismatch")

            if User.objects.filter(username=email).exists():
                raise ValueError("Email already registered")

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
                    raise ValueError("Document upload failed")

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
            return prepare_response(message=str(e), status=500)

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
            return prepare_response(message=str(e), status=500)

    else:
        return prepare_response(
            message="Invalid request method",
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

            if not all([first_name, last_name, email, password, role]):
                return prepare_response(
                    message="Required fields missing",
                    status=400
                )

            if role not in [constants.OWNER, constants.TENANT]:
                return prepare_response(
                    message="Invalid role",
                    status=400
                )

            if User.objects.filter(email=email).exists():
                return prepare_response(
                    message="User already exists",
                    status=400
                )

            django_user = User.objects.create_user(
                username=email,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            profile = UserProfile.objects.create(
                user=django_user,
                user_role=role,
                contact_number=phone,
                address=body.get("address"),
                locality=body.get("locality"),
                pin_code=body.get("pin_code"),
                created_by=user.user
            )

            return prepare_response(
                message="User created successfully",
                content={
                    "user_id": profile.id,
                    "email": django_user.email,
                    "role": profile.user_role
                },
                status=201
            )

        # ---- GET: Fetch users with filters and pagination ----
        elif request.method == "GET":
            # ---- Query params ----
            is_active_param = request.GET.get("is_active", "true").lower()
            is_active = is_active_param == "true"

            role = request.GET.get("role")
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            start_epoch = request.GET.get("start_date")
            end_epoch = request.GET.get("end_date")
            user_id = request.GET.get("user_id")

            # ---- Base queryset ----
            users_qs = UserProfile.objects.select_related("user").filter(
                     is_active=is_active,
                  created_by=user.user  # only users created by this company user
                    )

            # ---- Filters ----
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

            # ---- Pagination ----
            total_count = users_qs.count()
            paginator = Paginator(users_qs, limit)

            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            # ---- Response data ----
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
                content={
                    "user_count": total_count,
                    "data": data
                },
                pagination=pagination_meta,
                status=200
            )

        # ---- PUT / DELETE placeholders ----
        elif request.method == "PUT":
            return prepare_response(
                message="Update user API will be added later",
                status=501
            )

        elif request.method == "DELETE":
            return prepare_response(
                message="Delete user API will be added later",
                status=501
            )

        else:
            return prepare_response(
                message="Invalid request method",
                status=405
            )

    except Exception as e:
        return prepare_response(
            message=f"Error: {str(e)}",
            status=500
        )




# @is_request_authenticated
# def user_profile_view(request):
#     try:
#         current_user = request.user

#         if request.method == "PUT":
#             data = json.loads(request.body)
#             user_fields = ["profile_image", "country", "time_zone", "utc","profile_image_type"]

          
#             first_name = data.get("first_name")
#             last_name = data.get("last_name")

#             if first_name:
#                 current_user.first_name = first_name.strip()
#             if last_name:
#                 current_user.last_name = last_name.strip()

#             current_user.save()
    

  
#             full_name = f"{current_user.first_name} {current_user.last_name}".strip()

       
#             related_data = {
#                 "mobile_number": data.get("contact_number"),
#                 "address": data.get("address"),
#                 "state": data.get("state"),
#                 "postal_code": data.get("postal_code"),
#             }


#             if current_user.user_type in [constants.OWNER, constants.TENANT]:
#                 related_data["full_name"] = full_name

#             elif current_user.user_type == constants.PROPERTY_MANAGER:
#                 related_data["company_name"] = data.get("company_name", full_name)

   
#             related_data = {k: v for k, v in related_data.items() if v is not None}

   
#             for field in user_fields:
#                 if field in data and data[field] is not None:
#                     setattr(current_user, field, data[field])
#             current_user.save()

        
#             if current_user.user_type == constants.OWNER:
#                 model = OwnerDetails

#             elif current_user.user_type == constants.TENANT:
#                 model = TenantDetails

#             elif current_user.user_type == constants.PROPERTY_MANAGER:
#                 model = PropertyManagerCompanyDetails

                
#                 if "mobile_number" in related_data:
#                     related_data["phone_number"] = related_data.pop("mobile_number")
#                 if "address" in related_data:
#                     related_data["company_address"] = related_data.pop("address")

#             else:
#                 model = None

        
#             if model:
#                 obj = model.objects.filter(user=current_user).first()
#                 if obj:
#                     for field, value in related_data.items():
#                         setattr(obj, field, value)
#                     obj.save()
#                 else:
#                     model.objects.create(user=current_user, **related_data)

#             return prepare_response(
#                 message=constants.PROFILE_UPDATED_SUCCESS,
#                 status=status.HTTP_200_OK
#             )


#         elif request.method == "GET":
          
#             user_data = {
#                 "id": current_user.id,
#                 "email": current_user.email,
                
#                 "profile_image": current_user.profile_image if current_user.profile_image else None,
#                 "country": current_user.country,
#                 "time_zone": current_user.time_zone,
#                 "utc": current_user.utc,
#                 "user_type": current_user.user_type,
#                 "first_name":current_user.first_name,
#                 "last_name":current_user.last_name,
#                 "profile_image_type":current_user.profile_image_type,
                
#             }

        
#             related_info = {}
#             if current_user.user_type == constants.OWNER:
#                 obj = OwnerDetails.objects.filter(user=current_user).first()
#                 if obj:
#                     related_info = {
#                         "full_name":obj.full_name,
#                         "contact_number": obj.mobile_number,
#                         "address": obj.address,
#                         "state": obj.state,
#                         "postal_code": obj.postal_code,
#                     }
#             elif current_user.user_type == constants.PROPERTY_MANAGER:
#                 obj = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
#                 if obj:
#                     related_info = {
#                         "contact_number": obj.phone_number,
#                         "address": obj.company_address,
#                         "state": obj.state,
#                         "postal_code": obj.postal_code,
#                         "company_name":obj.company_name,

#                     }
#             elif current_user.user_type == constants.TENANT:
#                 obj = TenantDetails.objects.filter(user=current_user).first()
#                 if obj:
#                     related_info = {
#                         "contact_number": obj.mobile_number,
#                         "address": obj.address,
#                         "state": obj.state,
#                         "postal_code": obj.postal_code,
#                     }

#             user_data.update(related_info)

#             return prepare_response(
#                 message=constants.USER_PROFILE_FETCHED,
#                 status=status.HTTP_200_OK,
#                 content=user_data
#             )

#         else:
#             return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

#     except Exception as e:
    
#         return prepare_response(
#             message=f"Error: {str(e)}",
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )




# def user_management_view(request):

#     if request.method == "GET":
#         try:
#             is_deleted_param = request.GET.get("is_deleted", "false").lower()
#             is_deleted = is_deleted_param == "true"

#             recently_user_param = request.GET.get("recently_user", "false").lower()
#             recently_user = recently_user_param == "true"


#             search = request.GET.get("search", "").strip()
#             page = int(request.GET.get("page", 1))
#             limit = int(request.GET.get("limit", 10))
#             start_epoch = request.GET.get("start_date")
#             end_epoch = request.GET.get("end_date")

#             user_type = request.GET.get("user_type")

#             users_qs = UserProfile.objects.filter(is_deleted=is_deleted)
#             if user_type:
#                 users_qs = users_qs.filter(user_type=user_type.upper())
#             user_id = request.GET.get("user_id")
#             if user_id:
#                 users_qs = users_qs.filter(id=user_id)

#             if start_epoch and end_epoch:
#                 try:
#                     start_epoch = int(start_epoch)
#                     end_epoch = int(end_epoch)

#                     s = safe_epoch_to_datetime(start_epoch)
#                     e = safe_epoch_to_datetime(end_epoch)

#                     if not s or not e:
#                         return prepare_response(
#                             message="Invalid epoch timestamp",
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#                     users_qs = users_qs.filter(created__range=[s, e])



#                 except Exception as e:
#                     return prepare_response(
#             message=f"Invalid epoch format: {str(e)}",
#             status=status.HTTP_400_BAD_REQUEST
#          )

            
#             if recently_user:
#                 users_qs = users_qs.filter(last_login__isnull=False).order_by("-last_login")[:5]

#             if search:
#                 users_qs = users_qs.filter(
#                     Q(email__icontains=search) |
#                     Q(owner_details__full_name__icontains=search) |
#                     Q(tenant_details__full_name__icontains=search) |
#                     Q(property_manager_details__full_name__icontains=search)
#                 ).distinct()

#             total_count = users_qs.count()
#             paginator = Paginator(users_qs, limit)
#             try:
#                 page_obj = paginator.page(page)
#             except EmptyPage:
#                 page_obj = paginator.page(paginator.num_pages)

#             data = []
#             for user in page_obj:
#                 phone_number = None
#                 user_type = user.user_type.lower()

#                 if user_type == "owner":
#                     details = getattr(user, "owner_details", None)
#                     if details.exists():
#                         phone_number = details.first().mobile_number

#                 elif user_type == "tenant":
#                     details = getattr(user, "tenant_details", None)
#                     if details.exists():
#                         phone_number = details.first().mobile_number

#                 elif user_type == "property_manager":
#                     details = getattr(user, "property_manager_details", None)
#                     if details.exists():
#                         phone_number = details.first().phone_number
#                 role_key = user.user_type
#                 role_value = " ".join([w.capitalize() for w in role_key.lower().split("_")])
#                 data.append({
#                     "id": user.id,
#                     "email": user.email,
#                     "is_verified": user.is_verified,
#                     "is_deleted": user.is_deleted,
#                     "is_login_allowed": user.is_login_allowed,
#                     "contact_number": phone_number,
#                     "created_on": datetime_to_epoch_millis(user.created),
#                     "last_login": datetime_to_epoch_millis(user.last_login) if user.last_login else None,
#                     "is_active": user.is_active,
#                     "first_name":user.first_name,
#                     "last_name":user.last_name,
#                     "profile_image_type":user.profile_image_type,
#                     "active_status": "Active" if user.is_active else "Inactive",
#                     "location":user.country,
#                     "password": user.hashed_password,
#                     "confirm_password":user.hashed_password,
#                      "role": {
#                           "key": role_key,
#                           "value": role_value
#                               },
#                     "profile_image":user.profile_image,
                    
                    
#                 })

#             pagination_meta = {
#                 "current_page": page_obj.number,
#                 "limit": limit,
#                 "total_records": paginator.count,
#                 "total_pages": paginator.num_pages
#             }

#             return prepare_response(
#                 message=constants.USER_FETCHED_SUCCESS,
#                    content={
#                     "user_count": total_count,
#                      "data": data
#                         },
#                 pagination=pagination_meta,
#                 status=status.HTTP_200_OK,
            
#             )

#         except Exception as e:
#             return prepare_response(
#                 message=f"Error fetching users: {str(e)}",
#                 status=status.HTTP_400_BAD_REQUEST
#             )


#     elif request.method == "POST":
#         try:
#             body = json.loads(request.body)

           
#             first_name = body.get("first_name")
#             last_name = body.get("last_name")
#             email = body.get("email")
#             phone_number = body.get("contact_number")
#             user_type = body.get("user_type")
#             location = body.get("location")
#             password = body.get("password")
#             confirm_password = body.get("confirm_password")
#             profile_image = body.get("profile_image")

        
#             if not all([first_name, last_name, email, phone_number, user_type, location, password, confirm_password]):
#                 return prepare_response(
#                     message=constants.ALL_USER_FIELDS_REQUIRED,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             if password != confirm_password:
#                 return prepare_response(
#                     message=constants.PASSWORD_MISMATCH,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             if UserProfile.objects.filter(email=email).exists():
#                 return prepare_response(
#                     message=constants.EMAIL_ALREADY_REGISTERED,
#                     status=status.HTTP_409_CONFLICT
#                 )

          
#             full_name = f"{first_name} {last_name}"

         
#             hashed_password = make_password(password)

#             user = UserProfile.objects.create(
#                 email=email,
#                 hashed_password=hashed_password,
#                 user_type=user_type,
#                 first_name=first_name,
#                 last_name=last_name,
#                 profile_image=profile_image,
#                 is_verified=False,
#                 is_deleted=False,
#                 is_login_allowed=False,
#                 last_login=timezone.now(),
#                 country=location
                
#             )

       
#             if user_type.lower() == "owner":
#                 OwnerDetails.objects.create(
#                     user=user,
#                     full_name=full_name,
#                     mobile_number=phone_number,
                    
#                 )

#             elif user_type.lower() == "tenant":
#                 TenantDetails.objects.create(
#                     user=user,
#                     full_name=full_name,
#                     mobile_number=phone_number,
                  
#                 )

#             elif user_type.lower() == "property_manager":
#                 PropertyManagerCompanyDetails.objects.create(
#                     user=user,
#                     full_name=full_name,
#                     phone_number=phone_number,
                    
#                 )

#             elif user_type.lower() == "staff":
#                 StaffDetails.objects.create(
#                     user=user,
#                     full_name=full_name,
#                     phone_number=phone_number,
                   
#                 )

#             return prepare_response(
#                 message=constants.USER_CREATED,
#                 content={
#                     "id": user.id,
#                     "email": user.email,
#                     "full_name": full_name,
#                     "phone_number": phone_number,
#                     "role": user.user_type,
#                     "location": location,
#                     "created_on": user.created,
#                     "last_login": user.last_login,
#                     "is_active": user.is_active
#                 },
#                 status=status.HTTP_201_CREATED
#             )

#         except Exception as e:
#             return prepare_response(
#                 message=f"Error creating user: {str(e)}",
#                 status=status.HTTP_400_BAD_REQUEST
#             )

 
#     elif request.method == "PUT":
#         try:
#             body = json.loads(request.body)
#             user_id = body.get("user_id")
#             if not user_id:
#                 return prepare_response(
#                     message=constants.ID_REQUIRE_QUERY_PARAMS,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )
#             user = UserProfile.objects.filter(id=user_id, is_deleted=False).first()
#             if not user:
#                 return prepare_response(
#                     message=constants.USER_NOT_FOUND,
#                     status=status.HTTP_404_NOT_FOUND
#                 )
            
#             first_name = body.get("first_name")
#             last_name = body.get("last_name")
#             location = body.get("location")
            
#             first_name_db = user.first_name or ""
#             last_name_db = user.last_name or ""


#             if first_name:
#                 user.first_name = first_name
#             if last_name:
#                 user.last_name = last_name
#             if location:
#                 user.country=location
#             if "profile_image" in body:
#                 user.profile_image = body["profile_image"]
            

#             full_name = f"{user.first_name or ''} {user.last_name or ''}".strip()
#             phone_number = body.get("contact_number")
#             user_type = user.user_type.lower()


#             if user_type == "owner":
#                 OwnerDetails.objects.update_or_create(
#         user=user,
#         defaults={
#             "full_name": full_name,
#             "mobile_number": phone_number or ""
#         }
#     )

                    
#             elif user_type == "tenant":
#                 TenantDetails.objects.update_or_create(
#         user=user,
#         defaults={
#             "full_name": full_name,
#             "mobile_number": phone_number or ""
#         }
#     )



#             elif user_type == "property_manager":
#                 defaults_data = {
#         "phone_number": phone_number or "",
       
#         "company_name": full_name or "",
#     }
#                 details, created = PropertyManagerCompanyDetails.objects.update_or_create(
#         user=user,
#         defaults=defaults_data
#     )


#             elif user_type == "staff":
#                 StaffDetails.objects.update_or_create(
#         user=user,
#         defaults={
#             "full_name": full_name,
#             "phone_number": phone_number or ""
#         }
#     )



#             user.save()

#             return prepare_response(
#                 message=constants.USER_UPDATED_SUCCESS,
#                 content={"id": user.id, "email": user.email},
#                 status=status.HTTP_200_OK
#             )

#         except Exception as e:
#             return prepare_response(
#                 message=f"Error updating user: {str(e)}",
#                 status=status.HTTP_400_BAD_REQUEST
#             )

#     elif request.method == "DELETE":
#         try:
#             user_id = request.GET.get("user_id")
#             if not user_id:
#                 return prepare_response(
#                     message=constants.ID_REQUIRE_QUERY_PARAMS,
#                     status=status.HTTP_400_BAD_REQUEST
#                 )

#             user = UserProfile.objects.filter(id=user_id).first()
#             if not user:
#                 return prepare_response(
#                     message=constants.USER_NOT_FOUND,
#                     status=status.HTTP_404_NOT_FOUND
#                 )

#             if not user.is_deleted:
#                 user.is_deleted = True
#                 user.save()
#                 return prepare_response(
#                     message=constants.USER_SOFT_DELETED,
#                     content={"id": user.id, "is_deleted": user.is_deleted},
#                     status=status.HTTP_200_OK
#                 )
#             else:
#                 user.delete()
#                 return prepare_response(
#                     message=constants.USER_PERMANENTLY_DELETED,
#                     content={"id": user_id},
#                     status=status.HTTP_200_OK
#                 )

#         except Exception as e:
#             return prepare_response(
#                 message=f"Error deleting user: {str(e)}",
#                 status=status.HTTP_400_BAD_REQUEST
#             )


#     else:
#         return prepare_response(
#             message=constants.INVALID_REQUEST_METHOD,
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )



# @is_request_authenticated
# def toggle_user_active(request):

#     if request.method != "PUT":
#         return prepare_response(
#             message=constants.INVALID_REQUEST_METHOD,
#             status=status.HTTP_405_METHOD_NOT_ALLOWED
#         )

#     try:
#         body = json.loads(request.body)
#         user_id = body.get("user_id")
#         if not user_id:
#             return prepare_response(
#                 message=constants.USER_ID_REQUIRED,
#                 status=status.HTTP_400_BAD_REQUEST
#             )
#         user_profile = UserProfile.objects.filter(id=user_id).first()
#         if not user_profile:
#             return prepare_response(
#                 message=constants.USER_NOT_FOUND,
#                 status=status.HTTP_404_NOT_FOUND
#             )
#         user_profile.is_active = not user_profile.is_active
#         user_profile.save()
#         if user_profile.is_active:
#             return prepare_response(
#                 message=constants.USER_ACTIVE,
#                 status=status.HTTP_200_OK
#             )
#         else:
#             return prepare_response(
#                 message=constants.USER_INACTIVE,
#                 status=status.HTTP_200_OK
#             )

#     except Exception as e:
#         return prepare_response(
#             message=str(e),
#             status=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )





