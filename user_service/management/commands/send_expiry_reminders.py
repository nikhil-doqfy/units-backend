from django.core.management.base import BaseCommand
from user_service.tasks import send_agreement_expiry_reminders


class Command(BaseCommand):
    help = 'Send daily expiry reminders for agreements'

    def handle(self, *args, **options):
        result = send_agreement_expiry_reminders()
        self.stdout.write(self.style.SUCCESS(result))