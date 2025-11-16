import json
import uuid
from django.contrib.auth.hashers import make_password
from utilities import status, constants
from utilities.helper_functions import prepare_response 
from user_service.models import UserProfile ,StaffDetails , PropertyManagerCompanyDetails , StaffRole
from property_management.models import OwnerDetails , TenantDetails
from user_service.utils import request_otp_sent
from django.db import transaction
from utilities.decorator import is_request_authenticated
from django.core.paginator import Paginator, EmptyPage
def user_sign_up(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        password = data.get("password")
        confirm_password = data.get("confirm_password")
        user_type = data.get("user_type")

        if not all([email, password, confirm_password, user_type]):
            return prepare_response(
                message=constants.FIELD_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        if password != confirm_password:
            return prepare_response(
                message=constants.PASSWORD_MISMATCH,
                status=status.HTTP_400_BAD_REQUEST
            )
        if UserProfile.objects.filter(email=email).exists():
            return prepare_response(
                message=constants.EMAIL_ALREADY_REGISTERED,
                status=status.HTTP_400_BAD_REQUEST
            )
        user = UserProfile.objects.create(
            email=email,
            hashed_password=make_password(password),
            user_type=user_type,
            is_login_allowed=True
        )
        return prepare_response(
            content={
                "id": user.id,
                "email": user.email,
                "user_type": user.user_type
            },
            message=constants.USER_REGISTERED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


def send_otp(request):
    if request.method == "POST":
        data = json.loads(request.body)
        email = data.get("email")
        user_profile = UserProfile.objects.filter(email=email).first()
        if not user_profile:
            return prepare_response(
                message=constants.USER_NOT_ONBOARDED,
                status=status.HTTP_400_BAD_REQUEST
            )
        otp = request_otp_sent()
        user_profile.otp = otp
        user_profile.save(update_fields=['otp'])
        return prepare_response(
            content={"otp": otp},
            message=constants.OTP_GENERATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


@is_request_authenticated
def staff_signup(request):
    if request.method != 'POST':
        return prepare_response(message=constants.ONLY_POST_METHOD_ALLOWED,  status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return prepare_response(message=constants.INVALID_JSON_BODY, status=status.HTTP_400_BAD_REQUEST)
    user_profile = request.user  
    if user_profile.user_type not in [constants.PROPERTY_MANAGER, constants.STAFF]:
        return prepare_response(
            message=constants.ACCESS_DENIED_FOR_STAFF,
            status=status.HTTP_400_BAD_REQUEST
        )
    property_manager_details = None
    if user_profile.user_type == constants.STAFF:
        staff_details = StaffDetails.objects.filter(user=user_profile).first() 
        if not staff_details:
            return prepare_response(
                message=constants.STAFF_DETAILS_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        staff_role = staff_details.staff_role
        if not staff_role:
            return prepare_response(
                message=constants.STAFF_ROLE_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        if not staff_role.permissions.get("Staff Management", {}).get("Add Staff", False):
            return prepare_response(
                message=constants.ACCESS_DENIED_FOR_STAFF,
                status=status.HTTP_400_BAD_REQUEST
            )
        property_manager_details = staff_details.property_manager
        if not property_manager_details:
            return prepare_response(
                message=constants.STAFF_USER_NOT_PROPERTY_MANAGER,
                status=status.HTTP_400_BAD_REQUEST
            )
    elif user_profile.user_type == constants.PROPERTY_MANAGER:
        property_manager_details = PropertyManagerCompanyDetails.objects.filter(
            user=user_profile
        ).first()
        if not property_manager_details:
            return prepare_response(
                message=constants.PROPERTY_MANAGER_DETAILS_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        staff_role = StaffRole.objects.filter(
            id=data.get("staff_role_id"),
            property_manager=property_manager_details
        ).first()
        if not staff_role:
            return prepare_response(
                message=constants.STAFF_ROLE_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
    try:
        with transaction.atomic():
            user = UserProfile.objects.update_or_create(
                email=data.get("email"),
                hashed_password=make_password(data.get("hashed_password")),
                user_type=data.get("user_type"),
                is_login_allowed=True
            )
            staff_id = data.get("staff_id") or str(uuid.uuid4())
            staff_details = StaffDetails.objects.create(
                staff_name=data.get("staff_name"),
                phone_number=data.get("phone_number"),
                staff_id=staff_id,
                assign_property=data.get("assign_property"),
                staff_role=staff_role,
                property_manager=property_manager_details,
                user=user,  
            )
    except Exception as e:
        return prepare_response(
            message=constants.STAFF_CREATION_FAILED,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    return prepare_response(
        content={
            "user_id": user.id,
            "email_id": user.email,
            "type": user.user_type,
            "otp_verified": user.is_verified,
            "is_detail_updated": user.is_detail_updated,
            "is_document_uploaded": user.is_document_uploaded,
            "staff_role_id": staff_details.staff_role.id,
        },
        message=constants.STAFF_USER_CREATED_SUCCESS,
        status=status.HTTP_201_CREATED
    ) 








@is_request_authenticated
def user_profile_view(request):
    try:
        current_user = request.user

        if request.method == "PUT":
            data = json.loads(request.body)

           
            user_fields = ["profile_image", "country", "time_zone", "utc"]
            for field in user_fields:
                if field in data and data[field] is not None:
                    setattr(current_user, field, data[field])
            current_user.save()

           
            related_data = {
                "mobile_number": data.get("contact"),
                "address": data.get("address"),
                "state": data.get("state"),
                "postal_code": data.get("postal_code"),
            }
            related_data = {k: v for k, v in related_data.items() if v is not None}

            if current_user.user_type == constants.OWNER:
                model = OwnerDetails
            elif current_user.user_type == constants.PROPERTY_MANAGER:
                model = PropertyManagerCompanyDetails
                if "mobile_number" in related_data:
                    related_data["phone_number"] = related_data.pop("mobile_number")
                if "address" in related_data:
                    related_data["company_address"] = related_data.pop("address")
            elif current_user.user_type == constants.TENANT:
                model = TenantDetails
            else:
                model = None

            if model:
                obj = model.objects.filter(user=current_user).first()
                if obj:
                    for key, value in related_data.items():
                        setattr(obj, key, value)
                    obj.save()
                else:
                    model.objects.create(user=current_user, **related_data)

            return prepare_response(
                message=constants.PROFILE_UPDATED_SUCCESS,
                status=status.HTTP_200_OK
            )

        elif request.method == "GET":
          
            user_data = {
                "id": current_user.id,
                "email": current_user.email,
                
                "profile_image": current_user.profile_image if current_user.profile_image else None,
                "country": current_user.country,
                "time_zone": current_user.time_zone,
                "utc": current_user.utc,
                "user_type": current_user.user_type,
            }

        
            related_info = {}
            if current_user.user_type == constants.OWNER:
                obj = OwnerDetails.objects.filter(user=current_user).first()
                if obj:
                    related_info = {
                        "Full name":obj.full_name,
                        "mobile_number": obj.mobile_number,
                        "address": obj.address,
                        "state": obj.state,
                        "postal_code": obj.postal_code,
                    }
            elif current_user.user_type == constants.PROPERTY_MANAGER:
                obj = PropertyManagerCompanyDetails.objects.filter(user=current_user).first()
                if obj:
                    related_info = {
                        "phone_number": obj.phone_number,
                        "company_address": obj.company_address,
                        "state": obj.state,
                        "postal_code": obj.postal_code,
                    }
            elif current_user.user_type == constants.TENANT:
                obj = TenantDetails.objects.filter(user=current_user).first()
                if obj:
                    related_info = {
                        "mobile_number": obj.mobile_number,
                        "address": obj.address,
                        "state": obj.state,
                        "postal_code": obj.postal_code,
                    }

            user_data.update(related_info)

            return prepare_response(
                message="User profile fetched successfully",
                status=status.HTTP_200_OK,
                content=user_data
            )

        else:
            return prepare_response("Invalid HTTP method", status=405)

    except Exception as e:
        print("Error in user_profile_view:", e)
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )











from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q
from django.utils import timezone

def user_management_view(request):

    if request.method == "GET":
        try:
            is_deleted_param = request.GET.get("is_deleted", "false").lower()
            is_deleted = is_deleted_param == "true"

            recently_user_param = request.GET.get("recently_user", "false").lower()
            recently_user = recently_user_param == "true"


            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))

            users_qs = UserProfile.objects.filter(is_deleted=is_deleted)
            total_count = users_qs.count()
            if recently_user:
                users_qs = users_qs.filter(last_login__isnull=False).order_by("-last_login")[:5]

            if search:
                users_qs = users_qs.filter(
                    Q(email__icontains=search) |
                    Q(owner_details__full_name__icontains=search) |
                    Q(tenant_details__full_name__icontains=search) |
                    Q(property_manager_details__full_name__icontains=search)
                ).distinct()


            paginator = Paginator(users_qs, limit)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            data = []
            for user in page_obj:
                phone_number = None
                user_type = user.user_type.lower()

                if user_type == "owner":
                    details = getattr(user, "owner_details", None)
                    if details.exists():
                        phone_number = details.first().mobile_number

                elif user_type == "tenant":
                    details = getattr(user, "tenant_details", None)
                    if details.exists():
                        phone_number = details.first().mobile_number

                elif user_type == "property_manager":
                    details = getattr(user, "property_manager_details", None)
                    if details.exists():
                        phone_number = details.first().phone_number

                data.append({
                    "id": user.id,
                    "email": user.email,
                    "role": user.user_type,
                    "is_verified": user.is_verified,
                    "is_deleted": user.is_deleted,
                    "is_login_allowed": user.is_login_allowed,
                    "phone_number": phone_number,
                    "created_on": user.created,
                    "last_login": user.last_login,
                    "is_active": user.is_active,
                    "profile_image":user.profile_image,
                    
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
                status=status.HTTP_200_OK,
            
            )

        except Exception as e:
            return prepare_response(
                message=f"Error fetching users: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )


    elif request.method == "POST":
        try:
            body = json.loads(request.body)

           
            first_name = body.get("first_name")
            last_name = body.get("last_name")
            email = body.get("email")
            phone_number = body.get("phone_number")
            user_type = body.get("user_type")
            location = body.get("location")
            password = body.get("password")
            confirm_password = body.get("confirm_password")
            profile_image = body.get("profile_image")

        
            if not all([first_name, last_name, email, phone_number, user_type, location, password, confirm_password]):
                return prepare_response(
                    message="All fields (first_name, last_name, email, phone_number, role, location, password, confirm_password) are required.",
                    status=status.HTTP_400_BAD_REQUEST
                )

            if password != confirm_password:
                return prepare_response(
                    message="Password and Confirm Password do not match.",
                    status=status.HTTP_400_BAD_REQUEST
                )

            if UserProfile.objects.filter(email=email).exists():
                return prepare_response(
                    message=constants.EMAIL_ALREADY_REGISTERED,
                    status=status.HTTP_409_CONFLICT
                )

          
            full_name = f"{first_name} {last_name}"

         
            hashed_password = make_password(password)

            user = UserProfile.objects.create(
                email=email,
                hashed_password=hashed_password,
                user_type=user_type,
                profile_image=profile_image,
                is_verified=False,
                is_deleted=False,
                is_login_allowed=False,
                last_login=timezone.now()    
            )

       
            if user_type.lower() == "owner":
                OwnerDetails.objects.create(
                    user=user,
                    full_name=full_name,
                    mobile_number=phone_number,
                    
                )

            elif user_type.lower() == "tenant":
                TenantDetails.objects.create(
                    user=user,
                    full_name=full_name,
                    mobile_number=phone_number,
                  
                )

            elif user_type.lower() == "property_manager":
                PropertyManagerCompanyDetails.objects.create(
                    user=user,
                    full_name=full_name,
                    phone_number=phone_number,
                    
                )

            elif user_type.lower() == "staff":
                StaffDetails.objects.create(
                    user=user,
                    full_name=full_name,
                    phone_number=phone_number,
                   
                )

            return prepare_response(
                message="User created successfully.",
                content={
                    "id": user.id,
                    "email": user.email,
                    "full_name": full_name,
                    "phone_number": phone_number,
                    "role": user.user_type,
                    "location": location,
                    "created_on": user.created,
                    "last_login": user.last_login,
                    "is_active": user.is_active
                },
                status=status.HTTP_201_CREATED
            )

        except Exception as e:
            return prepare_response(
                message=f"Error creating user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

 
    elif request.method == "PUT":
        try:
            user_id = request.GET.get("id")
            if not user_id:
                return prepare_response(
                    message=constants.ID_REQUIRE_QUERY_PARAMS,
                    status=status.HTTP_400_BAD_REQUEST
                )

            body = json.loads(request.body)
            user = UserProfile.objects.filter(id=user_id, is_deleted=False).first()
            if not user:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            if "email" in body:
                user.email = body["email"]

            user.save()

            return prepare_response(
                message=constants.USER_UPDATED_SUCCESS,
                content={"id": user.id, "email": user.email},
                status=status.HTTP_200_OK
            )

        except Exception as e:
            return prepare_response(
                message=f"Error updating user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )

    elif request.method == "DELETE":
        try:
            user_id = request.GET.get("user_id")
            if not user_id:
                return prepare_response(
                    message=constants.ID_REQUIRE_QUERY_PARAMS,
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = UserProfile.objects.filter(id=user_id).first()
            if not user:
                return prepare_response(
                    message=constants.USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            if not user.is_deleted:
                user.is_deleted = True
                user.save()
                return prepare_response(
                    message="User soft deleted successfully.",
                    content={"id": user.id, "is_deleted": user.is_deleted},
                    status=status.HTTP_200_OK
                )
            else:
                user.delete()
                return prepare_response(
                    message="User permanently deleted.",
                    content={"id": user_id},
                    status=status.HTTP_200_OK
                )

        except Exception as e:
            return prepare_response(
                message=f"Error deleting user: {str(e)}",
                status=status.HTTP_400_BAD_REQUEST
            )


    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
