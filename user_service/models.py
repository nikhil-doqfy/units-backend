from django.db import models
from property_management.models import Base
from utilities import constants
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User

class UserProfile(Base):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profile")
    USER_ROLE_CHOICES = (
        (constants.OWNER, "Owner"),
        (constants.COMPANY_USER, "COMPANY USER"),
        (constants.TENANT, "Tenant"),
        
    )
    TENANT_STATUS_CHOICES = (
        (constants.PENDING, "Pending"),
        (constants.APPROVED, "Approved"),
        (constants.REJECTED, "Rejected"),
    )

    user_code=models.CharField(max_length=255, null=True, blank=True)
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
    time_zone = models.CharField(max_length=50, null=True, blank=True)
    utc = models.CharField(max_length=10, null=True, blank=True)
    locality = models.CharField(max_length=255, null=True, blank=True)
    pin_code = models.CharField(max_length=20, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    additional_address = models.CharField(max_length=255, null=True, blank=True)
    emirate_id = models.CharField(max_length=255, null=True, blank=True)
    uae_residence_visa = models.CharField(max_length=100, null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    trade_license_number = models.CharField(max_length=255, null=True, blank=True)
    manage_through = models.CharField(max_length=20, choices=constants.choices,null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    #-------------------new fileds----------------
    telephone_number = models.CharField(max_length=20,blank=True, null=True)
    fax_number = models.CharField(max_length=20,blank=True,null=True)
    passport_number = models.CharField( max_length=50,blank=True,null=True)
    passport_expiry_datetime = models.DateTimeField(blank=True,null=True)
    visa_number = models.CharField(max_length=50,blank=True,null=True)
    visa_expiry_datetime = models.DateTimeField( blank=True,null=True)

    tenant_status = models.CharField(
        max_length=20,
        choices=TENANT_STATUS_CHOICES,
        default="PENDING",
        null=True,
        blank=True
    )

    def __str__(self):
        return f"{self.id}-{self.user.email}-{self.user_role}"

class Company(Base):
    company_user = models.ForeignKey( UserProfile, on_delete=models.CASCADE, related_name="company_user")
    company_code = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_address = models.CharField(max_length=255, null=True, blank=True)
    # ----------------- Add New-------------------------------------------------- 
    licence_number = models.CharField(max_length=100)
    licence_expiry_date = models.DateTimeField(null=True, blank=True)
    licence_issuer = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.company_name}"


class Permission(Base):
    codename = models.CharField(max_length=100,null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Role(Base):
    name = models.CharField(max_length=255,null=True, blank=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="staff_roles",null=True, blank=True )

    def __str__(self):
        return self.name


class CompanyStaff(Base):
    staff = models.ForeignKey(UserProfile, on_delete=models.CASCADE,related_name="staff_companies")
    company = models.ForeignKey("Company",on_delete=models.CASCADE,related_name="company_staff" )
    roles = models.ManyToManyField("Role", blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    
        
    
class Property(Base):
    property_name = models.CharField(max_length=255,null=True, blank=True)
    total_floors = models.IntegerField(null=True, blank=True)
    total_units = models.IntegerField(null=True, blank=True)
    additional_address = models.TextField(null=True, blank=True)
    locality = models.CharField(max_length=20, null=True, blank=True)
    postal_code = models.CharField(max_length=20, null=True, blank=True)
    
    Property_code = models.CharField(
        max_length=255,  null=True, blank=True
    )
    property_type_options = models.CharField(
        max_length=50,
        choices=constants.PROPERTY_TYPE_CHOICES,
        default="Apartment"
    )
    city = models.ForeignKey(
        "City",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    def __str__(self):
        return self.property_name or f"Property #{self.id}"


class PropertyUnitDetails(Base):

    RENTAL_STATUS_CHOICES = [
        (constants.AVAILABLE, "Available"),
        (constants.NOT_AVAILABLE, "Not Available"),
    ]
    property_unit_name = models.CharField(max_length=255, null=True, blank=True)
    land_dm_no = models.CharField(max_length=255, null=True, blank=True)
    area_of_property = models.FloatField(null=True, blank=True)
    no_of_parking = models.IntegerField(null=True, blank=True)
    makani_no = models.CharField(max_length=255, null=True, blank=True)
    dewa_no = models.CharField(max_length=255, null=True, blank=True)
    property_type = models.CharField(max_length=50, default="Apartment")
    land_area = models.CharField(max_length=50, default="1048")
    apartment_no = models.CharField(max_length=50, default="48")
    bedrooms = models.CharField(max_length=50, default="Select bedroom")
    apartment_floor_no = models.CharField(max_length=50, default="3")
    balcony = models.CharField(max_length=50, default="1")
    plot_no = models.CharField(max_length=50, default="128")
    area_unit = models.CharField(max_length=20, default="Sq-ft")
    land_area_unit = models.CharField(max_length=20, null=True, blank=True)
    no_of_floors = models.IntegerField(default=1,null=True, blank=True)
    dimension= models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)

    property = models.ForeignKey(
        Property, on_delete=models.CASCADE, related_name="units",null=True, blank=True
    )
    
    owner = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        limit_choices_to={'user_role': constants.OWNER},
        related_name="owner_properties",
        null=True, blank=True
    )

    company = models.ForeignKey(
        Company, on_delete=models.CASCADE, related_name="properties",null=True, blank=True
    )
    assigned_staff = models.ManyToManyField(CompanyStaff,related_name="assigned_properties")

    is_occupied = models.BooleanField(default=False)
    property_code = models.CharField(
        max_length=255, null=True, blank=True
    )
    step_status = models.CharField(
        max_length=50,
        choices=constants.STEP_CHOICES,
        default="BASIC_DETAILS"
    )
    rent = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    security_deposit = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    booking_amount = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cycle = models.CharField(max_length=50, null=True, blank=True)
    notice_period = models.CharField(max_length=50, null=True, blank=True)
    commission_percent = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return f"{self.property_unit_name} - {self.id} "


class PropertyImages(Base):
    property = models.ForeignKey(
        PropertyUnitDetails,
        on_delete=models.CASCADE,
        related_name="property_images",null=True, blank=True
    )
    image_path = models.TextField(null=True, blank=True)
    image_type = models.CharField(
        max_length=20,
        choices=constants.IMAGE_TYPE_CHOICES,
        default="INTERIOR",null=True, blank=True
    )
    file_name = models.CharField(max_length=255,null=True, blank=True)

    def __str__(self):
        return f"Image for {self.property.property_unit_name}"




class PropertyInterest(Base):
    property_unit = models.ForeignKey(
        PropertyUnitDetails,
        on_delete=models.CASCADE,
        related_name="interests"
    )
    tenant = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="interested_properties"
    )
    

    class Meta:
        unique_together = ("property_unit", "tenant")

    def __str__(self):
        return f"{self.tenant} → {self.property_unit}"


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
        default=constants.EMAIL_VERIFICATION,null=True, blank=True
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
    file_name = models.CharField(max_length=200,null=True, blank=True)
    file_path = models.CharField(max_length=500,null=True, blank=True)

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
        related_name="property_documents",null=True, blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="property_document_mappings",null=True, blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=PROPERTY_DOCUMENT_CHOICES,default=constants.FLOOR_PLAN
    )

    def __str__(self):
        return f"{self.property} -> {self.document}"


class OwnerDocumentsMapping(Base):

    OWNER_DOCUMENT_CHOICES = (
           (constants.EMIRATES_ID, "Emirates ID"),
    (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
    (constants.DLD_CERTIFICATE ,"DLD Certificate"),) 

    owner = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.OWNER},
        on_delete=models.CASCADE,
        related_name="owner_documents",null=True, blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="owner_document_mappings",null=True, blank=True
    )

    document_choice = models.CharField(
        max_length=50,
        choices= OWNER_DOCUMENT_CHOICES,default=constants.EMIRATES_ID 
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
        related_name="tenant_documents",null=True, blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="tenant_document_mappings",null=True, blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices= TENANT_DOCUMENT_CHOICES,default=constants.EMIRATES_ID 
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
        related_name="company_user_documents",null=True, blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="company_user_document_mappings",null=True, blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices= COMPANY_DOCUMENT_CHOICES,default=constants.EMIRATES_ID 
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
     
        on_delete=models.CASCADE,
        related_name="staff_documents",null=True, blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="staff_document_mappings",null=True, blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=STAFF_DOCUMENT_CHOICES,default=constants.EMIRATES_ID 
    )

    def __str__(self):
        return f"{self.staff} -> {self.document}"


class Country(models.Model):
    name = models.CharField(max_length=100,null=True, blank=True)
    code = models.CharField(max_length=10,  null=True, blank=True)

    def __str__(self):
        return self.name


class State(models.Model):
    country = models.ForeignKey(
        Country,
        on_delete=models.CASCADE,
        related_name="states"
    )
    name = models.CharField(max_length=100,null=True, blank=True)
    code = models.CharField(max_length=10,  null=True, blank=True)
    def __str__(self):
        return f"{self.name} ({self.country.name})"
    

class City(models.Model):
    state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name="cities",null=True, blank=True
    )
    code = models.CharField(max_length=10,  null=True, blank=True)
    name = models.CharField(max_length=100,null=True, blank=True)
    
    def __str__(self):
        return f"{self.name} ({self.state.name}, {self.state.country.name})"
    


class Complaint(Base):
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    message = models.TextField()

    def __str__(self):
        return f"Complaint by {self.user}"


class PrivacyPolicy(Base):
    title = models.CharField(max_length=255)
    content = models.TextField()
    other_policy_content = models.TextField()

    def __str__(self):
        return self.title


class FAQ(models.Model):
    question = models.CharField(max_length=255)
    answer = models.TextField()

    def __str__(self):
        return self.question











