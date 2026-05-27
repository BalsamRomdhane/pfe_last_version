"""
Django management command to train compliance analysis models.
"""

from django.core.management.base import BaseCommand
from ml.services import compliance_service


class Command(BaseCommand):
    help = 'Train compliance analysis models for ISO standards'

    def add_arguments(self, parser):
        parser.add_argument(
            '--standard',
            type=str,
            default='ISO9001',
            help='ISO standard to train models for (default: ISO9001)'
        )

        parser.add_argument(
            '--force',
            action='store_true',
            help='Force retraining even if models exist'
        )

    def handle(self, *args, **options):
        standard = options['standard']
        force = options['force']

        self.stdout.write(
            self.style.SUCCESS(f'Starting training for {standard}...')
        )

        try:
            result = compliance_service.retrain_models(standard)

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Training completed for {standard}')
                )
                self.stdout.write(f'Message: {result["message"]}')
            else:
                self.stdout.write(
                    self.style.ERROR(f'❌ Training failed for {standard}')
                )
                self.stdout.write(f'Error: {result["message"]}')

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Training error: {str(e)}')
            )

        self.stdout.write(
            self.style.SUCCESS('Training process completed.')
        )