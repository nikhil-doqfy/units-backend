from drf_yasg import openapi
from drf_yasg.utils import swagger_auto_schema


PROPERTY_MANAGEMENT_TAG = ["Property Management"]


# ---------------- OPTIONS / DROPDOWN API ----------------

options_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Get dropdown options",
    operation_description="Get dropdown data using option_type. Multiple option types can be passed comma-separated.",
    manual_parameters=[
        openapi.Parameter("option_type", openapi.IN_QUERY, description="Option type like COUNTRY, STATE, CITY, PROPERTY_TYPE, TENANTS, LEASE_STATUS, PAYMENT_METHOD", type=openapi.TYPE_STRING, required=True, example="COUNTRY,STATE,CITY"),
        openapi.Parameter("country_id", openapi.IN_QUERY, description="Country ID, required for STATE", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("state_id", openapi.IN_QUERY, description="State ID, required for CITY", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID for property related options", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("block_id", openapi.IN_QUERY, description="Block ID for unit by block option", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("parent_property_id", openapi.IN_QUERY, description="Parent property ID for lease related unit options", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("tenant_status", openapi.IN_QUERY, description="Tenant status filter", type=openapi.TYPE_STRING, required=False, example="APPROVED"),
    ],
)


# ---------------- INVITATION API ----------------

send_invitation_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Send invitation",
    operation_description="Send invitation from owner to PMC, PMC to owner, or PMC to tenant.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["email", "invitation_type", "property_unit_id"],
        properties={
            "email": openapi.Schema(type=openapi.TYPE_STRING, description="Invitation receiver email", example="owner@example.com"),
            "invitation_type": openapi.Schema(type=openapi.TYPE_STRING, description="Invitation type", example="PMC_TO_OWNER"),
            "property_unit_id": openapi.Schema(type=openapi.TYPE_INTEGER, description="Property unit ID", example=1),
        },
    ),
)


# ---------------- DASHBOARD APIs ----------------

dashboard_overview_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Dashboard overview",
    operation_description="Get overview dashboard data like total units, rented units, vacant units, active leads, and complaints.",
)

dashboard_occupancy_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Dashboard occupancy",
    operation_description="Get occupancy data and top properties by occupancy.",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)

dashboard_top_revenue_properties_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Top revenue properties",
    operation_description="Get top revenue properties based on realized lease transactions.",
)

dashboard_monthly_revenue_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Monthly revenue dashboard",
    operation_description="Get monthly revenue data for selected year or date range.",
    manual_parameters=[
        openapi.Parameter("city_id", openapi.IN_QUERY, description="City ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_unit_id", openapi.IN_QUERY, description="Property unit ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("from_date", openapi.IN_QUERY, description="From date in epoch milliseconds", type=openapi.TYPE_INTEGER, required=False, example=1735689600000),
        openapi.Parameter("to_date", openapi.IN_QUERY, description="To date in epoch milliseconds", type=openapi.TYPE_INTEGER, required=False, example=1767225599000),
        openapi.Parameter("year", openapi.IN_QUERY, description="Year filter", type=openapi.TYPE_INTEGER, required=False, example=2026),
    ],
)

dashboard_cheque_visibility_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Cheque visibility dashboard",
    operation_description="Get cheque visibility list with filters.",
    manual_parameters=[
        openapi.Parameter("city_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("property_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("cheque_status", openapi.IN_QUERY, type=openapi.TYPE_STRING, required=False, example="REALIZED"),
        openapi.Parameter("from_date", openapi.IN_QUERY, description="From date in epoch milliseconds", type=openapi.TYPE_INTEGER, required=False, example=1735689600000),
        openapi.Parameter("to_date", openapi.IN_QUERY, description="To date in epoch milliseconds", type=openapi.TYPE_INTEGER, required=False, example=1767225599000),
    ],
)

dashboard_cheque_aging_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Cheque aging dashboard",
    operation_description="Get cheque aging breakup for bounced cheques.",
    manual_parameters=[
        openapi.Parameter("property_id", openapi.IN_QUERY, description="Property ID filter", type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)

dashboard_other_type_payments_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Other payment type dashboard",
    operation_description="Get monthly payment breakup by payment type.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("property_unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)

dashboard_yearly_dues_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Yearly dues dashboard",
    operation_description="Get yearly total, received, and due amount with monthly breakup.",
    manual_parameters=[
        openapi.Parameter("year", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=2026),
        openapi.Parameter("property_unit_id", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
    ],
)

dashboard_property_owned_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Property owned dashboard",
    operation_description="Get property owned summary with rented and vacant units.",
    manual_parameters=[
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("limit", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=5),
    ],
)


# ---------------- DASHBOARD VISUALIZATION ----------------

dashboard_visualization_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Get dashboard visualization preferences",
    operation_description="Get all dashboard visualization settings for logged-in user.",
)

dashboard_visualization_post = swagger_auto_schema(
    method="post",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Save dashboard visualization preferences",
    operation_description="Save selected visible dashboard visualization keys.",
    request_body=openapi.Schema(
        type=openapi.TYPE_OBJECT,
        required=["visualization"],
        properties={
            "visualization": openapi.Schema(
                type=openapi.TYPE_ARRAY,
                description="List of selected dashboard keys",
                items=openapi.Schema(type=openapi.TYPE_STRING),
                example=["DASH_OVERVIEW", "OCCUPANCY", "MONTHLY_REVENUE"],
            ),
        },
    ),
)


# ---------------- FAQ API ----------------

faq_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Get FAQs",
    operation_description="Get all FAQ records.",
)


# ---------------- AUDIT LOG API ----------------

audit_log_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Get audit logs",
    operation_description="Get audit logs with filters, pagination, and CSV export.",
    manual_parameters=[
        openapi.Parameter("user_id", openapi.IN_QUERY, description="Filter by user profile ID", type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("search", openapi.IN_QUERY, description="Search in message, action type, or user name", type=openapi.TYPE_STRING, required=False, example="created"),
        openapi.Parameter("time_range", openapi.IN_QUERY, description="today, 7days, or 30days", type=openapi.TYPE_STRING, required=False, example="7days"),
        openapi.Parameter("page", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=1),
        openapi.Parameter("page_size", openapi.IN_QUERY, type=openapi.TYPE_INTEGER, required=False, example=20),
        openapi.Parameter("export", openapi.IN_QUERY, description="Use true to export CSV", type=openapi.TYPE_STRING, required=False, example="true"),
    ],
)


# ---------------- GLOBAL SEARCH API ----------------

global_search_get = swagger_auto_schema(
    method="get",
    tags=PROPERTY_MANAGEMENT_TAG,
    operation_summary="Global search",
    operation_description="Search properties, units, owners, and tenants.",
    manual_parameters=[
        openapi.Parameter("search", openapi.IN_QUERY, description="Search text. Minimum 2 characters.", type=openapi.TYPE_STRING, required=True, example="rahul"),
    ],
)