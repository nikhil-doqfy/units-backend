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
    is_detail_updated = models.BooleanField(default=False)
    is_document_uploaded = models.BooleanField(default=False)
    is_login_allowed = models.BooleanField(default=False)
    profile_image = models.CharField(max_length=255, null=True, blank=True, default=None)
    token = models.TextField(null=True, blank=True)
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
    trade_license_number = models.CharField(max_length=255)
    license_issuer = models.CharField(max_length=255)
    rera_license = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=20)
    email_address = models.EmailField(null=True, blank=True)
    pmc_documents = models.JSONField(default=dict)
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
    user = models.ForeignKey(UserProfile, null=True, blank=True, related_name="staff_details",on_delete=models.SET_NULL) #changes 
    staff_role = models.ForeignKey(StaffRole, on_delete=models.CASCADE, related_name="staff_details")
    property_manager = models.ForeignKey(PropertyManagerCompanyDetails, on_delete=models.CASCADE, null=True, blank=True)
    assigned_properties = models.ManyToManyField('PropertyDetails',blank=True)
    def __str__(self):
        return "{}".format(self.staff_name)
    

class PropertyDetails(Base):
    property_name = models.CharField(max_length=255)
    land_dm_no = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    area_of_property = models.FloatField(blank=True, null=True)
    no_of_parking = models.IntegerField(blank=True, null=True)
    makani_no = models.CharField(max_length=255, blank=True, null=True)
    dewa_no = models.CharField(max_length=255, blank=True, null=True)
    property_type = models.CharField(max_length=50, default="Apartment")
    land_area = models.CharField(max_length=50, default="1048")
    apartment_no = models.CharField(max_length=50, default="48")
    bedrooms = models.CharField(max_length=50, default="Select bedroom")
    apartment_floor_no = models.CharField(max_length=50, default="3")
    balcony = models.CharField(max_length=50, default="1")
    plot_no = models.CharField(max_length=50, default="128")
    area_unit = models.CharField(max_length=20, default="Sq-ft")
    land_area_unit = models.CharField(max_length=20, default="Sq-ft", blank=True, null=True)
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
    rental_status = models.CharField(max_length=50, default="Available")
    property_code = models.CharField(max_length=255, unique=True, blank=True, null=True)
    invited_email_id = models.EmailField(blank=True, null=True)
    def __str__(self):
        return "{}".format(self.property_name)    


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
    
