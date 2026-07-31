from django.db import models
from user_service.models import UserProfile
from property_management.models import Base
from utilities import constants
from utilities.org_scope import get_pmc_ids_for_user


class LeadQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(pmc_id__in=pmc_ids)


class Lead(Base):
    objects = LeadQuerySet.as_manager()
    code = models.CharField(max_length=255, blank=True)
    unit = models.ForeignKey("property.Unit",on_delete=models.CASCADE,related_name="leads")
    tenant = models.ForeignKey(UserProfile,on_delete=models.SET_NULL,related_name="tenant_leads",null=True,blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField()
    contact_number = models.CharField(max_length=20)
    status = models.CharField(max_length=20,choices=constants.LEAD_STATUS_CHOICES,default=constants.INTERESTED)
    platform = models.CharField(max_length=20,choices=constants.PLATFORM_CHOICES)
    lead_type = models.CharField(max_length=20,choices=constants.LEAD_TYPE_CHOICES)
    referred_by = models.ForeignKey(
        UserProfile,
        on_delete=models.SET_NULL,
        related_name="referred_leads",
        null=True,
        blank=True
    )
    pmc = models.ForeignKey(
        "property.PropertyManagmentCompany",
        on_delete=models.CASCADE,
        related_name="leads"
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            from utilities.helper_functions import generate_lead_code
            self.code = generate_lead_code()
            Lead.objects.filter(pk=self.pk).update(code=self.code)



class ActivityLog(Base):
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activity_logs")
    activity_type = models.CharField(
        max_length=20,
        choices=constants.ACTIVITY_TYPE_CHOICES,
        default=constants.NOTE,
    )
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    scheduled_date = models.DateTimeField(null=True, blank=True)