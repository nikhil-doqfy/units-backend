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
    manage_through = models.CharField(max_length=20, choices=constants.choices)
    owner_documents = models.JSONField(default=dict, blank=True)
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
    uae_residence_visa = models.CharField(max_length=100)
    trade_license_number = models.CharField(max_length=100)
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
    city = models.CharField(max_length=255, null=True, blank=True)
    manage_through = models.CharField(max_length=20, choices=constants.choices)
    tenant_documents = models.JSONField(default=dict, blank=True)   



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
    owner = models.ForeignKey(
        "OwnerDetails",
        on_delete=models.SET_NULL,
        related_name="owned_properties",
        blank=True,
        null=True
    )
    created_by=models.ForeignKey(
        "user_service.PropertyManagerCompanyDetails",
        on_delete=models.SET_NULL,
        related_name="owned_properties",
        blank=True,
        null=True
    )
    
    lease_start_date = models.DateTimeField()
    lease_end_date = models.DateTimeField()
    lease_grace_start_date = models.DateTimeField(null=True, blank=True)
    lease_grace_end_date = models.DateTimeField(null=True, blank=True)
    lease_remarks = models.TextField(null=True, blank=True)
    step_status = models.CharField(max_length=50,
                                   choices=constants.LEASE_STEP_STATUS, default="LEASE_DETAILS")
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



class LeaseEjariUpload(models.Model):
    lease = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.CASCADE,
        related_name="ejari_uploads"
    )
    file_name = models.CharField(max_length=200)
    file_path = models.CharField(max_length=500)
    document_type = models.CharField(
     max_length=50,
    choices=constants.Ejari_DOCUMENT_CATEGORY_CHOICES 
    )


 
    def __str__(self):
        return f"{self.document_type} - {self.file_name}"   
    






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
    


class Template(Base):
    name = models.CharField(max_length=100)
    template_path = models.CharField(max_length=1000)
    is_active = models.BooleanField(default=True)
    is_predefined = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)
    pdf_path = models.CharField(max_length=2000, blank=True, null=True)
    
       
    def _str_(self):
        return self.name
 
 
class TemplateFields(Base):
    FIELD_TYPE_CHOICES = (
        (constants.NUMBER, "Number"),
        (constants.DATE, "Date"),
        (constants.TEXT, "Text"),
        (constants.RADIO, "Radio"),
        (constants.CHOICE, "Choice"),
        (constants.CHECKBOX, "Check Box"),
    )
    document_template = models.ForeignKey(Template, on_delete=models.CASCADE)
    name_attribute = models.CharField(max_length=150)
    id_attribute = models.CharField(max_length=150)
    value_attribute = models.CharField(max_length=150, null=True, blank=True)
    class_attribute = models.CharField(max_length=150, null=True, blank=True)
    label_attribute = models.CharField(max_length=150)
    html_tag = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
    required = models.BooleanField(default=False)
    min_value = models.IntegerField(null=True, blank=True)
    max_value = models.IntegerField(null=True, blank=True)
    min_length = models.IntegerField(null=True, blank=True)
    max_length = models.IntegerField(null=True, blank=True)
    pattern = models.CharField(max_length=20, null=True, blank=True)
    predefined_value = models.CharField(max_length=200, null=True, blank=True)

    def __str__(self):
        return f"{self.label_attribute} - {self.document_template.name}"

 
 
 
class TemplateValues(Base):
    document_template = models.ForeignKey(Template, on_delete=models.CASCADE)
    value = models.JSONField(default=dict, blank=True)

    lease = models.ForeignKey(
        "LeasePropertyDetails",
        on_delete=models.CASCADE,
        related_name="lease"
    )
    def __str__(self):
        return f"Template: {self.document_template.name} | Lease ID: {self.lease.id}"
        
    
 

    def _str_(self):
        return self.key

