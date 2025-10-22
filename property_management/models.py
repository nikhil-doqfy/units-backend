from django.db import models
# from user_service.models import UserProfile


# from property_management.models import PropertyDetails  
# ---------- Base Class ----------
class Base(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True

# ---------- OwnerDetails ----------
class OwnerDetails(Base):  # inherit from Base
    user = models.ForeignKey(
        "user_service.UserProfile",  # <-- use string reference
        on_delete=models.CASCADE,  # Delete owner details if user is deleted
        related_name="owner_details"  # Access all owner details of a user via user.owner_details.all()
    )

    full_name = models.CharField(max_length=255)
    emirate_id = models.CharField(max_length=100)
    uae_residence_visa = models.CharField(max_length=100)
    trade_license_number = models.CharField(max_length=100)
    owner_number = models.CharField(max_length=50)
    mobile_number = models.CharField(max_length=20)

    # Property Management Options
    manage_manually = models.BooleanField(default=False)
    manage_through_pmc = models.BooleanField(default=False)

    # Document Upload Fields (S3 URLs)
    emirates_id_file = models.CharField(max_length=255, null=True, blank=True)
    residence_visa_file = models.CharField(max_length=255, null=True, blank=True)
    dld_certificate_file = models.CharField(max_length=255, null=True, blank=True)
    dewa_registration_file = models.CharField(max_length=255, null=True, blank=True)


    def __str__(self):
        return self.full_name








class PropertyDocuments(models.Model):
    # Auto-increment primary key
    document_id = models.AutoField(primary_key=True)

    # JSON field to store multiple documents
    property_documents = models.JSONField(default=dict)  #  JSONField

    # Title of the document
    document_title = models.CharField(max_length=255, null=True, blank=True, default=None)


    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ------------------PropertyDetails not create it yet ---------------------------------------

    # Foreign key linking to PropertyDetails
    # property = models.ForeignKey(
    #     PropertyDetails,
    #     on_delete=models.CASCADE,
    #     related_name="documents"
    # )

    def __str__(self):
        return self.document_title or f"Document {self.document_id}"
