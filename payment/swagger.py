# Import Swagger tools
from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


PAYMENT_TAG = ["Payment"]


# ---------------- PAYMENT APIs ----------------
# These decorators are used for payment app APIs.


# GET /payment/access-rental-account
# Get lease/rental account details. If lease_id is passed, returns only that lease.
access_rental_account_get = swagger_auto_schema(
    method="get",
    tags=PAYMENT_TAG,
    operation_summary="Access rental account",
    operation_description="Get rental account lease details. Pass lease_id to get details for a specific lease.",
    manual_parameters=[
        openapi.Parameter(
            "lease_id",
            openapi.IN_QUERY,
            description="Lease ID to filter rental account details",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=1,
        ),
    ],
)


# GET /payment/owner-rent-amounts
# Get owner-side rent amount list with pagination.
owner_rent_amounts_get = swagger_auto_schema(
    method="get",
    tags=PAYMENT_TAG,
    operation_summary="Get owner rent amounts",
    operation_description="Get rent amount details for leases connected to the logged-in owner.",
    manual_parameters=[
        openapi.Parameter(
            "page",
            openapi.IN_QUERY,
            description="Page number",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=1,
        ),
        openapi.Parameter(
            "limit",
            openapi.IN_QUERY,
            description="Number of records per page",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=10,
        ),
    ],
)


# GET /payment/rental-payments
# Get rental payment transactions created by logged-in user.
rental_payments_get = swagger_auto_schema(
    method="get",
    tags=PAYMENT_TAG,
    operation_summary="Get rental payments",
    operation_description="Get rental payment transaction list. Pass lease_id to filter payments for a specific lease.",
    manual_parameters=[
        openapi.Parameter(
            "lease_id",
            openapi.IN_QUERY,
            description="Lease ID to filter rental payments",
            type=openapi.TYPE_INTEGER,
            required=False,
            example=1,
        ),
    ],
)