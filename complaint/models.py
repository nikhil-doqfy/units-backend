from django.db import models
from user_service.models import UserProfile
from property_management.models import Base
from user_service import constants

# Create your models here.

class Complaint(Base):
    STATUS_CHOICES = (
        (constants.IN_PROGRESS, "In Progress"),
        (constants.COMPLETED, "Completed"),
        (constants.ASSIGNED_ENGINEER, "Assigned to Engineer"),
        (constants.REJECTED, "Rejected"),
    )
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    message = models.TextField()
    status = models.CharField(
        max_length=30,
        choices=STATUS_CHOICES,
        default=constants.IN_PROGRESS
    )

    def __str__(self):
        return f"Complaint by {self.user}"