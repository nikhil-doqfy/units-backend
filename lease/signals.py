"""
Django signals for the lease app.

First signals.py in units-backend (see lease/apps.py's LeaseConfig.ready()).
Registers the sole trigger mechanism for notifying Finance (units-finance)
of LeaseTransaction creates/status changes -- AD-4 in
docs/finance/ARCHITECTURE-SPINE.md. No polling, no Celery, no Redis, no
queue: this synchronous post_save receiver is the only event source.

Story 2.6 adds a second post_save receiver, on Lease itself -- units-backend's
second-ever signal. Same unconditional-fire idiom: it fires on every
Lease.save() regardless of update_fields (confirmed unreliable -- the
generic Lease PUT endpoint, and both known activation call sites
(activate_lease_view, submit_ejari_signature), save with an explicit
update_fields list that would silently exclude a naive update_fields-based
gate). Finance decides whether to post a security deposit by inspecting the
current lease_status/security_deposit values on every sync, not by diffing.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver

from lease.finance_sync import sync_lease_to_finance, sync_lease_transaction_to_finance
from lease.models import Lease, LeaseTransaction


@receiver(post_save, sender=LeaseTransaction)
def sync_lease_transaction_on_save(sender, instance, created, **kwargs):
    """
    Fires on every LeaseTransaction.save() (create and update) -- no
    filtering on which fields changed. Finance's own idempotency check
    (Story 2.2+) is what prevents duplicate postings, not this signal.
    """
    sync_lease_transaction_to_finance(instance.id)


@receiver(post_save, sender=Lease)
def sync_lease_on_save(sender, instance, created, **kwargs):
    """
    Fires on every Lease.save() (create and update) -- no filtering on
    which fields changed, and no update_fields gating (confirmed unreliable:
    the generic Lease PUT endpoint saves with update_fields=None, and the
    known activation call sites save with a partial update_fields list that
    doesn't necessarily include every field Finance cares about). Finance's
    own idempotency check (Story 2.6, keyed on (lease_id, "ACTIVATE")) is
    what prevents duplicate deposit postings, not this signal.
    """
    sync_lease_to_finance(instance.id)
