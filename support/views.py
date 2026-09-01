import json
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from user_service.models import PropertyManager, Tenant
from property.models import PMCPMMapping
from lease.models import Lease
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import constants
from .models import SupportTicket, SupportMessage
from django.db.models import Q

# from notification.utils import notify_support_ticket_created


@is_request_authenticated
def support_ticket_api(request):
    user = request.user

    if request.method == "POST":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return prepare_response(
                message="Invalid JSON body",
                status=status.HTTP_400_BAD_REQUEST
            )
        description = body.get("description", "").strip()
        if not description:
            return prepare_response(
                message="Description is required",
                status=status.HTTP_400_BAD_REQUEST
            )
        tenant = Tenant.objects.filter(pk=user.pk).first()
        if not tenant:
            return prepare_response(
                message="Only tenant can create support ticket",
                status=status.HTTP_403_FORBIDDEN
            )

        lease = (
            Lease.objects
            .filter(tenant=tenant)
            .select_related(
                "unit__parent_property",
                "unit__property_block_tower__property"
            )
            .order_by("-id")
            .first()
        )

        if not lease:
            return prepare_response(
                message="No lease found for tenant",
                status=status.HTTP_404_NOT_FOUND
            )

        unit = lease.unit
        if not unit:
            return prepare_response(
                message="Unit not found for tenant",
                status=status.HTTP_404_NOT_FOUND
            )

        if unit.parent_property:
            pmc = unit.parent_property.pmc
        elif unit.property_block_tower and unit.property_block_tower.property:
            pmc = unit.property_block_tower.property.pmc
        else:
            pmc = None

        if not pmc:
            return prepare_response(
                message="Property management company not found",
                status=status.HTTP_404_NOT_FOUND
            )

        if not PMCPMMapping.objects.filter(pmc=pmc).exists():
            return prepare_response(
                message="Property manager not assigned to this PMC",
                status=status.HTTP_404_NOT_FOUND
            )

        ticket = SupportTicket.objects.create(
            tenant=tenant,
            description=description,
            status=constants.OPEN,
            created_by=user.user
        )

        pm_mappings = (
            PMCPMMapping.objects
            .filter(pmc=pmc, is_active=True)
            .select_related("pm")
        )

        # for mapping in pm_mappings:
        #     notify_support_ticket_created(
        #         user=mapping.pm,
        #         ticket=ticket
        #     )

        return prepare_response(
            content={
                "id": ticket.id,
                "description": ticket.description,
                "status": ticket.status,
                "created": ticket.created,
                "modified": ticket.modified,
            },
            message="Support ticket created successfully",
            status=status.HTTP_201_CREATED
        )

    elif request.method == "GET":
        ticket_id = request.GET.get("ticket_id")
        search = request.GET.get("search", "").strip()
        support_status = request.GET.get("support_status", "").strip().upper()
        valid_statuses = {value for value, label in constants.SUPPORT_STATUS_CHOICES}
        if support_status and support_status not in valid_statuses:
            return prepare_response( message="Invalid ticket status", status=status.HTTP_400_BAD_REQUEST)
        tenant = Tenant.objects.filter(pk=user.pk).first()

        if ticket_id:
            ticket = (
                SupportTicket.objects
                .filter(pk=ticket_id)
                .select_related("tenant__user")
                .first()
            )

            if not ticket:
                return prepare_response(
                    message="Support ticket not found",
                    status=status.HTTP_404_NOT_FOUND
                )

            if tenant:
                if ticket.tenant_id != tenant.pk:
                    return prepare_response(
                        message="You are not authorized to view this ticket",
                        status=status.HTTP_403_FORBIDDEN
                    )
            else:
                pm_profile = PropertyManager.objects.filter(pk=user.pk).first()
                if not pm_profile:
                    return prepare_response(
                        message="User is not authorized",
                        status=status.HTTP_403_FORBIDDEN
                    )

                pmc_ids = (
                    PMCPMMapping.objects
                    .filter(pm=pm_profile)
                    .values_list("pmc_id", flat=True)
                )

                if not ticket.tenant.pmc.filter(id__in=pmc_ids).exists():
                    return prepare_response(
                        message="You are not authorized to view this ticket",
                        status=status.HTTP_403_FORBIDDEN
                    )

            message_data = []
            messages = (
                ticket.messages
                .select_related("sender")
                .order_by("created")
            )

            for msg in messages:
                message_data.append({
                    "id": msg.id,
                    "sender_id": msg.sender_id,
                    "message": msg.message,
                    "attachment": msg.attachment,
                    "created": msg.created,
                    "modified": msg.modified,
                })

            return prepare_response(
                content={
                    "id": ticket.id,
                    "description": ticket.description,
                    "status": ticket.status,
                    "tenant": {
                        "id": ticket.tenant_id,
                        "name": (
                            f"{ticket.tenant.user.first_name} "
                            f"{ticket.tenant.user.last_name}".strip()
                            if ticket.tenant and ticket.tenant.user
                            else None
                        )
                    },
                    "created": ticket.created,
                    "modified": ticket.modified,
                    "messages": message_data,
                },
                status=status.HTTP_200_OK
            )

        if tenant:
            tickets = (
                SupportTicket.objects
                .filter(tenant=tenant)
                .select_related("tenant__user")
                .order_by("-created")
            )
        else:
            pm_profile = PropertyManager.objects.filter(pk=user.pk).first()
            if not pm_profile:
                return prepare_response(
                    message="User is not authorized",
                    status=status.HTTP_403_FORBIDDEN
                )

            pmc_ids = (
                PMCPMMapping.objects
                .filter(pm=pm_profile)
                .values_list("pmc_id", flat=True)
            )

            tickets = (
                SupportTicket.objects
                .filter(tenant__pmc__id__in=pmc_ids)
                .select_related("tenant__user")
                .distinct()
                #.order_by("-created")
            )
        # Status filter
        if support_status:
            tickets = tickets.filter(status=support_status)
            
        # Search filter
        if search:
            tickets = tickets.filter(
                Q(description__icontains=search) |
                Q(tenant__user__first_name__icontains=search) |
                Q(tenant__user__last_name__icontains=search)
            )

        tickets = tickets.order_by("-created")
        ticket_data = []

        for ticket in tickets:
            ticket_data.append({
                "id": ticket.id,
                "description": ticket.description,
                "status": ticket.status,
                "tenant": {
                    "id": ticket.tenant_id,
                    "name": (
                        f"{ticket.tenant.user.first_name} "
                        f"{ticket.tenant.user.last_name}".strip()
                        if ticket.tenant and ticket.tenant.user
                        else None
                    )
                },
                "created": ticket.created,
                "modified": ticket.modified,
            })

        return prepare_response(
            content=ticket_data,
            status=status.HTTP_200_OK
        )

    elif request.method == "PUT":
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return prepare_response(
                message="Invalid JSON body",
                status=status.HTTP_400_BAD_REQUEST
            )

        ticket_id = body.get("ticket_id")
        ticket_status = body.get("status", "").strip().upper()

        if not ticket_id:
            return prepare_response(
                message="ticket_id is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        if not ticket_status:
            return prepare_response(
                message="status is required",
                status=status.HTTP_400_BAD_REQUEST
            )

        valid_statuses = {value for value, label in constants.SUPPORT_STATUS_CHOICES}

        if ticket_status not in valid_statuses:
            return prepare_response(
                message="Invalid ticket status",
                status=status.HTTP_400_BAD_REQUEST
            )

        pm_profile = PropertyManager.objects.filter(pk=user.pk).first()
        if not pm_profile:
            return prepare_response(
                message="Only property manager can update ticket status",
                status=status.HTTP_403_FORBIDDEN
            )

        pmc_ids = (
            PMCPMMapping.objects
            .filter(pm=pm_profile)
            .values_list("pmc_id", flat=True)
        )

        ticket = (
            SupportTicket.objects
            .filter(
                pk=ticket_id,
                tenant__pmc__id__in=pmc_ids
            )
            .first()
        )

        if not ticket:
            return prepare_response(
                message="Support ticket not found",
                status=status.HTTP_404_NOT_FOUND
            )

        ticket.status = ticket_status
        ticket.save()

        return prepare_response(
            content={
                "id": ticket.id,
                "description": ticket.description,
                "status": ticket.status,
                "created": ticket.created,
                "modified": ticket.modified,
            },
            message="Support ticket status updated successfully",
            status=status.HTTP_200_OK
        )

    return prepare_response(
        message=constants.INVALID_REQUEST_METHOD,
        status=status.HTTP_405_METHOD_NOT_ALLOWED
    )


@is_request_authenticated
@csrf_exempt
def support_ticket_reply_api(request):
    if request.method != "POST":
        return prepare_response(
            message=constants.INVALID_REQUEST_METHOD,
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )

    user = request.user

    try:
        body = json.loads(request.body)
    except json.JSONDecodeError:
        return prepare_response(
            message="Invalid JSON body",
            status=status.HTTP_400_BAD_REQUEST
        )

    ticket_id = body.get("ticket_id")
    message = body.get("message", "").strip()
    attachment = body.get("attachment")

    if not ticket_id:
        return prepare_response(
            message="ticket_id is required",
            status=status.HTTP_400_BAD_REQUEST
        )

    if not message:
        return prepare_response(
            message="message is required",
            status=status.HTTP_400_BAD_REQUEST
        )

    ticket = SupportTicket.objects.filter(pk=ticket_id).first()
    if not ticket:
        return prepare_response(
            message="Support ticket not found",
            status=status.HTTP_404_NOT_FOUND
        )

    tenant = Tenant.objects.filter(pk=user.pk).first()

    if tenant:
        if ticket.tenant_id != tenant.pk:
            return prepare_response(
                message="You are not authorized to reply to this ticket",
                status=status.HTTP_403_FORBIDDEN
            )
    else:
        pm_profile = PropertyManager.objects.filter(pk=user.pk).first()

        if not pm_profile:
            return prepare_response(
                message="User is not authorized",
                status=status.HTTP_403_FORBIDDEN
            )

        pmc_ids = (
            PMCPMMapping.objects
            .filter(pm=pm_profile)
            .values_list("pmc_id", flat=True)
        )

        if not ticket.tenant.pmc.filter(id__in=pmc_ids).exists():
            return prepare_response(
                message="You are not authorized to reply to this ticket",
                status=status.HTTP_403_FORBIDDEN
            )

    support_message = SupportMessage.objects.create(
        ticket=ticket,
        sender=user,
        message=message,
        attachment=attachment,
        created_by=user.user
    )

    return prepare_response(
        content={
            "id": support_message.id,
            "ticket_id": ticket.id,
            "sender_id": support_message.sender_id,
            "message": support_message.message,
            "attachment": support_message.attachment,
            "created": support_message.created,
            "modified": support_message.modified,
        },
        message="Message sent successfully",
        status=status.HTTP_201_CREATED
    )