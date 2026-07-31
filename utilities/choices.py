# ── User Roles ─────────────────────────────────────────────────────────────────
OWNER            = "OWNER"
COMPANY_USER     = "COMPANY_USER"
TENANT           = "TENANT"
PROPERTY_MANAGER = "PROPERTY_MANAGER"
STAFF            = "STAFF"
PROPERTY         = "PROPERTY"
UNIT             = "UNIT"
LEASE_CHEQUE     = "LEASE_CHEQUE"

# ── Invitation / Management ────────────────────────────────────────────────────
MOBILE_VERIFICATION = "MOBILE_VERIFICATION"
EMAIL_VERIFICATION  = "EMAIL_VERIFICATION"
RESET_PASSWORD      = "reset_password"
LOGIN               = "login"
SIGNUP              = "signup"
COMPANY             = "Company"
AVAILABLE           = "AVAILABLE"
NOT_AVAILABLE       = "NOT_AVAILABLE"

MANAGEMENT_CHOICES = [("MYSELF", "Myself"), ("PMC", "PMC")]

# ── Status Flags ───────────────────────────────────────────────────────────────
ACTIVE    = "ACTIVE"
PENDING   = "PENDING"
APPROVED  = "APPROVED"
REJECTED  = "REJECTED"
SCHEDULED = "SCHEDULED"

# ── Approval / Document Status ─────────────────────────────────────────────────
DOCUMENTS_STATUS_CHOICES = (
    ("PENDING",  "Pending"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
)

APPROVAL_STATUS_CHOICES = (
    ("PENDING",  "Pending"),
    ("APPROVED", "Approved"),
    ("REJECTED", "Rejected"),
)

INVITATION_STATUS_CHOICES = (
    ("pending",  "Pending"),
    ("accepted", "Accepted"),
    ("rejected", "Rejected"),
)

# ── Lease Status ───────────────────────────────────────────────────────────────
LEASE_STATUS_CHOICES = [
    ("DRAFT",    "Draft"),
    ("ACTIVE",   "Active"),
    ("INACTIVE", "Inactive"),
    ("EXPIRED",  "Expired"),
    ("REJECTED", "Rejected"),
]

# ── Lease Onboarding Stages ────────────────────────────────────────────────────
INVITE             = "INVITE"
WAITING_FOR_SIGNUP = "WAITING_FOR_SIGNUP"
ONBOARDING         = "ONBOARDING"
NEGOTIATION_SENT   = "NEGOTIATION_SENT"
PENDING_APPROVAL   = "PENDING_APPROVAL"
OWNER_APPROVED     = "OWNER_APPROVED"
TENANT_APPROVED    = "TENANT_APPROVED"
WAITING_CHEQUE     = "WAITING_CHEQUE"
CHEQUE_REQUESTED   = "CHEQUE_REQUESTED"
CHEQUE_COLLECTED   = "CHEQUE_COLLECTED"
CHEQUE_VERIFIED    = "CHEQUE_VERIFIED"
AGREEMENT          = "AGREEMENT"
AGREEMENT_SIGNING  = "AGREEMENT_SIGNING"
AGREEMENT_SIGNED   = "AGREEMENT_SIGNED"
EJARI              = "EJARI"
EJARI_DOCUMENT_UPLOAD = "EJARI_DOCUMENT_UPLOAD"
EJARI_SIGNING      = "EJARI_SIGNING"
ACTIVATED          = "ACTIVATED"

BASIC_DETAILS               = "BASIC_DETAILS"
COMMERCIAL_DETAILS          = "COMMERCIAL_DETAILS"
MANAGER_APPROVAL_REQUIRED   = "MANAGER_APPROVAL_REQUIRED"
MANAGER_APPROVED            = "MANAGER_APPROVED"

LEASE_STAGE_CHOICES = (
    (BASIC_DETAILS,             "Basic Details"),
    (COMMERCIAL_DETAILS,        "Commercial Details"),
    (MANAGER_APPROVAL_REQUIRED, "Manager Approval Required"),
    (MANAGER_APPROVED,          "Manager Approved"),
    (INVITE,                    "Invite"),
    (WAITING_FOR_SIGNUP,        "Waiting for Signup"),
    (ONBOARDING,                "Onboarding"),
    (NEGOTIATION_SENT,          "Negotiation Sent"),
    (OWNER_APPROVED,            "Owner Approved"),
    (TENANT_APPROVED,           "Tenant Approved"),
    (WAITING_CHEQUE,            "Waiting for Cheque"),
    (CHEQUE_REQUESTED,          "Cheque Requested"),
    (CHEQUE_COLLECTED,          "Cheque Collected"),
    (CHEQUE_VERIFIED,           "Cheque Verified"),
    (AGREEMENT,                 "Agreement"),
    (AGREEMENT_SIGNING,         "Agreement Signing"),
    (AGREEMENT_SIGNED,          "Agreement Signed"),
    (EJARI,                     "Ejari"),
    (EJARI_DOCUMENT_UPLOAD,     "Ejari Document Upload"),
    (EJARI_SIGNING,             "Ejari Signing"),
    (ACTIVATED,                 "Activated"),
)

# ── Cheque Types ───────────────────────────────────────────────────────────────
RENT_CHEQUE       = "RENT_CHEQUE"
ADDITIONAL_CHEQUE = "ADDITIONAL_CHEQUE"
OTHER_CHARGE      = "OTHER_CHARGE"

CHEQUE_TYPE_CHOICES = (
    (RENT_CHEQUE,       "Rent Cheque"),
    (ADDITIONAL_CHEQUE, "Additional Cheque"),
    (OTHER_CHARGE,      "Other Charge"),
)

# ── Cheque Status ──────────────────────────────────────────────────────────────
CHEQUE_STATUS_BALANCE  = "BALANCE"
CHEQUE_STATUS_CREDITED = "CREDITED"
CHEQUE_STATUS_REALIZED = "REALIZED"
CHEQUE_STATUS_BOUNCED  = "BOUNCED"

CHEQUE_STATUS_CHOICES = (
    (CHEQUE_STATUS_BALANCE,  "Balance"),
    (CHEQUE_STATUS_CREDITED, "Credited"),
    (CHEQUE_STATUS_REALIZED, "Realized"),
    (CHEQUE_STATUS_BOUNCED,  "Bounced"),
)

# ── Payment Type ───────────────────────────────────────────────────────────────
PAYMENT_TYPE_CHEQUE        = "CHEQUE"
PAYMENT_TYPE_CASH          = "CASH"
PAYMENT_TYPE_BANK_TRANSFER = "BANK_TRANSFER"
PAYMENT_TYPE_PDC           = "PDC"

PAYMENT_TYPE_CHOICES = (
    (PAYMENT_TYPE_CHEQUE,        "Cheque"),
    (PAYMENT_TYPE_CASH,          "Cash"),
    (PAYMENT_TYPE_BANK_TRANSFER, "Bank Transfer"),
    (PAYMENT_TYPE_PDC,           "PDC"),
)

# ── Payment Method ─────────────────────────────────────────────────────────────
CASH         = "CASH"
CHEQUE       = "CHEQUE"
RENT         = "RENT"
OTHER        = "OTHER"
CREDIT_CARD  = "CREDIT_CARD"
DEBIT_CARD   = "DEBIT_CARD"
NET_BANKING  = "NET_BANKING"

PAYMENT_PENDING    = "PAYMENT_PENDING"
PAYMENT_SUCCESSFUL = "PAYMENT_SUCCESSFUL"
PAYMENT_FAILED     = "PAYMENT_FAILED"
PAYMENT_BOUNCED    = "PAYMENT_BOUNCED"

# ── Property Type ──────────────────────────────────────────────────────────────
APARTMENT  = "APARTMENT"
VILLA      = "VILLA"
TOWNHOUSE  = "TOWNHOUSE"
PENTHOUSE  = "PENTHOUSE"
STUDIO     = "STUDIO"
OFFICE     = "OFFICE"
SHOP       = "SHOP"
WAREHOUSE  = "WAREHOUSE"

PROPERTY_TYPE_CHOICES = (
    (APARTMENT,  "Apartment"),
    (VILLA,      "Villa"),
    (TOWNHOUSE,  "Townhouse"),
    (PENTHOUSE,  "Penthouse"),
    (STUDIO,     "Studio"),
    (OFFICE,     "Office"),
    (SHOP,       "Shop"),
    (WAREHOUSE,  "Warehouse"),
)

# ── Area Unit ──────────────────────────────────────────────────────────────────
SQ_FT = "SQ_FT"
SQ_MT = "SQ_MT"
SQ_YD = "SQ_YD"

AREA_UNIT_CHOICES = (
    (SQ_FT, "Sq ft"),
    (SQ_MT, "Sq mt"),
    (SQ_YD, "Sq yd"),
)

# ── Unit Usage ─────────────────────────────────────────────────────────────────
RESIDENTIAL = "RESIDENTIAL"
COMMERCIAL  = "COMMERCIAL"
INDUSTRIAL  = "INDUSTRIAL"

UNIT_USAGE_CHOICES = (
    (RESIDENTIAL, "Residential"),
    (COMMERCIAL,  "Commercial"),
    (INDUSTRIAL,  "Industrial"),
)

# ── Unit Type ──────────────────────────────────────────────────────────────────
FLAT = "FLAT"

UNIT_TYPE_CHOICES = (
    (FLAT,      "Flat"),
    (APARTMENT, "Apartment"),
    (VILLA,     "Villa"),
    (STUDIO,    "Studio"),
)

# ── Occupancy ──────────────────────────────────────────────────────────────────
VACANT   = "VACANT"
OCCUPIED = "OCCUPIED"
ONGOING        = "ONGOING"
ABOUT_TO_EXPIRE = "ABOUT_TO_EXPIRE"
EXPIRED        = "EXPIRED"

# ── Numeric Choices ────────────────────────────────────────────────────────────
BLOCKS_CHOICES  = tuple((i, str(i)) for i in range(1, 21))
UNITS_CHOICES   = tuple((i, str(i)) for i in range(1, 101))
BEDROOM_CHOICES = tuple((i, str(i)) for i in range(1, 11))
FLOOR_CHOICES   = tuple((i, str(i)) for i in range(0, 51))
BALCONY_CHOICES = tuple((i, str(i)) for i in range(0, 11))
PARKING_CHOICES = tuple((i, str(i)) for i in range(0, 11))

# ── Property Step ──────────────────────────────────────────────────────────────
ADDRESS_DETAILS          = "ADDRESS_DETAILS"
FINANCIAL                = "FINANCIAL"
COMPLETED                = "COMPLETED"
COMMERCIALS_DETAILS      = "COMMERCIALS_DETAILS"
PROPERTY_IMAGES_DETAILS  = "PROPERTY_IMAGES_DETAILS"
DOCUMENTS_DETAILS        = "DOCUMENTS_DETAILS"

STEP_CHOICES = (
    (BASIC_DETAILS,          "Basic Details"),
    (COMMERCIALS_DETAILS,    "Commercial Details"),
    (PROPERTY_IMAGES_DETAILS,"Property Images"),
    (DOCUMENTS_DETAILS,      "Documents"),
)

PROPERTY_STEP_CHOICES = (
    (BASIC_DETAILS,   "Basic Details"),
    (ADDRESS_DETAILS, "Address Details"),
    (FINANCIAL,       "Financial"),
    (COMPLETED,       "Completed"),
)

LAYOUT_CHOICES = [
    ("AI_GENERATED",      "Create Layout by AI"),
    ("TEMPLATE_SELECTED", "Select Template"),
    ("TEMPLATE_UPLOADED", "Upload Template"),
]

# ── Property Document ──────────────────────────────────────────────────────────
FLOOR_PLAN        = "FLOOR_PLAN"
EJARI_CERTIFICATE = "EJARI_CERTIFICATE"
PMC_DOCUMENT      = "PMC_DOCUMENT"
CHEQUE_DOCUMENT   = "CHEQUE_DOCUMENT"
OWNER_DOCUMENT    = "OWNER_DOCUMENT"
TENANT_DOCUMENT   = "TENANT_DOCUMENT"

PROPERTY_DOCUMENT_CHOICES = (
    (FLOOR_PLAN,        "Floor Plan"),
    (EJARI_CERTIFICATE, "Ejari Certificate"),
    (PMC_DOCUMENT,      "PMC Document"),
    (CHEQUE_DOCUMENT,   "Cheque Document"),
)

LEASE_DOCUMENT_CHOICES = (
    (EJARI_CERTIFICATE, "Ejari Certificate"),
    (CHEQUE_DOCUMENT,   "Cheque Document"),
)

Ejari_DOCUMENT_CATEGORY_CHOICES = (
    ("EMIRATES_ID",      "Emirates ID"),
    ("PASSPORT_SELF",    "Passport (Self)"),
    ("PASSPORT_FAMILY",  "Passport (Family)"),
    ("EMPLOYMENT_PROOF", "Employment Proof"),
    ("VISA_SELF",        "Visa (Self)"),
    ("VISA_FAMILY",      "Visa (Family)"),
    ("BANK_STATEMENT",   "Bank Statement"),
)

IMAGE_TYPE_CHOICES = (
    ("INTERIOR", "Interior"),
    ("EXTERIOR", "Exterior"),
)

# ── Document Identity ──────────────────────────────────────────────────────────
EMIRATES_ID        = "emirates_id"
UAE_RESIDENCE_VISA = "uae_residence_visa"
DLD_CERTIFICATE    = "dld_certificate"

# ── Audit Actions ──────────────────────────────────────────────────────────────
CREATED   = "CREATED"
UPDATED   = "UPDATED"
SUBMITTED = "SUBMITTED"
DELETED   = "DELETED"

AUDIT_ACTION_CHOICES = (
    (CREATED,   "Created"),
    (UPDATED,   "Updated"),
    (SUBMITTED, "Submitted"),
    (DELETED,   "Deleted"),
)

# ── Template Field Types ───────────────────────────────────────────────────────
NUMBER   = "number"
DATE     = "date"
TEXT     = "text"
RADIO    = "radio"
CHOICE   = "choice"
CHECKBOX = "checkbox"

# ── Access Level ───────────────────────────────────────────────────────────────
VIEW_ONLY   = "VIEW_ONLY"
ADD         = "ADD"
MODIFIED    = "MODIFIED"
TERMINATED  = "TERMINATED"

ACCESS_LEVEL_CHOICES = [
    ("NO_ACCESS",   "No Access"),
    ("VIEW_ONLY",   "View Only"),
    ("FULL_ACCESS", "Full Access"),
]

# ── API Methods ────────────────────────────────────────────────────────────────
GET    = "GET"
POST   = "POST"
PUT    = "PUT"
PATCH  = "PATCH"
DELETE = "DELETE"
OPTION = "OPTION"

# ── Activity Log ───────────────────────────────────────────────────────────────
NOTE          = "NOTE"
CALL_LOG      = "CALL_LOG"
EMAIL_LOG     = "EMAIL_LOG"
MEETING       = "MEETING"
WHATSAPP_LOG  = "WHATSAPP_LOG"
STATUS_CHANGE = "STATUS_CHANGE"

ACTIVITY_TYPE_CHOICES = (
    (NOTE,          "Note"),
    (CALL_LOG,      "Call"),
    (EMAIL_LOG,     "Email"),
    (MEETING,       "Meeting"),
    (WHATSAPP_LOG,  "WhatsApp"),
    (STATUS_CHANGE, "Status Change"),
)

# ── Lead ───────────────────────────────────────────────────────────────────────
INTERESTED     = "INTERESTED"
NOT_INTERESTED = "NOT_INTERESTED"
LEASE_TENANCY  = "LEASE_TENANCY"

PROPERTY_FINDER = "PROPERTY_FINDER"
BAYUT           = "BAYUT"
DIRECT          = "DIRECT"
REFERRAL        = "REFERRAL"

EMAIL    = "EMAIL"
WHATSAPP = "WHATSAPP"
CALL     = "CALL"

LP = "LP"
VC = "VC"

PORTAL_PLATFORMS = [PROPERTY_FINDER, BAYUT]

LEAD_STATUS_CHOICES = (
    (INTERESTED,     "Interested"),
    (NOT_INTERESTED, "Not Interested"),
    (LEASE_TENANCY,  "Lease / Tenancy"),
)

PLATFORM_CHOICES = (
    (PROPERTY_FINDER, "Property Finder"),
    (BAYUT,           "Bayut"),
    (DIRECT,          "Direct"),
    (REFERRAL,        "Referral"),
)

LEAD_TYPE_CHOICES = (
    (EMAIL,    "Email"),
    (WHATSAPP, "WhatsApp"),
    (CALL,     "Call"),
)

# ── Complaint ──────────────────────────────────────────────────────────────────
ASSIGNED            = "ASSIGNED"
IN_PROGRESS         = "IN_PROGRESS"
RESOLVED            = "RESOLVED"
CLOSED              = "CLOSED"
REOPENED            = "REOPENED"
CANCELLED           = "CANCELLED"

COMPLAINT_STATUS_CHOICES = (
    (PENDING,    "Pending"),
    (ASSIGNED,   "Assigned"),
    (IN_PROGRESS,"In Progress"),
    (RESOLVED,   "Resolved"),
    (CLOSED,     "Closed"),
    (REOPENED,   "Reopened"),
    (CANCELLED,  "Cancelled"),
)

ASSIGNED_TIMELINE        = "ASSIGNED"
WORK_STARTED             = "WORK_STARTED"
WORK_COMPLETED           = "WORK_COMPLETED"
COMPLAINT_CLOSED         = "CLOSED"
ASSIGNED_TO_ENGINEER     = "ASSIGNED_TO_ENGINEER"
ASSIGNED_ENGINEER        = "ASSIGNED_ENGINEER"

COMPLAINT_TIMELINE_STATUS_CHOICES = (
    (CREATED,           "Complaint Created"),
    (ASSIGNED_TIMELINE, "Complaint Assigned"),
    (WORK_STARTED,      "Work Started"),
    (WORK_COMPLETED,    "Work Completed"),
    (COMPLAINT_CLOSED,  "Complaint Closed"),
)

LOW    = "LOW"
MEDIUM = "MEDIUM"
HIGH   = "HIGH"
URGENT = "URGENT"

COMPLAINT_PRIORITY_CHOICES = (
    (LOW,    "Low"),
    (MEDIUM, "Medium"),
    (HIGH,   "High"),
    (URGENT, "Urgent"),
)

# ── Service Provider Types ─────────────────────────────────────────────────────
AC_TECH       = "AC_TECH"
PLUMBER       = "PLUMBER"
ELECTRICIAN   = "ELECTRICIAN"
CARPENTER     = "CARPENTER"
CLEANING      = "CLEANING"
INTERNET_TECH = "INTERNET_TECH"
LIFT_TECH     = "LIFT_TECH"
PAINTER       = "PAINTER"
GARDENER      = "GARDENER"
SECURITY      = "SECURITY"
PEST_CONTROL  = "PEST_CONTROL"

SERVICE_TYPE_CHOICES = (
    (AC_TECH,       "AC Technician"),
    (PLUMBER,       "Plumber"),
    (ELECTRICIAN,   "Electrician"),
    (CARPENTER,     "Carpenter"),
    (CLEANING,      "Cleaning"),
    (INTERNET_TECH, "Internet Technician"),
    (LIFT_TECH,     "Lift Technician"),
    (PAINTER,       "Painter"),
    (GARDENER,      "Gardener"),
    (SECURITY,      "Security"),
    (PEST_CONTROL,  "Pest Control"),
    (OTHER,         "Other"),
)

# ── Appointment Status ─────────────────────────────────────────────────────────
APPOINTMENT_PROPOSED    = "PROPOSED"
APPOINTMENT_APPROVED    = "APPROVED"
APPOINTMENT_RESCHEDULED = "RESCHEDULED"
APPOINTMENT_CONFIRMED   = "CONFIRMED"
APPOINTMENT_DECLINED    = "DECLINED"
APPOINTMENT_FINALIZED   = "FINALIZED"

APPOINTMENT_STATUS_CHOICES = (
    (APPOINTMENT_PROPOSED,    "Proposed"),
    (APPOINTMENT_APPROVED,    "Approved"),
    (APPOINTMENT_RESCHEDULED, "Rescheduled"),
    (APPOINTMENT_CONFIRMED,   "Confirmed"),
    (APPOINTMENT_DECLINED,    "Declined"),
    (APPOINTMENT_FINALIZED,   "Finalized"),
)

# ── Agreement Status ───────────────────────────────────────────────────────────
AGREEMENT_STATUS_CHOICES = (
    ("ACTIVE",        "Active"),
    ("EXPIRED",       "Expired"),
    ("EXPIRING_SOON", "Expiring Soon"),
    ("DRAFT",         "Draft"),
    ("TERMINATED",    "Terminated"),
)

# ── Notification Types ─────────────────────────────────────────────────────────
NOTIFICATION_TYPE_CHOICES = (
    ("PAYMENT_REMINDER", "Payment Reminder"),
    ("PAYMENT_SUCCESS",  "Payment Success"),
    ("CHEQUE_BOUNCED",   "Cheque Bounced"),
    ("CHEQUE_REALIZED",  "Cheque Realized"),
    ("LEASE_EXPIRY",     "Lease Expiry"),
    ("DOCUMENT_EXPIRY",  "Document Expiry"),
    ("COMPLAINT",        "Complaint"),
    ("ACCOUNT_ACTIVITY", "Account Activity"),
    ("GLOBAL",           "Global"),
    ("GENERAL",          "General"),
)

# ── Dashboard ──────────────────────────────────────────────────────────────────
DASH_OVERVIEW             = "OVERVIEW"
OCCUPANCY                 = "OCCUPANCY"
TOP_REVENUE_PROPERTIES    = "TOP_REVENUE_PROPERTIES"
DASH_MONTHLY_REVENUE      = "MONTHLY_REVENUE"
DASH_CHEQUE_VISIBILITY    = "CHEQUE_VISIBILITY"
DASH_CHEQUE_AGING         = "CHEQUE_AGING"
DASH_OTHER_TYPE_PAYMENTS  = "OTHER_TYPE_PAYMENTS"
DASH_YEARLY_DUES          = "YEARLY_DUES"
DASH_PROPERTY_OWNED       = "PROPERTY_OWNED"

DASHBOARD_CHOICES = [
    (DASH_OVERVIEW,            "Overview"),
    (OCCUPANCY,                "Occupancy"),
    (TOP_REVENUE_PROPERTIES,   "Most Revenue Generating Properties"),
    (DASH_MONTHLY_REVENUE,     "Monthly Revenue"),
    (DASH_CHEQUE_VISIBILITY,   "Cheque Visibility"),
    (DASH_CHEQUE_AGING,        "Cheque Aging"),
    (DASH_OTHER_TYPE_PAYMENTS, "Other Type Payments"),
    (DASH_YEARLY_DUES,         "Yearly Dues"),
    (DASH_PROPERTY_OWNED,      "Property Owned"),
]

# ── Permissions ────────────────────────────────────────────────────────────────
PERM_PROPERTIES          = "Properties"
PERM_LEAD                = "Lead"
PERM_TENANT              = "Tenant"
PERM_OWNER               = "Owner"
PERM_CHEQUE              = "Cheque"
PERM_RENTAL_PORTFOLIO    = "Rental Portfolio"
PERM_APPROVAL            = "Approval"
PERM_COMPLAINTS          = "Complaints"
PERM_BROADCAST           = "Broadcast"
PERM_USERS               = "Users"
PERM_TEAM                = "Team"
PERM_ROLES_AND_PERMISSION = "Roles and Permission"

PERMISSION_MODULE_CHOICES = [
    (PERM_PROPERTIES,           "Properties"),
    (PERM_LEAD,                 "Lead"),
    (PERM_TENANT,               "Tenant"),
    (PERM_OWNER,                "Owner"),
    (PERM_CHEQUE,               "Cheque"),
    (PERM_RENTAL_PORTFOLIO,     "Rental Portfolio"),
    (PERM_APPROVAL,             "Approval"),
    (PERM_COMPLAINTS,           "Complaints"),
    (PERM_BROADCAST,            "Broadcast"),
    (PERM_USERS,                "Users"),
    (PERM_TEAM,                 "Team"),
    (PERM_ROLES_AND_PERMISSION, "Roles and Permission"),
]

DEFAULT_PERMISSIONS = {
    "Property Management": {
        "View Property": False,
        "Add Property":  False,
        "Edit Property": False,
    },
    "Tenant Management": {
        "View Tenant":   False,
        "Invite Tenant": False,
    },
    "Owner Management": {
        "View Owner":   False,
        "Invite Owner": False,
    },
    "Staff Management": {
        "View Staff": False,
        "Add Staff":  False,
        "Edit Staff": False,
    },
    "Role Manager": {
        "View Roles": False,
        "Add Role":   False,
        "Edit Role":  False,
    },
}

# ── Timezone ───────────────────────────────────────────────────────────────────
TIMEZONE_CHOICES = (
    ("UTC",  "UTC"),
    ("GMT",  "GMT"),
    ("EST",  "EST"),
    ("CST",  "CST"),
    ("MST",  "MST"),
    ("PST",  "PST"),
    ("IST",  "IST"),
    ("CET",  "CET"),
    ("EET",  "EET"),
    ("JST",  "JST"),
    ("AEST", "AEST"),
)

# ── Rental Availability ────────────────────────────────────────────────────────
RENTAL_AVAILABLE     = "Available"
RENTAL_NOT_AVAILABLE = "Not Available"

# ── Config ─────────────────────────────────────────────────────────────────────
JWT_TOKEN_EXPIRY_MINUTES = 60
OTP_EXPIRY_MINUTES       = 5
