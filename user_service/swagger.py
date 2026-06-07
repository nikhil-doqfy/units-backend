# Swagger documentation for user_service app APIs
# This file contains Swagger decorators used in user_service/views.py

from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


USER_SERVICE_TAG = ["User Service"]


# Common permission schema used while creating/updating roles
permission_schema = openapi.Schema(
    type=openapi.TYPE_ARRAY,
    items=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "module_name": openapi.Schema(type=openapi.TYPE_STRING, example="PROPERTY"),
            "create": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
            "edit": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
            "delete": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
            "view": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=True),
        },
    ),
)


# ================= USER SIGNUP =================

user_sign_up_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="User signup",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email", "password", "confirm_password", "user_role"],
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "password": openapi.Schema(type=openapi.TYPE_STRING, example="Password@123"),
            "confirm_password": openapi.Schema(type=openapi.TYPE_STRING, example="Password@123"),
            "user_role": openapi.Schema(type=openapi.TYPE_STRING, example="OWNER"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "pin_code": openapi.Schema(type=openapi.TYPE_STRING, example="00000"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai"),
            "emirate_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1998-1234567-1"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, example="VISA12345"),
            "company_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "trade_license_number": openapi.Schema(type=openapi.TYPE_STRING, example="TL123456"),
        },
    ),
)


# ================= USER PROFILE =================

userprofile_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get user profile",
)

userprofile_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update user profile",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "city": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "profile_image": openapi.Schema(type=openapi.TYPE_STRING, example="data:image/png;base64,iVBORw0KGgo..."),
            "pin_code": openapi.Schema(type=openapi.TYPE_STRING, example="00000"),
            "address": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina"),
            "additional_address": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai"),
            "locality": openapi.Schema(type=openapi.TYPE_STRING, example="Marina"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "emirate_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1998-1234567-1"),
            "time_zone": openapi.Schema(type=openapi.TYPE_STRING, example="Asia/Dubai"),
        },
    ),
)


# ================= USER MANAGEMENT =================

user_management_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get users",
    manual_parameters=[
        openapi.Parameter("is_active", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="true"),
        openapi.Parameter("role", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="OWNER"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("user_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)

user_management_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create user",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["first_name", "last_name", "email", "password", "role"],
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "password": openapi.Schema(type=openapi.TYPE_STRING, example="Password@123"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "role": openapi.Schema(type=openapi.TYPE_STRING, example="TENANT"),
            "profile_image": openapi.Schema(type=openapi.TYPE_STRING, example="data:image/png;base64,iVBORw0KGgo..."),
        },
    ),
)

user_management_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update user",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["user_id"],
        properties={
            "user_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "profile_image": openapi.Schema(type=openapi.TYPE_STRING, example="data:image/png;base64,iVBORw0KGgo..."),
        },
    ),
)

user_management_delete = swagger_auto_schema(
    method="delete",
    tags=USER_SERVICE_TAG,
    operation_summary="Delete or deactivate user",
    manual_parameters=[
        openapi.Parameter("user_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ================= ROLE =================

create_role_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create role",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["name"],
        properties={
            "name": openapi.Schema(type=openapi.TYPE_STRING, example="Property Executive"),
            "permissions": permission_schema,
        },
    ),
)

role_table_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get roles",
    manual_parameters=[
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="manager"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("start_date", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1735689600000),
        openapi.Parameter("end_date", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1767225599000),
        openapi.Parameter("is_active", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="true"),
    ],
)

role_table_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update role",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["role_id", "name"],
        properties={
            "role_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "name": openapi.Schema(type=openapi.TYPE_STRING, example="Senior Property Executive"),
            "permissions": permission_schema,
        },
    ),
)


# ================= EXPORT USERS CSV =================

export_users_csv_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Export users CSV",
    manual_parameters=[
        openapi.Parameter("is_active", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="true"),
        openapi.Parameter("role", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="OWNER"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("start_date", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1735689600000),
        openapi.Parameter("end_date", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1767225599000),
        openapi.Parameter("user_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


# ================= STAFF =================

staff_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get staff list or single staff",
    manual_parameters=[
        openapi.Parameter("staff_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("role", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_number", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
    ],
)

staff_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create staff",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["first_name", "email", "password"],
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "password": openapi.Schema(type=openapi.TYPE_STRING, example="Password@123"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "role": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "assigned_property": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                example=[1, 2, 3],
            ),
        },
    ),
)

staff_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update staff",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["staff_id"],
        properties={
            "staff_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "role": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "assigned_property": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                items=openapi.Schema(type=openapi.TYPE_INTEGER),
                example=[1, 2, 3],
            ),
        },
    ),
)


# ================= EXPORT STAFF CSV =================

export_staff_csv_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Export staff CSV",
    manual_parameters=[
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("role_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("staff_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


# ================= CONTACT LIST =================

contact_list_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get contact list",
    manual_parameters=[
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("role", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Tenant"),
    ],
)


# ================= OWNER =================

owner_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get owners",
    manual_parameters=[
        openapi.Parameter("owner_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("tenancy_status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="OCCUPIED"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("export", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="csv"),
    ],
)

owner_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create owner",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email"],
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1990-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, example="Indian"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai"),
            "pin_code": openapi.Schema(type=openapi.TYPE_STRING, example="00000"),
            "passport_number": openapi.Schema(type=openapi.TYPE_STRING, example="P1234567"),
            "passport_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2030-12-31"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, example="VISA123"),
            "visa_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2028-12-31"),
            "owner_number": openapi.Schema(type=openapi.TYPE_STRING, example="OWN123"),
            "trade_license_number": openapi.Schema(type=openapi.TYPE_STRING, example="TL123"),
            "license_number": openapi.Schema(type=openapi.TYPE_STRING, example="LIC123"),
            "license_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2030-12-31"),
            "license_issuer": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Authority"),
            "fax_number": openapi.Schema(type=openapi.TYPE_STRING, example="123456"),
            "po_box_number": openapi.Schema(type=openapi.TYPE_STRING, example="PO123"),
        },
    ),
)

owner_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update owner",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["owner_id"],
        properties={
            "owner_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1990-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, example="Indian"),
            "license_number": openapi.Schema(type=openapi.TYPE_STRING, example="LIC123"),
            "license_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2030-12-31"),
        },
    ),
)

owner_delete = swagger_auto_schema(
    method="delete",
    tags=USER_SERVICE_TAG,
    operation_summary="Delete owner",
    manual_parameters=[
        openapi.Parameter("owner_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ================= TENANT =================

tenant_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get tenants",
    manual_parameters=[
        openapi.Parameter("tenant_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("email", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="himanshu@doqfy.in"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("tab", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="onboarding"),
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("export", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="csv"),
    ],
)

tenant_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create tenant",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email"],
        properties={
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu Kolhe"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1998-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, example="Indian"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai"),
            "pin_code": openapi.Schema(type=openapi.TYPE_STRING, example="00000"),
            "passport_number": openapi.Schema(type=openapi.TYPE_STRING, example="P1234567"),
            "passport_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2030-12-31"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, example="VISA123"),
            "visa_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, example="2028-12-31"),
        },
    ),
)

tenant_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update tenant",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["tenant_id"],
        properties={
            "tenant_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "first_name": openapi.Schema(type=openapi.TYPE_STRING, example="Himanshu"),
            "last_name": openapi.Schema(type=openapi.TYPE_STRING, example="Kolhe"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, example="784-1998-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, example="Indian"),
            "passport_number": openapi.Schema(type=openapi.TYPE_STRING, example="P1234567"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, example="VISA123"),
        },
    ),
)


# ================= EXPORT TENANT CSV =================

export_tenant_csv_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Export tenant CSV",
    manual_parameters=[
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("tab", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="active"),
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


# ================= APPROVAL =================

approval_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get rent approvals",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("approval_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="PENDING"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
    ],
)

approval_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create rent approval request",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["tenant_id", "unit_id", "requested_rent"],
        properties={
            "tenant_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "requested_rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=60000),
            "requested_tenure": openapi.Schema(type=openapi.TYPE_STRING, example="12 months"),
        },
    ),
)

approval_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Approve or reject rent approval",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["approval_id", "action"],
        properties={
            "approval_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "action": openapi.Schema(type=openapi.TYPE_STRING, example="APPROVE"),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, example=60000),
            "tenure": openapi.Schema(type=openapi.TYPE_STRING, example="12 months"),
        },
    ),
)


# ================= OWNER PMC =================

owner_pmc_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get owner PMC list",
    manual_parameters=[
        openapi.Parameter("company_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Doqfy"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
    ],
)


# ================= EXPORT OWNER PMC CSV =================

export_owner_pmc_csv_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Export owner PMC CSV",
    manual_parameters=[
        openapi.Parameter("company_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Doqfy"),
    ],
)


# ================= EXPORT COMPANY OWNERS CSV =================

export_company_owners_csv_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Export company owners CSV",
    manual_parameters=[
        openapi.Parameter("owner_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("tenancy_status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="OCCUPIED"),
    ],
)


# ================= COMPANY TENANTS =================

company_tenants_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get company tenants",
    manual_parameters=[
        openapi.Parameter("tenant_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("tenant_status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="PENDING"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="Himanshu"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
    ],
)

company_tenants_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update company tenant status",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["tenant_id", "tenant_status"],
        properties={
            "tenant_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "tenant_status": openapi.Schema(type=openapi.TYPE_STRING, example="APPROVED"),
        },
    ),
)


# ================= AGREEMENT =================

agreement_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get agreements",
    manual_parameters=[
        openapi.Parameter("status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="ACTIVE"),
        openapi.Parameter("search", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="agreement"),
        openapi.Parameter("does_not_expire", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="false"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=10),
    ],
)

agreement_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Create agreement",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["agreement_name", "document_type_id"],
        properties={
            "agreement_name": openapi.Schema(type=openapi.TYPE_STRING, example="Property Management Agreement"),
            "agreement_type": openapi.Schema(type=openapi.TYPE_STRING, example="PROPERTY_MANAGEMENT"),
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "issued_by": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Authority"),
            "does_not_expire": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
            "start_date": openapi.Schema(type=openapi.TYPE_INTEGER, example=1735689600),
            "end_date": openapi.Schema(type=openapi.TYPE_INTEGER, example=1767225600),
            "notes": openapi.Schema(type=openapi.TYPE_STRING, example="Agreement notes"),
            "cc_emails": openapi.Schema(type=openapi.TYPE_STRING, example="admin@example.com,manager@example.com"),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, example="agreement.pdf"),
            "file_path": openapi.Schema(type=openapi.TYPE_STRING, example="agreements/agreement.pdf"),
        },
    ),
)


# ================= AGREEMENT DETAIL =================

agreement_detail_get = swagger_auto_schema(
    method="get",
    tags=USER_SERVICE_TAG,
    operation_summary="Get agreement detail",
    manual_parameters=[
        openapi.Parameter("pk", openapi.IN_PATH, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)

agreement_detail_put = swagger_auto_schema(
    method="put",
    tags=USER_SERVICE_TAG,
    operation_summary="Update agreement",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        properties={
            "agreement_name": openapi.Schema(type=openapi.TYPE_STRING, example="Updated Agreement"),
            "agreement_type": openapi.Schema(type=openapi.TYPE_STRING, example="PROPERTY_MANAGEMENT"),
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "issued_by": openapi.Schema(type=openapi.TYPE_STRING, example="Dubai Authority"),
            "does_not_expire": openapi.Schema(type=openapi.TYPE_BOOLEAN, example=False),
            "start_date": openapi.Schema(type=openapi.TYPE_INTEGER, example=1735689600),
            "end_date": openapi.Schema(type=openapi.TYPE_INTEGER, example=1767225600),
            "notes": openapi.Schema(type=openapi.TYPE_STRING, example="Updated notes"),
            "cc_emails": openapi.Schema(type=openapi.TYPE_STRING, example="admin@example.com"),
            "status": openapi.Schema(type=openapi.TYPE_STRING, example="ACTIVE"),
        },
    ),
)

agreement_detail_delete = swagger_auto_schema(
    method="delete",
    tags=USER_SERVICE_TAG,
    operation_summary="Delete agreement",
    manual_parameters=[
        openapi.Parameter("pk", openapi.IN_PATH, type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ================= RENEW AGREEMENT =================

renew_agreement_patch = swagger_auto_schema(
    method="patch",
    tags=USER_SERVICE_TAG,
    operation_summary="Renew agreement",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["new_end_date"],
        properties={
            "new_end_date": openapi.Schema(type=openapi.TYPE_INTEGER, example=1767225600),
        },
    ),
)


# ================= UPLOAD AGREEMENT DOCUMENT =================

upload_agreement_document_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Upload agreement document",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["file_name", "file_data"],
        properties={
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, example="agreement.pdf"),
            "file_data": openapi.Schema(type=openapi.TYPE_STRING, example="data:application/pdf;base64,JVBERi0xLjQK..."),
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
        },
    ),
)


# ================= SHARE PROFILE =================

share_profile_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Share profile",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["profile_id", "recipient_email"],
        properties={
            "profile_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "recipient_email": openapi.Schema(type=openapi.TYPE_STRING, example="himanshu@doqfy.in"),
        },
    ),
)


# ================= RESET USER PASSWORD =================

reset_user_password_post = swagger_auto_schema(
    method="post",
    tags=USER_SERVICE_TAG,
    operation_summary="Reset user password",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["user_id", "new_password", "confirm_password"],
        properties={
            "user_id": openapi.Schema(type=openapi.TYPE_INTEGER, example=1),
            "new_password": openapi.Schema(type=openapi.TYPE_STRING, example="NewPassword@123"),
            "confirm_password": openapi.Schema(type=openapi.TYPE_STRING, example="NewPassword@123"),
        },
    ),
)