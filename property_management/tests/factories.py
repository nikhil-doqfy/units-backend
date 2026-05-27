"""
factories.py — Test factories for property_management tests
Location: property_management/tests/factories.py

Usage:
    from property_management.tests.factories import (
        UserFactory, CompanyFactory, PropertyManagerFactory,
        OwnerFactory, TenantFactory, PropertyFactory,
        BlockFactory, UnitFactory
    )

Note:
    Unit.property_block_tower → ForeignKey to PropertyBlocks
    So UnitFactory uses BlockFactory directly — no BlockTowerFactory needed
"""
import factory
from django.contrib.auth.models import User
from django.utils import timezone
from user_service.models import DocumentType

from property.models import (
    PropertyManagmentCompany,
    Property,
    PropertyBlocks,
    Unit,
)
from user_service.models import PropertyManager, Tenant, Owner


# ── Django User ───────────────────────────────────────────────────────────────
class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username   = factory.Sequence(lambda n: f"user{n}")
    email      = factory.Sequence(lambda n: f"user{n}@test.com")
    password   = factory.PostGenerationMethodCall("set_password", "testpass123")
    first_name = factory.Sequence(lambda n: f"First{n}")
    last_name  = factory.Sequence(lambda n: f"Last{n}")


# ── PropertyManagmentCompany ──────────────────────────────────────────────────
class CompanyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyManagmentCompany

    name                = factory.Sequence(lambda n: f"Company {n}")
    address_line_1      = "Test Address Line 1"
    address_line_2      = "Test Address Line 2"
    licence_number      = factory.Sequence(lambda n: f"LIC{n:04d}")
    licence_expiry_date = factory.LazyFunction(timezone.now)
    licence_issuer      = "Test Gov"
    created_by          = factory.SubFactory(UserFactory)


# ── PropertyManager ───────────────────────────────────────────────────────────
# PropertyManager IS the UserProfile (same pk)
# decorator sets: request.user = UserProfile.filter(user__email=email).first()
# token must match what is sent in HTTP_AUTHORIZATION header
class PropertyManagerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyManager

    user       = factory.SubFactory(UserFactory)
    email      = factory.LazyAttribute(lambda obj: obj.user.email)
    token      = factory.Sequence(lambda n: f"pmtoken{n}")
    company    = factory.SubFactory(CompanyFactory)
    created_by = factory.SubFactory(UserFactory)


# ── Owner ─────────────────────────────────────────────────────────────────────
class OwnerFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Owner

    user       = factory.SubFactory(UserFactory)
    email      = factory.LazyAttribute(lambda obj: obj.user.email)
    token      = factory.Sequence(lambda n: f"ownertoken{n}")
    created_by = factory.SubFactory(UserFactory)


# ── Tenant ────────────────────────────────────────────────────────────────────
class TenantFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Tenant

    user       = factory.SubFactory(UserFactory)
    email      = factory.LazyAttribute(lambda obj: obj.user.email)
    token      = factory.Sequence(lambda n: f"tenanttoken{n}")
    created_by = factory.SubFactory(UserFactory)


# ── Property ──────────────────────────────────────────────────────────────────
class PropertyFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Property

    property_name  = factory.Sequence(lambda n: f"Property {n}")
    address_line_1 = "addr1"
    address_line_2 = "addr2"
    landmark       = "landmark"
    pincode        = "123456"
    no_of_blocks   = 1
    no_of_units    = 1
    pmc            = factory.SubFactory(CompanyFactory)
    created_by     = factory.SubFactory(UserFactory)


# ── PropertyBlocks ────────────────────────────────────────────────────────────
class BlockFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = PropertyBlocks

    property      = factory.SubFactory(PropertyFactory)
    block_name    = factory.Sequence(lambda n: f"Block {n}")
    no_of_floors  = 3
    no_of_parking = 2
    no_of_units   = 10
    created_by    = factory.SubFactory(UserFactory)


# ── Unit ──────────────────────────────────────────────────────────────────────
# Unit.property_block_tower → ForeignKey to PropertyBlocks (not a separate BlockTower model)
# Chain: Unit → PropertyBlocks → Property → pmc (company)
class UnitFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Unit

    property_block_tower = factory.SubFactory(BlockFactory)
    unit_name            = factory.Sequence(lambda n: f"Unit {n}")
    rent                 = 5000
    cycle                = "MONTHLY"
    created_by           = factory.SubFactory(UserFactory)

