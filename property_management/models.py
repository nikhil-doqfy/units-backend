from django.db import models
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from utilities import constants
from utilities.helper_functions import datetime_to_epoch ,datetime_to_epoch_millis

class Base(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        abstract = True
    
class LeasePropertyDetails(Base):
    lease_number = models.CharField(max_length=50, unique=True, null=True, blank=True)
    lease_property = models.ForeignKey(
        "user_service.PropertyUnitDetails", 
        on_delete=models.CASCADE,
        related_name="lease_details",null=True, blank=True
    )

    tenant = models.ForeignKey(
        "user_service.UserProfile",  
        limit_choices_to={'user_role': constants.TENANT},
        on_delete=models.CASCADE,
        related_name="tenant_leases",
        null=True,
        blank=True
    )

    owner = models.ForeignKey(
        "user_service.UserProfile", 
        limit_choices_to={'user_role': constants.OWNER},
        on_delete=models.SET_NULL,
        related_name="owner_leases",
        null=True,
        blank=True
    )

    lease_start_date = models.DateTimeField( null=True, blank=True)
    lease_end_date = models.DateTimeField( null=True, blank=True)
    lease_grace_start_date = models.DateTimeField(null=True, blank=True)
    lease_grace_end_date = models.DateTimeField(null=True, blank=True)
    lease_remarks = models.TextField(null=True, blank=True)
    step_status = models.CharField(
        max_length=50,
        choices=constants.LEASE_STEP_STATUS,
        default="LEASE_DETAILS"
    )
    lease_status = models.CharField(
        max_length=20,
        choices=constants.LEASE_STATUS_CHOICES,
        default="DRAFT"
    )
    approval_status = models.CharField(
        max_length=20,
        choices=constants.APPROVAL_STATUS_CHOICES,
        default="PENDING"
    )
    pdf_path = models.CharField(max_length=2000, null=True, blank=True)
    
    annual_amount = models.FloatField( null=True, blank=True)
    actual_annual_amount = models.FloatField(null=True, blank=True)
    rent = models.FloatField( null=True, blank=True)
    booking_amount = models.FloatField(null=True, blank=True)
    security_deposit = models.FloatField(null=True, blank=True)
    maintenance_charges = models.FloatField(null=True, blank=True)
    commission_percentage = models.FloatField(null=True, blank=True)
    notice_period = models.IntegerField(null=True, blank=True)
    discount = models.FloatField(null=True, blank=True)

    def __str__(self):
        return "{}-{}".format(self.lease_number, self.lease_status)
    
    def _get_lease_details_info(self):
        data =  model_to_dict(self, fields=(
            "id", 
            "lease_number",
            "lease_remarks", 
            "annual_amount",
            "actual_annual_amount",
            "rent",
            "booking_amount",
            "security_deposit",
            "maintenance_charges",
            "commission_percentage",
            "notice_period",
            "discount"
        )) 
        data["created"] = datetime_to_epoch_millis(self.created)
        data["lease_status"] = {"key": self.lease_status, "value": self.get_lease_status_display()}
        data["approval_status"] = {"key": self.approval_status, "value": self.get_approval_status_display()}
        data["step_status"] = {"key": self.step_status, "value": self.get_step_status_display()}
        data["lease_start_date"] = datetime_to_epoch_millis(self.lease_start_date)
        data["lease_end_date"] = datetime_to_epoch_millis(self.lease_end_date)
        data["lease_grace_start_date"] = datetime_to_epoch_millis(self.lease_grace_start_date)
        data["lease_grace_end_date"] = datetime_to_epoch_millis(self.lease_grace_end_date)
        data["lease_property"] = model_to_dict(self.lease_property, fields=["id", "property_unit_name"])
        data["tenant"] = {"id": self.tenant.id, "first_name": self.tenant.user.first_name ,"contact_number":self.tenant.contact_number ,"email":self.tenant.user.email } if self.tenant else None
        data["owner"] = {"id": self.owner.id, "first_name": self.owner.user.first_name} if self.owner else None
        return data


class LeaseDocumentsMapping(Base):
    LEASE_DOCUMENT_CHOICES = (
        (constants.EJARI_CERTIFICATE, "Ejari Certificate"),
        (constants.CHEQUE_DOCUMENT, "Cheque Document")
    )
    lease = models.ForeignKey(
        LeasePropertyDetails,
        on_delete=models.CASCADE,
        related_name="lease_documents", null=True, blank=True
    )
    document = models.ForeignKey(
         "user_service.Documents", 
        on_delete=models.CASCADE,
        related_name="lease_document_mappings", null=True, blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=LEASE_DOCUMENT_CHOICES
    )

    def __str__(self):
        return f"Lease {self.lease.id} -> Document {self.document.file_name}"




class UserInvitation(Base):
    INVITATION_TYPE_CHOICES = (
        ("OWNER_TO_PMC", "Owner inviting Property Manager"),
        ("PMC_TO_OWNER", "Property Manager inviting Owner"),
        ("PMC_TO_TENANT", "Property Manager inviting Tenant"),
    )
    email = models.EmailField( null=True, blank=True)
    invited_by = models.ForeignKey(
        "user_service.UserProfile", 
        on_delete=models.CASCADE,
        related_name="sent_invitations", null=True, blank=True
    )
    invitation_type = models.CharField(
        max_length=30,
        choices=INVITATION_TYPE_CHOICES
    )
    token = models.CharField(max_length=255, null=True, blank=True)
    property_unit = models.ForeignKey(
        "user_service.PropertyUnitDetails",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unit_invitations"
    )
    status = models.CharField(
        max_length=20,
        choices=constants.INVITATION_STATUS_CHOICES,
        default=constants.PENDING
    )

    def __str__(self):
        return f"{self.email} - {self.invitation_type} - {self.status}"


class Template(Base):
    name = models.CharField(max_length=100, null=True, blank=True)
    template_path = models.CharField(max_length=1000, null=True, blank=True)
    is_predefined = models.BooleanField(default=False)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name


class TemplateFields(Base):
    FIELD_TYPE_CHOICES = (
        (constants.NUMBER, "Number"),
        (constants.DATE, "Date"),
        (constants.TEXT, "Text"),
        (constants.RADIO, "Radio"),
        (constants.CHOICE, "Choice"),
        (constants.CHECKBOX, "Check Box"),)
    document_template = models.ForeignKey(Template, on_delete=models.CASCADE, null=True, blank=True)
    name_attribute = models.CharField(max_length=150, null=True, blank=True)
    id_attribute = models.CharField(max_length=150, null=True, blank=True)
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
    document_template = models.ForeignKey(Template, on_delete=models.CASCADE, null=True, blank=True)
    value = models.JSONField(default=dict, blank=True)
    lease = models.ForeignKey(
        "property_management.LeasePropertyDetails", 
        on_delete=models.CASCADE,
        related_name="lease", null=True, blank=True
    )

    def __str__(self):
        return f"Template: {self.document_template.name} | Lease ID: {self.lease.id}"
    

