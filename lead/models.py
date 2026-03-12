from django.db import models
from user_service.models import UserProfile
from property_management.models import Base
from user_service import constants

# Create your models here.
class Lead(Base):
    lead_id = models.CharField(max_length=20, unique=True)

    unit = models.ForeignKey(
        "property.Unit",
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
        "property.PropertyManagmentCompany",
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
