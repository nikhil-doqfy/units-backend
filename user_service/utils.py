import random
from user_service.models import UserProfile
from utilities import status, constants
from utilities.helper_functions import prepare_response ,upload_file_to_s3_base64,datetime_to_epoch_millis,safe_epoch_to_datetime,get_extension_from_base64,get_user_code_prefix,generate_unique_code
from user_service.models import UserProfile,Documents,OwnerDocumentsMapping,  CompanyUserDocumentsMapping,TenantDocumentsMapping , Company,Country, State, City , Role, PropertyUnitDetails,Permission
from user_service.models import CompanyStaff

def request_otp_sent():
    otp = random.randint(100000, 999999)
    return otp

    





# def get_company_staff(user):
#     try:
#         profile = user.profile.first()
#         return CompanyStaff.objects.select_related(
#             "company"
#         ).prefetch_related(
#             "roles__permissions",
#             "permissions"
#         ).get(staff=profile)
#     except CompanyStaff.DoesNotExist:
#         return None



# def get_user_permissions(user):
#     staff = get_company_staff(user)

#     if not staff:
#         return set()

#     permissions = set()

#     # Role permissions
#     for role in staff.roles.all():
#         for perm in role.permissions.all():
#             permissions.add(perm.codename)

#     # Direct staff permissions
#     for perm in staff.permissions.all():
#         permissions.add(perm.codename)

#     return permissions



# def require_permission(permission):
#     def decorator(view_func):
#         def wrapper(request, *args, **kwargs):
#             if not request.user.is_authenticated:
#                 return prepare_response("Unauthorized", 401)

#             user_permissions = get_user_permissions(request.user)

#             if permission not in user_permissions:
#                 return prepare_response("Permission denied", 403)

#             return view_func(request, *args, **kwargs)
#         return wrapper
#     return decorator



# def require_any_permission(permission_list):
#     def decorator(view_func):
#         def wrapper(request, *args, **kwargs):
#             perms = get_user_permissions(request.user)

#             if not any(p in perms for p in permission_list):
#                 return prepare_response("Permission denied", 403)

#             return view_func(request, *args, **kwargs)
#         return wrapper
#     return decorator



# def require_all_permissions(permission_list):
#     def decorator(view_func):
#         def wrapper(request, *args, **kwargs):
#             perms = get_user_permissions(request.user)

#             if not all(p in perms for p in permission_list):
#                 return prepare_response("Permission denied", 403)

#             return view_func(request, *args, **kwargs)
#         return wrapper
#     return decorator




# def seed_permissions():
#     permissions = [
#         "PROPERTY_VIEW", "PROPERTY_CREATE", "PROPERTY_EDIT", "PROPERTY_DELETE",
#         "TENANT_VIEW", "TENANT_CREATE", "TENANT_EDIT", "TENANT_DELETE",
#         "ROLE_MANAGEMENT", "STAFF_MANAGEMENT"
#     ]

#     for perm in permissions:
#         Permission.objects.get_or_create(
#             codename=perm,
#             defaults={"name": perm.replace("_", " ").title()}
#         )
