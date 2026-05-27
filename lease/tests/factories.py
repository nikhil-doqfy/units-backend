"""
factories.py  — central test-data factory for the project.

Usage:
    from lease.tests.factories import (
        UserFactory, CompanyFactory, PropertyManagerFactory,
        PropertyFactory, BlockFactory, UnitFactory,
        TenantFactory, OwnerFactory, LeaseFactory,
    )

All factories use django.test.TestCase-compatible helpers — no
third-party library (factory_boy) required.
"""

from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.utils import timezone
from property.models import PropertyManagmentCompany, Property, PropertyBlocks, Unit
from user_service.models import PropertyManager, Tenant, Owner

# Counter so every factory call produces a unique username / email / number
_counters: dict = {}


def _seq(name: str) -> int:
    _counters[name] = _counters.get(name, 0) + 1
    return _counters[name]


def reset_sequences():
    """Call in tearDown / setUp if you want deterministic IDs across tests."""
    _counters.clear()

# UserFactory
def UserFactory(
    *,
    first_name="Test",
    last_name="User",
    email=None,
    password="testpass123",
    **kwargs,
) -> User:
    n = _seq("user")
    email = email or f"user{n}@test.com"
    return User.objects.create_user(
        username=email,
        email=email,
        first_name=first_name,
        last_name=last_name,
        password=password,
        **kwargs,
    )
# CompanyFactory
def CompanyFactory(*, created_by: User, name=None, **kwargs) -> PropertyManagmentCompany:
    n = _seq("company")
    return PropertyManagmentCompany.objects.create(
        name=name or f"Test PMC {n}",
        address_line_1="123 Main St",
        address_line_2="Suite 1",
        licence_number=f"LIC{n:04d}",
        licence_expiry_date=timezone.now() + timedelta(days=365),
        licence_issuer="Gov Authority",
        created_by=created_by,
        **kwargs,
    )

# PropertyManagerFactory
def PropertyManagerFactory(
    *,
    company: PropertyManagmentCompany,
    created_by: User,
    user: User = None,
    token: str = None,
    **kwargs,
) -> PropertyManager:
    n = _seq("pm")
    if user is None:
        user = UserFactory(
            first_name="PM",
            last_name=f"User{n}",
            email=f"pm{n}@test.com",
        )
    token = token or f"pmtoken{n}"
    return PropertyManager.objects.create(
        user=user,
        email=user.email,
        token=token,
        company=company,
        created_by=created_by,
        **kwargs,
    )

# PropertyFactory
def PropertyFactory(
    *,
    company: PropertyManagmentCompany,
    created_by: User,
    name: str = None,
    **kwargs,
) -> Property:
    n = _seq("property")
    return Property.objects.create(
        property_name=name or f"Test Property {n}",
        address_line_1="1 Property Lane",
        address_line_2="",
        landmark="Near Park",
        pincode=f"{100000 + n}",
        no_of_blocks=1,
        no_of_units=5,
        pmc=company,
        created_by=created_by,
        **kwargs,
    )

# BlockFactory
def BlockFactory(
    *,
    property: Property,
    created_by: User,
    no_of_floors: int = 5,
    no_of_parking: int = 10,
    name: str = None,
    **kwargs,
) -> PropertyBlocks:
    n = _seq("block")
    return PropertyBlocks.objects.create(
        property=property,
        block_name=name or f"Block {n}",
        no_of_units=5,
        no_of_floors=no_of_floors,
        no_of_parking=no_of_parking,
        created_by=created_by,
        **kwargs,
    )
# UnitFactory
def UnitFactory(
    *,
    block: PropertyBlocks,
    created_by: User,
    name: str = None,
    rent: int = 5000,
    cycle: str = "MONTHLY",
    **kwargs,
) -> Unit:
    n = _seq("unit")
    return Unit.objects.create(
        property_block_tower=block,
        unit_name=name or f"Unit {n}",
        rent=rent,
        cycle=cycle,
        created_by=created_by,
        **kwargs,
    )

# TenantFactory
def TenantFactory(
    *,
    created_by: User,
    user: User = None,
    email: str = None,
    first_name: str = "Alice",
    last_name: str = "Smith",
    contact_number: str = "9876543210",
    passport_expiry: datetime = None,
    visa_expiry: datetime = None,
    **kwargs,
) -> Tenant:
    n = _seq("tenant")
    email = email or f"tenant{n}@test.com"
    if user is None:
        user = UserFactory(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
    return Tenant.objects.create(
        user=user,
        created_by=created_by,
        email=email,
        contact_number=contact_number,
        emirate_id=f"784-1990-{n:07d}-1",
        nationality="AE",
        passport_number=f"AB{n:07d}",
        passport_expiry_datetime=passport_expiry or timezone.make_aware(datetime(2027, 6, 30)),
        visa_number=f"VIS{n:05d}",
        visa_expiry_datetime=visa_expiry or timezone.make_aware(datetime(2026, 12, 31)),
        **kwargs,
    )

# OwnerFactory
def OwnerFactory(
    *,
    created_by: User,
    user: User = None,
    email: str = None,
    first_name: str = "Bob",
    last_name: str = "Owner",
    **kwargs,
) -> Owner:
    n = _seq("owner")
    email = email or f"owner{n}@test.com"
    if user is None:
        user = UserFactory(
            first_name=first_name,
            last_name=last_name,
            email=email,
        )
    return Owner.objects.create(
        user=user,
        created_by=created_by,
        email=email,
        contact_number="1234567890",
        emirate_id=f"784-2000-{n:07d}-1",
        nationality="AE",
        passport_number=f"OW{n:07d}",
        passport_expiry_datetime=datetime(2028, 1, 1),
        visa_expiry_datetime=datetime(2027, 6, 1),
        license_expiry_date=datetime(2026, 3, 1).date(),
        **kwargs,
    )

# LeaseFactory
def LeaseFactory(
    *,
    unit: Unit,
    tenant: Tenant,
    created_by: User,
    lease_status: str = "DRAFT",
    is_active: bool = True,
    start_date=None,
    end_date=None,
    rent: int = 4000,
    **kwargs,
):
    
    from lease.models import Lease

    n = _seq("lease")
    return Lease.objects.create(
        unit=unit,
        tenant=tenant,
        created_by=created_by,
        lease_status=lease_status,
        is_active=is_active,
        start_date=start_date or timezone.make_aware(datetime(2024, 1, 1)),
        end_date=end_date or timezone.make_aware(datetime(2024, 12, 31)),
        rent=rent,
        **kwargs,
    )

# Convenience: build the full stack (company → pm → property → block → unit)
# in one call — useful for lease tests.
def build_standard_stack():
    """
    Returns a dict with all commonly needed objects pre-created.

        stack = build_standard_stack()
        stack["pm"]       # PropertyManager (logged-in user)
        stack["unit"]     # Unit ready for leasing
        stack["tenant"]   # Tenant
        stack["token"]    # auth token string  e.g. "pmtoken1"

    """
    admin = UserFactory(first_name="Admin", last_name="User", email="admin@stack.com")
    company = CompanyFactory(created_by=admin)

    pm_user = UserFactory(first_name="PM", last_name="Manager", email="pm@stack.com")
    n = _seq("stack_token")
    token = f"stacktoken{n}"
    pm = PropertyManagerFactory(
        company=company,
        created_by=admin,
        user=pm_user,
        token=token,
    )

    prop = PropertyFactory(company=company, created_by=admin)
    block = BlockFactory(property=prop, created_by=admin)
    unit = UnitFactory(block=block, created_by=admin)
    tenant = TenantFactory(created_by=pm_user)

    return {
        "admin": admin,
        "company": company,
        "pm": pm,
        "pm_user": pm_user,
        "token": token,
        "property": prop,
        "block": block,
        "unit": unit,
        "tenant": tenant,
    }