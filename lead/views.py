import json
from django.shortcuts import render
from utilities.decorator import is_request_authenticated
from utilities.helper_functions import prepare_response
from utilities import constants, status
from user_service.models import UserProfile
from property_management.models import PropertyManagmentCompany, Unit
from lead.models import Lead
# Create your views here.


@is_request_authenticated
def create_lead(request):
    if request.method == "POST":
        body = json.loads(request.body)
        name           = body.get("name")
        email          = body.get("email")
        contact_number = body.get("contact_number")
        status_value   = body.get("status")
        platform       = body.get("platform")
        lead_type      = body.get("lead_type")
        unit_id        = body.get("unit")
        referred_by_id = body.get("referred_by")

        if not name:
            return prepare_response(
                message=constants.NAME_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        if not platform:
            return prepare_response(
                message=constants.PLATFORM_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )
        if not lead_type:
            return prepare_response(
                message=constants.LEAD_TYPE_REQUIRED,
                status=status.HTTP_400_BAD_REQUEST
            )

        company = PropertyManagmentCompany.objects.filter(company_user=request.user,is_active=True).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        unit = None
        if unit_id:
            unit = Unit.objects.filter(id=unit_id,is_active=True ).first()
            if not unit:
                return prepare_response(
                    message=constants.UNIT_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

        tenant = None
        if email:
            tenant = UserProfile.objects.filter(user__email=email,is_active=True).first()

        referred_by = None
        if referred_by_id:
            referred_by = UserProfile.objects.filter(id=referred_by_id,is_active=True).first()
            if not referred_by:
                return prepare_response(
                    message=constants.REFERRED_USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )

        Lead.objects.create(
            name=name,
            email=email,
            contact_number=contact_number,
            status=status_value or constants.INTERESTED,
            platform=platform,
            lead_type=lead_type,
            unit=unit,
            tenant=tenant,
            referred_by=referred_by,
            company=company,
            created_by=request.user.user
        )

        return prepare_response(
            message=constants.LEAD_CREATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "GET":

        company = PropertyManagmentCompany.objects.filter(company_user=request.user,is_active=True).first()

        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead_id = request.GET.get("lead_id")

        if lead_id:
            leads = Lead.objects.filter(lead_id=lead_id,company=company,is_active=True)
        else:
            leads = Lead.objects.filter(company=company,is_active=True)

        data = [{
            "id": lead.id,
            "lead_id": lead.lead_id,
            "name": lead.name,
            "email": lead.email,
            "contact_number": lead.contact_number,
            "status": lead.status,
            "platform": lead.platform,
            "lead_type": lead.lead_type,
            "created": lead.created.strftime("%m/%d/%Y %H:%M") if lead.created else None,
        } for lead in leads]

        return prepare_response(
            content=data,
            message=constants.LEAD_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
    elif request.method == "PUT":
        body = json.loads(request.body)
        lead_id = request.GET.get("lead_id")

        if not lead_id:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        company = PropertyManagmentCompany.objects.filter(company_user=request.user,is_active=True).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead = Lead.objects.filter(lead_id=lead_id, company=company,is_active=True).first()
        if not lead:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead.name = body.get("name", lead.name)
        lead.email = body.get("email", lead.email)
        lead.contact_number = body.get("contact_number", lead.contact_number)
        lead.status = body.get("status", lead.status)
        lead.platform = body.get("platform", lead.platform)
        lead.lead_type = body.get("lead_type", lead.lead_type)

        unit_id = body.get("unit")
        if unit_id:
            unit = Unit.objects.filter(id=unit_id,is_active=True).first()
            if not unit:
                return prepare_response(
                    message=constants.UNIT_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            lead.unit = unit

        referred_by_id = body.get("referred_by")
        if referred_by_id:
            referred_by = UserProfile.objects.filter(id=referred_by_id,is_active=True).first()
            if not referred_by:
                return prepare_response(
                    message=constants.REFERRED_USER_NOT_FOUND,
                    status=status.HTTP_404_NOT_FOUND
                )
            lead.referred_by = referred_by

        lead.save()

        return prepare_response(
            message=constants.LEAD_UPDATED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

    elif request.method == "DELETE":

        lead_id = request.GET.get("lead_id")

        if not lead_id:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        company = PropertyManagmentCompany.objects.filter(company_user=request.user,is_active=True).first()

        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead = Lead.objects.filter(lead_id=lead_id,company=company).first()

        if not lead:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead.delete()

        return prepare_response(
            message=constants.LEAD_DELETED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )

@is_request_authenticated
def convert_lead_to_tenant(request):
    if request.method == "GET":
        lead_id = request.GET.get("lead_id")

        if not lead_id:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_400_BAD_REQUEST
            )

        company = PropertyManagmentCompany.objects.filter(
            company_user=request.user,
            is_active=True
        ).first()
        if not company:
            return prepare_response(
                message=constants.COMPANY_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        lead = Lead.objects.filter(
            lead_id=lead_id,
            company=company,
            is_active=True
        ).first()
        if not lead:
            return prepare_response(
                message=constants.LEAD_NOT_FOUND,
                status=status.HTTP_404_NOT_FOUND
            )

        data = {
            "lead_id": lead.lead_id,
            "platform": lead.platform,
            "tenant_details": {
                "name": lead.name,
                "email": lead.email,
                "contact": lead.contact_number,
                "status": lead.get_status_display(),
            },

            "property_details": {
                "property_name": lead.unit.property.property_name if lead.unit and lead.unit.property else None,
                "block_tower": lead.unit.property_block_tower.property_name if lead.unit and lead.unit.property_block_tower else None,
                "unit": lead.unit.unit_name if lead.unit else None,
                "rent": f"AED{lead.unit.rent}" if lead.unit and lead.unit.rent else None,
            } if lead.unit else None,
        }

        return prepare_response(
            content=data,
            message=constants.LEAD_FETCHED_SUCCESSFULLY,
            status=status.HTTP_200_OK
        )
