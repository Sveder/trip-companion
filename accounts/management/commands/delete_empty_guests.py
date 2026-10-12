"""T232: delete guest families that never set up a trip and did not come back.

A browser with no cookie (a crawler, too) gets a new guest family on its first family page.
Most of those never set up a trip. Such a family holds no files: clips and photos hang on a trip.
Deleting the user cascades its Contact and reminders; its analytics events keep user = NULL."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.guest import GUEST_PREFIX
from analytics.models import Event


def empty_guests(days=30, now=None):
    """Guest families older than `days` with no trip and no event in the last `days`."""
    cutoff = (now or timezone.now()) - timedelta(days=days)
    recent = Event.objects.filter(at__gte=cutoff, user__isnull=False).values("user_id")
    return (get_user_model().objects
            .filter(username__startswith=GUEST_PREFIX, email="", date_joined__lt=cutoff, trips__isnull=True)
            .exclude(id__in=recent)
            .distinct())


class Command(BaseCommand):
    help = "Delete guest families with no trip and no visit in the last N days (default 30)."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30)
        parser.add_argument("--dry-run", action="store_true", help="List the families; delete nothing.")

    def handle(self, *args, days, dry_run, **options):
        guests = list(empty_guests(days))
        if dry_run:
            for user in guests:
                self.stdout.write(f"{user.username} joined {user.date_joined:%Y-%m-%d}")
            self.stdout.write(f"would delete {len(guests)} guest families")
            return
        for user in guests:
            user.delete()
        self.stdout.write(f"{timezone.now():%Y-%m-%d %H:%M} deleted {len(guests)} guest families")
