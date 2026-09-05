from django.db import models
from django.db.models import Q
from property_management.models import Base
from utilities import constants
from utilities.org_scope import get_pmc_ids_for_user
from user_service.models import Documents, PropertyManager
from property_management.models import City


class PropertyQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(pmc_id__in=pmc_ids)


class UnitQuerySet(models.QuerySet):
    def for_user(self, user_profile):
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(
            Q(parent_property__pmc_id__in=pmc_ids) |
            Q(property_block_tower__property__pmc_id__in=pmc_ids)
        ).distinct()


class Organization(Base):
    code = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255, unique=True)
    address = models.TextField()
    email = models.EmailField(blank=True, null=True)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organization_location"
    )
    expiry_date = models.DateField(null=True, blank=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            self.code = f"ORG{self.pk:04d}"
            Organization.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self):
        return self.name

class PropertyManagmentCompany(Base):
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE, 
        related_name="companies",
    )
    code = models.CharField(max_length=255, blank=True) 
    name = models.CharField(max_length=255)
    email = models.EmailField(max_length=255)
    phone_number = models.CharField(max_length=20)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    locality = models.CharField(max_length=150)
    postal_code = models.CharField(max_length=20)
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


PROPERTY_STATUS_CHOICES = [
    ('DRAFT', 'Draft'),
    ('PUBLIC', 'Public'),
]


class PMCPMMapping(Base):
    pmc = models.ForeignKey(
        PropertyManagmentCompany,
        on_delete=models.CASCADE,
        related_name="pm_mappings"
    )

    pm = models.ForeignKey(
        PropertyManager,
        on_delete=models.CASCADE,
        related_name="pmc_mappings"
    )

    class Meta:
        unique_together = ("pmc", "pm")
        verbose_name = "PMC - Property Manager Mapping"
        verbose_name_plural = "PMC - Property Manager Mappings"

    def __str__(self):
        return f"{self.pm} -> {self.pmc}"

class PropertyType(Base):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class Property(Base):
    objects = PropertyQuerySet.as_manager()

    code = models.CharField(max_length=255, blank=True)
    property_name = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20,
        choices=PROPERTY_STATUS_CHOICES,
        default='DRAFT'
    )
    no_of_blocks = models.IntegerField(choices=constants.BLOCKS_CHOICES)
    no_of_units = models.IntegerField(choices=constants.UNITS_CHOICES)
    # property_type = models.CharField(
    #     max_length=20,
    #     choices=constants.PROPERTY_TYPE_CHOICES,
    #     default=constants.APARTMENT
    # )
    property_type = models.ManyToManyField(
        PropertyType,
        blank=True,
        related_name="properties"
    )
    platforms = models.JSONField(default=list, blank=True)
    land_area = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    land_area_unit = models.CharField(
        max_length=20,
        choices=constants.AREA_UNIT_CHOICES,
        default=constants.SQ_FT
    )
    land_dm_no = models.CharField(max_length=100, null=True, blank=True)
    plot_no = models.CharField(max_length=100, null=True, blank=True)
    dewa_no = models.CharField(max_length=100, null=True, blank=True)
    address_line_1 = models.CharField(max_length=255)
    address_line_2 = models.CharField(max_length=255)
    landmark = models.CharField(max_length=255)
    pincode = models.CharField(max_length=20)
    latitude = models.DecimalField(max_digits=20, decimal_places=15, null=True, blank=True)
    longitude = models.DecimalField(max_digits=20, decimal_places=15, null=True, blank=True)
    map_address = models.TextField(null=True, blank=True)
    approx_rent = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
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
        img = (
            self.property_images.filter(image_type="EXTERIOR").first()
            or self.property_images.first()
        )
        if not img:
            return None
        from utilities.helper_functions import fetch_s3_presigned_url
        return fetch_s3_presigned_url(img.image_path, img.file_name)

    def _serialize_property(self):
        platform_choices = dict(constants.PLATFORM_CHOICES)
        return {
            "id": self.id,
            "code": self.code,
            "property_name": self.property_name,
            #"property_type": self.property_type,
            "property_type": [{"key": pt.code, "value": pt.name}for pt in self.property_type.all()],
            #"no_of_blocks": PropertyBlocks.objects.filter(property=self).count(),
            "no_of_blocks": self.no_of_blocks,
            "no_of_units": self.no_of_units,
            "platforms": [
                platform_choices.get(platform, platform.replace("_", " ").title()).lower()
                for platform in (self.platforms or [])
            ],
            # "no_of_units": Unit.objects.filter(property_block_tower__property=self).count(),
            "land_area": self.land_area,
            "land_area_unit": self.land_area_unit,
            "land_dm_no": self.land_dm_no,
            "plot_no": self.plot_no,
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
            "thumbnail": self._get_thumbnail(),
            "approx_rent": str(self.approx_rent) if self.approx_rent is not None else None,
            "status": self.status,
        }
    
class PropertyBlocks(Base):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="property_blocks")
    block_name = models.CharField(max_length=255)
    no_of_floors = models.IntegerField(choices=constants.FLOOR_CHOICES)
    no_of_parking = models.IntegerField(choices=constants.PARKING_CHOICES)
    no_of_units = models.IntegerField(choices=constants.UNITS_CHOICES)
    makani_no = models.CharField(max_length=100, null=True, blank=True)

    def __str__(self):
        return f"{self.block_name} - {self.property.property_name}"
    
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


class PropertyDocuments(Documents):
    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        related_name="property_documents"
    )
    def __str__(self):
        return f"{self.property}"


class Unit(Base):
    objects = UnitQuerySet.as_manager()

    code = models.CharField(max_length=255, blank=True)
    parent_property = models.ForeignKey(Property, on_delete=models.CASCADE, related_name="units", null=True, blank=True)
    property_block_tower = models.ForeignKey(
        PropertyBlocks,
        on_delete=models.CASCADE,
        related_name="block_towers",
        null=True,   
        blank=True
    )
    unit_name = models.CharField(max_length=255)
    unit_size = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    area = models.CharField(max_length=255, null=True, blank=True)
    dm_no = models.CharField(max_length=100, null=True, blank=True)
    no_of_bedrooms = models.IntegerField(choices=constants.BEDROOM_CHOICES, null=True, blank=True)
    floor_no = models.IntegerField(choices=constants.FLOOR_CHOICES, null=True, blank=True)
    parking_no = models.CharField(max_length=50, null=True, blank=True)
    no_of_balcony = models.IntegerField(choices=constants.BALCONY_CHOICES, null=True, blank=True)
    land_no = models.CharField(max_length=100, null=True, blank=True)
    unit_usage = models.CharField(max_length=50, choices=constants.UNIT_USAGE_CHOICES, null=True, blank=True)
    unit_type = models.CharField(max_length=50, choices=constants.UNIT_TYPE_CHOICES, null=True, blank=True)
    sub_type = models.CharField(max_length=255, null=True, blank=True)
    makani_no = models.CharField(max_length=100, null=True, blank=True)
    dewa_no = models.CharField(max_length=100, null=True, blank=True)
    rent = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    security_deposit = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    booking_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    maintenance_charges = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cycle = models.CharField(max_length=50, null=True, blank=True)
    notice_period = models.CharField(max_length=50, null=True, blank=True)
    commission_percent = models.DecimalField(max_digits=5, decimal_places=3, null=True, blank=True)
    is_occupied = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.code:
            from utilities.helper_functions import generate_unit_code
            self.code = generate_unit_code()
            Unit.objects.filter(pk=self.pk).update(code=self.code)

    def __str__(self):
        return f"{self.unit_name} - {self.id}"

    def _get_unit_thumbnail(self):
        img = self.unit_images.filter(image_type="EXTERIOR").first()
        if not img:
            img = self.unit_images.first()
        if not img:
            return None
        from utilities.helper_functions import fetch_s3_presigned_url
        return fetch_s3_presigned_url(img.image_path, img.file_name)

    def _serialize_unit(self):
        block = self.property_block_tower
        prop = block.property if block else self.parent_property
        return {
            "id": self.id,
            "code": self.code,
            "unit_name": self.unit_name,
            "thumbnail": self._get_unit_thumbnail(),
            "block_id": block.id if block else None,
            "block_name": block.block_name if block else None,
            # "property_id": self.property_block_tower.property_id,
            "property_id": prop.id if prop else None,
            # "property_name": self.property_block_tower.property.property_name,
            "property_name": prop.property_name if prop else None,
            # "property_address_line_1": self.property_block_tower.property.address_line_1,
            "property_address_line_1": prop.address_line_1 if prop else None,
            # "property_address_line_2": self.property_block_tower.property.address_line_2,
            "property_address_line_2": prop.address_line_2 if prop else None,
            # "property_landmark": self.property_block_tower.property.landmark,
            "property_landmark": prop.landmark if prop else None,
            "unit_size": str(self.unit_size) if self.unit_size is not None else None,
            "area": self.area,
            "dm_no": self.dm_no,
            "no_of_bedrooms": self.no_of_bedrooms,
            "floor_no": self.floor_no,
            "parking_no": self.parking_no,
            "no_of_balcony": self.no_of_balcony,
            "land_no": self.land_no,
            "unit_usage": self.unit_usage,
            "unit_type": self.unit_type,
            "sub_type": self.sub_type,
            "makani_no": self.makani_no,
            "dewa_no": self.dewa_no,
            "rent": str(self.rent) if self.rent is not None else None,
            "security_deposit": str(self.security_deposit) if self.security_deposit is not None else None,
            "booking_amount": str(self.booking_amount) if self.booking_amount is not None else None,
            "maintenance_charges": str(self.maintenance_charges) if self.maintenance_charges is not None else None,
            "cycle": self.cycle,
            "notice_period": self.notice_period,
            "commission_percent": str(self.commission_percent) if self.commission_percent is not None else None,
            "pmc": prop.pmc.name if prop and prop.pmc else None,
            "unit_owners": [
                {
                    "id": o.id,
                    "owner_id": o.owner_id,
                    "name": f"{o.owner.user.first_name} {o.owner.user.last_name}".strip() if o.owner else None,
                    "email": o.owner.email if o.owner else None,
                    "contact_number": o.owner.contact_number if o.owner else None,
                    "emirates_id": o.owner.emirate_id if o.owner else None,
                    "owner_number": o.owner.owner_number if o.owner else None,
                    "trade_license_number": o.owner.trade_license_number if o.owner else None,
                    "license_number": o.owner.license_number if o.owner else None,
                    "license_expiry_date": o.owner.license_expiry_date.isoformat() if o.owner and o.owner.license_expiry_date else None,
                    "license_issuer": o.owner.license_issuer if o.owner else None,
                    "fax_number": o.owner.fax_number if o.owner else None,
                    "po_box_number": o.owner.po_box_number if o.owner else None,
                }
                for o in self.unit_owners.select_related("owner__user").all()
            ],
        }


class UnitImages(Base):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="unit_images",
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
        return f"Image for Unit #{self.unit_id}"


class UnitDocuments(Documents):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="unit_documents"
    )
    def __str__(self):
        return f"{self.unit}"


class UnitOwner(Base):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="unit_owners"
    )
    owner = models.ForeignKey(
        "user_service.Owner",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="unit_owner_links"
    )

    def __str__(self):
        return f"Owner #{self.owner_id} -> Unit #{self.unit_id}"
    

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


class PropertyManagerAssignedUnits(Base):
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="assigned_managers"
    )
    property_manager = models.ForeignKey(
        "user_service.PropertyManager",
        on_delete=models.CASCADE,
        related_name="assigned_units"
    )

    class Meta:
        unique_together = ("unit", "property_manager")

    def __str__(self):
        return f"PM #{self.property_manager_id} -> Unit #{self.unit_id}"
