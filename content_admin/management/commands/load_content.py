from django.core.management.base import BaseCommand

from content_admin.loader import load_country


class Command(BaseCommand):
    help = "Load content/<country>/*.yaml into the database. Modules changed in the admin are skipped."

    def add_arguments(self, parser):
        parser.add_argument("countries", nargs="*", default=["japan"])
        parser.add_argument("--force", action="store_true", help="Also load modules changed in the admin.")
        parser.add_argument("--dir", default=None, help="Content folder (default: the repo's content/).")

    def handle(self, *args, countries, force, dir, **options):
        log = self.stdout.write if options["verbosity"] > 1 else None
        for country in countries:
            n = load_country(country, content_dir=dir, force=force, log=self._warn_skips(log))
            self.stdout.write(self.style.SUCCESS(f"{country}: {n} modules loaded"))

    def _warn_skips(self, log):
        def write(msg):
            if msg.startswith("skip"):
                self.stderr.write(self.style.WARNING(msg))
            elif log:
                log(msg)
        return write
