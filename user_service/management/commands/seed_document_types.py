from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from user_service.models import DocumentType
from utilities import constants


DOCUMENT_TYPES = [
    # ── Property Manager documents ──────────────────────────────────────────
    {"name": "Emirates ID",        "section": constants.PROPERTY_MANAGER},
    {"name": "UAE Residence Visa", "section": constants.PROPERTY_MANAGER},
    {"name": "DLD Certificate",    "section": constants.PROPERTY_MANAGER},

    # ── Property documents ──────────────────────────────────────────────────
    {"name": "Floor Plan",   "section": constants.PROPERTY},
    {"name": "PMC Document", "section": constants.PROPERTY},
    {"name": "Other",        "section": constants.PROPERTY},

    # ── Unit documents ──────────────────────────────────────────────────
    {"name": "Floor Plan",   "section": constants.UNIT},
    {"name": "PMC Document", "section": constants.UNIT},
    {"name": "Other",        "section": constants.UNIT},

    # ── Tenant documents ────────────────────────────────────────────────
    {"name": "Emirates ID",        "section": constants.TENANT},
    {"name": "UAE Residence Visa", "section": constants.TENANT},
    {"name": "Passport",           "section": constants.TENANT},
    {"name": "Bank Statement",     "section": constants.TENANT},
    {"name": "Employment Proof",   "section": constants.TENANT},
    {"name": "Visa",               "section": constants.TENANT},
    {"name": "Other",              "section": constants.TENANT},
]


class Command(BaseCommand):
    help = "Seed DocumentType records for Property Manager, Property, Unit and Tenant sections"

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

        created_count = 0
        for entry in DOCUMENT_TYPES:
            obj, created = DocumentType.objects.get_or_create(
                name=entry["name"],
                section=entry["section"],
                defaults={"created_by": user},
            )
            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  Created: [{entry['section']}] {entry['name']}")
                )
            else:
                self.stdout.write(f"  Exists:  [{entry['section']}] {entry['name']}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone — {created_count} new record(s) created, "
                f"{len(DOCUMENT_TYPES) - created_count} already existed."
            )
        )
