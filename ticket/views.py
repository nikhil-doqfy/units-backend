import json
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from utilities.helper_functions import (
    prepare_response,
    datetime_to_epoch,
)
from utilities import (
    constants,
    status,
)
from property_management.models import (
    LeasePropertyDetails,
)
from user_service.models import (
    UserProfile
)
from utilities.decorator import is_request_authenticated
from ticket.models import (
    Category,
    Vendor,
    Ticket,
    TicketImages,
    TicketAuditLog,
    VendorTicketBroadcast,
)


#------------------------------------Start of ticket api's---------------------------------------

#=================================================
# FETCH TICKET CATEGORIES
#=================================================
@is_request_authenticated
def fetch_ticket_categories(request):
    if request.method == "GET":
        req_data = request.GET
        ticket_category_id = req_data.get("ticket_category_id")
        page_number = req_data.get("page", 1)
        limit = req_data.get("limit", 10)

        kwargs = {}

        if ticket_category_id:
            kwargs["id"] = ticket_category_id
        
        categories = Category.objects.filter(**kwargs).order_by("-created")

        paginator = Paginator(categories, limit)
        paginated_queryset = paginator.get_page(page_number)

        category_data = [
            obj._get_category_info() for obj in paginated_queryset
        ]

        return prepare_response(
            content=category_data,
            paginator=paginated_queryset,
            total_records=paginator.count,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
        
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )
#------------------------------------Ticket api's---------------------------------------

#=================================================
# CREATE NEW TICKET API
#=================================================
@is_request_authenticated
def tenant_create_ticket(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_code = data.get("ticket_code")
        property_id = data.get("property_id")
        category_id = data.get("ticket_category_id")
        priority = data.get("priority")
        description = data.get("description")

        property = LeasePropertyDetails.objects.filter(id=property_id).first()
        if not property:
            return prepare_response(
                message=constants.PROPERTY_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        category = Category.objects.filter(id=category_id).first()
        if not category:
            return prepare_response(
                message=constants.INVALID_CATEGORY_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_profile = UserProfile.objects.filter(user=request.user).first()
        if not user_profile:
            return prepare_response(
                message=constants.USER_PROFILE_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if user_profile.user_role != constants.TENANT:
            return prepare_response(
                message=constants.ONLY_TENANT_ALLOWED,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket = Ticket.objects.create(
            ticket_code=ticket_code,
            tenant=user_profile,
            property=property,
            ticket_category=category,
            priority=priority,
            status=constants.NEW,
            description=description
        )

        ticket_data = ticket._get_ticket_info()

        return prepare_response(
            content=ticket_data,
            message=constants.TICKET_CREATED_SUCCESSFULLY,
            status=status.HTTP_201_CREATED
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )


#=================================================
# ACCESS VENDORS ASSOCIATED CATEGORY
#=================================================
@is_request_authenticated
def fetch_eligible_vendors(request):
    if request.method == "GET":
        req_data = request.GET
        category_id = req_data.get("category_id")

        if not category_id:
            return prepare_response(
                message=constants.CATEGORY_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        category = Category.objects.filter(id=category_id).first()
        if not category:
            return prepare_response(
                message=constants.INVALID_CATEGORY_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        vendors = Vendor.objects.filter(
            is_available=True,
            ticket_category=category
        ).select_related("vendor").distinct()

        vendor_data = [
            vendor._get_vendor_info() for vendor in vendors
        ]
        
        return prepare_response(
            content=vendor_data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

#=================================================
# BROADCAST TICKET TO VENDORS
#=================================================
@is_request_authenticated
def broadcast_ticket_to_vendors(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")

        ticket = Ticket.objects.filter(id=ticket_id).first()
        if not ticket:
            return prepare_response(
                message=constants.TICKET_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        vendors = Vendor.objects.filter(
            ticket_category=ticket.ticket_category,
            is_available=True
        )

        vendor_data = []

        for vendor in vendors:
            vendor_kwargs = {
                "ticket": ticket,
                "vendor":vendor,
                "status": constants.SENT,
                "responded_at": None,
                "created_by": request.user,
            }

            vendor_data.append(VendorTicketBroadcast(**vendor_kwargs))

        with transaction.atomic():
            VendorTicketBroadcast.objects.bulk_create(vendor_data)

            ticket.status = constants.BROADCASTED
            ticket.save(update_fields=["status"])

        return prepare_response(
            message=constants.TICKET_SUCCESSFULLY_BROADCASTED,
            status=status.HTTP_201_CREATED
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

#=================================================
# VENDOR ACCEPT TICKET
#=================================================
@is_request_authenticated
def vendor_accept_ticket(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")
        vendor_id = data.get("vendor_id")

        with transaction.atomic():
            ticket = Ticket.objects.filter(id=ticket_id).first()
            if not ticket:
                return prepare_response(
                    message=constants.TICKET_DOES_NOT_EXIST,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if ticket.status != constants.BROADCASTED:
                return prepare_response(
                    message=f"Ticket cannot be accepted. Current status: {ticket.status}",
                    status=status.HTTP_400_BAD_REQUEST
                )


            vendor = Vendor.objects.filter(id=vendor_id).first()
            if not vendor:
                return prepare_response(
                    message=constants.VENDOR_DOES_NOT_EXIST,
                    status=status.HTTP_400_BAD_REQUEST
                )
        
            broadcast = VendorTicketBroadcast.objects.filter(
                    ticket=ticket,
                    vendor=vendor,
                    status=constants.SENT
                ).first()

            if not broadcast:
                return prepare_response(
                    message=constants.VENDOR_NOT_ELIGIBLE_TO_ACCEPT,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
        # Assign ticket
        ticket.status = constants.ASSIGNED
        ticket.assigned_vendor = vendor
        ticket.assigned_at = timezone.now()
        ticket.save(update_fields=["status", "assigned_vendor", "assigned_at"])

        # Update broadcast status
        broadcast.status = constants.ACCEPTED
        broadcast.responded_at = timezone.now()
        broadcast.save(update_fields=["status", "responded_at"])

        VendorTicketBroadcast.objects.filter(
                ticket=ticket
            ).exclude(vendor=vendor).update(
                status=constants.EXPIRED,
            responded_at=timezone.now()
        )


        assigned_data={
            "status": constants.ASSIGNED,
            "assigned_vendor": str(vendor.id)
        }


        return prepare_response(
            content=assigned_data,
            message=constants.TICKET_ASSIGNED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

#=================================================
# VENDOR REJECT TICKET
#=================================================
@is_request_authenticated
def vendor_reject_ticket(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")
        reason = data.get("reason")

        if not ticket_id:
            return prepare_response(
                message=constants.TICKET_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            vendor = Vendor.objects.filter(user=request.user).first()
            if not vendor:
                return prepare_response(
                    message=constants.VENDOR_DOES_NOT_EXIST,
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            ticket = Ticket.objects.filter(id=ticket_id).first()
            if not ticket:
                return prepare_response(
                    message=constants.TICKET_DOES_NOT_EXIST, 
                    status=status.HTTP_400_BAD_REQUEST
                )

            broadcast = VendorTicketBroadcast.objects.filter(
                ticket=ticket,
                vendor=vendor,
                status=constants.SENT
            ).first()
            if not broadcast:
                return prepare_response(
                    message=constants.VENDOR_NOT_ELIGIBLE_TO_REJECT,
                    status=status.HTTP_400_BAD_REQUEST
                )

            broadcast.status = constants.REJECTED
            broadcast.responded_at = timezone.now()
            broadcast.save(update_fields=["status", "responded_at"])


        vendor_ticket_data = {
            "ticket_id": str(broadcast.ticket.id),
            "status": constants.REJECTED,
            "vendor": str(vendor.id),
            "reason": reason
        },

        return prepare_response(
            content=vendor_ticket_data,
            message=constants.TICKET_REJECTED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

# =================================================
# VENDOR SUBMIT WORK PROOF
# =================================================
@is_request_authenticated
def vendor_submit_work_proof(request):
    if request.method == "POST":
        ticket_id = request.POST.get("ticket_id")
        file = request.FILES.get("file")

        ticket = Ticket.objects.filter(id=ticket_id).first()
        if not ticket:
            return prepare_response(
                message=constants.TICKET_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )

        TicketImages.objects.create(
            ticket=ticket,
            ticket_images=file,
            uploaded_by=ticket.assigned_vendor
        )

        ticket.status = constants.PENDING_APPROVAL
        ticket.work_submitted_at = timezone.now()
        ticket.save()

        return prepare_response(
            message=constants.WORK_SUBMITTED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

# =================================================
# TENANT APPROVES WORK
# =================================================
@is_request_authenticated
def tenant_approve_ticket(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")

        if not ticket_id:
            return prepare_response(
                message=constants.TICKET_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        with transaction.atomic():
            ticket = Ticket.objects.filter(
                id=ticket_id,
                tenant__user=request.user,
                status=constants.PENDING_APPROVAL
            ).first()
            if not ticket:
                return prepare_response(
                    message=constants.TICKET_DOES_NOT_EXIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            ticket.status = constants.CLOSED
            ticket.closed_at = timezone.now()
            ticket.save(update_fields=["status", "closed_at"])

        return prepare_response(
            message=constants.TICKET_CLOSED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

#=================================================
# TENANT REJECT TICKET
#=================================================
@is_request_authenticated
def tenant_reject_ticket(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")
        reason = data.get("reason", "")

        with transaction.atomic():
            ticket = Ticket.objects.filter(
                id=ticket_id,
                tenant__user=request.user,
                status=constants.PENDING_APPROVAL
            ).first()
            if not ticket:
                return prepare_response(
                    message=constants.TICKET_DOES_NOT_EXIST,
                    status=status.HTTP_400_BAD_REQUEST
                )

            ticket.status = constants.REJECTED
            ticket.save(update_fields=["status"])

            TicketAuditLog.objects.create(
                ticket=ticket,
                action="Tenant rejected work",
                metadata={"reason": reason},
                actor_type=constants.TENANT
            )

        return prepare_response(
            content={
                "ticket_id": str(ticket.id),
                "status": constants.REJECTED,
                "assigned_vendor": str(ticket.assigned_vendor.id) if ticket.assigned_vendor else None,
                "reason": reason
            },
            message=constants.TICKET_REJECTED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )
    
#=================================================
# TICKET STATUS LOOKUP (WhatsApp Query)
#=================================================
@is_request_authenticated
def ticket_status_lookup(request):
    if request.method == "GET":
        req_data = request.GET
        ticket_id = req_data.get("ticket_id")

        if not ticket_id:
            return prepare_response(
                message=constants.TICKET_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket = Ticket.objects.filter(id=ticket_id).first()
        if not ticket:
            return prepare_response(
                message=constants.TICKET_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_data = {
            "status": ticket.status,
            "vendor": ticket.assigned_vendor.vendor.user.first_name if ticket.assigned_vendor else None,
            "last_updated": datetime_to_epoch(ticket.modified)
        }
        return prepare_response(
            content=response_data,
            message=constants.TICKET_STATUS_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )


#------------------------------------End of ticket api's---------------------------------------
