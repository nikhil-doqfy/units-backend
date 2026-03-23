import random
from datetime import timedelta
from utilities.helper_functions import upload_file_to_s3_base64, get_extension_from_base64
from user_service.models import DocumentType
from user_service.models import Approval
from django.utils import timezone

def request_otp_sent():
    otp = random.randint(100000, 999999)
    return otp


def upload_document(base64_data, file_prefix, document_type_id, document_model, extra_kwargs, folder_name, user):
    if not base64_data or not document_type_id:
        return None
    doc_type = DocumentType.objects.filter(id=document_type_id).first()
    if not doc_type:
        return None
    extension = get_extension_from_base64(base64_data) or ".png"
    filename = f"{file_prefix}{extension}"
    object_name = f"{folder_name}/{filename}"
    uploaded_url = upload_file_to_s3_base64(base64_data, object_name)
    if not uploaded_url:
        return None
    return document_model.objects.create(
        file_name=filename,
        file_path=uploaded_url,
        document_type=doc_type,
        created_by=user,
        **extra_kwargs
    )

def process_rent_approval(approval_id, user_profile, rent=None, tenure=None, action="approve"):

    approval = Approval.objects.select_related("unit").filter(id=approval_id).first()

    if not approval:
        return None, "Approval request not found"

    if action == "approve":

        approval.approved = True
        approval.approved_by = user_profile
        approval.approved_at = timezone.now()
        approval.save()
        unit = approval.unit

        if rent:
            unit.rent = rent

        if tenure:
            unit.cycle = tenure

        unit.save()

        return approval, "Rent request approved successfully"

    elif action == "reject":

        approval.approved = False
        approval.approved_by = user_profile
        approval.approved_at = timezone.now()
        approval.save()

        return approval, "Rent request rejected"

    return None, "Invalid action"

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
