from django.db import models
from property_management.models import Base
from utilities import constants
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from utilities.config import OTP_VALID_TIME


class UserProfile(Base):
    STATUS_CHOICES = (
        (constants.PENDING, "Pending"),
        (constants.APPROVED, "Approved"),
        (constants.REJECTED, "Rejected"),
    )
    code = models.CharField(max_length=255, blank=True, default='')
    city = models.ForeignKey("property_management.City", on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profile")
    profile_image = models.TextField(null=True, blank=True)
    pin_code = models.CharField(max_length=20, null=True, blank=True)
    
    address_line_1 = models.CharField(max_length=255, null=True, blank=True)
    address_line_2 = models.CharField(max_length=255, null=True, blank=True)
    locality = models.CharField(max_length=255, null=True, blank=True)
    emirate_id = models.CharField(max_length=255, null=True, blank=True)
    email = models.EmailField(max_length=255, null=True, blank=True)
    contact_number = models.CharField(max_length=20, null=True, blank=True)
    timezone = models.CharField(max_length=100, choices=constants.TIMEZONE_CHOICES, default=constants.TIMEZONE_CHOICES[0][0])
    nationality = models.CharField(max_length=100, blank=True, null=True)
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    passport_expiry_datetime = models.DateTimeField(blank=True, null=True)
    visa_number = models.CharField(max_length=50, blank=True, null=True)
    visa_expiry_datetime = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CHOICES[0][0])
    token = models.TextField(null=True, blank=True)
    password_change_timestamp = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.id}-{self.user.email}"


class Owner(UserProfile):
    trade_license_number = models.CharField(max_length=255, blank=True, default='')
    owner_number = models.CharField(max_length=20, null=True, blank=True)
    license_number = models.CharField(max_length=255, blank=True, default='')
    license_expiry_date = models.DateTimeField(null=True, blank=True)
    license_issuer = models.CharField(max_length=150, blank=True, default='')
    fax_number = models.CharField(max_length=20, null=True, blank=True)
    po_box_number = models.CharField(max_length=20, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"OW{self.pk:05d}"
            UserProfile.objects.filter(pk=self.pk).update(code=self.code)


class PropertyManager(UserProfile):
    company = models.ForeignKey("property.PropertyManagmentCompany", on_delete=models.CASCADE, related_name="company_staff")
    roles = models.ManyToManyField("Role", blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"PM{self.pk:05d}"
            UserProfile.objects.filter(pk=self.pk).update(code=self.code)


class Tenant(UserProfile):
    is_onboarding = models.BooleanField(default=False)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"TN{self.pk:05d}"
            UserProfile.objects.filter(pk=self.pk).update(code=self.code)


class Permission(Base):
    module_name = models.CharField(max_length=100, choices=constants.PERMISSION_MODULE_CHOICES)
    create = models.BooleanField(default=False)
    edit = models.BooleanField(default=False)
    delete = models.BooleanField(default=False)
    view = models.BooleanField(default=False)

    def __str__(self):
        return self.module_name


class Role(Base):
    name = models.CharField(max_length=255)
    company = models.ForeignKey("property.PropertyManagmentCompany", on_delete=models.CASCADE, related_name="staff_roles")
    permissions = models.ManyToManyField(Permission, blank=True)

    def __str__(self):
        return self.name


class UserVerification(models.Model):
    VERIFICATION_TYPE_CHOICES = (
        (constants.MOBILE_VERIFICATION, "Mobile Verification"),
        (constants.EMAIL_VERIFICATION, "Email Verification"),
    )
    PURPOSE_CHOICES = (
        (constants.LOGIN, "Login"),
        (constants.SIGNUP, "Signup"),
        (constants.RESET_PASSWORD, "Reset Password"),
    )
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="verifications")
    verification_type = models.CharField(
        max_length=50,
        choices=VERIFICATION_TYPE_CHOICES,
        default=constants.EMAIL_VERIFICATION,
        null=True,
        blank=True
    )
    otp = models.IntegerField(null=True, blank=True)
    verified_time = models.DateTimeField(null=True, blank=True)
    is_verified = models.BooleanField(default=False)
    purpose = models.CharField(
        max_length=50,
        choices=PURPOSE_CHOICES,
        default="login"
    )

    def __str__(self):
        return f"{self.email} - {self.purpose} - OTP: {self.otp}"
    
    def verify_otp(self, otp):
        if int(otp) != self.otp:
            return {'status': False, 'message': constants.INCORRECT_OTP}
        
        if self.verified_time + timedelta(seconds=OTP_VALID_TIME) > timezone.now():
            return {'status': True, 'message': constants.OTP_SUCCESS}
        else:
            return {'status': False, 'message': constants.OTP_EXPIRED}


class DocumentType(Base):
    SECTION_CHOICES = (
        (constants.OWNER, "Owner"),
        (constants.TENANT, "Tenant"),
        (constants.PROPERTY_MANAGER, "Property Manager"),
        (constants.PROPERTY, "Property"),
        (constants.UNIT, "Unit"),
        (constants.LEASE_CHEQUE, "Lease Cheque"),
    )
    name = models.CharField(max_length=255)
    section = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Documents(Base):
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name="documents")
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)

    def __str__(self):
        return f"{self.file_path} - {self.file_name}"


class OwnerDocuments(Documents):
    owner = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="owner_documents")

    def __str__(self):
        return f"{self.owner}"


class TenantDocuments(Documents):
    tenant = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="tenant_documents")

    def __str__(self):
        return f"{self.tenant}"


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

class Approval(Base):

    tenant = models.ForeignKey("user_service.Tenant",on_delete=models.CASCADE,related_name="tenant_rent_requests")
    unit = models.ForeignKey("property.Unit",on_delete=models.CASCADE,related_name="rent_approvals")
    requested_rent = models.DecimalField(max_digits=10,decimal_places=2)
    requested_tenure = models.CharField(max_length=50,null=True,blank=True)
    approved = models.BooleanField(default=False)
    approved_by = models.ForeignKey("user_service.UserProfile",on_delete=models.SET_NULL,null=True,blank=True,related_name="approved_rent_requests")
    approved_at = models.DateTimeField(null=True, blank=True)
    def __str__(self):
        return f"{self.unit} - {self.tenant}"

class AssignedUnit(Base):
    property_manager = models.ForeignKey("PropertyManager",on_delete=models.CASCADE,related_name="user_assigned_units")
    unit = models.ForeignKey("property.Unit",on_delete=models.CASCADE,related_name="user_assigned_managers")
 
    class Meta:
        unique_together = ("property_manager", "unit")
 
    def __str__(self):
        return f"{self.property_manager} - {self.unit}"