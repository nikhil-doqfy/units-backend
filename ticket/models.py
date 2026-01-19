from django.db import models
from django.forms.models import model_to_dict
from utilities.helper_functions import (
    datetime_to_epoch,
)
from utilities import constants
from property_management.models import (
    Base, 
    LeasePropertyDetails,
)
from user_service.models import (
    UserProfile
)

# =============================================================================
# Property Management – Ticket Flow Models
# =============================================================================


class Category(Base):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return "{}".format(self.name)
    
    def _get_category_info(self):
        data = model_to_dict(
            self, 
            fields=(
                "id",
                "name",
                "description",
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        return data
    

class Vendor(Base):
    vendor = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="vendor_profiles",
        limit_choices_to={"user_role": constants.COMPANY_USER}
    )
    ticket_category = models.ManyToManyField(Category)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return "{}".format(self.vendor.user.username)
    
    def _get_vendor_info(self):
        data = model_to_dict(
            self, 
            fields=(
                "id",
                "is_available",
            )
        )
        data["vendor"] = self.vendor._get_user_basic_info()
        data["created"] = datetime_to_epoch(self.created)
        data["categories"] = [
            category._get_category_info()
            for category in self.ticket_category.all()
        ]        
        return data


class Ticket(Base):
    TICKET_PRIORITY_CHOICES = (
        (constants.LOW, "Low"),
        (constants.MEDIUM, "Medium"),
        (constants.HIGH, "High"),
    )

    TICKET_STATUS_CHOICES = (
        (constants.NEW, "New"),
        (constants.CATEGORIZED, "Categorized"),
        (constants.BROADCASTED, "Broadcasted"),
        (constants.ASSIGNED, "Assigned"),
        (constants.IN_PROGRESS, "In Progress"),
        (constants.WORK_SUBMITTED, "Wok Submitted"),
        (constants.PENDING_APPROVAL, "Pending Approval"),
        (constants.CLOSED, "Closed"),
        (constants.REJECTED, "Rejected"),
        (constants.EXPIRED, "Expired"),
    )

    ticket_code = models.CharField(max_length=50, unique=True)
    tenant = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name="tickets",
        limit_choices_to={"user_role": constants.TENANT}
    )
    property = models.ForeignKey(LeasePropertyDetails, on_delete=models.CASCADE)
    ticket_category = models.ForeignKey(Category, on_delete=models.CASCADE)
    priority = models.CharField(max_length=20, choices=TICKET_PRIORITY_CHOICES)
    status = models.CharField(max_length=50, choices=TICKET_STATUS_CHOICES)
    description = models.TextField()
    assigned_vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    work_submitted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return "{}".format(self.ticket_code)

    def _get_ticket_info(self):
        ticket_data = model_to_dict(
            self, 
            fields=(
                "id",
                "ticket_code",
                "description",
            )
        )
        ticket_data["tenant"] = self.tenant._get_user_basic_info() if self.tenant else None
        ticket_data["property"] = model_to_dict(self.property, fields=("id", "lease_number"))
        ticket_data["ticket_category"] = self.ticket_category._get_category_info()
        ticket_data["priority"] = self.get_priority_display()
        ticket_data["display_status"] = self.get_status_display()
        ticket_data["assigned_vendor"] = self.assigned_vendor.vendor._get_user_basic_info() if self.assigned_vendor else None
        ticket_data["created"] = datetime_to_epoch(self.created)
        ticket_data["assigned_at"] = datetime_to_epoch(self.assigned_at)
        ticket_data["work_submitted_at"] = datetime_to_epoch(self.work_submitted_at)
        ticket_data["closed_at"] = datetime_to_epoch(self.closed_at)
        return ticket_data


class TicketImages(Base):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    ticket_images = models.FileField(upload_to='ticket_images/', max_length=100, null=True, blank=True)
    uploaded_by = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="uploaded_proofs")

    def __str__(self):
        return "{}-{}".format(self.id, self.ticket.ticket_code)

    def _get_ticket_image_info(self):
        data = model_to_dict(
            self, 
            fields=(
                "id",
                "is_available",
            )
        )
        data["created"] = datetime_to_epoch(self.created)
        data["ticket"] = model_to_dict(self.ticket, fields=("id", "ticket_code"))
        data["ticket_image"] = self.ticket_images.url if self.ticket_images else None
        return data


class TicketAuditLog(Base):
    ACTOR_TYPE_CHOICES = (
        (constants.TENANT, "Tenant"),
        (constants.VENDOR, "Vendor"),
        (constants.SYSTEM, "System"),
    )

    action = models.CharField(max_length=255)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    metadata = models.JSONField(null=True, blank=True)
    remarks = models.TextField(null=True, blank=True)
    actor_type = models.CharField(max_length=20, choices=ACTOR_TYPE_CHOICES)

    def __str__(self):
        return "{}".format(self.ticket.ticket_code)
    
    def _get_ticket_audit_log_info(self):
        audit_data = model_to_dict(
            self,
            fields=(
                "id",
                "action",
                "remark",
            )
        )
        audit_data["created"] = datetime_to_epoch(self.created)
        audit_data["actor_type"] = self.actor_type.get_actor_type_display()
        audit_data["ticket"] = model_to_dict(self.ticket, fields=("id", "ticket_code"))
        audit_data["metadata"] = self.metadata if self.metadata else None
        return audit_data



class VendorTicketBroadcast(Base):
    BROADCAST_STATUS_CHOICES = (
        (constants.SENT, "Sent"),
        (constants.ACCEPTED, "Accepted"),
        (constants.REJECTED, "Rejected"),
        (constants.EXPIRED, "Expired"),
    )

    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE)
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=BROADCAST_STATUS_CHOICES, default=constants.SENT)
    responded_at = models.DateTimeField(null=True, blank=True)


    class Meta:
        unique_together = ("ticket", "vendor")

    def __str__(self):
        return "{}-{}".format(self.ticket.ticket_code, self.vendor)
    
    def _get_vendor_ticket_broadcast_info(self):
        data = model_to_dict(
            self,
            fields=(
                "id",
            )
        )
        data["display_status"] = self.get_status_display()
        data["ticket"] = model_to_dict(self.ticket, fields=("id", "ticket_code"))
        data["vendor"] = self.vendor.vendor._get_user_basic_info()
        data["responded_at"] = datetime_to_epoch(self.responded_at)
        data["created"] = datetime_to_epoch(self.created)
        return data
#================================================================================================================================