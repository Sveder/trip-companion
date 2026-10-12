from django.core.management.base import BaseCommand

from content_admin.exporter import export_country
from content_admin.loader import CONTENT_DIR


class Command(BaseCommand):
    help = "Write the database content back to content/<country>/*.yaml (comments in the files stay)."

    def add_arguments(self, parser):
        parser.add_argument("countries", nargs="*", default=["japan"])
        parser.add_argument("--out", default=str(CONTENT_DIR), help="Content folder (default: the repo's content/).")

    def handle(self, *args, countries, out, **options):
        for country in countries:
            changed = export_country(country, out, log=self.stdout.write)
            self.stdout.write(self.style.SUCCESS(f"{country}: {len(changed)} files changed"))
