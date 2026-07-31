"""
Org-isolation helpers.

get_pmc_ids_for_user(user_profile) -> list[int]
    Returns all PropertyManagmentCompany IDs the given user is allowed to access.
    Call this once per request; pass the result into every queryset filter.

OrgScopedQuerySet
    Base QuerySet mixin that adds .for_user(user_profile).
    Add a custom manager on each model to narrow which pmc_ids field to filter on.
"""

from django.db.models import QuerySet


def get_pmc_ids_for_user(user_profile):
    from user_service.models import PropertyManager, Owner, Tenant
    from property.models import PMCPMMapping, Property

    # PropertyManager — use all mapped PMCs, fallback to primary company
    pm = PropertyManager.objects.filter(pk=user_profile.pk).select_related('company').first()
    if pm:
        mapped = list(PMCPMMapping.objects.filter(pm=pm).values_list('pmc_id', flat=True))
        return mapped if mapped else [pm.company_id]

    # Owner — all PMCs whose properties contain units they own
    owner = Owner.objects.filter(pk=user_profile.pk).first()
    if owner:
        via_blocks = list(
            Property.objects.filter(
                property_blocks__block_towers__unit_owners__owner=owner
            ).values_list('pmc_id', flat=True).distinct()
        )
        via_direct = list(
            Property.objects.filter(
                units__unit_owners__owner=owner
            ).values_list('pmc_id', flat=True).distinct()
        )
        return list(set(via_blocks + via_direct))

    # Tenant — all PMCs whose properties contain units they have an active lease on
    tenant = Tenant.objects.filter(pk=user_profile.pk).first()
    if tenant:
        via_blocks = list(
            Property.objects.filter(
                property_blocks__block_towers__leases__tenant=tenant,
                property_blocks__block_towers__leases__is_active=True,
            ).values_list('pmc_id', flat=True).distinct()
        )
        via_direct = list(
            Property.objects.filter(
                units__leases__tenant=tenant,
                units__leases__is_active=True,
            ).values_list('pmc_id', flat=True).distinct()
        )
        return list(set(via_blocks + via_direct))

    return []


class OrgScopedQuerySet(QuerySet):
    """
    Subclass this and set `_pmc_field` to the dotted ORM path from this model to
    PropertyManagmentCompany.id. Then call .for_user(user_profile) in views.

    Example:
        class LeaseQuerySet(OrgScopedQuerySet):
            _pmc_field = 'unit__parent_property__pmc_id'
    """
    _pmc_field = None

    def for_user(self, user_profile):
        if self._pmc_field is None:
            raise NotImplementedError('Set _pmc_field on the QuerySet subclass.')
        pmc_ids = get_pmc_ids_for_user(user_profile)
        if not pmc_ids:
            return self.none()
        return self.filter(**{f'{self._pmc_field}__in': pmc_ids})
