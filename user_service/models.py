from django.db import models
from property_management.models import Base
from utilities import constants
from utilities.org_scope import get_pmc_ids_for_user
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import timedelta
from utilities.config import OTP_VALID_TIME
from django.db.models import F, Q


class OwnerQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(
            Q(unit_owner_links__unit__parent_property__pmc_id__in=pmc_ids) |
            Q(unit_owner_links__unit__property_block_tower__property__pmc_id__in=pmc_ids)
        ).distinct()


class TenantQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(
            Q(lease__unit__parent_property__pmc_id__in=pmc_ids) |
            Q(lease__unit__property_block_tower__property__pmc_id__in=pmc_ids)
        ).distinct()


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

    def get_user_basic_info(self):
        return {
            "id":             self.id,
            "name":           self.user.get_full_name() or self.user.username,
            "email":          self.email or self.user.email,
            "contact_number": self.contact_number,
            "code":           self.code,
            "profile_image":  self.profile_image or None,
        }

    def __str__(self):
        return f"{self.id}-{self.user.email}"


class Owner(UserProfile):
    objects = OwnerQuerySet.as_manager()

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
    objects = TenantQuerySet.as_manager()

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
        #return f"{self.email} - {self.purpose} - OTP: {self.otp}"
        return f"{self.user_profile.user.email} - {self.purpose} - OTP: {self.otp}"
    
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


class Documentation(Documents):

    code = models.CharField(max_length=50, blank=True)
    user = models.ForeignKey('user_service.PropertyManager',on_delete=models.CASCADE,related_name='agreements')
    agreement_name = models.CharField(max_length=255)
    agreement_type = models.CharField(max_length=50,)
    status = models.CharField(max_length=20,choices=constants.AGREEMENT_STATUS_CHOICES,default='ACTIVE')
    issued_by = models.CharField(max_length=255,null=True, blank=True,help_text="Name of person or authority who issued this document")
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    does_not_expire = models.BooleanField(default=False,help_text="If True, this document never expires")
    is_expired = models.BooleanField(default=False)
    expiry_reminder_sent_at = models.DateTimeField(null=True, blank=True)
    last_email_sent_date = models.DateField(null=True, blank=True)
    expiry_reminder_sent_count = models.IntegerField(default=0)
    expiry_expired_sent_count = models.IntegerField(default=0)
    is_renewed = models.BooleanField(default=False)
    renewed_at = models.DateTimeField(null=True, blank=True)
    renewed_by = models.ForeignKey(
        'user_service.UserProfile',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='renewed_agreements'
    )
    cc_emails = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    # ── Helpers ───────────────────────────────────────────────

    def get_cc_emails_list(self):
        if not self.cc_emails:
            return []
        return [e.strip() for e in self.cc_emails.split(',') if e.strip()]

    def generate_code(self):
        agreement_type = (self.agreement_type or "").upper()
        prefix = "LP" if agreement_type in ["LEASE_PURCHASE", "PROPERTY_MANAGEMENT"] else "VC"
        return f"{prefix}{self.pk:04d}"

    # ── STATUS LOGIC ───────────────────────────────────────────

    def get_status(self):
        if self.does_not_expire:
            return 'ACTIVE'

        if self.is_expired:
            return 'EXPIRED'

        if not self.end_date:
            return self.status

        now = timezone.now()

        if self.end_date < now:
            return 'EXPIRED'

        if self.end_date <= now + timedelta(days=7):
            return 'EXPIRING_SOON'

        return 'ACTIVE'

    def get_status_display_label(self):
        status = self.get_status()

        if status == 'EXPIRED':
            return 'Expired'

        if status == 'EXPIRING_SOON' and self.end_date:
            now = timezone.now()
            diff = self.end_date - now
            days = diff.days

            if days <= 0:
                return "Expires today"
            elif days == 1:
                return "Expires in 1 day"
            else:
                return f"Expires in {days} days"

        if self.does_not_expire:
            return 'Active (No Expiry)'

        return 'Active'

    def update_status(self):
        computed = self.get_status()
        changed = False

        if computed == 'EXPIRED' and not self.is_expired:
            self.is_expired = True
            changed = True

        if self.status != computed:
            self.status = computed
            changed = True

        if changed:
            Documentation.objects.filter(pk=self.pk).update(
                is_expired=self.is_expired,
                status=self.status
            )

    def should_send_reminder(self):
        from django.utils import timezone

        if not self.end_date:
            return False

        if self.is_expired:
            return False

        if self.is_renewed:
            return False

        today = timezone.now().date()
        end = self.end_date.date()

        days_left = (end - today).days

        # YOUR RULE (KEEP ONLY THIS LOGIC)
        if days_left > 7:
            return False

        return True

    def mark_reminder_sent(self):
        Documentation.objects.filter(pk=self.pk).update(
            expiry_reminder_sent_at=timezone.now(),
            expiry_reminder_sent_count=F('expiry_reminder_sent_count') + 1
        )

    def mark_renewed(self, user, new_end_date):

        self.is_renewed = True
        self.is_expired = False
        self.end_date = new_end_date

        self.expiry_reminder_sent_at = None
        self.expiry_reminder_sent_count = 0
        self.expiry_expired_sent_count = 0

        self.renewed_at = timezone.now()
        self.renewed_by = user

        self.save()
    
    def get_expiry_progress(self):
        if not self.end_date:
            return "0/7"

        now = timezone.now().date()
        end = self.end_date.date()

        days_diff = (end - now).days

        # 🟡 BEFORE EXPIRY (including today)
        if 0 <= days_diff <= 7:
            return f"{self.expiry_reminder_sent_count}/7 (reminder)"

        # 🔴 AFTER EXPIRY
        if -7 <= days_diff < 0:
            return f"{self.expiry_expired_sent_count}/7 (expired)"

        return "0/7"

    # ── SAVE METHOD ───────────────────────────────────────────

    def save(self, *args, **kwargs):

        if self.is_renewed:
            self.status = "ACTIVE"
            self.is_expired = False

        elif self.does_not_expire:
            self.status = "ACTIVE"
            self.is_expired = False

        elif self.end_date:
            now = timezone.now()

            if self.end_date < now:
                self.status = "EXPIRED"
                self.is_expired = True

            elif self.end_date <= now + timedelta(days=7):
                self.status = "EXPIRING_SOON"
                self.is_expired = False

            else:
                self.status = "ACTIVE"
                self.is_expired = False

        super().save(*args, **kwargs)

        # FIX: generate code safely
        if not self.code:
            self.code = self.generate_code()
            Documentation.objects.filter(pk=self.pk).update(code=self.code)

    # ── STRING ────────────────────────────────────────────────
    def __str__(self):
        return f"{self.code} - {self.agreement_name}"