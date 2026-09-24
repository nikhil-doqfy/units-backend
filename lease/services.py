"""
Shared lease-creation logic used by both `lease_view` (lease/views.py) and
the new Proposal/Hold conversion endpoint (`confirm_hold_and_proceed`,
lead/views.py) -- factored out here rather than duplicated so the two stay
in sync (Dubai Leasing Management Flow, Phase 1).
"""
from lease.models import Lease


def get_active_lease_for_tenant(tenant):
    """Return the tenant's existing ACTIVE lease, if any, else None."""
    return Lease.objects.filter(
        tenant=tenant,
        lease_status="ACTIVE",
        is_active=True,
    ).first()
