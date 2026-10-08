from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from reminders.logic import describe, due, send


class Command(BaseCommand):
    help = "Email each family whose next activity (or, in Japan, the next hunt thing) has waited two days or more."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="List who would get an email; send nothing.")

    def handle(self, *args, dry_run=False, **opts):
        count = 0
        for user in get_user_model().objects.filter(is_active=True).order_by("id"):
            item = due(user)
            if item is None:
                continue
            count += 1
            line = f"{user.email}: {describe(item)}"
            if dry_run:
                self.stdout.write("would send " + line)
                continue
            try:
                send(user, item)
                self.stdout.write("sent " + line)
            except Exception as exc:  # one bad address must not stop the rest
                self.stderr.write(f"FAILED {line}: {exc}")
        self.stdout.write(f"{'would send' if dry_run else 'sent'} {count}")
