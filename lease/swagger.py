from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema

LEASE_TAG = ["Lease"]


# ---------------- LEASE CRUD APIs ----------------
# These decorators are used for lease_view GET, POST, PUT, DELETE APIs.

# GET /lease/
# Get lease list using filters, pagination, or get single lease by lease_id.
lease_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease list or single lease",
    operation_description="Get all leases with filters, pagination, or get single lease using lease_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("tenant_id", openapi.IN_QUERY, description="Tenant ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("lease_status", openapi.IN_QUERY, description="Lease status filter", type=openapi.TYPE_STRING, required=False, example="ACTIVE"),
        openapi.Parameter("lease_stage", openapi.IN_QUERY, description="Lease stage filter", type=openapi.TYPE_STRING, required=False, example="BASIC_DETAILS"),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search by lease code", type=openapi.TYPE_STRING, required=False, example="LS00001"),
        openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, description="Records per page", type=openapi.TYPE_INTEGER, required=False, example=20),
    ],
)


# POST /lease/
# Create a new lease. Tenant can be selected by tenant_id or created/updated using email.
lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Create lease",
    operation_description="Create a new lease with tenant and unit details.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id"],
        properties={
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Unit ID", example=1),
            "tenant_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Existing tenant ID", example=1),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant email", example="tenant@example.com"),
            "tenant_name": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant full name", example="Rahul Sharma"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant contact number", example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant Emirates ID", example="784-1998-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant nationality", example="Indian"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant address line 1", example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant address line 2", example="Dubai"),
            "passport_number": openapi.Schema(type=openapi.TYPE_STRING, description="Passport number", example="P1234567"),
            "passport_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, description="Passport expiry date", example="2030-12-31"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, description="Visa number", example="VISA12345"),
            "visa_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, description="Visa expiry date", example="2028-12-31"),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Lease start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Lease end date", example="2027-05-31"),
            "grace_start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Grace start date", example="2026-06-01"),
            "grace_end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Grace end date", example="2026-06-10"),
            "annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Annual amount", example=60000),
            "actual_annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Actual annual amount", example=65000),
            "booking_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Booking amount", example=5000),
            "maintenance_charges": openapi.Schema(type=openapi.TYPE_NUMBER, description="Maintenance charges", example=2000),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, description="Rent amount", example=5000),
            "security_deposit": openapi.Schema(type=openapi.TYPE_NUMBER, description="Security deposit", example=5000),
            "commission": openapi.Schema(type=openapi.TYPE_NUMBER, description="Commission", example=3000),
            "notice_period": openapi.Schema(type=openapi.TYPE_INTEGER, description="Notice period in days", example=60),
            "discount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Discount amount", example=1000),
            "contract_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Contract amount", example=59000),
            "payment_count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Number of installments", example=4),
            "shell_and_core": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Is shell and core unit", example=False),
            "remarks": openapi.Schema(type=openapi.TYPE_STRING, description="Lease remarks", example="New lease created"),
            "lease_status": openapi.Schema(type=openapi.TYPE_STRING, description="Lease status", example="ACTIVE"),
            "lease_stage": openapi.Schema(type=openapi.TYPE_STRING, description="Lease stage", example="INVITE"),
            "platform": openapi.Schema(type=openapi.TYPE_STRING, description="Platform", example="WEBSITE"),
        },
    ),
)


# PUT /lease/
# Update existing lease details using lease_id.
lease_put = swagger_auto_schema(
    method="put",
    tags=LEASE_TAG,
    operation_summary="Update lease",
    operation_description="Update existing lease using lease_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated end date", example="2027-05-31"),
            "annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated annual amount", example=65000),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated rent", example=5500),
            "security_deposit": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated security deposit", example=5000),
            "commission": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated commission", example=3000),
            "lease_status": openapi.Schema(type=openapi.TYPE_STRING, description="Updated lease status", example="ACTIVE"),
            "lease_stage": openapi.Schema(type=openapi.TYPE_STRING, description="Updated lease stage", example="NEGOTIATION_SENT"),
            "remarks": openapi.Schema(type=openapi.TYPE_STRING, description="Updated remarks", example="Lease updated"),
            "payment_count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Updated payment count", example=4),
            "shell_and_core": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Updated shell and core value", example=False),
        },
    ),
)


# DELETE /lease/
# Soft delete lease using lease_id.
lease_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease",
    operation_description="Soft delete lease using lease_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- LEASE ONBOARDING DOCUMENT APIs ----------------

lease_onboarding_documents_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease onboarding documents",
    operation_description="Get tenant and lease documents for a lease.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


lease_onboarding_documents_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Upload lease onboarding documents",
    operation_description="Upload one or more base64 documents for a lease.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "documents"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "documents": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of documents to upload",
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Document type ID", example=1),
                        "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Original file name", example="passport.pdf"),
                        "data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 file data", example="data:application/pdf;base64,JVBERi0xLjQK..."),
                    },
                ),
            ),
        },
    ),
)


lease_onboarding_documents_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease document",
    operation_description="Delete lease document using document_id.",
    manual_parameters=[
        openapi.Parameter("document_id", openapi.IN_QUERY, description="Document ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- TEMPLATE APIs ----------------

templates_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get templates",
    operation_description="Get all active lease templates.",
)


template_fields_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get template fields",
    operation_description="Get template fields, saved values, lease defaults, and generated PDF URL.",
    manual_parameters=[
        openapi.Parameter("template_id", openapi.IN_QUERY, description="Template ID", type=openapi.TYPE_INTEGER, required=True, example=1),
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


generate_contract_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Generate lease contract",
    operation_description="Generate lease contract PDF using template values.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["template_id", "lease_id", "values"],
        properties={
            "template_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Template ID", example=1),
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "values": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="Template field values",
                example={
                    "tenant_name": "Rahul Sharma",
                    "annual_rent": "60000",
                    "contract_start_date": "2026-06-01",
                    "contract_end_date": "2027-05-31"
                },
            ),
        },
    ),
)


# ---------------- EMAIL / NEGOTIATION / SIGNATURE REQUEST APIs ----------------

send_lease_invite_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease invite",
    operation_description="Send invite email to tenant for lease onboarding.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


send_negotiation_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease negotiation email",
    operation_description="Send negotiation email to tenant and owners.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


send_for_signature_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease for signature",
    operation_description="Send signature request email to tenant and owners.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


# ---------------- LEASE APPROVAL OTP APIs ----------------

lease_approval_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease approval OTP",
    operation_description="Send OTP to owner or tenant for lease approval.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


lease_approval_verify_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Verify lease approval OTP",
    operation_description="Verify OTP and return lease approval details.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "otp"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "otp": openapi.Schema(type=openapi.TYPE_STRING, description="OTP received on email", example="123456"),
        },
    ),
)


approve_lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Approve lease",
    operation_description="Approve lease after OTP verification.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


# ---------------- LEASE SIGNATURE OTP APIs ----------------

lease_signature_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease signature OTP",
    operation_description="Send OTP to owner or tenant for lease signature.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


lease_signature_verify_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Verify lease signature OTP",
    operation_description="Verify OTP and return lease PDF details for signing.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "otp"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "otp": openapi.Schema(type=openapi.TYPE_STRING, description="OTP received on email", example="123456"),
        },
    ),
)


submit_lease_signature_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Submit lease signature",
    operation_description="Submit base64 signature image and stamp it on lease PDF.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "signature_data"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "signature_data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 signature image", example="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."),
        },
    ),
)


# ---------------- LEASE CHEQUE APIs ----------------

lease_cheque_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease cheques",
    operation_description="Get cheques by lease_id or get single cheque using cheque_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("cheque_id", openapi.IN_QUERY, description="Cheque ID", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


lease_cheque_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Create lease cheque",
    operation_description="Create cheque or transaction record for a lease.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Document type ID", example=1),
            "origin_bank_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Origin bank ID", example=1),
            "settlement_bank_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Settlement bank ID", example=2),
            "cheque_type": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque type", example="RENT_CHEQUE"),
            "payment_type": openapi.Schema(type=openapi.TYPE_STRING, description="Payment type", example="CHEQUE"),
            "cheque_number": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque number", example="CHQ123456"),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="End date", example="2026-08-31"),
            "cheque_date": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque date", example="2026-06-05"),
            "origin_account_number": openapi.Schema(type=openapi.TYPE_INTEGER, description="Origin account number", example=123456789),
            "settlement_account_number": openapi.Schema(type=openapi.TYPE_INTEGER, description="Settlement account number", example=987654321),
            "amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Cheque amount", example=15000),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque file name", example="cheque.jpg"),
            "file_data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 cheque file data", example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."),
        },
    ),
)


lease_cheque_put = swagger_auto_schema(
    method="put",
    tags=LEASE_TAG,
    operation_summary="Update lease cheque",
    operation_description="Update cheque details using cheque_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["cheque_id"],
        properties={
            "cheque_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Cheque ID", example=1),
            "cheque_type": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque type", example="RENT_CHEQUE"),
            "payment_type": openapi.Schema(type=openapi.TYPE_STRING, description="Updated payment type", example="CHEQUE"),
            "cheque_number": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque number", example="CHQ987654"),
            "amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated amount", example=16000),
            "status": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque status", example="REALIZED"),
            "cheque_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque date", example="2026-06-10"),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Updated file name", example="updated_cheque.jpg"),
            "file_data": openapi.Schema(type=openapi.TYPE_STRING, description="Updated base64 file data", example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."),
        },
    ),
)


lease_cheque_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease cheque",
    operation_description="Delete cheque using cheque_id.",
    manual_parameters=[
        openapi.Parameter("cheque_id", openapi.IN_QUERY, description="Cheque ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- CHEQUE DASHBOARD / ANALYTICS APIs ----------------

cheque_summary_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get cheque summary",
    operation_description="Get cheque counts and amount summary grouped by status.",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
    ],
)


all_cheques_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get all cheques",
    operation_description="Get all cheques with pagination, search, and filters.",
    manual_parameters=[
        openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, description="Records per page", type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search by cheque, unit, tenant, or property", type=openapi.TYPE_STRING, required=False, example="CHQ123456"),
        openapi.Parameter("status", openapi.IN_QUERY, description="Cheque status filter", type=openapi.TYPE_STRING, required=False, example="REALIZED"),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
    ],
)


cheque_monthly_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get monthly cheque analytics",
    operation_description="Get monthly cheque amount analytics for selected year.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


rent_analytics_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get rent analytics",
    operation_description="Get rent analytics with received, pending, bounced, and total amount data.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


# ---------------- ACTIVATE LEASE API ----------------

activate_lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Activate lease",
    operation_description="Activate a lease using lease_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


# ---------------- LEASE CRUD APIs ----------------
# These decorators are used for lease_view GET, POST, PUT, DELETE APIs.

# GET /lease/
# Get lease list using filters, pagination, or get single lease by lease_id.
lease_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease list or single lease",
    operation_description="Get all leases with filters, pagination, or get single lease using lease_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("tenant_id", openapi.IN_QUERY, description="Tenant ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("lease_status", openapi.IN_QUERY, description="Lease status filter", type=openapi.TYPE_STRING, required=False, example="ACTIVE"),
        openapi.Parameter("lease_stage", openapi.IN_QUERY, description="Lease stage filter", type=openapi.TYPE_STRING, required=False, example="BASIC_DETAILS"),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search by lease code", type=openapi.TYPE_STRING, required=False, example="LS00001"),
        openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, description="Records per page", type=openapi.TYPE_INTEGER, required=False, example=20),
    ],
)


# POST /lease/
# Create a new lease. Tenant can be selected by tenant_id or created/updated using email.
lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Create lease",
    operation_description="Create a new lease with tenant and unit details.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["unit_id"],
        properties={
            "unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Unit ID", example=1),
            "tenant_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Existing tenant ID", example=1),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant email", example="tenant@example.com"),
            "tenant_name": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant full name", example="Rahul Sharma"),
            "contact_number": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant contact number", example="+971501234567"),
            "emirates_id": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant Emirates ID", example="784-1998-1234567-1"),
            "nationality": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant nationality", example="Indian"),
            "address_line_1": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant address line 1", example="Dubai Marina"),
            "address_line_2": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant address line 2", example="Dubai"),
            "passport_number": openapi.Schema(type=openapi.TYPE_STRING, description="Passport number", example="P1234567"),
            "passport_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, description="Passport expiry date", example="2030-12-31"),
            "visa_number": openapi.Schema(type=openapi.TYPE_STRING, description="Visa number", example="VISA12345"),
            "visa_expiry_date": openapi.Schema(type=openapi.TYPE_STRING, description="Visa expiry date", example="2028-12-31"),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Lease start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Lease end date", example="2027-05-31"),
            "grace_start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Grace start date", example="2026-06-01"),
            "grace_end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Grace end date", example="2026-06-10"),
            "annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Annual amount", example=60000),
            "actual_annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Actual annual amount", example=65000),
            "booking_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Booking amount", example=5000),
            "maintenance_charges": openapi.Schema(type=openapi.TYPE_NUMBER, description="Maintenance charges", example=2000),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, description="Rent amount", example=5000),
            "security_deposit": openapi.Schema(type=openapi.TYPE_NUMBER, description="Security deposit", example=5000),
            "commission": openapi.Schema(type=openapi.TYPE_NUMBER, description="Commission", example=3000),
            "notice_period": openapi.Schema(type=openapi.TYPE_INTEGER, description="Notice period in days", example=60),
            "discount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Discount amount", example=1000),
            "contract_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Contract amount", example=59000),
            "payment_count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Number of installments", example=4),
            "shell_and_core": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Is shell and core unit", example=False),
            "remarks": openapi.Schema(type=openapi.TYPE_STRING, description="Lease remarks", example="New lease created"),
            "lease_status": openapi.Schema(type=openapi.TYPE_STRING, description="Lease status", example="ACTIVE"),
            "lease_stage": openapi.Schema(type=openapi.TYPE_STRING, description="Lease stage", example="INVITE"),
            "platform": openapi.Schema(type=openapi.TYPE_STRING, description="Platform", example="WEBSITE"),
        },
    ),
)


# PUT /lease/
# Update existing lease details using lease_id.
lease_put = swagger_auto_schema(
    method="put",
    tags=LEASE_TAG,
    operation_summary="Update lease",
    operation_description="Update existing lease using lease_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated end date", example="2027-05-31"),
            "annual_amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated annual amount", example=65000),
            "rent": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated rent", example=5500),
            "security_deposit": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated security deposit", example=5000),
            "commission": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated commission", example=3000),
            "lease_status": openapi.Schema(type=openapi.TYPE_STRING, description="Updated lease status", example="ACTIVE"),
            "lease_stage": openapi.Schema(type=openapi.TYPE_STRING, description="Updated lease stage", example="NEGOTIATION_SENT"),
            "remarks": openapi.Schema(type=openapi.TYPE_STRING, description="Updated remarks", example="Lease updated"),
            "payment_count": openapi.Schema(type=openapi.TYPE_INTEGER, description="Updated payment count", example=4),
            "shell_and_core": openapi.Schema(type=openapi.TYPE_BOOLEAN, description="Updated shell and core value", example=False),
        },
    ),
)


# DELETE /lease/
# Soft delete lease using lease_id.
lease_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease",
    operation_description="Soft delete lease using lease_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- LEASE ONBOARDING DOCUMENT APIs ----------------

lease_onboarding_documents_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease onboarding documents",
    operation_description="Get tenant and lease documents for a lease.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


lease_onboarding_documents_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Upload lease onboarding documents",
    operation_description="Upload one or more base64 documents for a lease.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "documents"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "documents": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of documents to upload",
                items=openapi.Schema(
                    type=openapi.TYPE_OBJECT,
                    properties={
                        "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Document type ID", example=1),
                        "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Original file name", example="passport.pdf"),
                        "data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 file data", example="data:application/pdf;base64,JVBERi0xLjQK..."),
                    },
                ),
            ),
        },
    ),
)


lease_onboarding_documents_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease document",
    operation_description="Delete lease document using document_id.",
    manual_parameters=[
        openapi.Parameter("document_id", openapi.IN_QUERY, description="Document ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- TEMPLATE APIs ----------------

templates_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get templates",
    operation_description="Get all active lease templates.",
)


template_fields_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get template fields",
    operation_description="Get template fields, saved values, lease defaults, and generated PDF URL.",
    manual_parameters=[
        openapi.Parameter("template_id", openapi.IN_QUERY, description="Template ID", type=openapi.TYPE_INTEGER, required=True, example=1),
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


generate_contract_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Generate lease contract",
    operation_description="Generate lease contract PDF using template values.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["template_id", "lease_id", "values"],
        properties={
            "template_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Template ID", example=1),
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "values": openapi.Schema(
                type=openapi.TYPE_OBJECT,
                description="Template field values",
                example={
                    "tenant_name": "Rahul Sharma",
                    "annual_rent": "60000",
                    "contract_start_date": "2026-06-01",
                    "contract_end_date": "2027-05-31"
                },
            ),
        },
    ),
)


# ---------------- EMAIL / NEGOTIATION / SIGNATURE REQUEST APIs ----------------

send_lease_invite_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease invite",
    operation_description="Send invite email to tenant for lease onboarding.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


send_negotiation_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease negotiation email",
    operation_description="Send negotiation email to tenant and owners.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


send_for_signature_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease for signature",
    operation_description="Send signature request email to tenant and owners.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)


# ---------------- LEASE APPROVAL OTP APIs ----------------

lease_approval_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease approval OTP",
    operation_description="Send OTP to owner or tenant for lease approval.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


lease_approval_verify_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Verify lease approval OTP",
    operation_description="Verify OTP and return lease approval details.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "otp"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "otp": openapi.Schema(type=openapi.TYPE_STRING, description="OTP received on email", example="123456"),
        },
    ),
)


approve_lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Approve lease",
    operation_description="Approve lease after OTP verification.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


# ---------------- LEASE SIGNATURE OTP APIs ----------------

lease_signature_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Send lease signature OTP",
    operation_description="Send OTP to owner or tenant for lease signature.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
        },
    ),
)


lease_signature_verify_otp_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Verify lease signature OTP",
    operation_description="Verify OTP and return lease PDF details for signing.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "otp"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "otp": openapi.Schema(type=openapi.TYPE_STRING, description="OTP received on email", example="123456"),
        },
    ),
)


submit_lease_signature_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Submit lease signature",
    operation_description="Submit base64 signature image and stamp it on lease PDF.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id", "role", "email", "signature_data"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "role": openapi.Schema(type=openapi.TYPE_STRING, description="User role", example="tenant"),
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Tenant or owner email", example="tenant@example.com"),
            "signature_data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 signature image", example="data:image/png;base64,iVBORw0KGgoAAAANSUhEUg..."),
        },
    ),
)


# ---------------- LEASE CHEQUE APIs ----------------

lease_cheque_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get lease cheques",
    operation_description="Get cheques by lease_id or get single cheque using cheque_id.",
    manual_parameters=[
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("cheque_id", openapi.IN_QUERY, description="Cheque ID", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


lease_cheque_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Create lease cheque",
    operation_description="Create cheque or transaction record for a lease.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
            "document_type_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Document type ID", example=1),
            "origin_bank_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Origin bank ID", example=1),
            "settlement_bank_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Settlement bank ID", example=2),
            "cheque_type": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque type", example="RENT_CHEQUE"),
            "payment_type": openapi.Schema(type=openapi.TYPE_STRING, description="Payment type", example="CHEQUE"),
            "cheque_number": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque number", example="CHQ123456"),
            "start_date": openapi.Schema(type=openapi.TYPE_STRING, description="Start date", example="2026-06-01"),
            "end_date": openapi.Schema(type=openapi.TYPE_STRING, description="End date", example="2026-08-31"),
            "cheque_date": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque date", example="2026-06-05"),
            "origin_account_number": openapi.Schema(type=openapi.TYPE_INTEGER, description="Origin account number", example=123456789),
            "settlement_account_number": openapi.Schema(type=openapi.TYPE_INTEGER, description="Settlement account number", example=987654321),
            "amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Cheque amount", example=15000),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Cheque file name", example="cheque.jpg"),
            "file_data": openapi.Schema(type=openapi.TYPE_STRING, description="Base64 cheque file data", example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."),
        },
    ),
)


lease_cheque_put = swagger_auto_schema(
    method="put",
    tags=LEASE_TAG,
    operation_summary="Update lease cheque",
    operation_description="Update cheque details using cheque_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["cheque_id"],
        properties={
            "cheque_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Cheque ID", example=1),
            "cheque_type": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque type", example="RENT_CHEQUE"),
            "payment_type": openapi.Schema(type=openapi.TYPE_STRING, description="Updated payment type", example="CHEQUE"),
            "cheque_number": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque number", example="CHQ987654"),
            "amount": openapi.Schema(type=openapi.TYPE_NUMBER, description="Updated amount", example=16000),
            "status": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque status", example="REALIZED"),
            "cheque_date": openapi.Schema(type=openapi.TYPE_STRING, description="Updated cheque date", example="2026-06-10"),
            "file_name": openapi.Schema(type=openapi.TYPE_STRING, description="Updated file name", example="updated_cheque.jpg"),
            "file_data": openapi.Schema(type=openapi.TYPE_STRING, description="Updated base64 file data", example="data:image/jpeg;base64,/9j/4AAQSkZJRgABAQ..."),
        },
    ),
)


lease_cheque_delete = swagger_auto_schema(
    method="delete",
    tags=LEASE_TAG,
    operation_summary="Delete lease cheque",
    operation_description="Delete cheque using cheque_id.",
    manual_parameters=[
        openapi.Parameter("cheque_id", openapi.IN_QUERY, description="Cheque ID", type=openapi.TYPE_INTEGER, required=True, example=1),
    ],
)


# ---------------- CHEQUE DASHBOARD / ANALYTICS APIs ----------------

cheque_summary_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get cheque summary",
    operation_description="Get cheque counts and amount summary grouped by status.",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
    ],
)


all_cheques_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get all cheques",
    operation_description="Get all cheques with pagination, search, and filters.",
    manual_parameters=[
        openapi.Parameter("page", openapi.IN_QUERY, description="Page number", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, description="Records per page", type=openapi.TYPE_INTEGER, required=False, example=10),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search by cheque, unit, tenant, or property", type=openapi.TYPE_STRING, required=False, example="CHQ123456"),
        openapi.Parameter("status", openapi.IN_QUERY, description="Cheque status filter", type=openapi.TYPE_STRING, required=False, example="REALIZED"),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
    ],
)


cheque_monthly_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get monthly cheque analytics",
    operation_description="Get monthly cheque amount analytics for selected year.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


rent_analytics_get = swagger_auto_schema(
    method="get",
    tags=LEASE_TAG,
    operation_summary="Get rent analytics",
    operation_description="Get rent analytics with received, pending, bounced, and total amount data.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("lease_id", openapi.IN_QUERY, description="Lease ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("unit_id", openapi.IN_QUERY, description="Unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)


# ---------------- ACTIVATE LEASE API ----------------

activate_lease_post = swagger_auto_schema(
    method="post",
    tags=LEASE_TAG,
    operation_summary="Activate lease",
    operation_description="Activate a lease using lease_id.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["lease_id"],
        properties={
            "lease_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Lease ID", example=1),
        },
    ),
)