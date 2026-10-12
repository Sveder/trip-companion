from django.core.management.base import BaseCommand

from accounts.views import make_account


class Command(BaseCommand):
    help = "Give the account of one email the admin (superuser). It signs in with the email code, no password."

    def add_arguments(self, parser):
        parser.add_argument("email")

    def handle(self, *args, email, **options):
        user = make_account(email.strip().lower())
        user.is_staff = user.is_superuser = True
        user.save(update_fields=["is_staff", "is_superuser"])
        self.stdout.write(self.style.SUCCESS(f"{user.email} is a superuser"))
