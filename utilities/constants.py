USER_NOT_ACTIVE = "User not active"
PASSWORD_EXPIRED = "Password has expired.Please contact Admin"
USER_NOT_ONBOARDED = "User not onboarded"
INVALID_EMAIL = "Invalid email address"
INCORRECT_OTP = "Incorrect OTP"
OTP_SUCCESS = "OTP successfully verified"
OTP_EXPIRED = "OTP has expired"
USER_DOES_NOT_EXIST = "User does not exist" 
INVALID_USERNAME_OR_PASSWORD = "Invalid username or password"
LOGIN_SUCCESSFUL ="Login successful"
INVALID_REQUEST = "Invalid request method"
INVALID_PARAMETER = "Only one parameter is allowed mobile number or email"
USER_DOES_NOT_EXIST = "User does not exist" 
OTP_GENERATED = "OTP generated successfully (Expire in 1 min)"
BAD_REQUEST = "Bad Request"
PASSWORD_MISMATCH = "Password does not match"
PASSWORD_CHANGE_SUCCESSFULL = "Password changed successfully"
INVALID_REQUEST_METHOD = "Invalid request method"
INVALID_TOKEN = "Invalid Token"
LOGOUT_SUCCESSFULL = "Logout Successfull"
ONLY_EMAIL_OR_CONTACT_NUMBER_ALLOWED = "Only 'email' or 'contact number' is allowed"
EMAIL_OR_CONTACT_NUMBER_REQUIRED = "'Email' or 'Contact number' is required"
MULTIPLE_USER_FOUND_ERROR = "Multiple user found  please contact Optiex"
INVALID_OTP = " Invalid OTP" 
FIELD_REQUIRED = "field is required."
PASSWORDS_DO_NOT_MATCH = "Passwords do not match."
EMAIL_ALREADY_REGISTERED = "Email already registered."
USER_REGISTERED_SUCCESSFULLY = "User registered successfully."
OTP_GENERATED_SUCCESSFULLY = "OTP sent successfully.",
ACCESS_DENIED_FOR_STAFF = "Access denied. Only Property Managers and authorized Staff can create staff accounts."
STAFF_DETAILS_NOT_FOUND = "Staff details not found for the current user."
STAFF_ROLE_NOT_FOUND = "Staff role not found for the current user's staff details."
STAFF_USER_NOT_PROPERTY_MANAGER = "Staff user is not associated with any property manager"
PROPERTY_MANAGER_DETAILS_NOT_FOUND = "Property Manager details not found for the authenticated user."
STAFF_USER_CREATED_SUCCESS = "Staff user created successfully."
INVALID_CREDENTIALS = "Invalid credentials"
FIELD_REQUIRED = "Required fields are missing"
LOGIN_NOT_ALLOWED = "Login not allowed"
LOGIN_SUCCESSFUL = "Login successful"
MOBILE_VERIFICATION = "MOBILE_VERIFICATION"
EMAIL_VERIFICATION = "EMAIL_VERIFICATION"
ONLY_POST_METHOD_ALLOWED = "Only POST method allowed."
INVALID_JSON_BODY = "Invalid JSON body."
MISSING_FIELDS = "Missing fields in document."
AN_ERROR_OCCURRED = "An error occurred."
ONLY_POST_REQUEST_ALLOWED = "Only POST requests are allowed."
ACCESS_DENIED_OWNER_ONLY = "Access denied. Only owners can access this resource."
INVALID_OPTION = "Invalid option. Choose either 'manual' or 'pmc'."
STAFF_CREATION_FAILED = "Failed to create staff details."
STAFF_CREATION_SUCCESS = "Staff user created successfully."
OWNER_DETAILS_NOT_FOUND = "Owner details not found for this user."
OWNER_DETAILS_ALREADY_EXISTS = "Owner details already exist for this user."
OWNER_DETAILS_SAVE_FAILED = "Failed to save owner details."
OWNER_DETAILS_SAVE_SUCCESS = "Owner details saved successfully."
DOCUMENTS_FETCH_SUCCESS = "Documents fetched successfully."
DOCUMENTS_FETCH_FAILED = "Failed to fetch documents."
DOCUMENTS_UPLOAD_SUCCESS = "Documents uploaded successfully."
ALL_DOCUMENTS_REQUIRED = "All 4 documents are required."
MANAGEMENT_OPTION_UPDATED_SUCCESS = "Management option updated successfully."
INTERNAL_SERVER_ERROR = "Internal Server Error."
UNEXPECTED_ERROR = "Unexpected error."
METHOD_NOT_ALLOWED = "Method not allowed."
OAUTH_TOKEN_REQUIRED = "OAuth token is required."
OWNER_DETAILS_SAVED_SUCCESS = "Owner details saved successfully."
OWNER_DETAILS_SAVE_FAILED = "Failed to save owner details."
DOCUMENTS_ALREADY_UPLOADED = "Documents are already uploaded for this user."
EMAIL_AND_OTP_REQUIRED = "Email and OTP required."
INVALID_OTP = "Invalid OTP."
OTP_EXPIRED = "OTP expired."
OTP_VERIFIED_SUCCESS = "OTP verified successfully."
OTP_SEND_SUCCESS = "OTP sent successfully."
OTP_SEND_FAILED = "Failed to send OTP email."
USER_NOT_FOUND = "User with this email does not exist."
EMAIL_OTP_PASSWORD_REQUIRED = "Email, otp, password, and confirm_password are required."
PASSWORD_MISMATCH = "Password and confirm password do not match."
WEAK_PASSWORD = "Weak password. Must contain upper, lower, number, and special char."
PASSWORD_RESET_SUCCESS = "Password reset successfully."
LOGOUT_SUCCESS = "Logout successful."
OWNER_DETAILS_SAVE_FAILED = "Failed to save owner details: {error}"
ONLY_GET_REQUEST_ALLOWED = "Only GET requests are allowed."
AUTH_HEADER_MISSING = "Authorization header missing."
INVALID_TOKEN_PAYLOAD = "Invalid token payload."
USER_NOT_FOUND = "User not found."
AUTHENTICATION_FAILED = "Authentication failed."
ACCESS_DENIED_TENANTS_ONLY="Access denied. Only tenants can submit or edit details."
TENANT_DETAILS_ALREADY_EXISTS="Tenant details already exist for this user."
TENANT_DETAILS_SAVED_SUCCESS="Tenant details saved successfully."
TENANT_DETAILS_NOT_FOUND="Tenant details not found for the authenticated user."
TENANT_DETAILS_UPDATED_SUCCESSFULLY="Tenant details updated successfully."
ACCESS_DENIED_TENANTS_ONLY_UPLOAD_DOC="Access denied. Only tenants can upload documents."
DOCUMENTS_UPLOAD_SUCCESS="Documents uploaded successfully."
NO_NEW_DOC_PROVIDED="No new documents provided for update."
TENANT_DETAILS_FETCHED_SUCCESS="Tenant details fetched successfully."
PROPERTY_MANAGER_Details_NOT_FOUND="Property Manager details not found."
ACCESS_DENIED_PROPERTY_MANAGER = "Access denied. Only property managers can submit details."
PROPERTY_MANAGER_DETAILS_EXISTS = "Property Manager details already exist."
PROPERTY_MANAGER_DETAILS_SAVED = "Property Manager details saved successfully."
ALL_THREE_DOCUMENTS_REQUIRED = "All three documents (Emirates ID, Trade License, RERA License) are required."
ACCESS_DENIED_PROPERTY_MANAGER_UPLOAD = "Access denied. Only property managers can upload documents."
PROPERTY_MANAGER_DETAILS_UPDATED = "Property Manager details updated successfully."
PROPERTY_MANAGER_DETAILS_FETCHED = "Property Manager details fetched successfully."

PROPERTY_LIST_FETCHED = "Property details list fetched successfully."
PROPERTY_NOT_FOUND = "Property details not found."
PROPERTY_DELETED = "Property detail deleted successfully."
PROPERTY_UPDATE_SUCCESS = "Property details updated successfully."
PROPERTY_ADDED = "Property added successfully."
TENANT_LIST_FETCHED_SUCCES="Tenant list fetched successfully"
PROPERTY_ID_REQUIRED="Property ID is required in query params (e.g. ?id=5)"
DATA_NOT_FOUND='data not found'
PROPERTY_MANAGER_LIST_FETCHED="property manager list fetch successfully"
OWNER_LIST_FETCHED_SUCCESS="owner list fetch successfully"

OWNER = "OWNER"
PROPERTY_MANAGER = "PROPERTY_MANAGER"
TENANT = "TENANT"
STAFF = "STAFF"
AVAILABLE="AVAILABLE"
NOT_AVAILABLE="NOT_AVAILABLE"


LEASE_STATUS_CHOICES = [
    ("DRAFT", "Draft"),
    ("ACTIVE", "Active"),
    ("INACTIVE", "In Active"),
    ("EXPIRED", "Expired"),
]

LAYOUT_CHOICES = [
        ("AI_GENERATED", "Create Layout by AI"),
        ("TEMPLATE_SELECTED", "Select Template"),
        ("TEMPLATE_UPLOADED", "Upload Template"),
    ]

DEFAULT_PERMISSIONS = {
    "Property Management": {
        "View Property": False,
        "Add Property": False,
        "Edit Property": False,
    },
    "Tenant Management": {
        "View Tenant": False,
        "Invite Tenant": False,
    },
    "Owner Management": {
        "View Owner": False,
        "Invite Owner": False,
    },
    "Staff Management": {
        "View Staff": False,
        "Add Staff": False,
        "Edit Staff": False,
    },
    "Role Manager": {
        "View Roles": False,
        "Add Role": False,
        "Edit Role": False,
    },
}




JWT_TOKEN_EXPIRY_MINUTES = 60
OTP_EXPIRY_MINUTES = 5 