"""
Management command: sync_all_datasets

Single entry point to:
1. Rebuild TrainingSample from RuleTrainingSample (all norms)
2. Check coherence: if RuleTrainingSample > 0 but TrainingSample = 0
   for a norm, auto-generate synthetic data if needed.
3. Print a coherence report.

Usage:
    python manage.py sync_all_datasets
    python manage.py sync_all_datasets --generate-if-empty
    python manage.py sync_all_datasets --generate-if-empty --min-samples 100
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from api.models import Norme, RuleTrainingSample, TrainingSample
from ml.dataset_builder import sync_training_samples_from_evidence


class Command(BaseCommand):
    help = 'Sync all training datasets and print coherence report.'

    def add_arguments(self, parser):
        parser.add_argument('--generate-if-empty', action='store_true',
                            help='Generate synthetic data if a norm has 0 samples')
        parser.add_argument('--min-samples', type=int, default=100,
                            help='Minimum samples per norm before triggering generation')

    def handle(self, *args, **options):
        generate = options['generate_if_empty']
        min_samples = options['min_samples']

        self.stdout.write('=== SYNC ALL DATASETS ===\n')

        # Step 1: Sync TrainingSample from RuleTrainingSample
        self.stdout.write('Step 1: Syncing TrainingSample from RuleTrainingSample...')
        result = sync_training_samples_from_evidence()
        self.stdout.write(f"  Created={result['created']} Updated={result['updated']} Documents={result['documents']}\n")

        # Step 2: Coherence report per norm
        self.stdout.write('Step 2: Coherence report\n')
        self.stdout.write(f"{'Norm':<30} {'RuleTS':>8} {'Approved':>10} {'Rejected':>10} {'Rules':>7} {'Coverage':>10}")
        self.stdout.write('-' * 80)

        needs_generation = []

        for norm in Norme.objects.prefetch_related('rules').all():
            rts_total = RuleTrainingSample.objects.filter(norm=norm).count()
            rts_approved = RuleTrainingSample.objects.filter(norm=norm, label='approved').count()
            rts_rejected = RuleTrainingSample.objects.filter(norm=norm, label='rejected').count()
            rules_total = norm.rules.count()
            rules_covered = (
                RuleTrainingSample.objects
                .filter(norm=norm, label__in=['approved', 'rejected'])
                .values('rule_id').distinct().count()
            )
            coverage_pct = round(rules_covered / max(rules_total, 1) * 100, 1)

            self.stdout.write(
                f"{norm.name:<30} {rts_total:>8} {rts_approved:>10} {rts_rejected:>10} "
                f"{rules_total:>7} {coverage_pct:>9.1f}%"
            )

            if rts_total < min_samples:
                needs_generation.append((norm, rts_total))

        self.stdout.write('')

        # Step 3: Generate if needed
        if generate and needs_generation:
            self.stdout.write('Step 3: Generating synthetic data for under-populated norms...')
            for norm, current_count in needs_generation:
                name_upper = norm.name.upper()
                if 'ISO27001' in name_upper or '27001' in name_upper:
                    self._call_generate('ISO27001', min_samples)
                elif 'TISAX' in name_upper:
                    self._call_generate('TISAX', min_samples)
                elif 'ISO9001' in name_upper or '9001' in name_upper:
                    self._call_generate_iso9001(min_samples - current_count)
                else:
                    self.stdout.write(f"  No generator for norm '{norm.name}' — skipping.")

            # Re-sync after generation
            self.stdout.write('\nRe-syncing after generation...')
            sync_training_samples_from_evidence()
        elif needs_generation:
            self.stdout.write(
                f'\n⚠ {len(needs_generation)} norm(s) have < {min_samples} samples. '
                'Run with --generate-if-empty to auto-generate.'
            )

        self.stdout.write('\n=== SYNC COMPLETE ===')

    def _call_generate(self, norm_name, min_samples):
        from django.core.management import call_command
        self.stdout.write(f"  Generating {min_samples} samples for {norm_name}...")
        call_command('generate_iso27001_tisax_datasets', norm=norm_name, samples=min_samples, verbosity=0)

    def _call_generate_iso9001(self, needed):
        if needed <= 0:
            return
        from django.core.management import call_command
        self.stdout.write(f"  Generating {needed} samples for ISO9001...")
        call_command('generate_training_data', documents=max(30, needed // 7), verbosity=0)
