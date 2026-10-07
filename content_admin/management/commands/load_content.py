from django.core.management.base import BaseCommand

from content_admin.loader import load_country


class Command(BaseCommand):
    help = "Load content/<country>/*.yaml into the database."

    def add_arguments(self, parser):
        parser.add_argument("countries", nargs="*", default=["japan"])

    def handle(self, *args, countries, **options):
        for country in countries:
            n = load_country(country)
            self.stdout.write(self.style.SUCCESS(f"{country}: {n} modules loaded"))
