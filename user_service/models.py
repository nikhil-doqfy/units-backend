from django.db import models
from property_management.models import Base
from utilities import constants
from django.utils import timezone
from django.conf import settings 


class UserProfile(Base):
    USER_TYPE_CHOICES = (
       (constants.OWNER, "Owner"),
       (constants.PROPERTY_MANAGER, "Property Manager"),
       (constants.TENANT, "Tenant"),
       (constants.STAFF, "Staff"),  
    )
    email = models.EmailField(unique=True, db_index=True)
    hashed_password = models.CharField(max_length=255)
    user_type = models.CharField(max_length=50, choices=USER_TYPE_CHOICES)
    otp = models.CharField(max_length=20, null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    is_deleted=models.BooleanField(default=False)
    is_detail_updated = models.BooleanField(default=False)
    is_document_uploaded = models.BooleanField(default=False)
    is_login_allowed = models.BooleanField(default=False)
    profile_image = models.TextField(null=True, blank=True)
    token = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=100)  
    time_zone = models.CharField(max_length=50)  
    utc = models.CharField(max_length=10)  
    last_login = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    city = models.CharField(max_length=255, null=True, blank=True)
    locality = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    emirate_id = models.CharField(max_length=255)
    uae_residence_visa = models.CharField(max_length=100)
    contact_number=models.CharField(max_length=20)
    trade_license_number = models.CharField(max_length=255)
    state = models.CharField(max_length=100, blank=True, null=True)
    manage_through = models.CharField(max_length=20, choices=constants.choices)


    def __str__(self):
        return '{}-{}-{}'.format(self.id, self.email, self.user_type)


class Company(Base):
    pmc = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="property_manager_details")
    company_code = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255)
    
    def __str__(self):
        return "{}".format(self.company_name)
    


def get_default_permissions():
    return constants.DEFAULT_PERMISSIONS

class Role(Base):
    name = models.CharField(max_length=255)
    permissions = models.JSONField(default=get_default_permissions)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staff_roles")

    def __str__(self):
        return "{}".format(self.name)

    

    
class PropertyDetails(Base):
    RENTAL_STATUS_CHOICES = [
        (constants.AVAILABLE, "Available"),
        (constants.NOT_AVAILABLE, "Not Available"),
    ]
    property_name = models.CharField(max_length=255)
    land_dm_no = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
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
    land_area_unit = models.CharField(max_length=20, default="Sq-ft", blank=True, null=True)
    no_of_floors = models.IntegerField(default=1)
    owner = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="owner_properties",
        blank=True,
        null=True
    )

    property_manager = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="manager_properties",
        blank=True,
        null=True
    )

    staff = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="assigned_staff_properties",
        blank=True,
        null=True
    )

    is_occupied = models.BooleanField(default=False)
    tenancy_start_date = models.DateField(blank=True, null=True)
    tenancy_end_date = models.DateField(blank=True, null=True)
    rental_status = models.CharField(
        max_length=20,
        choices=RENTAL_STATUS_CHOICES,
        default="AVAILABLE"
    )
    property_code = models.CharField(max_length=255, unique=True, blank=True, null=True)
    invited_email_id = models.EmailField(blank=True, null=True)
    step_status = models.CharField(
        max_length=50,
        choices=constants.STEP_CHOICES,
        default="BASIC_DETAILS"
    )
    rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    booking_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    cycle = models.CharField(max_length=50, blank=True, null=True)
    notice_period = models.CharField(max_length=50, blank=True, null=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"{self.property_name}"



class PropertyImages(Base):
    property = models.ForeignKey(
        PropertyDetails,
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
        return f"Image for {self.property.property_name}"


class UserVerification(Base):
    VERIFICATION_TYPE_CHOICES = (
        (constants.MOBILE_VERIFICATION, "Mobile Verification"),
        (constants.EMAIL_VERIFICATION, "Email Verification"),
    )
    user = models.ForeignKey(
        "UserProfile", on_delete=models.CASCADE, null=True, blank=True
    )
    email = models.CharField(max_length=100, null=True, blank=True)
    verification_type = models.CharField(
        max_length=50, choices=VERIFICATION_TYPE_CHOICES, default=constants.EMAIL_VERIFICATION
    )
    otp = models.IntegerField(null=True, blank=True)
    verified_time = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    



class Documents(Base):
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)
    document_choice = models.CharField(
        max_length=50,
        choices=constants.DOCUMENT_TYPE_CHOICES
    )
    def __str__(self):
        return f"{self.document_choice} - {self.file_name}"


class PropertyDocumentsMapping(Base):
    property = models.ForeignKey(
        "PropertyDetails",
        on_delete=models.CASCADE,
        related_name="property_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="property_document_mappings"
    )

    def __str__(self):
        return f"{self.property} -> {self.document}"



class OwnerDocumentsMapping(Base):
    owner = models.ForeignKey(
        "UserProfile",
        limit_choices_to={'user_type': constants.OWNER},  
        on_delete=models.CASCADE,
        related_name="owner_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="owner_document_mappings"
    )

    def __str__(self):
        return f"{self.owner} -> {self.document}"



class TenantDocumentsMapping(Base):
    tenant = models.ForeignKey(
        "UserProfile",
        limit_choices_to={'user_type': constants.TENANT},  
        on_delete=models.CASCADE,
        related_name="tenant_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="tenant_document_mappings"
    )

    def __str__(self):
        return f"{self.tenant} -> {self.document}"



class StaffDocumentsMapping(Base):
    staff = models.ForeignKey(
        "UserProfile",
        limit_choices_to={'user_type': constants.STAFF},  
        on_delete=models.CASCADE,
        related_name="staff_documents"
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="staff_document_mappings"
    )

    def __str__(self):
        return f"{self.staff} -> {self.document}"





class StaffCompanyMapping(Base):
    staff = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_type': constants.STAFF},
        on_delete=models.CASCADE,
        related_name="staff_company_mapping"
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_staff_mapping"
    )
    assigned_by = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_type': constants.PROPERTY_MANAGER},
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_staff"
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_role_mapping"
    )

    def __str__(self):
        return f"{self.staff.first_name} {self.staff.last_name} -> {self.company.company_name} ({self.role}) Assigned by: {self.assigned_by}"
