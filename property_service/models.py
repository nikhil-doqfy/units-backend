from django.db import models
from property_management.models import Base
from utilities import constants


class Company(Base):
    company_user = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="company_user"
    )
    company_code = models.CharField(max_length=255, null=True, blank=True)
    company_name = models.CharField(max_length=255, null=True, blank=True)
    company_address = models.CharField(max_length=255, null=True, blank=True)
    licence_number = models.CharField(max_length=100)
    licence_expiry_date = models.DateTimeField(null=True, blank=True)
    licence_issuer = models.CharField(max_length=150)

    def __str__(self):
        return f"{self.company_name}"


class Property(Base):
    property_name = models.CharField(max_length=255)
    no_of_blocks = models.IntegerField(choices=constants.BLOCKS_CHOICES)
    no_of_units = models.IntegerField(choices=constants.UNITS_CHOICES)
    property_type = models.CharField(
        max_length=20,
        choices=constants.PROPERTY_TYPE_CHOICES,
        default=constants.APARTMENT
    )
    land_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    land_area_unit = models.CharField(
        max_length=20,
        choices=constants.AREA_UNIT_CHOICES,
        default=constants.SQ_FT
    )
    land_dm_no = models.CharField(max_length=100, null=True, blank=True)
    plot_no = models.CharField(max_length=100, null=True, blank=True)
    makani_no = models.CharField(max_length=100, null=True, blank=True)
    dewa_no = models.CharField(max_length=100, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255)
    pincode = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=20, decimal_places=15, null=True, blank=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=15, null=True, blank=True)
    map_address = models.TextField(null=True, blank=True)
    property_pmc = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="pmc_properties",
        null=True,
        blank=True
    )

    def __str__(self):
        return self.property_name or f"Property #{self.id}"


class Unit(Base):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units")
    property_block_tower = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="block_towers",
        null=True,
        blank=True
    )
    owner = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.SET_NULL,
        limit_choices_to={'user_role': constants.OWNER},
        related_name="owner_properties",
        null=True,
        blank=True
    )
    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="company_units",
        null=True,
        blank=True
    )
    assigned_staff = models.ManyToManyField(
        "user_service.CompanyStaff",
        related_name="assigned_units",
        blank=True
    )
    unit_name = models.CharField(max_length=255)
    property_type = models.CharField(
        max_length=20,
        choices=constants.PROPERTY_TYPE_CHOICES,
        default=constants.APARTMENT
    )
    land_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    land_area_unit = models.CharField(
        max_length=20,
        choices=constants.AREA_UNIT_CHOICES,
        default=constants.SQ_FT
    )
    land_dm_no = models.CharField(max_length=100, null=True, blank=True)
    no_of_bedrooms = models.IntegerField(choices=constants.BEDROOM_CHOICES, null=True, blank=True)
    area_of_property = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area_of_property_unit = models.CharField(
        max_length=20,
        choices=constants.AREA_UNIT_CHOICES,
        default=constants.SQ_FT
    )
    floor_no = models.IntegerField(choices=constants.FLOOR_CHOICES, null=True, blank=True)
    parking_no = models.CharField(max_length=50, null=True, blank=True)
    no_of_balcony = models.IntegerField(choices=constants.BALCONY_CHOICES, null=True, blank=True)
    plot_no = models.CharField(max_length=100, null=True, blank=True)
    makani_no = models.CharField(max_length=100, null=True, blank=True)
    dewa_no = models.CharField(max_length=100, null=True, blank=True)
    is_occupied = models.BooleanField(default=False)
    property_code = models.CharField(max_length=255, null=True, blank=True)
    step_status = models.CharField(
        max_length=50,
        choices=constants.STEP_CHOICES,
        default="BASIC_DETAILS"
    )
    rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cycle = models.CharField(max_length=50, null=True, blank=True)
    notice_period = models.CharField(max_length=50, null=True, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"{self.unit_name} - {self.id}"


class PropertyImages(Base):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="property_images",
        null=True,
        blank=True
    )
    image_path = models.TextField(null=True, blank=True)
    image_type = models.CharField(
        max_length=20,
        choices=constants.IMAGE_TYPE_CHOICES,
        default="INTERIOR",
        null=True,
        blank=True
    )
    file_name = models.CharField(max_length=255, null=True, blank=True)

    def __str__(self):
        return f"Image for Property #{self.property_id}"


class PropertyInterest(Base):
    property_unit = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="interests"
    )
    tenant = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="interested_properties"
    )

    class Meta:
        unique_together = ("property_unit", "tenant")

    def __str__(self):
        return f"{self.tenant} → {self.property_unit}"


class PropertyDocumentsMapping(Base):
    PROPERTY_DOCUMENT_CHOICES = (
        (constants.FLOOR_PLAN, "Floor Plan"),
        (constants.EJARI_CERTIFICATE, "Ejari Certificate"),
        (constants.PMC_DOCUMENT, "PMC Document"),
        (constants.CHEQUE_DOCUMENT, "Cheque Document"),
    )
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="property_documents",
        null=True,
        blank=True
    )
    document = models.ForeignKey(
        "user_service.Documents",
        on_delete=models.CASCADE,
        related_name="property_document_mappings",
        null=True,
        blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=PROPERTY_DOCUMENT_CHOICES,
        default=constants.FLOOR_PLAN
    )

    def __str__(self):
        return f"{self.property} -> {self.document}"


class CompanyUserDocumentsMapping(Base):
    COMPANY_DOCUMENT_CHOICES = (
        (constants.EMIRATES_ID, "Emirates ID"),
        (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
        (constants.DLD_CERTIFICATE, "DLD Certificate"),
    )
    company_user = models.ForeignKey(
        "user_service.UserProfile",
        limit_choices_to={'user_role': constants.COMPANY_USER},
        on_delete=models.CASCADE,
        related_name="company_user_documents",
        null=True,
        blank=True
    )
    document = models.ForeignKey(
        "user_service.Documents",
        on_delete=models.CASCADE,
        related_name="company_user_document_mappings",
        null=True,
        blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=COMPANY_DOCUMENT_CHOICES,
        default=constants.EMIRATES_ID
    )

    def __str__(self):
        return f"{self.company_user} -> {self.document}"


class StaffDocumentsMapping(Base):
    STAFF_DOCUMENT_CHOICES = (
        (constants.EMIRATES_ID, "Emirates ID"),
        (constants.UAE_RESIDENCE_VISA, "UAE Residence Visa"),
        (constants.DLD_CERTIFICATE, "DLD Certificate"),
    )
    staff = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="staff_documents",
        null=True,
        blank=True
    )
    document = models.ForeignKey(
        "user_service.Documents",
        on_delete=models.CASCADE,
        related_name="staff_document_mappings",
        null=True,
        blank=True
    )
    document_choice = models.CharField(
        max_length=50,
        choices=STAFF_DOCUMENT_CHOICES,
        default=constants.EMIRATES_ID
    )

    def __str__(self):
        return f"{self.staff} -> {self.document}"
