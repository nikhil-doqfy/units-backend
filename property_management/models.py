from django.db import models
from django.utils import timezone
from utilities import constants
from django.core.validators import EmailValidator

class Base(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class OwnerDetails(Base): 
    user = models.ForeignKey(
        "user_service.UserProfile",  
        on_delete=models.CASCADE,  
        related_name="owner_details"  
    )
    
    full_name = models.CharField(max_length=255)
    emirate_id = models.CharField(max_length=100)
    uae_residence_visa = models.CharField(max_length=100)
    trade_license_number = models.CharField(max_length=100)
    owner_number = models.CharField(max_length=50)
    mobile_number = models.CharField(max_length=20)
    manage_manually = models.BooleanField(default=False)
    manage_through_pmc = models.BooleanField(default=False)
    emirates_id_file = models.CharField(max_length=255, null=True, blank=True)
    residence_visa_file = models.CharField(max_length=255, null=True, blank=True)
    dld_certificate_file = models.CharField(max_length=255, null=True, blank=True)
    dewa_registration_file = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.full_name
    


class PropertyDocuments(Base):
    document_id = models.AutoField(primary_key=True)
    property_documents = models.JSONField(default=dict) 
    document_title = models.CharField(max_length=255, null=True, blank=True, default=None)
    property = models.ForeignKey(
        "user_service.PropertyDetails",
        on_delete=models.CASCADE,
        related_name="documents"
    )

    def __str__(self):
        return self.document_title or f"Document {self.document_id}"
    
    
    
class TenantDetails(Base):
    user = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="tenant_details",
    )
    property = models.ForeignKey(
        "user_service.PropertyDetails",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_details",
    )
    lease_property_details = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tenant_lease_details",
    )
    full_name = models.CharField(max_length=255)
    emirate_id = models.CharField(max_length=255)
    mobile_number = models.CharField(max_length=20)
    tenant_number = models.CharField(max_length=100)
    nationality = models.CharField(max_length=100)
    passport_self = models.CharField(max_length=255)
    passport_family_member = models.CharField(max_length=255, null=True, blank=True)
    passport_expiry = models.CharField(max_length=50)
    visa_self = models.CharField(max_length=255)
    visa_family_member = models.CharField(max_length=255, null=True, blank=True)
    visa_expiry = models.CharField(max_length=50)
    employment_proof = models.CharField(max_length=255)
    emirates_id_file = models.CharField(max_length=255, null=True, blank=True)
    passport_self_file = models.CharField(max_length=255, null=True, blank=True)
    passport_family_file = models.CharField(max_length=255, null=True, blank=True)
    visa_self_file = models.CharField(max_length=255, null=True, blank=True)
    visa_family_file = models.CharField(max_length=255, null=True, blank=True)
    employment_proof_file = models.CharField(max_length=255, null=True, blank=True)
    bank_statement_file = models.CharField(max_length=255, null=True, blank=True)
    address = models.TextField(blank=True, null=True)
    state = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.full_name}"
    

class LeasePropertyDetails(models.Model):
    lease_property = models.ForeignKey(
        "user_service.PropertyDetails",  
        on_delete=models.CASCADE,
        related_name="lease_properties"
    )
    lease_tenant = models.ForeignKey(
        "TenantDetails",  
        on_delete=models.CASCADE,
        related_name="tenant_leases"
    )
    lease_start_date = models.DateTimeField()
    lease_end_date = models.DateTimeField()
    lease_grace_start_date = models.DateTimeField(null=True, blank=True)
    lease_grace_end_date = models.DateTimeField(null=True, blank=True)
    lease_remarks = models.TextField(null=True, blank=True)
    lease_status = models.CharField(
        max_length=20,
        choices=constants.LEASE_STATUS_CHOICES,
        default="DRAFT"
        )

    def __str__(self):
        return f"Lease ID: {self.id} | Property: {self.lease_property_id} | Tenant: {self.lease_tenant_id}"
    


class LeaseCommercials(models.Model):
    lease = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.CASCADE,
        related_name="lease_commercials"
    )
    annual_amount = models.FloatField()
    actual_annual_amount = models.FloatField(null=True, blank=True)
    booking_amount = models.FloatField(null=True, blank=True)
    rent = models.FloatField()
    security_deposit = models.FloatField(null=True, blank=True)
    maintenance_charges = models.FloatField(null=True, blank=True)
    commission_percentage = models.FloatField(null=True, blank=True)
    notice_period = models.IntegerField(null=True, blank=True)
    discount = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"LeaseCommercials for Lease ID: {self.lease_id}"



class LeaseDocumentLayout(models.Model):
    lease = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.CASCADE,
        related_name="document_layout"
    )

    layout_type = models.CharField(max_length=50, choices=constants.LAYOUT_CHOICES)
    uploaded_template = models.FileField(
        upload_to="lease_documents/templates/",
        null=True, blank=True
    )
    selected_template_name = models.CharField(max_length=200, null=True, blank=True)
    ai_generated_doc = models.FileField(
        upload_to="lease_documents/generated/",
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Document Layout for Lease ID {self.lease_id}"





class LeaseEjariUpload(models.Model):
    lease = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.CASCADE,
        related_name="ejari_uploads"
    )
    property_floor_plan = models.TextField(null=True, blank=True)   
    tenant_doc = models.TextField(null=True, blank=True)            
    ejari_certificates = models.TextField(null=True, blank=True)   
    pmc_docs = models.TextField(null=True, blank=True)             
    cheque = models.TextField(null=True, blank=True)                 
    uploaded_by = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    uploaded_at = models.DateTimeField(default=timezone.now)  
    is_finalized = models.BooleanField(default=False)
    finalized_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Ejari Upload for Lease ID {self.lease.id}"
    


class AgreementFormVariables(Base):
    reference_no_date = models.CharField(max_length=255, null=True, blank=True)
    asset_management = models.ForeignKey(
        "user_service.PropertyManagerCompanyDetails", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="agreements"
    )
    lessor = models.ForeignKey(
        "OwnerDetails", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="agreements_as_lessor"
    )
    lessee = models.ForeignKey(
        "TenantDetails", 
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="agreements_as_lessee"
    )
    property = models.ForeignKey(
        "user_service.PropertyDetails",   
        on_delete=models.SET_NULL, 
        null=True, blank=True, 
        related_name="agreements"
    )  
    owner_address = models.TextField(null=True, blank=True)
    owner_email = models.EmailField(validators=[EmailValidator()], null=True, blank=True)
    owner_tel_no = models.CharField(max_length=50, null=True, blank=True)
    main_occupant = models.CharField(max_length=255, null=True, blank=True)
    main_occupant_email = models.EmailField(validators=[EmailValidator()], null=True, blank=True)
    main_occupant_mobile = models.CharField(max_length=50, null=True, blank=True)
    main_occupant_passport_no_expiry = models.CharField(max_length=255, null=True, blank=True)
    main_occupant_resident_visa_no = models.CharField(max_length=255, null=True, blank=True)
    main_occupant_emirates_id_no = models.CharField(max_length=255, null=True, blank=True)
    main_occupant_visa_expiry = models.CharField(max_length=255, null=True, blank=True)
    floor_unit = models.CharField(max_length=255, null=True, blank=True)
    unit_type = models.CharField(max_length=255, null=True, blank=True)
    lease_period = models.CharField(max_length=255, null=True, blank=True)
    commencement_date = models.CharField(max_length=255, null=True, blank=True)
    expiry_date = models.CharField(max_length=255, null=True, blank=True)
    rent_lease_period = models.CharField(max_length=255, null=True, blank=True)
    annualized_rent = models.CharField(max_length=255, null=True, blank=True)
    additional_facilities1 = models.CharField(max_length=255, null=True, blank=True)
    additional_amount1 = models.CharField(max_length=255, null=True, blank=True)
    additional_details1 = models.TextField(null=True, blank=True)
    additional_facilities2 = models.CharField(max_length=255, null=True, blank=True)
    additional_amount2 = models.CharField(max_length=255, null=True, blank=True)
    additional_details2 = models.TextField(null=True, blank=True)
    security_deposit = models.CharField(max_length=255, null=True, blank=True)
    pet_deposit = models.CharField(max_length=255, null=True, blank=True)
    contract_type = models.CharField(max_length=255, null=True, blank=True)
    remark = models.TextField(null=True, blank=True)

    def __str__(self):
        return f"Agreement - {self.reference_no_date or 'N/A'}"



class OwnerPMCInvitation(Base):
    email = models.EmailField()
    invited_by = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="pmc_invitations"
    )
    token = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=constants.INVITATION_STATUS_CHOICES,
        default=constants.PENDING
    )

    def __str__(self):
        return f"{self.email} - {self.status}"


class PMCOwnerInvitation(Base):
    email = models.EmailField(unique=True)
    invited_by = models.ForeignKey(
        "user_service.UserProfile",  
        on_delete=models.CASCADE,
        related_name="property_owner_invitations"
    )
    token = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=constants.INVITATION_STATUS_CHOICES,
        default=constants.PENDING
    )
    
    def __str__(self):
        return f"{self.email} - {self.status}"





class PMCTenantInvitation(Base):
    email = models.EmailField(unique=True)
    invited_by = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="tenant_invitations"
    )
    token = models.CharField(max_length=255, unique=True)
    status = models.CharField(
        max_length=20,
        choices=constants.INVITATION_STATUS_CHOICES,
        default=constants.PENDING
    )
 
    def __str__(self):
        return f"{self.email} - {self.status}"