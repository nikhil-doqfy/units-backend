import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.conf import settings
from lease.models import Template, TemplateField
from utilities import constants

TEMPLATE_PATH = os.path.join(settings.MEDIA_ROOT, "pre_defined_templates", "lease_agreement.html")


# ── Template definitions ──────────────────────────────────────────────────────
# Each entry defines one Template and its TemplateField.
# field keys map directly to TemplateField model attributes.

TEMPLATES = [
    {
        "name": "Unified Ejari Tenancy Contract",
        "template_path": TEMPLATE_PATH,
        "is_predefined": True,
        "description": "Dubai Land Department unified Ejari tenancy contract template.",
        "fields": [
            # ── Contract header ──────────────────────────────────────────
            {
                "label_attribute": "Contract Date",
                "name_attribute": "contract_date",
                "id_attribute": "contract_date",
                "html_tag": constants.DATE,
                "required": True,
                "predefined_value": "",
            },
            # ── Owner / Lessor ───────────────────────────────────────────
            {
                "label_attribute": "Owner's Name",
                "name_attribute": "owner_name",
                "id_attribute": "owner_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's Name",
                "name_attribute": "lessor_name",
                "id_attribute": "lessor_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's Emirates ID",
                "name_attribute": "lessor_emirates_id",
                "id_attribute": "lessor_emirates_id",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's License No. (Company)",
                "name_attribute": "lessor_license_no",
                "id_attribute": "lessor_license_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's Licensing Authority (Company)",
                "name_attribute": "lessor_licensing_authority",
                "id_attribute": "lessor_licensing_authority",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's Email",
                "name_attribute": "lessor_email",
                "id_attribute": "lessor_email",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lessor's Phone",
                "name_attribute": "lessor_phone",
                "id_attribute": "lessor_phone",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            # ── Tenant ──────────────────────────────────────────────────
            {
                "label_attribute": "Tenant's Name",
                "name_attribute": "tenant_name",
                "id_attribute": "tenant_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant's Emirates ID",
                "name_attribute": "tenant_emirates_id",
                "id_attribute": "tenant_emirates_id",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant's License No. (Company)",
                "name_attribute": "tenant_license_no",
                "id_attribute": "tenant_license_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant's Licensing Authority (Company)",
                "name_attribute": "tenant_licensing_authority",
                "id_attribute": "tenant_licensing_authority",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant's Email",
                "name_attribute": "tenant_email",
                "id_attribute": "tenant_email",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant's Phone",
                "name_attribute": "tenant_phone",
                "id_attribute": "tenant_phone",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            # ── Property ────────────────────────────────────────────────
            {
                "label_attribute": "Plot No.",
                "name_attribute": "plot_no",
                "id_attribute": "plot_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Makani No.",
                "name_attribute": "makani_no",
                "id_attribute": "makani_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Building Name",
                "name_attribute": "building_name",
                "id_attribute": "building_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Property No.",
                "name_attribute": "property_no",
                "id_attribute": "property_no",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Property Type",
                "name_attribute": "property_type",
                "id_attribute": "property_type",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Property Area (s.m)",
                "name_attribute": "property_area",
                "id_attribute": "property_area",
                "html_tag": constants.NUMBER,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Location",
                "name_attribute": "location",
                "id_attribute": "location",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Premises No. (DEWA)",
                "name_attribute": "dewa_premises_no",
                "id_attribute": "dewa_premises_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            # ── Contract ────────────────────────────────────────────────
            {
                "label_attribute": "Contract Start Date",
                "name_attribute": "contract_start_date",
                "id_attribute": "contract_start_date",
                "html_tag": constants.DATE,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Contract End Date",
                "name_attribute": "contract_end_date",
                "id_attribute": "contract_end_date",
                "html_tag": constants.DATE,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Contract Value (AED)",
                "name_attribute": "contract_value",
                "id_attribute": "contract_value",
                "html_tag": constants.NUMBER,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Annual Rent (AED)",
                "name_attribute": "annual_rent",
                "id_attribute": "annual_rent",
                "html_tag": constants.NUMBER,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Security Deposit Amount (AED)",
                "name_attribute": "security_deposit",
                "id_attribute": "security_deposit",
                "html_tag": constants.NUMBER,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Mode of Payment",
                "name_attribute": "mode_of_payment",
                "id_attribute": "mode_of_payment",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "Cheque",
            },
            # ── Additional terms ─────────────────────────────────────────
            {
                "label_attribute": "Additional Term 1",
                "name_attribute": "additional_term_1",
                "id_attribute": "additional_term_1",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Additional Term 2",
                "name_attribute": "additional_term_2",
                "id_attribute": "additional_term_2",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Additional Term 3",
                "name_attribute": "additional_term_3",
                "id_attribute": "additional_term_3",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Additional Term 4",
                "name_attribute": "additional_term_4",
                "id_attribute": "additional_term_4",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Additional Term 5",
                "name_attribute": "additional_term_5",
                "id_attribute": "additional_term_5",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed Template and TemplateField records in the lease app"

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            default="nikhil@doqfy.in",
            help="Email of the user to set as created_by (default: nikhil@doqfy.in)",
        )

    def handle(self, *args, **options):
        email = options["user"]
        user = User.objects.filter(email=email).first()
        if not user:
            raise CommandError(f"User with email '{email}' not found.")

        templates_created = 0
        fields_created = 0

        for tpl_data in TEMPLATES:
            fields = tpl_data.pop("fields")

            template, t_created = Template.objects.get_or_create(
                name=tpl_data["name"],
                defaults={
                    **tpl_data,
                    "created_by": user,
                },
            )

            if t_created:
                templates_created += 1
                self.stdout.write(self.style.SUCCESS(f"  Created template: {template.name}"))
            else:
                # Update template_path in case it was previously empty
                Template.objects.filter(pk=template.pk).update(
                    template_path=tpl_data["template_path"],
                    is_predefined=tpl_data["is_predefined"],
                    description=tpl_data["description"],
                )
                self.stdout.write(f"  Updated template: {template.name}")

            # Remove stale fields no longer in the definition
            current_names = {f["name_attribute"] for f in fields}
            deleted, _ = TemplateField.objects.filter(
                template=template
            ).exclude(name_attribute__in=current_names).delete()
            if deleted:
                self.stdout.write(self.style.WARNING(f"    - Removed {deleted} stale field(s)"))

            for field_data in fields:
                field, f_created = TemplateField.objects.get_or_create(
                    template=template,
                    name_attribute=field_data["name_attribute"],
                    defaults={**field_data, "created_by": user},
                )
                if f_created:
                    fields_created += 1
                    self.stdout.write(self.style.SUCCESS(f"    + Field: {field.label_attribute}"))
                else:
                    # Update label / html_tag / required / predefined_value
                    TemplateField.objects.filter(pk=field.pk).update(
                        label_attribute=field_data["label_attribute"],
                        id_attribute=field_data["id_attribute"],
                        html_tag=field_data["html_tag"],
                        required=field_data["required"],
                        predefined_value=field_data["predefined_value"],
                    )
                    self.stdout.write(f"    ~ Field: {field_data['label_attribute']} (updated)")

            # Restore fields list so subsequent runs work correctly
            tpl_data["fields"] = fields

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {templates_created} template(s) created, "
                f"{fields_created} field(s) created."
            )
        )
