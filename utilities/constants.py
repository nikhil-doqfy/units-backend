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












# ---------- User type choices ----------
OWNER = "OWNER"
PROPERTY_MANAGER = "PROPERTY_MANAGER"
TENANT = "TENANT"
STAFF = "STAFF"


# ---------- Default Permissions ----------
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
