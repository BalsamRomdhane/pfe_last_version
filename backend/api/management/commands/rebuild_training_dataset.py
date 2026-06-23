"""
Management command: rebuild_training_dataset

Rebuilds TrainingSample records for ALL norms from real data:
- ISO 9001 : from Documents + Validations (real TeamLead decisions)
- ISO 27001 / TISAX : from RuleTrainingSample evidence (grouped by norm+rule-set)

Usage:
    python manage.py rebuild_training_dataset            # all norms
    python manage.py rebuild_training_dataset --norm 4  # specific norm_id
    python manage.py rebuild_training_dataset --dry-run # preview only

NEVER generates random/fake data.
"""
import json
import logging
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from api.models import (
    Norme, Rule, Document, Validation,
    TrainingSample, RuleTrainingSample,
    aggregate_validation_metrics, extract_features, build_validation_feature_vector,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Rebuild TrainingSamples from real validations and evidence data'

    def add_arguments(self, parser):
        parser.add_argument('--norm', type=int, default=None, help='Norm ID to rebuild (default: all)')
        parser.add_argument('--dry-run', action='store_true', help='Preview without writing')
        parser.add_argument('--force', action='store_true', help='Overwrite existing samples')

    def handle(self, *args, **options):
        norm_id = options['norm']
        dry_run = options['dry_run']
        force   = options['force']

        norms = [Norme.objects.get(pk=norm_id)] if norm_id else list(Norme.objects.all())

        total_created = 0
        total_updated = 0
        total_skipped = 0

        for norm in norms:
            self.stdout.write(f'\n[{norm.id}] {norm.name}')
            docs = Document.objects.filter(norme=norm).count()

            if docs > 0:
                # ── Path A: Real Documents + Validations ──────────────────
                c, u, s = self._rebuild_from_documents(norm, dry_run, force)
            else:
                # ── Path B: RuleTrainingSample evidence (no documents) ────
                c, u, s = self._rebuild_from_evidence(norm, dry_run, force)

            self.stdout.write(f'  created={c} updated={u} skipped={s}')
            total_created += c
            total_updated += u
            total_skipped += s

        self.stdout.write(f'\nTOTAL: created={total_created} updated={total_updated} skipped={total_skipped}')
        if dry_run:
            self.stdout.write('DRY RUN — no changes written.')

    # ── Path A ────────────────────────────────────────────────────────────
    def _rebuild_from_documents(self, norm, dry_run, force):
        created = updated = skipped = 0
        docs = Document.objects.filter(norme=norm, is_finalized=True).select_related('norme').prefetch_related('validations__rule')

        for doc in docs:
            existing = TrainingSample.objects.filter(document=doc).first()
            if existing and not force:
                skipped += 1
                continue

            metrics      = aggregate_validation_metrics(doc)
            features     = extract_features(doc)
            fvector      = build_validation_feature_vector(doc)
            status_source= doc.final_decision or doc.status
            approved_flag= (True  if status_source in ['approved','auto_approved']
                           else False if status_source == 'rejected'
                           else None)

            defaults = {
                'norm_id':           doc.norme_id,
                'features':          features,
                'feature_vector':    fvector,
                'label':             status_source,
                'standard':          norm.name,
                'teamlead_decision': status_source,
                'final_decision':    status_source,
                'decision_reason':   doc.decision_reason,
                'approved':          approved_flag,
                'total_rules':       metrics['total_rules'],
                'valid_rules_count': metrics['valid_rules_count'],
                'invalid_rules_count': metrics['invalid_rules_count'],
                'approved_rules':    metrics['approved_rules'],
                'rejected_rules':    metrics['rejected_rules'],
                'rule_results_json': metrics['rule_results_json'],
                'compliance_score':  metrics['compliance_score'],
            }

            if dry_run:
                action = 'UPDATE' if existing else 'CREATE'
                self.stdout.write(f'    [{action}] doc#{doc.id} rules={metrics["total_rules"]} score={metrics["compliance_score"]} label={status_source}')
                if existing: updated += 1
                else:        created += 1
                continue

            with transaction.atomic():
                _, was_created = TrainingSample.objects.update_or_create(
                    document=doc, defaults=defaults
                )
            if was_created: created += 1
            else:           updated += 1

        return created, updated, skipped

    # ── Path B ────────────────────────────────────────────────────────────
    def _rebuild_from_evidence(self, norm, dry_run, force):
        """
        For norms with no Documents, build TrainingSample from RuleTrainingSample.

        Strategy: Group all evidence by label (approved/rejected), build one
        aggregate TrainingSample per group that summarises rule coverage.
        Since TrainingSample requires a Document FK (OneToOne), we cannot create
        standalone records. Instead we update EXISTING TrainingSamples for docs
        that DO have this norm linked, OR we report that construction is blocked.

        For norms with 0 documents, we cannot create TrainingSamples via the
        current schema. We report stats only.
        """
        rts_qs   = RuleTrainingSample.objects.filter(norm=norm)
        total    = rts_qs.count()
        approved = rts_qs.filter(label='approved').count()
        rejected = rts_qs.filter(label='rejected').count()
        rules    = norm.rules.count()
        covered  = rts_qs.filter(label='approved').values('rule_id').distinct().count()

        self.stdout.write(f'  Evidence-only norm: {total} RuleTS, approved={approved}, rejected={rejected}')
        self.stdout.write(f'  Rules: {rules} total, {covered} covered')
        self.stdout.write(f'  NOTE: Cannot create TrainingSample — no Documents linked.')
        self.stdout.write(f'  Use dataset_stats_api (uses RuleTrainingSample as source of truth).')
        self.stdout.write(f'  TrainingSamples for this norm require linked Documents.')

        return 0, 0, 0
