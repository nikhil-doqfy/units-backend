from django.utils import timezone
from complaint.models import ComplaintBroadcast, ServiceProvider


def get_ticket_aging(created):
    if not created:
        return None
    delta = timezone.now() - created
    total_seconds = int(delta.total_seconds())
    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return f"{days}d, {hours}hr, {minutes}min, {seconds}sec"


def format_work_duration(duration):
    """Convert timedelta to clean format like 6 min 50 sec"""
    if not duration:
        return None
    total_seconds = int(duration.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    if hours > 0:
        return f"{hours}hr {minutes}min {seconds}sec"
    elif minutes > 0:
        return f"{minutes}min {seconds}sec"
    else:
        return f"{seconds}sec"


def get_excluded_providers(complaint):
    return list(
        ComplaintBroadcast.objects.filter(
            complaint=complaint,
            is_rejected=True
        ).values_list('service_provider_id', flat=True)
    )


def get_broadcast_expiry():
    return timezone.now() + timezone.timedelta(hours=2)


def auto_broadcast(complaint, company, exclude_provider_ids=None):
    if exclude_provider_ids is None:
        exclude_provider_ids = get_excluded_providers(complaint)

    ComplaintBroadcast.objects.filter(
        complaint=complaint,
        is_accepted=False
    ).delete()

    # ── Same locality first ────────────────────────────────────
    providers = ServiceProvider.objects.filter(
        company=company,
        service_types__name=complaint.service_type,
        localities__locality=complaint.locality,
        is_available=True,
        is_active=True
    ).exclude(id__in=exclude_provider_ids).distinct()

    # ── Fallback to all ────────────────────────────────────────
    if not providers.exists():
        providers = ServiceProvider.objects.filter(
            company=company,
            service_types__name=complaint.service_type,
            is_available=True,
            is_active=True
        ).exclude(id__in=exclude_provider_ids).distinct()

    if not providers.exists():
        return 0

    expiry = get_broadcast_expiry()

    for provider in providers:
        ComplaintBroadcast.objects.create(
            complaint=complaint,
            service_provider=provider,
            is_priority=provider.avg_rating >= 4.0,
            priority_score=provider.avg_rating,
            expires_at=expiry,
            created_by=complaint.created_by
        )

    complaint.is_broadcasted = True
    complaint.broadcasted_at = timezone.now()
    complaint.broadcast_expiry = expiry
    complaint.attempt_count += 1
    complaint.save()

    return providers.count()


def auto_assign_best_technician(complaint, company, exclude_provider_ids=None):
    if exclude_provider_ids is None:
        exclude_provider_ids = get_excluded_providers(complaint)

    return ServiceProvider.objects.filter(
        company=company,
        service_types__name=complaint.service_type,
        is_available=True,
        is_active=True
    ).exclude(id__in=exclude_provider_ids).order_by('-avg_rating').first()