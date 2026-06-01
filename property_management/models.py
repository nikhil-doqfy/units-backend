from django.db import models
from django.forms.models import model_to_dict
from django.contrib.auth.models import User
from utilities import constants
from utilities.helper_functions import datetime_to_epoch

class Base(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        abstract = True
    
    
class Country(models.Model):
    name = models.CharField(max_length=100, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return self.name

    def _get_country_info(self):
        return {"id": self.id, "name": self.name, "code": self.code}


class State(models.Model):
    country = models.ForeignKey(Country, on_delete=models.CASCADE, related_name="states")
    name = models.CharField(max_length=100, null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.country.name})"


class City(models.Model):
    state = models.ForeignKey(State, on_delete=models.CASCADE, related_name="cities", null=True, blank=True)
    code = models.CharField(max_length=10, null=True, blank=True)
    name = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.state.name}, {self.state.country.name})"


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
        "property.Unit",
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


class TermAndCondition(models.Model):

    TERM_TYPE_CHOICES = (
        ("RERA", "RERA"),
        ("GENERAL", "General"),
        ("FINAL", "Final"),
        ("ADDITIONAL", "Additional"),
    )
    lease = models.ForeignKey(
        "lease.Lease",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="terms",
        help_text="NULL for predefined terms, set for additional lease-specific terms"
    )
    description = models.TextField()

    term_type = models.CharField(
        max_length=20,
        choices=TERM_TYPE_CHOICES
    )

    is_predefined = models.BooleanField(
        default=True,
        help_text="True = predefined (global), False = lease-specific"
    )

    def __str__(self):
        return f"{self.term_type} | {'Predefined' if self.is_predefined else 'Additional'}"


class AuditLog(Base):

    userprofile = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="audit_logs"
    )

    message = models.CharField(max_length=500)

    action_type = models.CharField(
        max_length=20,
        choices=constants.AUDIT_ACTION_CHOICES
    )

    class Meta:
        ordering = ["-created"]

    def __str__(self):
        return f"{self.userprofile} - {self.action_type}"

class DashboardVisualization(Base):
    user = models.ForeignKey("user_service.UserProfile", on_delete=models.CASCADE, related_name="dashboard_visualizations")
    visualization = models.CharField(max_length=50, choices=constants.DASHBOARD_CHOICES)
    is_visible = models.BooleanField(default=True)
    class Meta:
        unique_together = ("user", "visualization")
    def __str__(self):
        return f"{self.user} - {self.visualization}"

#==========================================================
#--------------- Role Permission management ---------------
#==========================================================
# class Role(Base):
#     name = models.CharField(max_length=255,null=True, blank=True)
#     priority = models.IntegerField(default=0)
    
#     def __str__(self):
#         return '{}'.format(self.name)
    
#     def _get_role_info(self):
#         data = model_to_dict(self, fields=("id", "priority"))
#         data["role_name"] = self.name.name 
#         data["role_created"] = datetime_to_epoch(self.created)
#         return data
    


# class Permissions(Base):
#     name = models.CharField(max_length=100)
#     is_active = models.BooleanField(default=True)

#     def __str__(self):
#         return '{}'.format(self.name)
    
#     def _get_permission_info(self):
#         data = model_to_dict(self, fields=("id", "name"))
#         return data


# class RolePermission(Base):
#     role = models.ForeignKey(Role, on_delete=models.CASCADE, null=True, blank=True)
#     permission = models.ForeignKey(Permissions, on_delete=models.CASCADE)
#     view_only = models.BooleanField(default=False)
#     add = models.BooleanField(default=False)
#     modified = models.BooleanField(default=False)
#     delete = models.BooleanField(default=False)

#     class Meta:
#         unique_together = ['role','permission']

#     def __str__(self):
#         return '{}'.format(self.role)
    
#     def _get_role_permission_info(self):
#         data = model_to_dict(self, fields=("id", "view_only", "add", "modified", "delete", "terminate"))
#         data["role"] = self.role._get_role_info()
#         permission_info = self.permission._get_permission_info()
#         data.update(permission_info)
#         return data
    

# class ApiPermissions(Base):
#     API_PERMISSIONS_TYPE_CHOICES = (
#         (constants.VIEW_ONLY, "View Only"),
#         (constants.ADD, "Add"),
#         (constants.MODIFIED, "Modified"),
#         (constants.DELETE, "Delete"),
#         (constants.TERMINATED, "Terminated"), 
#     )
#     REQUEST_METHOD_CHOICES = (
#         (constants.GET, "Get"),
#         (constants.POST, "Post"),
#         (constants.PUT, "Put"),
#         (constants.PATCH, "Patch"),
#         (constants.DELETE, "Delete"),
#         (constants.OPTION, "Option")
#     )
#     path = models.CharField(max_length=200)
#     permission_type = models.CharField(max_length=50, choices=API_PERMISSIONS_TYPE_CHOICES)
#     request_method = models.CharField(max_length=50, choices=REQUEST_METHOD_CHOICES)
#     permission = models.ForeignKey(Permissions, on_delete=models.CASCADE)
    
#     class Meta:
#         unique_together = ["path", "permission_type"]

#     def __str__(self):
#         return "{}-{}".format(self.path, self.permission_type)
