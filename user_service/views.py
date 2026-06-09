import json
from utilities import status, constants
from utilities.helper_functions import prepare_response, datetime_to_epoch_millis, safe_epoch_to_datetime, get_extension_from_base64, export_to_csv, send_ses_email, fetch_s3_presigned_url, upload_file_to_s3_base64
import uuid
from django.template.loader import render_to_string
from user_service.models import UserProfile, Documents, OwnerDocuments, TenantDocuments, Role, Owner, Tenant, PropertyManager ,Approval, DocumentType, Documentation
from property.models import PropertyManagerDocuments, Unit, Property, PropertyManagmentCompany, UnitOwner
from django.db import transaction
from django.views.decorators.csrf import csrf_exempt
from utilities.decorator import is_request_authenticated
from django.core.paginator import Paginator, EmptyPage
from django.db.models import Q, Count, Prefetch
from django.contrib.auth.models import User
from django.utils.crypto import get_random_string
from django.db import transaction
from property_management.utils import get_staff_details, get_property_images, get_full_user_data
from user_service.utils import upload_document, process_rent_approval
from lease.models import Lease, LeaseDocuments
from user_service.serializers import serialize_owner_detail, serialize_owner_unit
from user_service.tasks import send_renewal_email
import logging

logger = logging.getLogger(__name__)

EMIRATES_VISA_DOC_SPECS = [
    ("emirates_id_doc", "emirates_id", "emirates_id_doc_type"),
    ("uae_residence_visa_doc", "uae_residence_visa", "visa_doc_type"),
]
from property_management.models import  City
from django.utils import timezone
from utilities.helper_functions import prepare_response, fetch_s3_presigned_url, upload_file_to_s3_base64
import uuid

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
        logger.warning(
            "SIGNUP_FAILED | reason=REQUIRED_FIELDS_MISSING")
        return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
    if password != data.get("confirm_password"):
        logger.warning(
            "SIGNUP_FAILED | reason=PASSWORD_MISMATCH")
        return prepare_response(message=constants.PASSWORD_MISMATCH, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=email).exists():
        logger.warning(
            "SIGNUP_FAILED | email=%s | reason=EMAIL_ALREADY_EXISTS",
            email)
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
                logger.warning(
                    "SIGNUP_FAILED | reason=COMPANY_ID_MISSING")
                return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            profile = PropertyManager.objects.create(
                **common_profile_kwargs,
                company_id=company_id
            )
        else:
            logger.warning(
                "SIGNUP_FAILED | role=%s | reason=INVALID_ROLE",
                user_role )
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
    logger.info(
        "USER_SIGNUP_SUCCESS | user_id=%s | profile_id=%s | role=%s",
        user.id, profile.id, user_role )
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

            # Determine role from MTI subtype
            pm_instance = PropertyManager.objects.filter(pk=user_profile.pk).prefetch_related("roles__permissions").first()
            if pm_instance:
                user_role = constants.COMPANY_USER
            elif Owner.objects.filter(pk=user_profile.pk).exists():
                user_role = constants.OWNER
            elif Tenant.objects.filter(pk=user_profile.pk).exists():
                user_role = constants.TENANT
            else:
                user_role = constants.COMPANY_USER

            # Build permission map for PropertyManagers: {module_name: {create, edit, delete, view}}
            permissions = {}
            if pm_instance:
                for role in pm_instance.roles.all():
                    for perm in role.permissions.all():
                        existing = permissions.get(perm.module_name, {"create": False, "edit": False, "delete": False, "view": False})
                        permissions[perm.module_name] = {
                            "create": existing["create"] or perm.create,
                            "edit": existing["edit"] or perm.edit,
                            "delete": existing["delete"] or perm.delete,
                            "view": existing["view"] or perm.view,
                        }

            data = {
                "id": user_profile.id,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "user_role": user_role,
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
                "postal_code": user_profile.pin_code,
                "address": user_profile.address_line_1,
                "additional_address": user_profile.address_line_2,
                "locality": user_profile.locality,
                "contact_number": user_profile.contact_number,
                "emirate_id": user_profile.emirate_id,
                "time_zone": user_profile.timezone,
                "permissions": permissions,
            }
            logger.info(
                    "USER_PROFILE_FETCHED | user_id=%s | role=%s",
                    request.user.id, user_role )
            return prepare_response(
                content=data,
                message=constants.USER_PROFILE_FETCHED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(
                "USER_PROFILE_FETCH_ERROR | user_id=%s | error=%s",
                request.user.id, str(e) )
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

            # Direct model field mappings (body key → model field)
            field_map = {
                "profile_image": "profile_image",
                "pin_code": "pin_code",
                "address": "address_line_1",
                "additional_address": "address_line_2",
                "locality": "locality",
                "contact_number": "contact_number",
                "emirate_id": "emirate_id",
                "time_zone": "timezone",
            }
            for body_key, model_field in field_map.items():
                if body_key in body:
                    setattr(user_profile, model_field, body[body_key])
            user_profile.save()
               
            logger.info(
                "USER_PROFILE_UPDATED | user_id=%s",
                request.user.id )
            return prepare_response(
                message=constants.USER_PROFILE_UPDATED,
                status=status.HTTP_200_OK
            )

        except Exception as e:
            logger.exception(
                "USER_PROFILE_UPDATE_ERROR | user_id=%s | error=%s",
                request.user.id, str(e))
            return prepare_response(message=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    else:
        logger.warning(
            "USER_PROFILE_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
            request.user.id, request.method )
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
            last_name  = body.get("last_name")
            email      = body.get("email")
            password   = body.get("password")
            phone      = body.get("contact_number") or body.get("phone")
            role       = body.get("role")

            if not all([first_name, last_name, email, password, role]):
                logger.warning(
                    "USER_CREATE_FAILED | user_id=%s | reason=REQUIRED_FIELDS_MISSING",
                    request.user.id)
                return prepare_response(
                    message=constants.ALL_FIELD_REQUIRED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if role not in [constants.OWNER, constants.TENANT, constants.COMPANY_USER]:
                logger.warning(
                    "USER_CREATE_FAILED | user_id=%s | role=%s | reason=INVALID_ROLE",
                    request.user.id, role )
                return prepare_response(
                    message=constants.UNAUTHORIZED_USER_ROLE,
                    status=status.HTTP_400_BAD_REQUEST
                )

            if User.objects.filter(email=email).exists():
                logger.warning(
                    "USER_CREATE_FAILED | user_id=%s | reason=EMAIL_ALREADY_EXISTS",
                    request.user.id )
                return prepare_response(
                    message=constants.EMAIL_ALREADY_REGISTERED,
                    status=status.HTTP_400_BAD_REQUEST
                )

            common_kwargs = dict(
                contact_number=phone,
                profile_image=body.get("profile_image"),
                created_by=user.user,
            )

            with transaction.atomic():
                django_user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )

                if role == constants.OWNER:
                    profile = Owner.objects.create(user=django_user, **common_kwargs)
                elif role == constants.TENANT:
                    profile = Tenant.objects.create(user=django_user, **common_kwargs)
                elif role == constants.COMPANY_USER:
                    company = PropertyManagmentCompany.objects.filter(
                        created_by=user.user, is_active=True
                    ).first()
                    if not company:
                        pm_self = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
                        company = pm_self.company if pm_self else None
                    if not company:
                        logger.warning(
                            "USER_CREATE_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                            request.user.id )
                        return prepare_response(
                            message=constants.COMPANY_NOT_FOUND,
                            status=status.HTTP_404_NOT_FOUND
                        )
                    profile = PropertyManager.objects.create(
                        user=django_user, company=company, **common_kwargs
                    )
            logger.info(
                "USER_CREATED | user_id=%s | created_user_id=%s | role=%s",
                request.user.id, profile.id, role )
            return prepare_response(
                message=constants.USER_CREATED,
                content={"user_id": profile.id, "email": django_user.email, "role": role},
                status=status.HTTP_201_CREATED
            )
        elif request.method == "GET":
            is_active_raw = request.GET.get("is_active")
            role = request.GET.get("role")
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            user_id = request.GET.get("user_id")

            # Resolve the company for the logged-in user
            company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()
            if not company:
                pm_check = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
                company = pm_check.company if pm_check else None
            if not company:
                logger.warning(
                    "USER_LIST_FETCH_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                    request.user.id )
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            # Collect UserProfile IDs from all three user types linked to this company:
            # 1. Property Managers (staff) — directly linked via company FK
            pm_ids = set(PropertyManager.objects.filter(company=company).values_list("pk", flat=True))

            # 2. Owners — via UnitOwner → Unit → PropertyBlocks → Property → pmc
            owner_ids = set(
                UnitOwner.objects.filter(
                    unit__property_block_tower__property__pmc=company,
                    owner__isnull=False
                ).values_list("owner_id", flat=True)
            )

            # 3. Tenants — via Lease → Unit → PropertyBlocks → Property → pmc
            tenant_ids = set(
                Lease.objects.filter(
                    unit__property_block_tower__property__pmc=company
                ).values_list("tenant_id", flat=True)
            )

            all_profile_ids = pm_ids | owner_ids | tenant_ids

            users_qs = UserProfile.objects.select_related("user").filter(id__in=all_profile_ids)

            if is_active_raw is not None:
                users_qs = users_qs.filter(is_active=is_active_raw.lower() == "true")
            if user_id:
                users_qs = users_qs.filter(id=user_id)
            if search:
                users_qs = users_qs.filter(
                    Q(user__email__icontains=search) |
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(contact_number__icontains=search)
                )
            if role:
                role_upper = role.upper()
                if role_upper in ("OWNER",):
                    users_qs = users_qs.filter(id__in=owner_ids)
                elif role_upper in ("TENANT",):
                    users_qs = users_qs.filter(id__in=tenant_ids)
                elif role_upper in ("COMPANY_USER", "PROPERTY_MANAGER"):
                    users_qs = users_qs.filter(id__in=pm_ids)

            users_qs = users_qs.order_by("-created")
            paginator = Paginator(users_qs, limit)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            data = []
            for profile in page_obj:
                django_user = profile.user
                if profile.id in pm_ids:
                    role_label = "Property Manager"
                elif profile.id in owner_ids:
                    role_label = "Owner"
                elif profile.id in tenant_ids:
                    role_label = "Tenant"
                else:
                    role_label = "User"
                data.append({
                    "id": profile.id,
                    "code": profile.code or "",
                    "email": django_user.email,
                    "first_name": django_user.first_name,
                    "last_name": django_user.last_name,
                    "contact_number": profile.contact_number,
                    "profile_image": profile.profile_image,
                    "is_active": profile.is_active,
                    "created_on": datetime_to_epoch_millis(profile.created),
                    "last_login": datetime_to_epoch_millis(django_user.last_login) if django_user.last_login else None,
                    "role": {"key": role_label.upper().replace(" ", "_"), "value": role_label},
                })

            pagination_meta = {
                "current_page": page_obj.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages
            }
            logger.info(
                "USER_LIST_FETCHED | user_id=%s | total_records=%s",
                request.user.id, paginator.count )
            return prepare_response(
                message=constants.USER_FETCHED_SUCCESS,
                content=data,
                pagination=pagination_meta,
                status=status.HTTP_200_OK
            )
        elif request.method == "PUT":
            body = json.loads(request.body)
            user_id = body.get("user_id")
            if not user_id:
                logger.warning(
                    "USER_UPDATE_FAILED | user_id=%s | reason=USER_ID_MISSING",
                    request.user.id)
                return prepare_response(message=constants.USER_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            profile = UserProfile.objects.select_related("user").filter(id=user_id).first()
            if not profile:
                logger.warning(
                    "USER_UPDATE_FAILED | user_id=%s | target_user_id=%s | reason=USER_NOT_FOUND",
                    request.user.id, user_id )
                return prepare_response(message=constants.USER_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            django_user = profile.user
            if body.get("first_name"):
                django_user.first_name = body["first_name"]
            if body.get("last_name"):
                django_user.last_name = body["last_name"]
            django_user.save(update_fields=["first_name", "last_name"])

            update_fields = []
            if body.get("contact_number") is not None:
                profile.contact_number = body["contact_number"]
                update_fields.append("contact_number")
            if body.get("profile_image") is not None:
                profile.profile_image = body["profile_image"]
                update_fields.append("profile_image")
            if update_fields:
                profile.save(update_fields=update_fields)
            logger.info(
                "USER_UPDATED | user_id=%s | target_user_id=%s",
                request.user.id, profile.id )
            return prepare_response(
                message=constants.USER_UPDATED_SUCCESS if hasattr(constants, 'USER_UPDATED_SUCCESS') else "User updated successfully.",
                content={"user_id": profile.id},
                status=status.HTTP_200_OK
            )
        elif request.method == "DELETE":
            user_id = request.GET.get("user_id")
            if not user_id:
                logger.warning(
                    "USER_DELETE_FAILED | user_id=%s | reason=USER_ID_MISSING",
                    request.user.id )
                return prepare_response(message=constants.USER_ID_REQUIRED,status=status.HTTP_400_BAD_REQUEST)
            
            profile = UserProfile.objects.select_related("user").filter(
                          id=user_id,
                          created_by=user.user).first()
            if not profile:
                logger.warning(
                    "USER_DELETE_FAILED | user_id=%s | target_user_id=%s | reason=USER_NOT_FOUND",
                    request.user.id, user_id )
                return prepare_response( message=constants.USER_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            if profile.is_active: 
                profile.is_active = False
                profile.save(update_fields=["is_active"])
                logger.info(
                    "USER_DEACTIVATED | user_id=%s | target_user_id=%s",
                    request.user.id, profile.id )
                return prepare_response(message="User deactivated successfully",content={"user_id": profile.id,"is_active": profile.is_active},status=status.HTTP_200_OK)
            django_user = profile.user
            target_user_id = profile.id
            profile.delete()
            django_user.delete()
            logger.info(
                "USER_PERMANENTLY_DELETED | user_id=%s | target_user_id=%s",
                request.user.id, target_user_id)
            return prepare_response(
                message=constants.USER_PERMANENTLY_DELETED,
                 status=status.HTTP_200_OK
            )

        else:
            logger.warning(
                "USER_MANAGEMENT_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
                request.user.id, request.method )
            return prepare_response(
                message=constants.INVALID_METHOD,
                status=status.HTTP_405_METHOD_NOT_ALLOWED
            )

    except Exception as e:
        logger.exception(
            "USER_MANAGEMENT_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(
            message=f"Error: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )



def _save_role_permissions(role, permissions_data, created_by):
    """Replace all permissions on a role with the provided list."""
    from user_service.models import Permission
    role.permissions.all().delete()
    new_perms = []
    for perm in permissions_data:
        module_name = perm.get("module_name", "").strip()
        if not module_name:
            continue
        p = Permission.objects.create(
            module_name=module_name,
            create=bool(perm.get("create", False)),
            edit=bool(perm.get("edit", False)),
            delete=bool(perm.get("delete", False)),
            view=bool(perm.get("view", False)),
            created_by=created_by,
        )
        new_perms.append(p)
    if new_perms:
        role.permissions.set(new_perms)
    logger.info(
            "ROLE_PERMISSIONS_UPDATED | role_id=%s | permission_count=%s",
            role.id, len(new_perms) )

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
            logger.warning(
                "ROLE_CREATE_FAILED | user_id=%s | reason=ROLE_NAME_REQUIRED",
                request.user.id )
            return prepare_response(
                message=constants.ROLE_IS_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        user_profile = request.user
        django_user = user_profile.user
        company = PropertyManagmentCompany.objects.filter(created_by=django_user, is_active=True).first()
        if not company:
            pm_check = PropertyManager.objects.filter(pk=user_profile.pk).select_related("company").first()
            company = pm_check.company if pm_check else None
        if not company:
            logger.warning(
                "ROLE_CREATE_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )
        if Role.objects.filter(name__iexact=role_name, company=company, is_active=True).exists():
            logger.warning(
                "ROLE_CREATE_FAILED | user_id=%s | role_name=%s | reason=ROLE_ALREADY_EXISTS",
                request.user.id, role_name )
            return prepare_response(
                message=constants.ROLE_ALREADY_EXISTS_IN_COMPANY,
                status=status.HTTP_400_BAD_REQUEST
            )
        role = Role.objects.create(name=role_name, company=company, created_by=django_user)
        permissions_data = body.get("permissions", [])
        if permissions_data:
            _save_role_permissions(role, permissions_data, django_user)
        logger.info(
            "ROLE_CREATED | user_id=%s | role_id=%s | role_name=%s",
            request.user.id, role.id, role.name )
        return prepare_response(
            content={"id": role.id, "name": role.name},
            message=constants.ROLE_CREATED_SUCCESS,
            status=status.HTTP_201_CREATED
        )
    except Exception as e:
        logger.exception(
            "ROLE_CREATE_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        print("Create Role Error:", e)
        return prepare_response(
            message=constants.SOMETHING_WENT_WRONG,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def role_table_view(request):
    user = request.user
    try:
        django_user = user.user
        company = PropertyManagmentCompany.objects.filter(created_by=django_user, is_active=True).first()
        if not company:
            pm_check = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
            company = pm_check.company if pm_check else None
        if not company:
            logger.warning(
                "ROLE_FETCH_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page", 1))
            limit = int(request.GET.get("limit", 10))
            start_epoch = request.GET.get("start_date")
            end_epoch = request.GET.get("end_date")
            is_active_param = request.GET.get("is_active", "true").lower()
            is_active = is_active_param == "true"

            roles_qs = Role.objects.filter(company=company, is_active=is_active).prefetch_related("permissions")
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
            for role in page_obj.object_list:
                perms = role.permissions.all()
                data.append({
                    "role_id": role.id,
                    "role_name": role.name,
                    "created_on": datetime_to_epoch_millis(role.created),
                    "permissions": [
                        {
                            "module_name": p.module_name,
                            "create": p.create,
                            "edit": p.edit,
                            "delete": p.delete,
                            "view": p.view,
                        }
                        for p in perms
                    ],
                })
            pagination_meta = {
                "current_page": page_obj.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            }
            logger.info(
                "ROLE_LIST_FETCHED | user_id=%s | total_records=%s",
                request.user.id, paginator.count )
            return prepare_response(
                message=constants.ROLES_FETCH_SUCCESS,
                content=data,
                pagination=pagination_meta,
                status=status.HTTP_200_OK,
            )

        elif request.method == "PUT":
            body = json.loads(request.body)
            role_id = body.get("role_id")
            role_name = body.get("name", "").strip()
            if not role_id or not role_name:
                logger.warning(
                    "ROLE_UPDATE_FAILED | user_id=%s | reason=ROLE_ID_OR_NAME_MISSING",
                    request.user.id )
                return prepare_response(message=constants.ROLE_IS_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            role = Role.objects.filter(pk=role_id, company=company, is_active=True).first()
            if not role:
                logger.warning(
                    "ROLE_UPDATE_FAILED | user_id=%s | role_id=%s | reason=ROLE_NOT_FOUND",
                    request.user.id, role_id )
                return prepare_response(message=constants.ROLE_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
            if Role.objects.filter(name__iexact=role_name, company=company, is_active=True).exclude(pk=role_id).exists():
                logger.warning(
                    "ROLE_UPDATE_FAILED | user_id=%s | role_name=%s | reason=ROLE_ALREADY_EXISTS",
                    request.user.id, role_name )
                return prepare_response(message=constants.ROLE_ALREADY_EXISTS_IN_COMPANY, status=status.HTTP_400_BAD_REQUEST)
            role.name = role_name
            role.save()
            permissions_data = body.get("permissions", [])
            if permissions_data is not None:
                _save_role_permissions(role, permissions_data, django_user)
            logger.info(
                "ROLE_UPDATED | user_id=%s | role_id=%s | role_name=%s",
                request.user.id, role.id, role.name )
            return prepare_response(
                content={"role_id": role.id, "role_name": role.name},
                message=constants.ROLE_UPDATED_SUCCESS,
                status=status.HTTP_200_OK,
            )
        logger.warning(
            "ROLE_API_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
            request.user.id, request.method )
        return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        logger.exception(
            "ROLE_API_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        print("Role View Error:", e)
        return prepare_response(message=constants.SOMETHING_WENT_WRONG, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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
        logger.info(
            "USERS_EXPORTED | user_id=%s | total_records=%s",
            request.user.id, len(data_list) )
        return export_to_csv(
            filename="users_export",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        logger.exception(
            "USER_EXPORT_ERROR | user_id=%s | error=%s",
            getattr(request.user, "id", None), str(e) )
        return prepare_response(
            message=f"Error exporting users CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )





@is_request_authenticated
def staff_view(request):
    user = request.user
    try:
        company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()
        if not company:
            pm_check = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
            company = pm_check.company if pm_check else None
        if not company:
            logger.warning(
                "STAFF_ACCESS_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
            return prepare_response(message=constants.COMPANY_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

        if request.method == "GET":
            staff_id = request.GET.get("staff_id")
            search = request.GET.get("search", "").strip()
            page = int(request.GET.get("page_number", 1))
            limit = int(request.GET.get("limit", 10))

            qs = PropertyManager.objects.filter(company=company).select_related("user", "city").prefetch_related("roles")
            company_prop_ids = company.pmc_properties.filter(is_active=True).values_list("id", flat=True)

            if staff_id:
                pm = qs.filter(pk=staff_id).first()
                if not pm:
                    logger.warning(
                        "STAFF_FETCH_FAILED | user_id=%s | staff_id=%s | reason=STAFF_NOT_FOUND",
                        request.user.id, staff_id )
                    return prepare_response(message=constants.STAFF_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)
                pm_roles = list(pm.roles.all())
                first_role = {"key": pm_roles[0].id, "value": pm_roles[0].name} if pm_roles else None

                from property.models import PropertyManagerAssignedUnits, Unit as UnitModel
                assigned_unit_ids = list(
                    PropertyManagerAssignedUnits.objects.filter(property_manager=pm).values_list("unit_id", flat=True)
                )

                units_qs = UnitModel.objects.filter(
                    pk__in=assigned_unit_ids
                ).select_related(
                    "property_block_tower__property"
                ).prefetch_related(
                    "leases__tenant__user",
                    "unit_owners__owner__user",
                )

                assigned_properties = []
                for unit in units_qs:
                    prop = unit.property_block_tower.property
                    active_lease = unit.leases.filter(lease_status="ACTIVE", is_active=True).first()
                    tenant_name = active_lease.tenant.user.get_full_name() if active_lease and active_lease.tenant and active_lease.tenant.user else None
                    unit_owner = unit.unit_owners.first()
                    owner_name = unit_owner.owner.user.get_full_name() if unit_owner and unit_owner.owner and unit_owner.owner.user else None
                    assigned_properties.append({
                        "property_code": unit.code,
                        "property_name": f"{unit.unit_name} — {prop.property_name}",
                        "property_image": unit._get_unit_thumbnail(),
                        "tenant_name": tenant_name,
                        "owner_name": owner_name,
                    })

                data = {
                    "staff_id": pm.pk,
                    "staff_name": pm.user.get_full_name(),
                    "first_name": pm.user.first_name,
                    "last_name": pm.user.last_name,
                    "email": pm.user.email,
                    "contact_number": pm.contact_number,
                    "emirate_id": pm.emirate_id,
                    "city": pm.city.name if pm.city else "",
                    "locality": pm.locality,
                    "address": pm.address_line_1,
                    "additional_address": pm.address_line_2,
                    "postal_code": pm.pin_code,
                    "roles": [r.name for r in pm_roles],
                    "staff_role": first_role,
                    "code": pm.code,
                    "is_active": pm.is_active,
                    "profile_image": pm.profile_image,
                    "assigned_properties": assigned_properties,
                    "assigned_unit_ids": assigned_unit_ids,
                }
                logger.info(
                    "STAFF_FETCHED | user_id=%s | staff_id=%s",
                    request.user.id, pm.pk )
                return prepare_response(content=data, message=constants.USER_FETCHED_SUCCESS, status=status.HTTP_200_OK)

            role_filter = request.GET.get("role")
            if role_filter:
                qs = qs.filter(roles__id=role_filter)

            if search:
                qs = qs.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(contact_number__icontains=search)
                )
            qs = qs.order_by("-created")
            paginator = Paginator(qs, limit)
            try:
                page_obj = paginator.page(page)
            except EmptyPage:
                page_obj = paginator.page(paginator.num_pages)

            from property.models import Unit as UnitModel, PropertyManagerAssignedUnits
            from lease.models import Lease
            from collections import defaultdict

            pm_ids = [pm.pk for pm in page_obj]

            # Assigned units per PM
            assigned_rows = PropertyManagerAssignedUnits.objects.filter(
                property_manager_id__in=pm_ids
            ).values("property_manager_id", "unit_id")

            pm_unit_map = defaultdict(set)
            all_assigned_unit_ids = set()
            for row in assigned_rows:
                pm_unit_map[row["property_manager_id"]].add(row["unit_id"])
                all_assigned_unit_ids.add(row["unit_id"])

            # Occupied units among all assigned
            occupied_unit_ids = set(
                Lease.objects.filter(
                    unit_id__in=all_assigned_unit_ids,
                    lease_status="ACTIVE",
                    is_active=True,
                ).values_list("unit_id", flat=True)
            )

            # Thumbnails from assigned units
            unit_thumb_qs = UnitModel.objects.filter(
                pk__in=all_assigned_unit_ids
            ).prefetch_related("unit_images")[:20]
            property_thumbnails = []
            for unit in unit_thumb_qs:
                thumb = unit._get_unit_thumbnail()
                if thumb:
                    property_thumbnails.append(thumb)

            data = []
            for pm in page_obj:
                unit_ids = pm_unit_map[pm.pk]
                total = len(unit_ids)
                occupied = len(unit_ids & occupied_unit_ids)
                data.append({
                    "staff_id": pm.pk,
                    "staff_name": pm.user.get_full_name(),
                    "contact_number": pm.contact_number,
                    "roles": [r.name for r in pm.roles.all()],
                    "code": pm.code,
                    "is_active": pm.is_active,
                    "property_count": total,
                    "property_images": property_thumbnails,
                    "tenancy_ratio": f"{total}:{occupied}",
                })
            pagination_meta = {
                "current_page": page_obj.number,
                "limit": limit,
                "total_records": paginator.count,
                "total_pages": paginator.num_pages,
            }
            logger.info(
                "STAFF_LIST_FETCHED | user_id=%s | total_records=%s",
                request.user.id, paginator.count )
            return prepare_response(content=data, pagination=pagination_meta, message=constants.USER_FETCHED_SUCCESS, status=status.HTTP_200_OK)

        elif request.method == "POST":
            body = json.loads(request.body)
            first_name = (body.get("first_name") or body.get("staff_name", "")).strip()
            last_name = (body.get("last_name") or "").strip()
            email = body.get("email")
            password = body.get("password")
            contact_number = body.get("contact_number")
            role_id = body.get("role")

            if not all([first_name, email, password]):
                logger.warning(
                    "STAFF_CREATE_FAILED | user_id=%s | reason=REQUIRED_FIELDS_MISSING",
                    request.user.id )
                return prepare_response(message=constants.ALL_FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
            if User.objects.filter(email=email).exists():
                logger.warning(
                    "STAFF_CREATE_FAILED | user_id=%s | reason=EMAIL_ALREADY_EXISTS",
                    request.user.id )
                return prepare_response(message=constants.EMAIL_ALREADY_REGISTERED, status=status.HTTP_400_BAD_REQUEST)

            with transaction.atomic():
                django_user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                )
                pm = PropertyManager.objects.create(
                    user=django_user,
                    company=company,
                    contact_number=contact_number,
                    created_by=user.user,
                )
                if role_id:
                    role_obj = Role.objects.filter(id=role_id, company=company).first()
                    if role_obj:
                        pm.roles.add(role_obj)

                assigned_unit_ids = body.get("assigned_property") or []
                if assigned_unit_ids:
                    from property.models import PropertyManagerAssignedUnits, Unit as UnitModel
                    for unit_id in assigned_unit_ids:
                        unit = UnitModel.objects.filter(pk=unit_id).first()
                        if unit:
                            PropertyManagerAssignedUnits.objects.get_or_create(
                                unit=unit, property_manager=pm,
                                defaults={"created_by": user.user},
                            )
            logger.info(
                "STAFF_CREATED | user_id=%s | staff_id=%s ",
                request.user.id, pm.pk )
            return prepare_response(
                message=constants.USER_CREATED,
                content={"staff_id": pm.pk},
                status=status.HTTP_201_CREATED,
            )

        elif request.method == "PUT":
            body = json.loads(request.body)
            staff_id = body.get("staff_id")
            if not staff_id:
                logger.warning(
                    "STAFF_UPDATE_FAILED | user_id=%s | reason=STAFF_ID_MISSING",
                    request.user.id )
                return prepare_response(message=constants.USER_ID_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

            pm = PropertyManager.objects.select_related("user").filter(pk=staff_id, company=company).first()
            if not pm:
                logger.warning(
                    "STAFF_UPDATE_FAILED | user_id=%s | staff_id=%s | reason=STAFF_NOT_FOUND",
                    request.user.id, staff_id )
                return prepare_response(message=constants.STAFF_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            django_user = pm.user
            first_name = (body.get("first_name") or "").strip()
            last_name = (body.get("last_name") or "").strip()
            if not first_name and not last_name:
                staff_name = (body.get("staff_name") or "").strip()
                if staff_name:
                    parts = staff_name.split(" ", 1)
                    first_name = parts[0]
                    last_name = parts[1] if len(parts) > 1 else ""
            update_name_fields = []
            if first_name:
                django_user.first_name = first_name
                update_name_fields.append("first_name")
            if last_name is not None:
                django_user.last_name = last_name
                update_name_fields.append("last_name")
            if update_name_fields:
                django_user.save(update_fields=update_name_fields)

            if body.get("contact_number") is not None:
                pm.contact_number = body["contact_number"]
                pm.save(update_fields=["contact_number"])

            role_id = body.get("role")
            if role_id:
                role_obj = Role.objects.filter(id=role_id, company=company).first()
                if role_obj:
                    pm.roles.set([role_obj])

            if "assigned_property" in body:
                from property.models import PropertyManagerAssignedUnits, Unit as UnitModel
                PropertyManagerAssignedUnits.objects.filter(property_manager=pm).delete()
                for unit_id in (body["assigned_property"] or []):
                    unit = UnitModel.objects.filter(pk=unit_id).first()
                    if unit:
                        PropertyManagerAssignedUnits.objects.create(unit=unit, property_manager=pm, created_by=user.user)
            logger.info(
                "STAFF_UPDATED | user_id=%s | staff_id=%s",
                request.user.id, pm.pk )
            return prepare_response(message="Staff updated successfully.", status=status.HTTP_200_OK)

        else:
            return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)

    except Exception as e:
        logger.exception(
            "STAFF_API_ERROR | user_id=%s | error=%s",
            getattr(request.user, "id", None), str(e) )
        return prepare_response(message=f"Error: {str(e)}", status=status.HTTP_500_INTERNAL_SERVER_ERROR)


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

        company = PropertyManagmentCompany.objects.filter(created_by=user.user, is_active=True).first()
        if not company:
            pm_check = PropertyManager.objects.filter(pk=user.pk).select_related("company").first()
            company = pm_check.company if pm_check else None
        if not company:
            logger.warning(
                "STAFF_EXPORT_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        # When staff_id provided → export that staff's assigned properties
        if staff_id:
            pm = PropertyManager.objects.filter(pk=staff_id, company=company).select_related("user").first()
            if not pm:
                logger.warning(
                    "STAFF_EXPORT_FAILED | user_id=%s | staff_id=%s | reason=STAFF_NOT_FOUND",
                    request.user.id, staff_id )
                return prepare_response(message=constants.STAFF_NOT_FOUND, status=status.HTTP_404_NOT_FOUND)

            props_qs = company.pmc_properties.filter(
                is_active=True
            ).prefetch_related(
                "property_blocks__block_towers__leases__tenant__user",
                "property_blocks__block_towers__unit_owners__owner__user",
            )
            if search:
                props_qs = props_qs.filter(
                    Q(property_name__icontains=search) |
                    Q(code__icontains=search)
                )

            field_names = ["Code", "Property Name", "Tenant Name", "Assigned Staff", "Owner Name"]
            data_list = []
            for prop in props_qs:
                tenant_name = ""
                owner_name = ""
                for block in prop.property_blocks.all():
                    for unit in block.block_towers.all():
                        if not tenant_name:
                            lease = unit.leases.first()
                            if lease and lease.tenant and lease.tenant.user:
                                tenant_name = lease.tenant.user.get_full_name()
                        if not owner_name:
                            unit_owner = unit.unit_owners.first()
                            if unit_owner and unit_owner.owner and unit_owner.owner.user:
                                owner_name = unit_owner.owner.user.get_full_name()
                        if tenant_name and owner_name:
                            break
                    if tenant_name and owner_name:
                        break
                data_list.append({
                    "Code": prop.code or "",
                    "Property Name": prop.property_name,
                    "Tenant Name": tenant_name or "N/A",
                    "Assigned Staff": pm.user.get_full_name(),
                    "Owner Name": owner_name or "N/A",
                })
            logger.info(
                "STAFF_EXPORTED | user_id=%s | export_type=%s",
                request.user.id, "ASSIGNED_PROPERTIES" if staff_id else "STAFF_LIST" )
            return export_to_csv(filename="assigned_properties", field_names=field_names, data_list=data_list)

        # No staff_id → export staff list
        staff_qs = PropertyManager.objects.filter(
            company=company,
            is_active=True
        ).select_related("user").prefetch_related("roles")

        if search:
            staff_qs = staff_qs.filter(
                Q(user__first_name__icontains=search) |
                Q(user__email__icontains=search) |
                Q(contact_number__icontains=search)
            )

        if role_id:
            staff_qs = staff_qs.filter(roles__id=role_id)

        field_names = [
            "Staff Name",
            "Code",
            "Email",
            "Contact Number",
            "Staff Role"
        ]

        data_list = []
        for pm in staff_qs:
            data_list.append({
                "Staff Name": pm.user.get_full_name(),
                "Code": pm.code or "",
                "Email": pm.user.email,
                "Contact Number": pm.contact_number or "",
                "Staff Role": ", ".join([r.name for r in pm.roles.all()])
            })
        logger.info(
            "STAFF_EXPORTED | user_id=%s | export_type=STAFF_LIST | total_records=%s", 
            request.user.id, len(data_list) )
        return export_to_csv(
            filename="staff_list",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        logger.exception(
            "STAFF_EXPORT_ERROR | user_id=%s | error=%s",
            getattr(request.user, "id", None), str(e) )
        return prepare_response(
            message=f"Error exporting staff CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@is_request_authenticated
def contact_list_view(request):

    if request.method == "GET":
        search = request.GET.get("search")
        role   = request.GET.get("role")   # All | Tenant | Team | Landlord
        logged_in_profile = request.user

        company = PropertyManagmentCompany.objects.filter(
            company_staff=logged_in_profile,
            is_active=True
        ).first()

        if not company:
            company = PropertyManagmentCompany.objects.filter(
                created_by=logged_in_profile.user,
                is_active=True
            ).first()

        if not company:
            pm_check = PropertyManager.objects.filter(pk=logged_in_profile.pk).select_related("company").first()
            company = pm_check.company if pm_check else None

        if not company:
            logger.warning(
                "CONTACT_LIST_FETCH_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        from django.db.models import Value, CharField
        from django.db.models.functions import Concat

        def build_qs(model_cls, role_label):
            qs = model_cls.objects.select_related("user").filter(is_active=True)
            if model_cls.__name__ == "PropertyManager":
                qs = qs.filter(company=company).exclude(id=logged_in_profile.id)
            elif model_cls.__name__ == "Tenant":
                property_ids = company.pmc_properties.values_list("id", flat=True)
                from lease.models import Lease
                tenant_ids = Lease.objects.filter(
                    unit__property_block_tower__property_id__in=property_ids,
                    is_active=True,
                ).values_list("tenant_id", flat=True).distinct()
                qs = qs.filter(id__in=tenant_ids)
            elif model_cls.__name__ == "Owner":
                from property.models import UnitOwner
                owner_ids = UnitOwner.objects.filter(
                    unit__property_block_tower__property__pmc=company
                ).values_list("owner_id", flat=True).distinct()
                qs = qs.filter(id__in=owner_ids)

            if search:
                qs = qs.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(contact_number__icontains=search)
                )
            return [
                {
                    "id":            p.id,
                    "full_name":     f"{p.user.first_name} {p.user.last_name}".strip(),
                    "email":         p.user.email,
                    "phone":         p.contact_number,
                    "role":          role_label,
                    "profile_image": p.profile_image or None,
                }
                for p in qs
            ]

        role_map = {
            "Team":     [(PropertyManager, "Team")],
            "Tenant":   [(Tenant,          "Tenant")],
            "Landlord": [(Owner,           "Landlord")],
        }
        targets = role_map.get(role, [
            (PropertyManager, "Team"),
            (Tenant,          "Tenant"),
            (Owner,           "Landlord"),
        ])
        results = []
        for model_cls, label in targets:
            results += build_qs(model_cls, label)
        logger.info(
            "CONTACT_LIST_FETCHED | user_id=%s | role=%s | total_contacts=%s",
            request.user.id, role or "ALL", len(results) )
        return prepare_response(
            content=results,
            message=constants.CONTACTS_FETCH_SUCCESS,
            status=status.HTTP_200_OK
        )
    logger.warning(
        "CONTACT_LIST_FAILED | user_id=%s | method=%s | reason=METHOD_NOT_ALLOWED",
        request.user.id, request.method )
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
                logger.warning(
                    "OWNER_FETCH_FAILED | user_id=%s | owner_id=%s | reason=OWNER_NOT_FOUND",
                    request.user.id, owner_id )
                return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)
            # If units table is requested (detail page), return owner detail + units
            tenancy_status = request.GET.get("tenancy_status")
            units_qs = Unit.objects.filter(
                unit_owners__owner=owner
            ).prefetch_related(
                "leases",
                "leases__tenant__user",
                "property_block_tower__property",
            )
            table_data = []
            for unit in units_qs:
                is_occupied = unit.leases.filter(lease_status="ACTIVE", is_active=True).exists()
                if tenancy_status:
                    if tenancy_status == "OCCUPIED" and not is_occupied:
                        continue
                    if tenancy_status == "VACANT" and is_occupied:
                        continue
                table_data.append(serialize_owner_unit(unit, owner))
            logger.info(
                "OWNER_DETAILS_FETCHED | user_id=%s | owner_id=%s | unit_count=%s",
                request.user.id, owner.id, len(table_data) )
            return prepare_response(
                content={
                    "owner_details": serialize_owner_detail(owner),
                    "table": table_data,
                },
                message="Owner fetched",
                status=status.HTTP_200_OK,
            )

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
            logger.info(
                "OWNER_CSV_EXPORTED | user_id=%s | total_records=%s",
                request.user.id, owners.count() )
            return export_to_csv("owners", fields, rows)

        paginator = Paginator(owners, page_size)
        try:
            page_obj = paginator.page(page)
        except EmptyPage:
            page_obj = paginator.page(paginator.num_pages)
        logger.info(
            "OWNER_LIST_FETCHED | user_id=%s | total_records=%s",
            request.user.id, paginator.count )
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
            logger.warning(
                "OWNER_CREATE_FAILED | user_id=%s | reason=EMAIL_REQUIRED",
                request.user.id )
            return prepare_response(message="Email is required", status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(username=email).exists():
            logger.warning(
                "OWNER_CREATE_FAILED | user_id=%s | reason=EMAIL_ALREADY_EXISTS",
                request.user.id )
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
                password=get_random_string(12)
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
        logger.info(
            "OWNER_CREATED | user_id=%s | owner_id=%s",
            request.user.id, owner.id )
        return prepare_response(content=_serialize_owner(owner), message="Owner created", status=status.HTTP_201_CREATED)

    elif request.method == "PUT":
        from datetime import datetime as dt
        data = json.loads(request.body)
        owner_id = data.get("owner_id")
        if not owner_id:
            logger.warning(
                "OWNER_UPDATE_FAILED | user_id=%s | reason=OWNER_ID_MISSING",
                request.user.id )
            return prepare_response(message="owner_id is required", status=status.HTTP_400_BAD_REQUEST)

        owner = Owner.objects.select_related("user").filter(id=owner_id).first()
        if not owner:
            logger.warning(
                "OWNER_UPDATE_FAILED | user_id=%s | owner_id=%s | reason=OWNER_NOT_FOUND",
                request.user.id, owner_id )
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
        logger.info(
            "OWNER_UPDATED | user_id=%s | owner_id=%s",
            request.user.id, owner.id )
        return prepare_response(content=_serialize_owner(owner), message="Owner updated", status=status.HTTP_200_OK)

    elif request.method == "DELETE":
        owner_id = request.GET.get("owner_id", "").strip()
        if not owner_id:
            logger.warning(
                "OWNER_DELETE_FAILED | user_id=%s | reason=OWNER_ID_MISSING",
                request.user.id )
            return prepare_response(message="owner_id is required", status=status.HTTP_400_BAD_REQUEST)

        owner = Owner.objects.select_related("user").filter(id=owner_id).first()
        if not owner:
            logger.warning(
                "OWNER_DELETE_FAILED | user_id=%s | owner_id=%s | reason=OWNER_NOT_FOUND",
                request.user.id, owner_id )
            return prepare_response(message="Owner not found", status=status.HTTP_404_NOT_FOUND)

        owner.user.is_active = False
        owner.user.save()
        logger.info(
            "OWNER_DELETED | user_id=%s | owner_id=%s",
            request.user.id, owner.id )
        return prepare_response(message="Owner deleted", status=status.HTTP_200_OK)

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)


def _serialize_tenant(tenant):
    def _doc_entry(d):
        return {
            "id":        d.id,
            "file_name": d.file_name,
            "file_path": d.file_path,
        }

    # ── Lease documents grouped by document_type ─────────────────────
    groups = {}
    lease_docs = LeaseDocuments.objects.filter(
        lease__tenant=tenant
    ).select_related("document_type")
    for d in lease_docs:
        key = (d.document_type.name or "Documents") if d.document_type else "Lease Documents"
        groups.setdefault(key, []).append(_doc_entry(d))

    document_groups = [
        {"group": group_name, "files": files}
        for group_name, files in groups.items()
    ]

    return {
        "id":                   tenant.id,
        "code":                 tenant.code or "",
        "name":                 f"{tenant.user.first_name} {tenant.user.last_name}".strip(),
        "first_name":           tenant.user.first_name or "",
        "last_name":            tenant.user.last_name or "",
        "email":                tenant.email or tenant.user.email or "",
        "contact_number":       tenant.contact_number or "",
        "emirates_id":          tenant.emirate_id or "",
        "nationality":          tenant.nationality or "",
        "address_line_1":       tenant.address_line_1 or "",
        "address_line_2":       tenant.address_line_2 or "",
        "pin_code":             tenant.pin_code or "",
        "passport_number":      tenant.passport_number or "",
        "passport_expiry_date": tenant.passport_expiry_datetime.strftime("%Y-%m-%d") if tenant.passport_expiry_datetime else "",
        "visa_number":          tenant.visa_number or "",
        "visa_expiry_date":     tenant.visa_expiry_datetime.strftime("%Y-%m-%d") if tenant.visa_expiry_datetime else "",
        "document_groups":      document_groups,
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
                logger.warning(
                    "TENANT_FETCH_FAILED | user_id=%s | tenant_id=%s | reason=TENANT_NOT_FOUND", 
                    request.user.id, tenant_id )
                return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)
            logger.info(
                "TENANT_DETAILS_FETCHED | user_id=%s | tenant_id=%s",
                request.user.id, tenant.id )
            return prepare_response(content=_serialize_tenant(tenant))

        if email:
            tenant = Tenant.objects.select_related("user").filter(
                Q(email__iexact=email) | Q(user__email__iexact=email),
                user__is_active=True,
            ).first()
            if not tenant:
                logger.warning(
                    "TENANT_FETCH_FAILED | user_id=%s | reason=TENANT_NOT_FOUND",
                    request.user.id )
                return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)
            logger.info(
                "TENANT_DETAILS_FETCHED | user_id=%s | tenant_id=%s",
                request.user.id, tenant.id )
            return prepare_response(content=_serialize_tenant(tenant))

        # ── List mode: paginated tenant-lease table with tab filtering ───────
        from lease.models import Lease
        from lease.serializers import serialize_tenant_lease
        from django.db.models import Max
        from datetime import date as _date
        import csv as _csv
        from django.http import HttpResponse as _HttpResponse

        tab       = request.GET.get("tab", "onboarding")
        search    = request.GET.get("search", "").strip()
        page      = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))
        export    = request.GET.get("export", "")
        today     = _date.today()

        latest_ids = (
            Lease.objects
            .filter(is_active=True)
            .values("tenant")
            .annotate(latest_id=Max("id"))
            .values_list("latest_id", flat=True)
        )

        qs = (
            Lease.objects
            .select_related("tenant__user", "unit__property_block_tower__property")
            .prefetch_related("unit__property_block_tower__property__property_images")
            .filter(id__in=latest_ids)
        )

        if tab == "onboarding":
            qs = qs.filter(lease_status="DRAFT")
        elif tab == "active":
            qs = qs.filter(
                lease_status="ACTIVE",
                start_date__date__lte=today,
                end_date__date__gte=today,
            )
        elif tab == "past":
            qs = qs.filter(lease_status__in=["INACTIVE", "EXPIRED"])
        elif tab == "rejected":
            qs = qs.filter(lease_status="REJECTED")

        if search:
            qs = qs.filter(
                Q(tenant__user__first_name__icontains=search) |
                Q(tenant__user__last_name__icontains=search) |
                Q(tenant__email__icontains=search) |
                Q(tenant__contact_number__icontains=search) |
                Q(tenant__code__icontains=search) |
                Q(code__icontains=search)
            )

        property_id = request.GET.get("property_id", "").strip()
        block_id    = request.GET.get("block_id", "").strip()
        unit_id     = request.GET.get("unit_id", "").strip()

        if property_id:
            qs = qs.filter(unit__property_block_tower__property_id=property_id)
        if block_id:
            qs = qs.filter(unit__property_block_tower_id=block_id)
        if unit_id:
            qs = qs.filter(unit_id=unit_id)

        qs = qs.order_by("-created")

        if export == "csv":
            units_list = list(qs)

            if not units_list:
                return prepare_response(
                    message="No data available for export",
                    status=status.HTTP_404_NOT_FOUND
                )

            response = _HttpResponse(content_type="text/csv")
            response["Content-Disposition"] = f'attachment; filename="tenants_{tab}.csv"'

            writer = _csv.writer(response)
            writer.writerow([
                "Lease Code", "Tenant Code", "Tenant Name", "Email",
                "Contact", "Emirates ID", "Property", "Block",
                "Start Date", "End Date", "Rent", "Status",
            ])

            for l in units_list:
                row = serialize_tenant_lease(l)
                t = row.get("tenant", {})
                p = row.get("property", {})
                d = row.get("dates", {})
                f = row.get("financials", {})

                writer.writerow([
                    row.get("code"),
                    t.get("code"),
                    t.get("name"),
                    t.get("email"),
                    t.get("contact_number"),
                    t.get("emirates_id"),
                    p.get("name"),
                    p.get("block_name"),
                    d.get("start_date"),
                    d.get("end_date"),
                    f.get("rent"),
                    row.get("lease_status"),
                ])

            return response

        paginator = Paginator(qs, page_size)
        page_obj  = paginator.get_page(page)
        logger.info(
            "TENANT_LIST_FETCHED | user_id=%s | total_records=%s | tab=%s",
            request.user.id, paginator.count, tab )
        return prepare_response(
            content=[serialize_tenant_lease(l) for l in page_obj],
            pagination={
                "total_records": paginator.count,
                "total_pages":   paginator.num_pages,
                "current_page":  page,
                "page_size":     page_size,
            },
        )

    # ── POST (create or find-and-update by email) ─────────────────────────────
    elif request.method == "POST":
        data = json.loads(request.body)
        email = (data.get("email") or "").strip()

        if not email:
            logger.warning(
                "TENANT_CREATE_FAILED | user_id=%s | reason=EMAIL_REQUIRED",
                request.user.id )
            return prepare_response(message="email is required", status=status.HTTP_400_BAD_REQUEST)

        # Check if tenant with this email already exists
        existing = Tenant.objects.select_related("user").filter(
            Q(email__iexact=email) | Q(user__email__iexact=email),
            user__is_active=True,
        ).first()

        if existing:
            _apply_tenant_fields(existing, data)
            logger.info(
                "TENANT_UPDATED_BY_EMAIL | user_id=%s | tenant_id=%s",
                request.user.id, existing.id )
            return prepare_response(content=_serialize_tenant(existing), message="Tenant updated")

        # Create new tenant
        name = data.get("name", "").strip()
        first_name = data.get("first_name", "") or (name.partition(" ")[0] if name else "")
        last_name = data.get("last_name", "") or (name.partition(" ")[2] if name else "")

        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email,
                first_name=first_name, last_name=last_name,
                password=get_random_string(12),
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
        logger.info(
            "TENANT_CREATED | user_id=%s | tenant_id=%s",
            request.user.id, tenant.id )
        return prepare_response(content=_serialize_tenant(tenant), message="Tenant created", status=status.HTTP_201_CREATED)

    # ── PUT ───────────────────────────────────────────────────────────────────
    elif request.method == "PUT":
        data = json.loads(request.body)
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            logger.warning(
                "TENANT_UPDATE_FAILED | user_id=%s | reason=TENANT_ID_MISSING",
                request.user.id )
            return prepare_response(message="tenant_id is required", status=status.HTTP_400_BAD_REQUEST)

        tenant = Tenant.objects.select_related("user").filter(id=tenant_id, user__is_active=True).first()
        if not tenant:
            logger.warning(
                "TENANT_UPDATE_FAILED | user_id=%s | tenant_id=%s | reason=TENANT_NOT_FOUND",
                request.user.id, tenant_id )
            return prepare_response(message="Tenant not found", status=status.HTTP_404_NOT_FOUND)

        _apply_tenant_fields(tenant, data)
        logger.info(
            "TENANT_UPDATED | user_id=%s | tenant_id=%s",
            request.user.id, tenant.id )
        return prepare_response(content=_serialize_tenant(tenant), message="Tenant updated")

    return prepare_response(message=constants.INVALID_REQUEST_METHOD, status=status.HTTP_405_METHOD_NOT_ALLOWED)

@csrf_exempt
@is_request_authenticated
def approval_view(request):
    user_profile = request.user


    pm_profile = PropertyManager.objects.select_related("company").filter(pk=user_profile.pk).first()

    company = pm_profile.company
    if request.method == "GET":

        lease_id_param = request.GET.get("lease_id")
        if lease_id_param:
            lease = Lease.objects.select_related("tenant", "unit").filter(id=lease_id_param,unit__property_block_tower__property__pmc=company).first()
            if not lease:
                logger.warning(
                    "APPROVAL_FETCH_FAILED | user_id=%s | lease_id=%s | reason=LEASE_NOT_FOUND",
                    request.user.id, lease_id_param )
                return prepare_response(message="Lease not found", status=status.HTTP_404_NOT_FOUND)
            approval = Approval.objects.select_related(
                "tenant__user", "unit", "unit__property_block_tower__property", "created_by"
            ).filter(tenant=lease.tenant, unit=lease.unit,unit__property_block_tower__property__pmc=company).order_by("-id").first()
            if not approval:
                logger.warning(
                    "APPROVAL_FETCH_FAILED | user_id=%s | lease_id=%s | reason=APPROVAL_NOT_FOUND_FOR_THIS_LEASE",
                    request.user.id, lease_id_param)
                return prepare_response(message="No approval found for this lease", status=status.HTTP_404_NOT_FOUND)
            content = {
                "id": approval.id,
                "requested_date": approval.created,
                "tenant": f"{approval.tenant.user.first_name} {approval.tenant.user.last_name}".strip() if approval.tenant and approval.tenant.user else None,
                "created_by": (approval.created_by.get_full_name() or approval.created_by.username) if approval.created_by else None,
                "property": approval.unit.property_block_tower.property.property_name if approval.unit.property_block_tower and approval.unit.property_block_tower.property else None,
                "property_image": approval.unit.property_block_tower.property._get_thumbnail() if approval.unit.property_block_tower and approval.unit.property_block_tower.property else None,
                "block": approval.unit.property_block_tower.block_name if approval.unit.property_block_tower else None,
                "unit": approval.unit.unit_name,
                "requested_rent": approval.requested_rent,
                "requested_tenure": approval.requested_tenure,
                "actual_rent": approval.unit.rent,
                "actual_tenure": approval.unit.cycle,
                "approved": approval.approved,
                "status": "APPROVED" if approval.approved else ("REJECTED" if approval.approved_by_id else "PENDING"),
            }
            logger.info(
                "APPROVAL_FETCHED | user_id=%s | approval_id=%s",
                request.user.id, approval.id )
            return prepare_response(content=content, status=status.HTTP_200_OK)

        approval_id = request.GET.get("approval_id")

        if approval_id:

            approval = Approval.objects.select_related(
                "tenant",
                "unit",
                "unit__property_block_tower__property"
            ).filter(id=approval_id).first()

            if not approval:
                return prepare_response(
                    message="Approval request not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            content = {
                "id": approval.id,
                "requested_date": approval.created,
                "tenant": str(approval.tenant),
                "property": approval.unit.property_block_tower.property.property_name
                if approval.unit.property_block_tower and approval.unit.property_block_tower.property else None,
                "block": approval.unit.property_block_tower.block_name if approval.unit.property_block_tower else None,
                "unit": approval.unit.unit_name,
                "requested_rent": approval.requested_rent,
                "requested_tenure": approval.requested_tenure,
                "actual_rent": approval.unit.rent,
                "actual_tenure": approval.unit.cycle,
                "approved": approval.approved,
                "approved_by": str(approval.approved_by) if approval.approved_by else None,
                "approved_at": approval.approved_at
            }
            logger.info(
                "APPROVAL_FETCHED | user_id=%s | approval_id=%s",
                request.user.id, approval.id )
            return prepare_response(content=content, status=status.HTTP_200_OK)

        approval_status = request.GET.get("status")
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 10))

        approvals_qs = Approval.objects.select_related(
            "tenant__user",
            "unit",
            "unit__property_block_tower__property",
            "created_by",
        ).order_by("-id")

        if approval_status == "PENDING":
            approvals_qs = approvals_qs.filter(approved=False, approved_by_id__isnull=True)
        elif approval_status == "APPROVED":
            approvals_qs = approvals_qs.filter(approved=True)
        elif approval_status == "REJECTED":
            approvals_qs = approvals_qs.filter(approved=False, approved_by_id__isnull=False)

        total_records = approvals_qs.count()
        paginator_obj = Paginator(approvals_qs, page_size)
        try:
            page_obj = paginator_obj.page(page)
        except EmptyPage:
            page_obj = paginator_obj.page(paginator_obj.num_pages)

        content = [
            {
                "id": a.id,
                "requested_date": a.created,
                "created_by": (
                    a.created_by.get_full_name() or a.created_by.username
                ) if a.created_by else None,
                "tenant": (
                    f"{a.tenant.user.first_name} {a.tenant.user.last_name}".strip()
                    or a.tenant.user.username
                ) if a.tenant and a.tenant.user else None,
                "property": a.unit.property_block_tower.property.property_name
                if a.unit.property_block_tower and a.unit.property_block_tower.property else None,
                "property_image": a.unit.property_block_tower.property._get_thumbnail()
                if a.unit.property_block_tower and a.unit.property_block_tower.property else None,
                "block": a.unit.property_block_tower.block_name if a.unit.property_block_tower else None,
                "unit": a.unit.unit_name,
                "requested_rent": a.requested_rent,
                "requested_tenure": a.requested_tenure,
                "actual_rent": a.unit.rent,
                "actual_tenure": a.unit.cycle,
                "approved": a.approved,
                "status": "APPROVED" if a.approved else ("REJECTED" if a.approved_by_id else "PENDING"),
            }
            for a in page_obj
        ]
        logger.info(
            "APPROVAL_LIST_FETCHED | user_id=%s | status=%s | page=%s",
            request.user.id, approval_status, page )
        return prepare_response(
            content=content,
            pagination={
                "total_records": total_records,
                "page": page,
                "page_size": page_size,
                "total_pages": paginator_obj.num_pages,
            },
            status=status.HTTP_200_OK,
        )


    elif request.method == "POST":

        if not PropertyManager.objects.filter(user=user_profile.user).exists():
            return prepare_response(
                message="Only COMPANY_USER can create approval requests",
                status=status.HTTP_403_FORBIDDEN
            )

        data = json.loads(request.body)

        tenant_id = data.get("tenant_id")
        unit_id = data.get("unit_id")
        requested_rent = data.get("requested_rent")
        requested_tenure = data.get("requested_tenure")

        if not tenant_id:
            logger.warning(
                        "APPROVAL_CREATE_FAILED | user_id=%s | reason=TENANT_ID_MISSING",
                        request.user.id )
            return prepare_response(
                message="tenant_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        if not unit_id:
            logger.warning(
                "APPROVAL_CREATE_FAILED | user_id=%s | reason=UNIT_ID_MISSING", 
                request.user.id )
            return prepare_response(
                message="unit_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        if not requested_rent:
            logger.warning(
                "APPROVAL_CREATE_FAILED | user_id=%s | reason=REQUESTED_RENT_MISSING",
                request.user.id )
            return prepare_response(
                message="requested_rent is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        tenant = Tenant.objects.filter(id=tenant_id).first()

        if not tenant:
            logger.warning(
                "APPROVAL_CREATE_FAILED | user_id=%s | tenant_id=%s | reason=TENANT_NOT_FOUND",
                request.user.id, tenant_id )
            return prepare_response(
                message="Tenant not found",
                status=status.HTTP_404_NOT_FOUND
            )

        unit = Unit.objects.filter(id=unit_id).first()

        if not unit:
            logger.warning(
                "APPROVAL_CREATE_FAILED | user_id=%s | unit_id=%s | reason=UNIT_NOT_FOUND",
                request.user.id, unit_id )
            return prepare_response(
                message="Unit not found",
                status=status.HTTP_404_NOT_FOUND
            )

        approval = Approval.objects.create(
            created_by=user_profile.user,
            tenant=tenant,
            unit=unit,
            requested_rent=requested_rent,
            requested_tenure=requested_tenure
        )
        logger.info(
            "RENT_APPROVAL_CREATED | user_id=%s | approval_id=%s",
            request.user.id, approval.id )
        return prepare_response(
            message="Rent approval request created",
            content={"id": approval.id},
            status=status.HTTP_201_CREATED
        )


    elif request.method == "PUT":

        if not PropertyManager.objects.filter(user=user_profile.user).exists():
            return prepare_response(
                message="Only COMPANY_USER can approve requests",
                status=status.HTTP_403_FORBIDDEN
            )

        data = json.loads(request.body)

        approval_id = data.get("approval_id")
        rent = data.get("rent")
        tenure = data.get("tenure")
        action = data.get("action")

        if not approval_id:
            logger.warning(
                "APPROVAL_UPDATE_FAILED | user_id=%s | reason=APPROVAL_ID_MISSING",
                request.user.id )
            return prepare_response(
                message="approval_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        approval, message = process_rent_approval(
            approval_id,
            user_profile,
            rent,
            tenure,
            action
        )

        if not approval:
            logger.warning(
                "APPROVAL_UPDATE_FAILED | user_id=%s | approval_id=%s | reason=NOT_FOUND",
                request.user.id, approval_id )
            return prepare_response(
                message=message,
                status=status.HTTP_404_NOT_FOUND
            )
        logger.info(
            "APPROVAL_UPDATED | user_id=%s | approval_id=%s | action=%s",
            request.user.id, approval_id, action )
        return prepare_response(
            message=message,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )


# ---------------------------------------------------------------------------
# Functions moved from property_management/views.py
# ---------------------------------------------------------------------------

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
                logger.info(
                    "OWNER_PMC_FETCHED | user_id=%s | total_records=%s",
                    request.user.id, len(data) )
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
                    logger.warning(
                        "OWNER_PMC_FETCH_FAILED | user_id=%s | company_id=%s | reason=COMPANY_NOT_FOUND",
                        request.user.id, company_id )
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
                logger.info(
                    "OWNER_PMC_COMPANY_DETAILS_FETCHED | user_id=%s | company_id=%s | property_count=%s",
                    request.user.id, company_id, len(properties_data) )
                return prepare_response(
                    content={"company_profile": pmc_profile, "properties": properties_data},
                    message=constants.PMC_PROFILE_PROPERTY_SUCCESS,
                    pagination=pagination_meta,
                    status=status.HTTP_200_OK)

            else:
                return prepare_response(message=constants.UNAUTHORIZED_OR_MISSING_PARAMETERS, status=status.HTTP_403_FORBIDDEN)

        except Exception as e:
            logger.exception(
                "OWNER_PMC_FETCH_ERROR | user_id=%s | error=%s",
                request.user.id, str(e) )
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
            logger.info(
                "PMC_CSV_EXPORTED | user_id=%s",
                request.user.id
            )
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
                logger.warning(
                    "PMC_CSV_EXPORT_FAILED | user_id=%s | company_id=%s | reason=COMPANY_NOT_FOUND",
                    request.user.id, company_id )
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
            logger.info(
                "PMC_CSV_EXPORTED | user_id=%s",
                request.user.id )
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
        logger.exception(
            "PMC_CSV_EXPORT_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(
            message=f"Error exporting CSV: {str(e)}",
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
            logger.warning(
                "COMPANY_OWNER_CSV_EXPORT_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                request.user.id )
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
            logger.warning(
                "COMPANY_OWNER_CSV_EXPORT_FAILED | user_id=%s | owner_id=%s | reason=OWNER_NOT_FOUND",
                request.user.id, owner_id )
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
        logger.info(
            "COMPANY_OWNER_CSV_EXPORTED | user_id=%s | owner_id=%s | export_type=PROPERTY_LIST",
            request.user.id, owner_id )
        return export_to_csv(
            filename="owner_properties",
            field_names=field_names,
            data_list=data_list
        )

    except Exception as e:
        logger.exception(
            "COMPANY_OWNER_CSV_EXPORT_ERROR | user_id=%s | error=%s",
            request.user.id if hasattr(request, "user") else None,str(e) )
        return prepare_response(
            message=f"Error exporting owner CSV: {str(e)}",
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
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
                logger.warning(
                    "TENANT_CSV_EXPORT_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                    request.user.id )
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
        logger.info(
            "TENANT_CSV_EXPORTED | user_id=%s | total_records=%s",
            request.user.id, len(export_data) )
        return export_to_csv(
            filename="tenant_simple_export",
            field_names=field_names,
            data_list=export_data
        )

    except Exception as e:
        logger.exception(
            "TENANT_CSV_EXPORT_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        return prepare_response(
            message=f"Error exporting tenant CSV: {str(e)}",
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
                logger.warning(
                    "COMPANY_TENANT_FETCH_FAILED | user_id=%s | reason=COMPANY_NOT_FOUND",
                    request.user.id )
                return prepare_response(
                    message=constants.COMPANY_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            if tenant_id:
                logger.info(
                    "COMPANY_TENANT_DETAILS_FETCHED | user_id=%s | tenant_id=%s",
                    request.user.id, tenant_id )
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
            logger.info(
                "COMPANY_TENANTS_FETCHED | user_id=%s | total_records=%s",
                request.user.id, len(tenant_list) )
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
                logger.warning(
                    "COMPANY_TENANT_UPDATE_FAILED | user_id=%s | tenant_id=%s | reason=TENANT_NOT_FOUND",
                    request.user.id, tenant_id )
                return prepare_response(
                    message=constants.TENANT_DETAILS_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

            tenant.tenant_status = tenant_status
            tenant.save(update_fields=["tenant_status", "modified"])
            logger.info(
                "COMPANY_TENANT_STATUS_UPDATED | user_id=%s | tenant_id=%s | status=%s",
                request.user.id, tenant.id, tenant_status )
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
        logger.exception(
            "COMPANY_TENANT_ERROR | user_id=%s | error=%s",
            request.user.id, str(e) )
        print("PropertyManagmentCompany Tenants API Error:", e)
        return prepare_response(
            message=constants.INTERNAL_SERVER_ERROR,
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


def serialize_agreement(a):
    return {
        "id": a.id,
        "code": a.code,
        "agreement_name": a.agreement_name,
        "agreement_type": {
            "key": a.agreement_type,
            "value": a.get_agreement_type_display()
        },
        "status": {
            "key": a.get_status(),
            "label": a.get_status_display_label()
        },
        "issued_by": a.issued_by,
        "does_not_expire": a.does_not_expire,
        "is_expired": a.is_expired,
        "is_renewed": a.is_renewed,
        "renewed_at": int(a.renewed_at.timestamp()) if a.renewed_at else None,
        "start_date": int(a.start_date.timestamp()) if a.start_date else None,
        "end_date": int(a.end_date.timestamp()) if a.end_date else None,
        "expiry_reminder_count": a.expiry_reminder_count,
        "cc_emails": a.get_cc_emails_list(),
        "document": {
            "file_name": a.file_name,
            "url": fetch_s3_presigned_url(a.file_path, file_name=a.file_name) if a.file_path else None,
        } if a.file_path else None,
        "document_type": {
            "id": a.document_type.id,
            "name": a.document_type.name,
        } if a.document_type else None,
        "notes": a.notes,
        "created": int(a.created.timestamp()) if a.created else None,
    }


# =====================================================
# STEP 1 - agreement_api (GET ALL + POST)
# =====================================================

@is_request_authenticated
def agreement_api(request):

    if request.method == "GET":

        # Convert UserProfile to PropertyManager instance
        property_manager = PropertyManager.objects.filter(pk=request.user.pk).first()
        if not property_manager:
            logger.warning(
                "AGREEMENT_LIST_FETCH_FAILED | user_id=%s | reason=PROPERTY_MANAGER_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.ONLY_PM_ALLOWED,
                status=status.HTTP_403_FORBIDDEN
            )

        # ── Only logged in user's agreements ──────────────────
        agreements = Documentation.objects.filter(
            user=property_manager,
            is_active=True
        ).select_related(
            'document_type', 'user__user'
        ).order_by('-id')

        # ── Filters ───────────────────────────────────────────
        status_filter = request.GET.get("status")
        search = request.GET.get("search")
        does_not_expire = request.GET.get("does_not_expire")

        if status_filter:
            agreements = agreements.filter(status=status_filter.upper())

        if search:
            agreements = agreements.filter(agreement_name__icontains=search)

        if does_not_expire is not None:
            agreements = agreements.filter(does_not_expire=does_not_expire.lower() == 'true')

        # ── Pagination ────────────────────────────────────────
        page_size = int(request.GET.get("page_size", 10))
        page = int(request.GET.get("page", 1))
        total = agreements.count()
        start = (page - 1) * page_size
        end = start + page_size
        paginated = agreements[start:end]
         
        logger.info(
            "AGREEMENTS_FETCHED | user_id=%s | total=%s | page=%s",
            request.user.id, total, page )
        return prepare_response(
            content={
                "results": [serialize_agreement(a) for a in paginated],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            },
            message=constants.AGREEMENTS_FETCHED,
            status=status.HTTP_200_OK
        )

    elif request.method == "POST":
        body = json.loads(request.body)

        agreement_name = body.get("agreement_name")
        if not agreement_name:
            logger.warning(
                "AGREEMENT_CREATE_FAILED | user_id=%s | reason=AGREEMENT_NAME_MISSING",
                request.user.id )
            return prepare_response(
                message=constants.AGREEMENT_NAME_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        document_type_id = body.get("document_type_id")
        document_type = DocumentType.objects.filter(id=document_type_id).first()
        if not document_type:
            logger.warning(
                "AGREEMENT_CREATE_FAILED | user_id=%s | reason=DOCUMENT_TYPE_INVALID",
                request.user.id )
            return prepare_response(
                message=constants.DOCUMENT_TYPE_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        does_not_expire = body.get("does_not_expire", False)
        start_date = body.get("start_date")
        end_date = body.get("end_date")

        if not does_not_expire and not end_date:
            logger.warning(
                "AGREEMENT_CREATE_FAILED | user_id=%s | reason=END_DATE_REQUIRED",
                request.user.id )
            return prepare_response(
                message=constants.END_DATE_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        # Convert UserProfile to PropertyManager instance
        property_manager = PropertyManager.objects.filter(pk=request.user.pk).first()
        if not property_manager:
            logger.warning(
                "AGREEMENT_CREATE_FAILED | user_id=%s | reason=PROPERTY_MANAGER_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.ONLY_PM_CREATE,
                status=status.HTTP_403_FORBIDDEN
            )

        agreement = Documentation.objects.create(
            user=property_manager,
            document_type=document_type,
            agreement_name=agreement_name,
            agreement_type=body.get("agreement_type", "OTHER"),
            status='ACTIVE',
            issued_by=body.get("issued_by"),
            does_not_expire=does_not_expire,
            notes=body.get("notes"),
            cc_emails=body.get("cc_emails"),
            file_name=body.get("file_name", ""),
            file_path=body.get("file_path", ""),
            start_date=timezone.datetime.fromtimestamp(start_date, tz=timezone.utc) if start_date else None,
            end_date=timezone.datetime.fromtimestamp(end_date, tz=timezone.utc) if end_date and not does_not_expire else None,
            created_by=request.user.user
        )
        logger.info(
            "AGREEMENT_CREATED | user_id=%s | agreement_id=%s | agreement_code=%s",
            request.user.id, agreement.id, agreement.code )
        return prepare_response(
            content={"id": agreement.id, "code": agreement.code},
            message=constants.AGREEMENT_CREATED,
            status=status.HTTP_201_CREATED
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 2 - agreement_detail_api (GET + PUT + DELETE)
# =====================================================

@is_request_authenticated
def agreement_detail_api(request, pk):

    # Convert UserProfile to PropertyManager instance
    property_manager = PropertyManager.objects.filter(pk=request.user.pk).first()
    if not property_manager:
        logger.warning(
                    "AGREEMENT_ACCESS_FAILED | user_id=%s | reason=PROPERTY_MANAGER_NOT_FOUND",
                    request.user.id )
        return prepare_response(
            message="Only Property Managers can access agreements.",
            status=status.HTTP_403_FORBIDDEN
        )

    agreement = Documentation.objects.filter(
        id=pk,
        user=property_manager,
        is_active=True
    ).select_related('document_type', 'user__user').first()

    if not agreement:
        logger.warning(
            "AGREEMENT_ACCESS_FAILED | user_id=%s | agreement_id=%s | reason=NOT_FOUND",
            request.user.id, pk )
        return prepare_response(
            message="Agreement not found.",
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        logger.info(
            "AGREEMENT_FETCHED | user_id=%s | agreement_id=%s",
            request.user.id, agreement.id )
        return prepare_response(
            content=serialize_agreement(agreement),
            message=constants.AGREEMENT_FETCHED,
            status=status.HTTP_200_OK
        )

    elif request.method == "PUT":
        body = json.loads(request.body)

        agreement.agreement_name = body.get("agreement_name", agreement.agreement_name)
        agreement.agreement_type = body.get("agreement_type", agreement.agreement_type)
        agreement.notes = body.get("notes", agreement.notes)
        agreement.status = body.get("status", agreement.status)
        agreement.issued_by = body.get("issued_by", agreement.issued_by)
        agreement.cc_emails = body.get("cc_emails", agreement.cc_emails)
        agreement.does_not_expire = body.get("does_not_expire", agreement.does_not_expire)

        start_date = body.get("start_date")
        end_date = body.get("end_date")
        if start_date:
            agreement.start_date = timezone.datetime.fromtimestamp(start_date, tz=timezone.utc)
        if end_date:
            agreement.end_date = timezone.datetime.fromtimestamp(end_date, tz=timezone.utc)

        document_type_id = body.get("document_type_id")
        if document_type_id:
            document_type = DocumentType.objects.filter(id=document_type_id).first()
            if document_type:
                agreement.document_type = document_type

        agreement.save()
        agreement.update_status()
        logger.info(
            "AGREEMENT_UPDATED | user_id=%s | agreement_id=%s",
            request.user.id, agreement.id )
        return prepare_response(
            message=constants.AGREEMENT_UPDATED,
            status=status.HTTP_200_OK
        )

    elif request.method == "DELETE":
        agreement.is_active = False
        agreement.save()
        logger.info(
                "AGREEMENT_DELETED | user_id=%s | agreement_id=%s",
                request.user.id, agreement.id )
        return prepare_response(
            message=constants.AGREEMENT_DELETED,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


# =====================================================
# STEP 3 - renew_agreement
# =====================================================
@is_request_authenticated
def renew_agreement(request, pk):

    if request.method == "PATCH":

        from user_service.models import Documentation, PropertyManager
        from user_service.tasks import send_renewal_email

        property_manager = PropertyManager.objects.filter(pk=request.user.pk).first()
        if not property_manager:
            logger.warning(
                        "AGREEMENT_RENEW_FAILED | user_id=%s | reason=PROPERTY_MANAGER_NOT_FOUND",
                        request.user.id )
            return prepare_response(
                message=constants.ONLY_PM_RENEW,
                status=status.HTTP_403_FORBIDDEN
            )

        agreement = Documentation.objects.filter(
            id=pk,
            user=property_manager,
            is_active=True
        ).first()

        if not agreement:
            logger.warning(
                    "AGREEMENT_RENEW_FAILED | user_id=%s | agreement_id=%s | reason=AGREEMENT_NOT_FOUND",
                    request.user.id, pk )
            return prepare_response(
                message="Agreement not found.",
                status=status.HTTP_404_NOT_FOUND
            )

        body = json.loads(request.body)
        new_end_date_epoch = body.get("new_end_date")

        if not new_end_date_epoch:
            logger.warning(
                "AGREEMENT_RENEW_FAILED | user_id=%s | agreement_id=%s | reason=NEW_END_DATE_MISSING",
                request.user.id, pk )
            return prepare_response(
                message=constants.NEW_END_DATE_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        new_end_date = timezone.datetime.fromtimestamp(
            new_end_date_epoch,
            tz=timezone.utc
        )

        # ✅ 1. Renew Agreement
        agreement.mark_renewed(
            user=property_manager,
            new_end_date=new_end_date
        )

        # ✅ 2. IMPORTANT (ensure fresh data)
        agreement.refresh_from_db()

        # ✅ 3. SEND EMAIL ASYNC (BEST PRACTICE)
        send_renewal_email.delay(agreement.id, property_manager.id)
        logger.info(
            "AGREEMENT_RENEWED | user_id=%s | agreement_id=%s | agreement_code=%s",
            request.user.id, agreement.id, agreement.code )
        return prepare_response(
            content={
                "code": agreement.code,
                "new_end_date": new_end_date_epoch,
                "is_renewed": True
            },
            message=constants.AGREEMENT_RENEWED,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )

# =====================================================
# STEP 4 - upload_agreement_document
# =====================================================

@is_request_authenticated
def upload_agreement_document(request, pk):

    if request.method == "POST":
        # Convert UserProfile to PropertyManager instance
        property_manager = PropertyManager.objects.filter(pk=request.user.pk).first()
        if not property_manager:
            logger.warning(
                "AGREEMENT_DOCUMENT_UPLOAD_FAILED | user_id=%s | reason=PROPERTY_MANAGER_NOT_FOUND",
                request.user.id )
            return prepare_response(
                message=constants.ONLY_PM_UPLOAD,
                status=status.HTTP_403_FORBIDDEN
            )

        body = json.loads(request.body)

        agreement = Documentation.objects.filter(
            id=pk,
            user=property_manager,
            is_active=True
        ).first()

        if not agreement:
            logger.warning(
                "AGREEMENT_DOCUMENT_UPLOAD_FAILED | user_id=%s | agreement_id=%s | reason=NOT_FOUND",
                request.user.id, pk )
            return prepare_response(
                message=constants.AGREEMENT_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        file_name = body.get("file_name")
        file_data = body.get("file_data")

        if not file_name or not file_data:
            logger.warning(
                "AGREEMENT_DOCUMENT_UPLOAD_FAILED | user_id=%s | agreement_id=%s | reason=FILE_MISSING",
                request.user.id, pk )
            return prepare_response(
                message=constants.FILE_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        object_name = f"agreements/{agreement.code}/{uuid.uuid4()}_{file_name}"
        file_url = upload_file_to_s3_base64(
            file_data=file_data,
            object_name=object_name
        )

        agreement.file_path = file_url
        agreement.file_name = file_name
        agreement.save()
        logger.info(
            "AGREEMENT_DOCUMENT_UPLOADED | user_id=%s | agreement_id=%s | file_name=%s",
            request.user.id, agreement.id, file_name )
        return prepare_response(
            content={
                "file_name": file_name,
                "url": fetch_s3_presigned_url(file_url, file_name=file_name)
            },
            message=constants.DOCUMENT_UPLOADED,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.METHOD_NOT_ALLOWED,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )
@is_request_authenticated
def share_profile(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        data = json.loads(request.body)
        profile_id = data.get("profile_id")
        recipient_email = data.get("recipient_email", "").strip()

        if not all([profile_id, recipient_email]):
            logger.warning(
                "PROFILE_SHARE_FAILED | user_id=%s | reason=MISSING_REQUIRED_FIELDS",
                request.user.id )
            return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)

        profile = UserProfile.objects.select_related("user", "city").get(pk=profile_id)
        django_user = profile.user

        role = "User"
        if PropertyManager.objects.filter(pk=profile.pk).exists():
            role = "Property Manager"
        elif Owner.objects.filter(pk=profile.pk).exists():
            role = "Owner"
        elif Tenant.objects.filter(pk=profile.pk).exists():
            role = "Tenant"

        name = django_user.get_full_name() or django_user.email
        initials = "".join([p[0].upper() for p in name.split()[:2]]) if name else "?"

        sender_profile = request.user
        shared_by = sender_profile.user.get_full_name() or sender_profile.user.email

        raw_image = profile.profile_image or ""
        profile_image_url = ""
        if raw_image:
            try:
                if raw_image.startswith("http"):
                    # Already an S3 URL — generate presigned link
                    presigned = fetch_s3_presigned_url(raw_image, expiration=604800)
                    profile_image_url = presigned or ""
                elif raw_image.startswith("data:") or len(raw_image) > 100:
                    # Base64 string — upload to S3 then presign
                    s3_key = f"profile_shares/{profile_id}/{uuid.uuid4().hex}.png"
                    s3_url = upload_file_to_s3_base64(raw_image, s3_key)
                    presigned = fetch_s3_presigned_url(s3_url, expiration=604800)
                    profile_image_url = presigned or ""
            except Exception:
                profile_image_url = ""

        context = {
            "name": name,
            "initials": initials,
            "email": django_user.email,
            "phone": profile.contact_number or "",
            "code": profile.code or "",
            "city": profile.city.name if profile.city else "",
            "role": role,
            "profile_image": profile_image_url,
            "shared_by": shared_by,
        }

        body_html = render_to_string("email_templates/share_profile.html", context)
        body_text = (
            f"Profile Shared: {name}\n"
            f"Role: {role}\nEmail: {context['email']}\n"
            f"Phone: {context['phone']}\nCode: {context['code']}\n"
            f"Shared by: {shared_by}"
        )

        send_ses_email(recipient_email, f"Profile: {name}", body_text, body_html)
        logger.info(
            "PROFILE_SHARED | user_id=%s | profile_id=%s | recipient_email=%s",
            request.user.id, profile_id, recipient_email )
        return prepare_response(message="Profile shared successfully.", status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        logger.warning(
            "PROFILE_SHARE_FAILED | user_id=%s | profile_id=%s | reason=USER_NOT_FOUND",
            request.user.id, profile_id if 'profile_id' in locals() else None )
        return prepare_response(message="User not found.", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(
            "PROFILE_SHARE_ERROR | user_id=%s | profile_id=%s | error=%s",
            request.user.id if hasattr(request, "user") else None,
            profile_id if 'profile_id' in locals() else None, str(e) )
        print("share_profile error:", e)
        return prepare_response(message=constants.INTERNAL_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@is_request_authenticated
def reset_user_password(request):
    if request.method != "POST":
        return prepare_response(message=constants.INVALID_REQUEST, status=status.HTTP_405_METHOD_NOT_ALLOWED)
    try:
        data = json.loads(request.body)
        user_id = data.get("user_id")
        new_password = data.get("new_password")
        confirm_password = data.get("confirm_password")

        if not all([user_id, new_password, confirm_password]):
            logger.warning(
                "PASSWORD_RESET_FAILED | user_id=%s | reason=MISSING_REQUIRED_FIELDS",
                request.user.id )
            return prepare_response(message=constants.FIELD_REQUIRED, status=status.HTTP_400_BAD_REQUEST)
        if new_password != confirm_password:
            logger.warning(
                "PASSWORD_RESET_FAILED | user_id=%s | target_user_id=%s | reason=PASSWORD_MISMATCH",
                request.user.id, user_id )
            return prepare_response(message=constants.PASSWORD_MISMATCH, status=status.HTTP_400_BAD_REQUEST)
        if len(new_password) < 6:
            logger.warning(
                "PASSWORD_RESET_FAILED | user_id=%s | target_user_id=%s | reason=PASSWORD_TOO_SHORT",
                request.user.id, user_id )
            return prepare_response(message="Password must be at least 6 characters.", status=status.HTTP_400_BAD_REQUEST)

        profile = UserProfile.objects.select_related("user").get(pk=user_id)
        profile.user.set_password(new_password)
        profile.user.save()
        logger.info(
            "PASSWORD_RESET_SUCCESS | user_id=%s | target_user_id=%s", 
            request.user.id, user_id )
        return prepare_response(message="Password reset successfully.", status=status.HTTP_200_OK)
    except UserProfile.DoesNotExist:
        logger.warning(
            "PASSWORD_RESET_FAILED | user_id=%s | target_user_id=%s | reason=USER_NOT_FOUND",
            request.user.id, user_id if 'user_id' in locals() else None )
        return prepare_response(message="User not found.", status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.exception(
            "PASSWORD_RESET_ERROR | user_id=%s | target_user_id=%s | error=%s",
            request.user.id if hasattr(request, "user") else None,
            user_id if 'user_id' in locals() else None, str(e))
        print("reset_user_password error:", e)
        return prepare_response(message=constants.INTERNAL_SERVER_ERROR, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

