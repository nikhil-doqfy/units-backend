from django.db import models

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
# ------------------------------Not craeted yet ----------------------------

    # Link to LeasePropertyDetails (string ref for safety)
    # lease_property_details = models.ForeignKey(
    #     "property_management.LeasePropertyDetails",
    #     on_delete=models.SET_NULL,
    #     null=True,
    #     blank=True,
    #     related_name="tenant_lease_details",
    # )

    # Tenant Basic Information
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

    def __str__(self):
        return f"{self.full_name}"
    






