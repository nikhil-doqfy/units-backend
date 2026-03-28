# complaint/serializers.py
from utilities.helper_functions import fetch_s3_presigned_url
from complaint.utility import get_ticket_aging

def serialize_complaint(c):
    """
    Serialize a Complaint object into a JSON-ready dictionary.
    Includes assigned technicians, appointment slots, images, and rating.
    """
    return {
        "id": c.id,
        "code": c.code,
        "unit": {
            "id": c.unit.id,
            "unit_name": c.unit.unit_name,
            "property_name": c.unit.property_block_tower.property.property_name
                             if c.unit.property_block_tower else None,
        },
        "raised_by": {
            "id": c.raised_by.id,
            "name": f"{c.raised_by.user.first_name} {c.raised_by.user.last_name}".strip(),
            "profile_image": c.raised_by.profile_image,
        },
        "assigned_to": [
            {
                "id": sp.id,
                "name": sp.name,
                "phone": sp.phone,
                "avg_rating": str(sp.avg_rating),
            } for sp in c.assigned_to.all()
        ],
        "service_type": {
            "key": c.service_type,
            "value": c.get_service_type_display()
        },
        "priority": {
            "key": c.priority,
            "value": c.get_priority_display()
        },
        "description": c.description,
        "locality": c.locality,
        "status": {
            "key": c.status,
            "value": c.get_status_display()
        },
        "is_broadcasted": c.is_broadcasted,
        "broadcasted_at": int(c.broadcasted_at.timestamp()) if c.broadcasted_at else None,
        "attempt_count": c.attempt_count,
        "current_appointment": {
            "id": c.current_appointment.id,
            "status": c.current_appointment.status,
            "note": c.current_appointment.note,
            "slots": [
                {
                    "id": s.id,
                    "proposed_time": int(s.proposed_time.timestamp()) if s.proposed_time else None,
                    "is_selected": s.is_selected,
                    "selected_at": int(s.selected_at.timestamp()) if s.selected_at else None,
                } for s in c.current_appointment.slots.all()
            ]
        } if c.current_appointment else None,
        "work_started_at": int(c.work_started_at.timestamp()) if c.work_started_at else None,
        "work_completed_at": int(c.work_completed_at.timestamp()) if c.work_completed_at else None,
        "work_duration": str(c.work_duration()) if c.work_duration() else None,
        "issue_closed_on": int(c.issue_closed_on.timestamp()) if c.issue_closed_on else None,
        "ticket_aging": get_ticket_aging(c.created),
        "images": [
            {
                "id": img.id,
                "file_name": img.file_name,
                "url": fetch_s3_presigned_url(img.image_path, file_name=img.file_name),
            } for img in c.complaint_images.all()
        ],
        "images_count": c.complaint_images.count(),
        "rating": {
            "rating": c.rating.rating,
            "feedback": c.rating.feedback,
        } if hasattr(c, 'rating') and c.rating else None,
        "created": int(c.created.timestamp()) if c.created else None,
    }