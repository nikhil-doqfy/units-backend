from notification.models import Notification


def create_notification(user, title, message, notification_type='GENERAL',
                        reference_id=None, reference_code=None):
    """Create a notification for a specific user"""
    return Notification.objects.create(
        user=user,
        title=title,
        message=message,
        notification_type=notification_type,
        is_global=False,
        reference_id=reference_id,
        reference_code=reference_code,
        created_by=user.user if hasattr(user, "user") else None
    )


def create_global_notification(title, message, notification_type='GENERAL', created_by=None):
    """Create a global notification visible to all users"""
    from django.contrib.auth.models import User
    system_user = created_by or User.objects.filter(is_superuser=True).first()
    return Notification.objects.create(
        user=None,
        title=title,
        message=message,
        notification_type=notification_type,
        is_global=True,
        created_by=system_user
    )


# =====================================================
# CHEQUE NOTIFICATIONS
# =====================================================

def notify_cheque_bounced(user, cheque):
    create_notification(
        user=user,
        title="Cheque Bounced",
        message=f"Your cheque #{cheque.cheque_number} of amount ₹{cheque.amount} has been bounced. Please contact your bank immediately.",
        notification_type='CHEQUE_BOUNCED',
        reference_id=cheque.id,
        reference_code=cheque.cheque_number
    )


def notify_cheque_realized(user, cheque):
    create_notification(
        user=user,
        title="Payment Successful",
        message=f"Your cheque #{cheque.cheque_number} of amount AED {cheque.amount} has been realized successfully.",
        notification_type='CHEQUE_REALIZED',
        reference_id=cheque.id,
        reference_code=cheque.cheque_number
    )


def notify_payment_reminder(user, cheque):
    create_notification(
        user=user,
        title="Payment Reminder",
        message=f"Your EMI payment of AED {cheque.amount} is due soon. Please pay to avoid penalties.",
        notification_type='PAYMENT_REMINDER',
        reference_id=cheque.id,
        reference_code=cheque.cheque_number
    )


def notify_payment_success(user, cheque):
    create_notification(
        user=user,
        title="Repayment Confirmation",
        message=f"Thank you! Your payment of AED {cheque.amount} has been received successfully.",
        notification_type='PAYMENT_SUCCESS',
        reference_id=cheque.id,
        reference_code=cheque.cheque_number
    )


# =====================================================
# COMPLAINT NOTIFICATIONS
# =====================================================

def notify_complaint_created(user, complaint):
    create_notification(
        user=user,
        title="Complaint Raised",
        message=f"Your complaint {complaint.code} has been raised successfully. We will notify you once a technician is assigned.",
        notification_type='COMPLAINT',
        reference_id=complaint.id,
        reference_code=complaint.code
    )


def notify_complaint_assigned(user, complaint, technician_name):
    create_notification(
        user=user,
        title="Technician Assigned",
        message=f"{technician_name} has been assigned to your complaint {complaint.code}.",
        notification_type='COMPLAINT',
        reference_id=complaint.id,
        reference_code=complaint.code
    )


def notify_complaint_resolved(user, complaint):
    create_notification(
        user=user,
        title="Complaint Resolved",
        message=f"Your complaint {complaint.code} has been resolved. Please verify and close it.",
        notification_type='COMPLAINT',
        reference_id=complaint.id,
        reference_code=complaint.code
    )


def notify_complaint_closed(user, complaint):
    create_notification(
        user=user,
        title="Complaint Closed",
        message=f"Your complaint {complaint.code} has been verified and closed. Thank you!",
        notification_type='COMPLAINT',
        reference_id=complaint.id,
        reference_code=complaint.code
    )


# =====================================================
# DOCUMENT / LEASE NOTIFICATIONS
# =====================================================

def notify_document_expiring(user, agreement):
    from django.utils import timezone
    days_left = (agreement.end_date.date() - timezone.now().date()).days
    create_notification(
        user=user,
        title="Document Expiring Soon",
        message=f"Your document '{agreement.agreement_name}' ({agreement.code}) is expiring in {days_left} day(s). Please renew it.",
        notification_type='DOCUMENT_EXPIRY',
        reference_id=agreement.id,
        reference_code=agreement.code
    )


def notify_document_expired(user, agreement):
    create_notification(
        user=user,
        title="Document Expired",
        message=f"Your document '{agreement.agreement_name}' ({agreement.code}) has expired. Please renew it immediately.",
        notification_type='DOCUMENT_EXPIRY',
        reference_id=agreement.id,
        reference_code=agreement.code
    )


def notify_document_renewed(user, agreement):
    create_notification(
        user=user,
        title="Document Renewed",
        message=f"Your document '{agreement.agreement_name}' ({agreement.code}) has been renewed successfully.",
        notification_type='DOCUMENT_EXPIRY',
        reference_id=agreement.id,
        reference_code=agreement.code
    )


def notify_lease_expiring(user, lease):
    from django.utils import timezone
    days_left = (lease.end_date.date() - timezone.now().date()).days
    create_notification(
        user=user,
        title="Lease Expiring Soon",
        message=f"Your lease {lease.code} is expiring in {days_left} day(s). Please contact your property manager.",
        notification_type='LEASE_EXPIRY',
        reference_id=lease.id,
        reference_code=lease.code
    )
