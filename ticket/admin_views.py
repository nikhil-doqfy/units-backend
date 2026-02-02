import json
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q
from utilities.helper_functions import (
    prepare_response,
)
from utilities import (
    constants,
    status,
)
from utilities.decorator import is_request_authenticated
from ticket.models import (
    Vendor,
    Ticket,
    WhatsAppMessage,
)

#------------------------------------Start of admin fow api's---------------------------------------

#=================================================
# ADMIN FLOW API'S
#=================================================
@is_request_authenticated
def admin_ticket_list(request):
    if request.method == "GET":
        req_data = request.GET
        ticket_id = req_data.get("ticket_id")
        search_text = req_data.get('search_text', '')
        page_number = req_data.get("page", 1)
        limit = req_data.get("limit", 10)

        kwargs = {}

        if ticket_id:
            kwargs["id"] = ticket_id
        
        tickets = Ticket.objects.filter(**kwargs).order_by("-created")

        if len(search_text) > 2:
            condition = Q()
            search_words = search_text.split()
            for word in search_words:
                condition &= Q(name__icontains=word)
            tickets = tickets.filter(condition)

        paginator = Paginator(tickets, limit)
        paginated_queryset = paginator.get_page(page_number)

        ticket_data = [
            obj._get_ticket_info() for obj in paginated_queryset
        ]

        return prepare_response(
            content=ticket_data,
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
        

@is_request_authenticated
def admin_ticket_detail(request):
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
            
        ticket_data = ticket._get_ticket_info()
        
        return prepare_response(
            content=ticket_data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )


@is_request_authenticated
def admin_force_assign_vendor(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")
        vendor_id = data.get("vendor_id")

        if not ticket_id:
            return prepare_response(
                message=constants.TICKET_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not vendor_id:
            return prepare_response(
                message=constants.VENDOR_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ticket = Ticket.objects.filter(id=ticket_id).first()
        if not ticket:
            return prepare_response(
                message=constants.TICKET_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        vendor = Vendor.objects.filter(id=vendor_id).first()
        if not vendor:
            return prepare_response(
                message=constants.VENDOR_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket.assigned_vendor = vendor
        ticket.status = constants.ASSIGNED
        ticket.assigned_at = timezone.now()
        ticket.save()

        return prepare_response(
            message=constants.VENDOR_FORCE_ASSIGNED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )


@is_request_authenticated
def admin_force_ticket_close(request):
    if request.method == "POST":
        data = json.loads(request.body)
        ticket_id = data.get("ticket_id")
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
        
        ticket.status = constants.CLOSED
        ticket.save(update_fields=["status"])
        
        return prepare_response(
            message=constants.TICKET_CLOSED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )
        

@is_request_authenticated
def admin_vendor_list(request):
    if request.method == "GET":
        req_data = request.GET
        vendor_id = req_data.get("vendor_id")
        page_number = req_data.get("page", 1)
        limit = req_data.get("limit", 10)

        kwargs = {}

        if vendor_id:
            kwargs["id"] = vendor_id
        
        vendors = Vendor.objects.filter(**kwargs).order_by("-created")

        paginator = Paginator(vendors, limit)
        paginated_queryset = paginator.get_page(page_number)

        ticket_data = [
            obj._get_vendor_info() for obj in paginated_queryset
        ]

        return prepare_response(
            content=ticket_data,
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
        

@is_request_authenticated
def admin_vendor_detail(request):
    if request.method == "GET":
        req_data = request.GET
        vendor_id = req_data.get("vendor_id")
        
        if not vendor_id:
            return prepare_response(
                message=constants.VENDOR_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        vendor = Vendor.objects.filter(id=vendor_id).first()
        if not vendor:
            return prepare_response(
                message=constants.VENDOR_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        vendor_data = vendor._get_vendor_info()

        return prepare_response(
            content=vendor_data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_400_BAD_REQUEST
    )



@is_request_authenticated
def admin_toggle_vendor_availability(request):
    if request.method == "PATCH":
        data = json.loads(request.body)
        vendor_id = data.get("vendor_id")
        
        if not vendor_id:
            return prepare_response(
                message=constants.VENDOR_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
            
        vendor = Vendor.objects.filter(id=vendor_id).first()
        if not vendor:
            return prepare_response(
                message=constants.VENDOR_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            ) 

        vendor.is_available = not vendor.is_available
        vendor.save(update_fields=["is_available"])
        
        if vendor.is_available:
            return prepare_response(
                message=constants.VENDOR_IS_AVAILABLE,
                status=status.HTTP_200_OK
            )

        else:
            return prepare_response(
                message=constants.VENDOR_NOT_AVAILABLE,
                status=status.HTTP_200_OK
            )
            
    else:
        return prepare_response(
           message=constants.INVALID_REQUEST_METHOD,
           status=status.HTTP_400_BAD_REQUEST
        )
        

@is_request_authenticated
def admin_sla_overview(request):
    if request.method == "GET":
        
        ticket_data = {
            "total_tickets": Ticket.objects.count(),
            "open_tickets": Ticket.objects.exclude(status=constants.CLOSED).count(),
            "sla_breached": Ticket.objects.filter(status=constants.EXPIRED).count()
        }

        return prepare_response(
            content=ticket_data,
            message=constants.DATA_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    else:
        return prepare_response(
           message=constants.INVALID_REQUEST_METHOD,
           status=status.HTTP_400_BAD_REQUEST
        )
        
        
@is_request_authenticated
def admin_message_log(request):
    if request.method == "GET":
        req_data = request.GET
        page_number = req_data.get("page", 1)
        limit = req_data.get("limit", 10)
        status_filter = req_data.get("status")
        message_type = req_data.get("type")
        recipient = req_data.get("recipient")
        date_from = req_data.get("from_date")
        date_to = req_data.get("to_date")

        messages = WhatsAppMessage.objects.all().order_by("-created_at")

        if status_filter:
            messages = messages.filter(status=status_filter)
        if message_type:
            messages = messages.filter(message_type=message_type)
        if recipient:
            messages = messages.filter(recipient__icontains=recipient)
        if date_from:
            messages = messages.filter(created_at__gte=date_from)
        if date_to:
            messages = messages.filter(created_at__lte=date_to)

        paginator = Paginator(messages, limit)
        paginated_queryset = paginator.get_page(page_number)

        message_data = [msg._get_message_info() for msg in paginated_queryset]

        return prepare_response(
            content=message_data,
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


@is_request_authenticated
def admin_resend_message(request):
    if request.method == "POST":
        data = json.loads(request.body)
        message_id = data.get("message_id")

        if not message_id:
            return prepare_response(
                message=constants.MESSAGE_ID_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        message = WhatsAppMessage.objects.filter(id=message_id).first()
        if not message:
            return prepare_response(
                message=constants.MESSAGE_DOES_NOT_EXIST,
                status=status.HTTP_400_BAD_REQUEST
            )

        if message.status == constants.SENT:
            return prepare_response(
                message=constants.MESSAGE_ALREADY_SENT,
                status=status.HTTP_200_OK
            )

        # success = send_whatsapp_message(
        #     recipient=message.recipient,
        #     content=message.content
        # )

        # message.status = "sent" if success else "failed"
        message.retries = (message.retries or 0) + 1
        message.save(update_fields=["status", "retries"])

        return prepare_response(
            content={
                "message_id": str(message.id),
                "status": message.status,
                "retries": message.retries
            },
            message=constants.MESSAGE_RESEND_ATTEMPTED,
            status=status.HTTP_200_OK
        )
    
    else:
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_400_BAD_REQUEST
        )

#------------------------------------End of admin fow api's---------------------------------------
