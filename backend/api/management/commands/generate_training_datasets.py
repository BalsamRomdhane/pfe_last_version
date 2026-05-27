import json
from django.core.management.base import BaseCommand

from ...utils_dataset import generate_all_iso9001_datasets


class Command(BaseCommand):
    help = 'Generate training datasets and CSV exports for existing ISO9001 norms.'

    def handle(self, *args, **options):
        results = generate_all_iso9001_datasets()
        self.stdout.write(self.style.SUCCESS('Generated datasets for %d norms' % len(results)))
        self.stdout.write(json.dumps(results, indent=2, ensure_ascii=False))
from django.core.management.base import BaseCommand
import json

from ...utils_dataset import generate_all_iso9001_datasets


class Command(BaseCommand):
    help = 'Generate training datasets and CSV exports for all ISO9001 norms present in the DB.'

    def handle(self, *args, **options):
        results = generate_all_iso9001_datasets()
        self.stdout.write(self.style.SUCCESS('Dataset generation completed.'))
        self.stdout.write(json.dumps(results, indent=2, ensure_ascii=False))
