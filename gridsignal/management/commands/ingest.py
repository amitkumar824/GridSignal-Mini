from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from gridsignal.ingest import ingest_csv

class Command(BaseCommand):
    help = "Ingest an incident CSV batch into SQLite and update correlated alerts"

    def add_arguments(self, parser):
        parser.add_argument(
            'csv_path',
            nargs='?',
            type=str,
            default=str(settings.SEED_CSV_PATH),
            help="Path to the incident CSV file (defaults to data/seed_incidents.csv)"
        )

    def handle(self, *args, **options):
        csv_path = options['csv_path']
        self.stdout.write(self.style.NOTICE(f"Starting ingestion from: {csv_path}"))
        try:
            stats = ingest_csv(csv_path)
            self.stdout.write(self.style.SUCCESS("\n--- INGESTION SUMMARY ---"))
            for k, v in stats.items():
                self.stdout.write(f"  {k}: {v}")
        except Exception as e:
            raise CommandError(f"Ingestion failed: {e}")
