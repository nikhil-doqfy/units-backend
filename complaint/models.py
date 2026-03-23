from django.db import models
from property_management.models import Base
from utilities import constants


class Complaint(Base):

    unit = models.ForeignKey('property.Unit',on_delete=models.CASCADE,related_name='complaints')
    raised_by = models.ForeignKey('user_service.UserProfile',on_delete=models.CASCADE,related_name='raised_complaints')
    company = models.ForeignKey('property.PropertyManagmentCompany',on_delete=models.CASCADE,related_name='complaints')
    # ── Complaint Details ──────────────────────────────────────────
    complaint_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    description = models.TextField()
    status = models.CharField(
        max_length=30,
        choices=constants.COMPLAINT_STATUS_CHOICES,
        default=constants.PENDING
    )

    def save(self, *args, **kwargs):
        if not self.complaint_id:
            last = Complaint.objects.order_by('-id').first()
            new_number = (int(last.complaint_id[2:]) + 1) if last else 1
            self.complaint_id = f"CP{str(new_number).zfill(4)}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.complaint_id} - {self.status}"


class ComplaintImages(Base):
    complaint = models.ForeignKey(Complaint,on_delete=models.CASCADE,related_name='complaint_images')
    # ── Image Details ──────────────────────────────────────────────
    image_path = models.TextField()
    file_name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.complaint.complaint_id} - {self.file_name}"