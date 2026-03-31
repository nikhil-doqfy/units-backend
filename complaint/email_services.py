import logging
from django.template.loader import render_to_string
from django.utils import timezone
from utilities.helper_functions import send_ses_email
from complaint.utility import format_work_duration

logger = logging.getLogger(__name__)


# ==============================
# COMMON
# ==============================

def format_datetime(dt):
    return dt.strftime('%A %d %b %Y, %I:%M %p') if dt else None


# ==============================
# CORE EMAIL FUNCTION
# ==============================

def send_complaint_email(
    email,
    subject,
    user_name,
    title,
    message,
    complaint,
    extra_message=None,
    technician_name=None,
    technician_phone=None,
    slots=None,
    scheduled_time=None,
    rating=None,
    feedback=None,
):
    if not email:
        return

    try:
        context = {
            'title': title,
            'user_name': user_name,
            'message': message,
            'complaint_id': complaint.code,
            'service_type': complaint.get_service_type_display(),
            'description': complaint.description,
            'locality': getattr(complaint, 'locality', None),
            'priority': complaint.get_priority_display(),
            'status': complaint.get_status_display(),
            'work_started_at': format_datetime(getattr(complaint, 'work_started_at', None)),
            'work_completed_at': format_datetime(getattr(complaint, 'work_completed_at', None)),
            'issue_closed_on': format_datetime(getattr(complaint, 'issue_closed_on', None)),
            'work_duration': format_work_duration(complaint.work_duration()) if hasattr(complaint, 'work_duration') else None,
            'technician_name': technician_name,
            'technician_phone': technician_phone,
            'extra_message': extra_message,
            'slots': slots,
            'scheduled_time': scheduled_time,
            'rating': rating,
            'feedback': feedback,
        }

        body_html = render_to_string('email_templates/complaint_email.html', context)

        send_ses_email(
            to_email=email,
            subject=subject,
            body_text=message,
            body_html=body_html
        )

        logger.info(f"✅ Email sent to {email}")

    except Exception as e:
        import traceback
        logger.error(f"❌ Email error: {str(e)}")
        traceback.print_exc()


# ==============================
# Complaint Created → resident only
# ==============================

def email_complaint_created(complaint):
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Complaint Raised - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Complaint Raised Successfully",
        message="Your complaint has been raised successfully. We will notify you once a technician is assigned.",
        complaint=complaint,
    )


# ==============================
# Complaint Broadcasted → resident + all technicians (with slots)
# ==============================

def email_complaint_broadcasted(complaint, providers_count):
    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Finding Technician - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Finding Technician",
        message=f"We are finding a {complaint.get_service_type_display()} technician for your complaint.",
        complaint=complaint,
        extra_message=f"Broadcasted to technicians. You will be notified once someone accepts."
    )

    # ── Build slots list ───────────────────────────────────────────
    slots = []
    if complaint.current_appointment:
        for slot in complaint.current_appointment.slots.all():
            slots.append(format_datetime(timezone.localtime(slot.proposed_time)))

    # ── All technicians (with slots) ───────────────────────────────
    broadcasts = complaint.broadcasts.filter(
        is_accepted=False,
        is_rejected=False,
        is_expired=False
    )
    for broadcast in broadcasts:
        if broadcast.service_provider.email:
            send_complaint_email(
                email=broadcast.service_provider.email,
                subject=f"New Job Available - {complaint.code}",
                user_name=broadcast.service_provider.name,
                title="New Job Available",
                message=f"New {complaint.get_service_type_display()} job available in {complaint.locality or 'your area'}.",
                complaint=complaint,
                extra_message="Please accept or decline this job. Available slots are listed below.",
                slots=slots
            )


# ==============================
# Accepted → resident + technician (with confirmed slot)
# ==============================

def email_complaint_accepted(complaint, service_provider, slot=None):
    scheduled_time = format_datetime(timezone.localtime(slot.proposed_time)) if slot else None

    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Technician Assigned - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Technician Assigned",
        message=f"{service_provider.name} has accepted your complaint.",
        complaint=complaint,
        technician_name=service_provider.name,
        technician_phone=service_provider.phone,
        scheduled_time=scheduled_time,
        extra_message=f"Confirmed visit time: {scheduled_time}" if scheduled_time else None
    )

    # ── Technician ─────────────────────────────────────────────────
    if service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Job Accepted - {complaint.code}",
            user_name=service_provider.name,
            title="Job Accepted Successfully",
            message=f"You have accepted complaint {complaint.code}.",
            complaint=complaint,
            scheduled_time=scheduled_time,
            extra_message=f"Your confirmed visit time: {scheduled_time}" if scheduled_time else None
        )


# ==============================
# Declined → resident + technician + new technicians (with slots)
# ==============================

def email_complaint_declined(complaint, service_provider):
    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Finding New Technician - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Finding New Technician",
        message=f"{service_provider.name} has declined your complaint. We are finding another technician.",
        complaint=complaint,
        extra_message="You will be notified once a new technician accepts."
    )

    # ── Technician who declined ────────────────────────────────────
    if service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Job Declined - {complaint.code}",
            user_name=service_provider.name,
            title="Job Declined",
            message=f"You have declined complaint {complaint.code}.",
            complaint=complaint,
        )

    # ── Build slots for new broadcasts ────────────────────────────
    slots = []
    if complaint.current_appointment:
        for slot in complaint.current_appointment.slots.all():
            slots.append(format_datetime(timezone.localtime(slot.proposed_time)))

    # ── New technicians who got re-broadcast (with slots) ──────────
    new_broadcasts = complaint.broadcasts.filter(
        is_accepted=False,
        is_rejected=False,
        is_expired=False
    )
    for broadcast in new_broadcasts:
        if broadcast.service_provider.email:
            send_complaint_email(
                email=broadcast.service_provider.email,
                subject=f"New Job Available - {complaint.code}",
                user_name=broadcast.service_provider.name,
                title="New Job Available",
                message=f"New {complaint.get_service_type_display()} job available in {complaint.locality or 'your area'}.",
                complaint=complaint,
                extra_message="Please accept or decline. Available slots are listed below.",
                slots=slots
            )


# ==============================
# No Technician Available → resident only
# ==============================

def email_no_technician_available(complaint):
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"No Technician Available - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="No Technician Available",
        message="Unfortunately no technicians are available for your complaint at this time.",
        complaint=complaint,
        extra_message="Please contact PMC for assistance."
    )


# ==============================
# Slot Selected → resident + technician
# ==============================

def email_slot_selected(complaint, slot):
    service_provider = complaint.assigned_to.first()
    formatted_time = format_datetime(timezone.localtime(slot.proposed_time))

    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Appointment Confirmed - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Appointment Confirmed",
        message="Technician has confirmed the visit slot.",
        complaint=complaint,
        technician_name=service_provider.name if service_provider else None,
        technician_phone=service_provider.phone if service_provider else None,
        scheduled_time=formatted_time,
        extra_message=f"Confirmed visit time: {formatted_time}"
    )

    # ── Technician ─────────────────────────────────────────────────
    if service_provider and service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Appointment Confirmed - {complaint.code}",
            user_name=service_provider.name,
            title="Appointment Confirmed",
            message="You have confirmed the visit slot.",
            complaint=complaint,
            scheduled_time=formatted_time,
            extra_message=f"Your confirmed visit time: {formatted_time}"
        )


# ==============================
# Work Started → resident + technician
# ==============================

def email_work_started(complaint):
    service_provider = complaint.assigned_to.first()
    name = service_provider.name if service_provider else "Technician"
    phone = service_provider.phone if service_provider else None

    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Work Started - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Work Started",
        message=f"{name} has started work on your complaint.",
        complaint=complaint,
        technician_name=name,
        technician_phone=phone,
        extra_message=f"Work started at: {format_datetime(complaint.work_started_at)}"
    )

    # ── Technician ─────────────────────────────────────────────────
    if service_provider and service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Work Started - {complaint.code}",
            user_name=service_provider.name,
            title="Work Started",
            message=f"You have started work on complaint {complaint.code}.",
            complaint=complaint,
            extra_message=f"Work started at: {format_datetime(complaint.work_started_at)}"
        )


# ==============================
# Work Completed → resident + technician (clean duration)
# ==============================

def email_work_completed(complaint):
    service_provider = complaint.assigned_to.first()
    name = service_provider.name if service_provider else "Technician"
    phone = service_provider.phone if service_provider else None
    duration = format_work_duration(complaint.work_duration())

    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Work Completed - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Work Completed",
        message=f"{name} has completed work on your complaint.",
        complaint=complaint,
        technician_name=name,
        technician_phone=phone,
        extra_message=f"Work duration: {duration}. Please verify the work and close the complaint."
    )

    # ── Technician ─────────────────────────────────────────────────
    if service_provider and service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Work Completed - {complaint.code}",
            user_name=service_provider.name,
            title="Work Completed",
            message=f"You have completed work on complaint {complaint.code}.",
            complaint=complaint,
            extra_message=f"Work duration: {duration}. Waiting for owner verification."
        )


# ==============================
# Complaint Closed → resident + technician (with rating + duration)
# ==============================

def email_complaint_closed(complaint, rating=None, feedback=None):
    service_provider = complaint.assigned_to.first()
    duration = format_work_duration(complaint.work_duration())

    # ── Resident ───────────────────────────────────────────────────
    send_complaint_email(
        email=complaint.raised_by.user.email,
        subject=f"Complaint Closed - {complaint.code}",
        user_name=complaint.raised_by.user.first_name,
        title="Complaint Closed",
        message="Your complaint has been verified and closed successfully.",
        complaint=complaint,
        extra_message=f"Work duration: {duration}. Thank you for your patience.",
        rating=rating,
        feedback=feedback,
    )

    # ── Technician ─────────────────────────────────────────────────
    if service_provider and service_provider.email:
        send_complaint_email(
            email=service_provider.email,
            subject=f"Complaint Closed - {complaint.code}",
            user_name=service_provider.name,
            title="Complaint Closed",
            message=f"Complaint {complaint.code} has been verified and closed by the owner.",
            complaint=complaint,
            extra_message=f"Work duration: {duration}. Great work! Thank you.",
            rating=rating,
            feedback=feedback,
        )