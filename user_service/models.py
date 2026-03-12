from django.db import models
from property_management.models import Base
from utilities import constants
from django.utils import timezone
from django.contrib.auth.models import User
from utilities.helper_functions import datetime_to_epoch_millis


class UserProfile(Base):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="profile")
    USER_ROLE_CHOICES = (
        (constants.OWNER, "Owner"),
        (constants.COMPANY_USER, "Company User"),
        (constants.TENANT, "Tenant"),
    )
    TENANT_STATUS_CHOICES = (
        (constants.PENDING, "Pending"),
        (constants.APPROVED, "Approved"),
        (constants.REJECTED, "Rejected"),
    )

    user_code = models.CharField(max_length=255, null=True, blank=True)
    user_role = models.CharField(max_length=50, choices=USER_ROLE_CHOICES)
    profile_image = models.TextField(null=True, blank=True)
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
    manage_through = models.CharField(max_length=20, choices=constants.choices, null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    telephone_number = models.CharField(max_length=20, blank=True, null=True)
    fax_number = models.CharField(max_length=20, blank=True, null=True)
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    passport_expiry_datetime = models.DateTimeField(blank=True, null=True)
    visa_number = models.CharField(max_length=50, blank=True, null=True)
    visa_expiry_datetime = models.DateTimeField(blank=True, null=True)
    password_change_timestamp = models.DateTimeField(default=timezone.now)
    tenant_status = models.CharField(max_length=20,choices=TENANT_STATUS_CHOICES,default="PENDING",null=True,blank=True )
    license_expiry = models.DateTimeField(default=timezone.now)
    license_issuer = models.CharField(max_length=255, default='')
    po_box = models.CharField(max_length=100, null=True, blank=True)
    def __str__(self):
        return f"{self.id}-{self.user.email}-{self.user_role}"


class Permission(Base):
    codename = models.CharField(max_length=100, null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return self.name


class Role(Base):
    name = models.CharField(max_length=255, null=True, blank=True)
    company = models.ForeignKey(
        "property_service.Company",
        on_delete=models.CASCADE,
        related_name="staff_roles",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.name


class CompanyStaff(Base):
    staff = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name="staff_companies")
    company = models.ForeignKey(
        "property_service.Company",
        on_delete=models.CASCADE,
        related_name="company_staff"
    )
    roles = models.ManyToManyField("Role", blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)


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
        default=constants.EMAIL_VERIFICATION,
        null=True,
        blank=True
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
    file_name = models.CharField(max_length=200, null=True, blank=True)
    file_path = models.CharField(max_length=500, null=True, blank=True)

    def __str__(self):
        return f"{self.file_path} - {self.file_name}"


class OwnerDocumentsMapping(Base):
    OWNER_DOCUMENT_CHOICES = (
        (constants.EMIRATES_ID, "Emirates ID"),
        (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
        (constants.DLD_CERTIFICATE, "DLD Certificate"),
    )
    owner = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.OWNER},
        on_delete=models.CASCADE,
        related_name="owner_documents",
        null=True,
        blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="owner_document_mappings",
        null=True,
        blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=OWNER_DOCUMENT_CHOICES,
        default=constants.EMIRATES_ID
    )

    def __str__(self):
        return f"{self.owner} -> {self.document}"


class TenantDocumentsMapping(Base):
    TENANT_DOCUMENT_CHOICES = (
        (constants.EMIRATES_ID, "Emirates ID"),
        (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
        (constants.DLD_CERTIFICATE, "DLD Certificate"),
    )
    tenant = models.ForeignKey(
        UserProfile,
        limit_choices_to={'user_role': constants.TENANT},
        on_delete=models.CASCADE,
        related_name="tenant_documents",
        null=True,
        blank=True
    )
    document = models.ForeignKey(
        Documents,
        on_delete=models.CASCADE,
        related_name="tenant_document_mappings",
        null=True,
        blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=TENANT_DOCUMENT_CHOICES,
        default=constants.EMIRATES_ID
    )

    def __str__(self):
        return f"{self.tenant} -> {self.document}"


class Country(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.name

    def _get_country_info(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class State(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="states")
    name = models.CharField(max_length=100, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.country.name})"


class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities", null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.state.name}, {self.state.country.name})"


class Complaint(Base):
    STATUS_CHOICES = (
        (constants.IN_PROGRESS, "In Progress"),
        (constants.COMPLETED, "Completed"),
        (constants.ASSIGNED_ENGINEER, "Assigned to Engineer"),
        (constants.REJECTED, "Rejected"),
    )
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    message = models.TextField()
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=constants.IN_PROGRESS
    )

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


class Lead(Base):
    lead_id = models.CharField(max_length=20, unique=True)

    unit = models.ForeignKey(
        "property_service.Unit",
        on_delete=models.CASCADE,
        related_name="leads"
    )
    tenant = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="tenant_leads",
        null=True,
        blank=True
    )
    name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20)
    status = models.CharField(
        max_length=20,
        choices=constants.LEAD_STATUS_CHOICES,
        default=constants.INTERESTED
    )
    platform = models.CharField(
        max_length=20,
        choices=constants.PLATFORM_CHOICES
    )
    lead_type = models.CharField(
        max_length=20,
        choices=constants.LEAD_TYPE_CHOICES
    )
    referred_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="referred_leads",
        null=True,
        blank=True
    )
    company = models.ForeignKey(
        "property_service.Company",
        on_delete=models.CASCADE,
        related_name="leads"
    )

    def save(self, *args, **kwargs):
        if not self.lead_id:
            if self.platform in constants.PORTAL_PLATFORMS:
                prefix = constants.LP
            else:
                prefix = constants.VC
            last_lead = Lead.objects.filter(
                lead_id__startswith=prefix
            ).order_by('-id').first()

            if last_lead:
                last_number = int(last_lead.lead_id[len(prefix):])
                new_number = last_number + 1
            else:
                new_number = 1

            self.lead_id = f"{prefix}{str(new_number).zfill(4)}"
        super().save(*args, **kwargs)
