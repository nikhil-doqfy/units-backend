from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from lease.models import Template, TemplateFields
from utilities import constants


# ── Template definitions ──────────────────────────────────────────────────────
# Each entry defines one Template and its TemplateFields.
# field keys map directly to TemplateFields model attributes.

TEMPLATES = [
    {
        "name": "Standard Lease Agreement",
        "template_path": "",           # set to actual file path when available
        "is_predefined": True,
        "description": "Standard residential lease agreement template for UAE properties.",
        "fields": [
            {
                "label_attribute": "Tenant Full Name",
                "name_attribute": "tenant_name",
                "id_attribute": "tenant_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant Emirates ID",
                "name_attribute": "tenant_emirates_id",
                "id_attribute": "tenant_emirates_id",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant Passport Number",
                "name_attribute": "tenant_passport_no",
                "id_attribute": "tenant_passport_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "Tenant Contact Number",
                "name_attribute": "tenant_contact",
                "id_attribute": "tenant_contact",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Property Name",
                "name_attribute": "property_name",
                "id_attribute": "property_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Unit Number",
                "name_attribute": "unit_number",
                "id_attribute": "unit_number",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lease Start Date",
                "name_attribute": "lease_start_date",
                "id_attribute": "lease_start_date",
                "html_tag": constants.DATE,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Lease End Date",
                "name_attribute": "lease_end_date",
                "id_attribute": "lease_end_date",
                "html_tag": constants.DATE,
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
                "label_attribute": "Security Deposit (AED)",
                "name_attribute": "security_deposit",
                "id_attribute": "security_deposit",
                "html_tag": constants.NUMBER,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Number of Cheques",
                "name_attribute": "payment_count",
                "id_attribute": "payment_count",
                "html_tag": constants.NUMBER,
                "required": True,
                "predefined_value": "1",
            },
            {
                "label_attribute": "Notice Period (months)",
                "name_attribute": "notice_period",
                "id_attribute": "notice_period",
                "html_tag": constants.NUMBER,
                "required": False,
                "predefined_value": "3",
            },
            {
                "label_attribute": "Owner Full Name",
                "name_attribute": "owner_name",
                "id_attribute": "owner_name",
                "html_tag": constants.TEXT,
                "required": True,
                "predefined_value": "",
            },
            {
                "label_attribute": "Owner Emirates ID",
                "name_attribute": "owner_emirates_id",
                "id_attribute": "owner_emirates_id",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "RERA Registration Number",
                "name_attribute": "rera_no",
                "id_attribute": "rera_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
            {
                "label_attribute": "DLD Ejari Contract Number",
                "name_attribute": "ejari_contract_no",
                "id_attribute": "ejari_contract_no",
                "html_tag": constants.TEXT,
                "required": False,
                "predefined_value": "",
            },
        ],
    },
]


class Command(BaseCommand):
    help = "Seed Template and TemplateFields records in the lease app"

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
                self.stdout.write(f"  Exists  template: {template.name}")

            for field_data in fields:
                field, f_created = TemplateFields.objects.get_or_create(
                    document_template=template,
                    name_attribute=field_data["name_attribute"],
                    defaults={
                        **field_data,
                        "created_by": user,
                    },
                )
                if f_created:
                    fields_created += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"    + Field: {field.label_attribute}")
                    )
                else:
                    self.stdout.write(f"    ~ Field: {field.label_attribute} (exists)")

            # Restore fields list so subsequent runs work correctly
            tpl_data["fields"] = fields

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {templates_created} template(s) created, "
                f"{fields_created} field(s) created."
            )
        )
