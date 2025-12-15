from django.db import models
from property_management.models import Base
from utilities import constants
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User




class UserProfile(Base):
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name="profile"
    )
    USER_ROLE_CHOICES = (
        (constants.OWNER, "Owner"),
        (constants.COMPANY_USER, "COMPANY USER"),
        (constants.TENANT, "Tenant"),
        (constants.STAFF, "Staff"),
    )
    user_role = models.CharField(max_length=50, choices=USER_ROLE_CHOICES)
    otp = models.CharField(max_length=20, null=True, blank=True)
    profile_image = models.TextField(null=True, blank=True)
    token = models.TextField(null=True, blank=True)
    city = models.ForeignKey(
        "City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="users"
    )
    
    time_zone = models.CharField(max_length=50, blank=True, null=True)
    utc = models.CharField(max_length=10, blank=True, null=True)
   
    locality = models.CharField(max_length=255, blank=True, null=True)
    pin_code = models.CharField(max_length=20, blank=True, null=True)
    address = models.CharField(max_length=255, blank=True, null=True)
    additional_address = models.CharField(max_length=255, blank=True, null=True)
    emirate_id = models.CharField(max_length=255, blank=True, null=True)
    uae_residence_visa = models.CharField(max_length=100, blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    trade_license_number = models.CharField(max_length=255, blank=True, null=True)
    
    manage_through = models.CharField(max_length=20, choices=constants.choices)
    def __str__(self):
        return f"{self.id}-{self.user.email}-{self.user_role}"


class Company(Base):
    company_user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="company_user")
    company_code = models.CharField(max_length=255, blank=True, null=True)
    company_name = models.CharField(max_length=255, blank=True, null=True)
    company_address = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"{self.company_name}"


class Permission(Base):
    codename = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return self.name


class Role(Base):
    name = models.CharField(max_length=255)
    permissions = models.ManyToManyField(
        Permission, related_name="roles"
    )
    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="staff_roles"
    )

    def __str__(self):
        return self.name


class PMStaffCompanyMapping(Base):
    user_profile = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.STAFF},
        on_delete=models.CASCADE,
        related_name="staff_company_mapping"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_staff_mapping"
    )
    roles = models.ManyToManyField(Role, blank=True)


class Property(Base):
    property_name = models.CharField(max_length=255)
    total_floors = models.IntegerField(blank=True, null=True)
    total_units = models.IntegerField(blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    additional_address = models.TextField(blank=True, null=True)
    Property_code = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )

    def __str__(self):
        return self.property_name


class PropertyUnitDetails(Base):
    RENTAL_STATUS_CHOICES = [
        (constants.AVAILABLE, "Available"),
        (constants.NOT_AVAILABLE, "Not Available"),
    ]
    property_unit_name = models.CharField(max_length=255, blank=True, null=True)
    land_dm_no = models.CharField(max_length=255, blank=True, null=True)
    area_of_property = models.FloatField(blank=True, null=True)
    no_of_parking = models.IntegerField(blank=True, null=True)
    makani_no = models.CharField(max_length=255, blank=True, null=True)
    dewa_no = models.CharField(max_length=255, blank=True, null=True)

    property_type = models.CharField(max_length=50, default="Apartment")
    property_type_options = models.CharField(
        max_length=50,
        choices=constants.PROPERTY_TYPE_CHOICES,
        default="Apartment"
    )

    land_area = models.CharField(max_length=50, default="1048")
    apartment_no = models.CharField(max_length=50, default="48")
    bedrooms = models.CharField(max_length=50, default="Select bedroom")
    apartment_floor_no = models.CharField(max_length=50, default="3")
    balcony = models.CharField(max_length=50, default="1")
    plot_no = models.CharField(max_length=50, default="128")
    area_unit = models.CharField(max_length=20, default="Sq-ft")
    land_area_unit = models.CharField(max_length=20, blank=True, null=True)
    no_of_floors = models.IntegerField(default=1)

    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="units",blank=True,
        null=True
    )

    owner = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        limit_choices_to={'user_role': constants.OWNER},
        related_name="owner_properties",
        blank=True,
        null=True
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="properties",blank=True,
        null=True
    )

    assigned_staff = models.ManyToManyField(
        "PMStaffCompanyMapping",
        related_name="assigned_properties",
        blank=True
    )

    is_occupied = models.BooleanField(default=False)
    property_code = models.CharField(
        max_length=255, unique=True, blank=True, null=True
    )

    step_status = models.CharField(
        max_length=50,
        choices=constants.STEP_CHOICES,
        default="BASIC_DETAILS"
    )
# ---------------------commercilas details----------------------------------
    rent = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    security_deposit = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    booking_amount = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    maintenance_charges = models.DecimalField(
        max_digits=10, decimal_places=2, blank=True, null=True
    )
    cycle = models.CharField(max_length=50, blank=True, null=True)
    notice_period = models.CharField(max_length=50, blank=True, null=True)
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, blank=True, null=True
    )

    def __str__(self):
        return self.property_unit_name if self.property_unit_name else "Unit Details"


class PropertyImages(Base):
    property = models.ForeignKey(
        PropertyUnitDetails,
        on_delete=models.CASCADE,
        related_name="property_images"
    )
    image_path = models.TextField()
    image_type = models.CharField(
        max_length=20,
        choices=constants.IMAGE_TYPE_CHOICES,
        default="INTERIOR"
    )
    file_name = models.CharField(max_length=255)

    def __str__(self):
        return f"Image for {self.property.property_unit_name}"


class UserVerification(models.Model):
    VERIFICATION_TYPE_CHOICES = (
        (constants.MOBILE_VERIFICATION, "Mobile Verification"),
        (constants.EMAIL_VERIFICATION, "Email Verification"),
    )
    PURPOSE_CHOICES = (
        (constants.LOGIN, "login"),
        (constants.SIGNUP, "signup"),
         (constants.RESET_PASSWORD, "Reset Password"),
    )
    email = models.CharField(max_length=100, null=True, blank=True)
    verification_type = models.CharField(
        max_length=50,
        choices=VERIFICATION_TYPE_CHOICES,
        default=constants.EMAIL_VERIFICATION
    )
    otp = models.IntegerField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    verified_time = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    purpose = models.CharField(
        max_length=50,
        choices=PURPOSE_CHOICES,
        default="login"
    )

    def __str__(self):
        return f"{self.email} - {self.purpose} - OTP: {self.otp}"


class Documents(Base):
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)


    def __str__(self):
        return f"{self.file_path} - {self.file_name}"


class PropertyDocumentsMapping(Base):
    PROPERTY_DOCUMENT_CHOICES = (
    (constants.FLOOR_PLAN, "Floor Plan"),
    (constants.EJARI_CERTIFICATE, "Ejari Certificate"),
    (constants.PMC_DOCUMENT, "PMC Document"),
    (constants.CHEQUE_DOCUMENT, "Cheque Document"),
)
    property = models.ForeignKey(
        PropertyUnitDetails,
        on_delete=models.CASCADE,
        related_name="property_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="property_document_mappings"
    )
    document_choice = models.CharField(
        max_length=50,
        choices=PROPERTY_DOCUMENT_CHOICES
    )

    def __str__(self):
        return f"{self.property} -> {self.document}"


class OwnerDocumentsMapping(Base):

    OWNER_DOCUMENT_CHOICES = (
           (constants.EMIRATES_ID, "Emirates ID"),
    (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
    (constants.DLD_CERTIFICATE ,"DLD Certificate"),
   
) 

    owner = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.OWNER},
        on_delete=models.CASCADE,
        related_name="owner_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="owner_document_mappings"
    )

    document_choice = models.CharField(
        max_length=50,
        choices= OWNER_DOCUMENT_CHOICES
    )

    def __str__(self):
        return f"{self.owner} -> {self.document}"


class TenantDocumentsMapping(Base):
    TENANT_DOCUMENT_CHOICES = (
    (constants.EMIRATES_ID, "Emirates ID"),
    (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
    (constants.DLD_CERTIFICATE ,"DLD Certificate"),
   
) 
    tenant = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.TENANT},
        on_delete=models.CASCADE,
        related_name="tenant_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="tenant_document_mappings"
    )
    document_choice = models.CharField(
        max_length=50,
        choices= TENANT_DOCUMENT_CHOICES
    )

    def __str__(self):
        return f"{self.tenant} -> {self.document}"


class CompanyUserDocumentsMapping(Base):
    COMPANY_DOCUMENT_CHOICES = (  
    (constants.EMIRATES_ID, "Emirates ID"),
    (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
    (constants.DLD_CERTIFICATE ,"DLD Certificate"),
   
) 
    company_user = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.COMPANY_USER},
        on_delete=models.CASCADE,
        related_name="company_user_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="company_user_document_mappings"
    )
    document_choice = models.CharField(
        max_length=50,
        choices= COMPANY_DOCUMENT_CHOICES
    )
    def __str__(self):
        return f"{self.company_user} -> {self.document}"


class StaffDocumentsMapping(Base):
    STAFF_DOCUMENT_CHOICES = (  
    (constants.EMIRATES_ID, "Emirates ID"),
    (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
    (constants.DLD_CERTIFICATE ,"DLD Certificate"),
   ) 
    staff = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.STAFF},
        on_delete=models.CASCADE,
        related_name="staff_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="staff_document_mappings"
    )
    document_choice = models.CharField(
        max_length=50,
        choices=STAFF_DOCUMENT_CHOICES
    )

    def __str__(self):
        return f"{self.staff} -> {self.document}"








# class OwnerTenantCompanyMapping(Base):
#     tenant = models.ForeignKey(
#         "UserProfile",
#         limit_choices_to={'user_role': constants.TENANT},
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name="tenant_mappings"
#     )
#     owner = models.ForeignKey(
#         "UserProfile",
#         limit_choices_to={'user_role': constants.OWNER},
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name="owner_mappings"
#     )
#     company = models.ForeignKey(
#         "Company",
#         on_delete=models.SET_NULL,
#         null=True, blank=True,
#         related_name="company_mappings"
#     )



class Country(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name


class State(models.Model):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="states"
    )
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    def __str__(self):
        return f"{self.name} ({self.country.name})"
    

class City(models.Model):
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name="cities"
    )
    code = models.CharField(max_length=10, unique=True, blank=True, null=True)
    name = models.CharField(max_length=100)
    def __str__(self):
        return f"{self.name} ({self.state.name}, {self.state.country.name})"

