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
    profile_image_type = models.CharField(max_length=10, null=True, blank=True)
    token = models.TextField(null=True, blank=True)
    country = models.CharField(max_length=100)  
    time_zone = models.CharField(max_length=50)  
    utc = models.CharField(max_length=10)  
    last_login = models.DateTimeField(null=True, blank=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    


    def __str__(self):
        return '{}-{}-{}'.format(self.id, self.email, self.user_type)
    

class PropertyManagerCompanyDetails(models.Model):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="property_manager_details")
    company_code = models.CharField(max_length=255)
    company_name = models.CharField(max_length=255)
    company_id = models.CharField(max_length=255)
    company_address = models.CharField(max_length=255)
    city = models.CharField(max_length=255, null=True, blank=True)
    locality = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    company_emirate_id = models.CharField(max_length=255)
    uae_residence_visa = models.CharField(max_length=100)
    emirate_id = models.CharField(max_length=255)

    trade_license_number = models.CharField(max_length=255)
    license_issuer = models.CharField(max_length=255)
    rera_license = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email_address = models.EmailField(null=True, blank=True)
    pmc_documents = models.JSONField(default=dict, blank=True)
    state = models.CharField(max_length=100, blank=True, null=True)
     

    def __str__(self):
        return "{}".format(self.company_name)
    


def get_default_permissions():
    return constants.DEFAULT_PERMISSIONS

class StaffRole(models.Model):
    name = models.CharField(max_length=255)
    permissions = models.JSONField(default=get_default_permissions)
    property_manager = models.ForeignKey(PropertyManagerCompanyDetails, on_delete=models.CASCADE, related_name="staff_roles")

    def __str__(self):
        return "{}".format(self.name)


class StaffDetails(models.Model):
   
    staff_name = models.CharField(max_length=255, null=False, blank=False)
    phone_number = models.CharField(max_length=20, null=False, blank=False)
    staff_id = models.CharField(max_length=100, unique=True, null=False, blank=False)
    assign_property = models.IntegerField(null=True, blank=True)
    user = models.ForeignKey(UserProfile, null=True, blank=True, related_name="staff_details",on_delete=models.SET_NULL) 
    staff_role = models.ForeignKey(StaffRole, on_delete=models.CASCADE, related_name="staff_details")
    property_manager = models.ForeignKey(PropertyManagerCompanyDetails, on_delete=models.CASCADE, null=True, blank=True)
    assigned_properties = models.ManyToManyField('PropertyDetails',blank=True)
    emirate_id = models.CharField(max_length=100)

    city = models.CharField(max_length=100)
    locality = models.CharField(max_length=150)
    postal_code = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return "{}".format(self.staff_name)
    

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
    property_type_options = models.CharField(max_length=50,
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
        related_name="owned_properties",
        blank=True,
        null=True
    )
    property_manager = models.ForeignKey(
        PropertyManagerCompanyDetails,
        on_delete=models.SET_NULL,
        related_name="properties_managed",
        blank=True,
        null=True
    )
    staff = models.ForeignKey(
        StaffDetails,
        on_delete=models.SET_NULL,
        related_name="staff_properties",
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
    images = models.JSONField(default=list, blank=True, null=True)
    property_documents =models.JSONField(default=list, blank=True, null=True)

    step_status = models.CharField(
        max_length=50,
        choices=constants.STEP_CHOICES,
        default="BASIC_DETAILS"
    )
   

    def __str__(self):
        return "{}".format(self.property_name)  


class PropertyDocuments(Base):
    property = models.ForeignKey(
        "PropertyDetails",
        on_delete=models.CASCADE,
        related_name="property_docs_relationship"
    )

    rental_documents = models.JSONField(default=list)
    tenant_documents = models.JSONField(default=list)
    ejari_certificates = models.JSONField(default=list)
    owner_documents = models.JSONField(default=list)
    cheque_documents = models.JSONField(default=list)



class PropertyCommercial(Base):
    property = models.OneToOneField(   
        PropertyDetails,
        on_delete=models.CASCADE,
        related_name="commercial"
    )

    rent = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    booking_amount = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    cycle = models.CharField(max_length=50, blank=True, null=True)   
    notice_period = models.CharField(max_length=50, blank=True, null=True)  
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    def __str__(self):
        return f"Commercial Details for {self.property.property_name}"
    




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
    






