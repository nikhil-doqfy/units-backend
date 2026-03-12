from django.db import models
from property_management.models import Base
from utilities import constants
from user_service.models import Documents


class PropertyManagmentCompany(Base):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255)
    licence_number = models.CharField(max_length=100)
    licence_expiry_date = models.DateTimeField()
    licence_issuer = models.CharField(max_length=150)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"VC{self.pk:04d}"
            PropertyManagmentCompany.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self):
        return f"{self.name}"


class Property(Base):
    code = models.CharField(max_length=255, blank=True)
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
    pmc = models.ForeignKey(
        PropertyManagmentCompany,
        on_delete=models.CASCADE,
        related_name="pmc_properties",
        null=True,
        blank=True
    )

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            from utilities.helper_functions import generate_property_code
            self.code = generate_property_code()
            Property.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self):
        return self.property_name or f"Property #{self.id}"

    def _get_thumbnail(self):
        img = self.property_images.filter(image_type="EXTERIOR").first()
        if not img:
            return None
        from utilities.helper_functions import fetch_s3_presigned_url
        return fetch_s3_presigned_url(img.image_path, img.file_name)

    def _serialize_property(self):
        return {
            "id": self.id,
            "code": self.code,
            "property_name": self.property_name,
            "property_type": self.property_type,
            "no_of_blocks": self.no_of_blocks,
            "no_of_units": self.no_of_units,
            "land_area": self.land_area,
            "land_area_unit": self.land_area_unit,
            "land_dm_no": self.land_dm_no,
            "plot_no": self.plot_no,
            "makani_no": self.makani_no,
            "dewa_no": self.dewa_no,
            "address_line_1": self.address_line_1,
            "address_line_2": self.address_line_2,
            "landmark": self.landmark,
            "pincode": self.pincode,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "map_address": self.map_address,
            "pmc": {
                "key": self.pmc.id if self.pmc else None,
                "value": self.pmc.name if self.pmc else None,
            },
            "property_owners": [
                {
                    "id": po.owner.id,
                    "name": f"{po.owner.user.first_name} {po.owner.user.last_name}".strip(),
                    "email": po.owner.user.email,
                    "contact_number": po.owner.contact_number,
                    "emirates_id": po.owner.emirate_id,
                }
                for po in self.property_owners.select_related("owner__user").all()
            ],
            "thumbnail": self._get_thumbnail(),
        }
    
class PropertyOwner(Base):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="property_owners")
    owner = models.ForeignKey(
        "user_service.Owner",
        on_delete=models.CASCADE,
        related_name="property_owner_mappings"
    )

    def __str__(self):
        return f"{self.owner} -> {self.property}"
    

class PropertyBlocks(Base):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="property_blocks")
    block_name = models.CharField(max_length=255)
    no_of_floors = models.IntegerField(choices=constants.FLOOR_CHOICES)
    no_of_parking = models.IntegerField(choices=constants.PARKING_CHOICES)
    no_of_units = models.IntegerField(choices=constants.UNITS_CHOICES)

    def __str__(self):
        return f"{self.block_name} - {self.property.property_name}"

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
        related_name="owner_properties",
        null=True,
        blank=True
    )
    company = models.ForeignKey(
        PropertyManagmentCompany,
        on_delete=models.CASCADE,
        related_name="company_units",
        null=True,
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
    image_path = models.TextField()
    image_type = models.CharField(
        max_length=20,
        choices=constants.IMAGE_TYPE_CHOICES,
        default="INTERIOR"
    )
    file_name = models.CharField(max_length=255)

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


class PropertyDocuments(Documents):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="property_documents"
    )
    def __str__(self):
        return f"{self.property}"


class PropertyManagerDocuments(Documents):
    company_user = models.ForeignKey(
        "user_service.UserProfile",
        on_delete=models.CASCADE,
        related_name="company_user_documents",
        null=True,
        blank=True
    )
    def __str__(self):
        return f"{self.company_user} -> {self.document}"
