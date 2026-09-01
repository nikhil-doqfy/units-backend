from django.db import models
# Create your models here.
from user_service.models import PropertyManager, UserProfile, Tenant
from property_management.models import Base
from utilities import constants
 
 
class SupportTicket(Base):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="tenant_support_tickets"
    )
    description = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=constants.SUPPORT_STATUS_CHOICES,
        default=constants.OPEN
    )

 
class SupportMessage(Base):
    ticket = models.ForeignKey(
        SupportTicket,
        on_delete=models.CASCADE,
        related_name="messages"
    )
    sender = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE
    )
    message = models.TextField()
    attachment = models.TextField(null=True, blank=True)