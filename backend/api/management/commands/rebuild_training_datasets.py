"""
rebuild_training_datasets — reconstruit les TrainingSample depuis les données existantes.

Pour chaque norme (ISO9001, ISO27001, TISAX) :
  Phase 1 — Données réelles : Documents + Validations → TrainingSample
  Phase 2 — Données synthétiques : crée Documents synthétiques + TrainingSample
             si après Phase 1 le total reste < seuil cible.

Seuils : ISO9001=200, ISO27001=300, TISAX=300

Usage:
    python manage.py rebuild_training_datasets
    python manage.py rebuild_training_datasets --dry-run
    python manage.py rebuild_training_datasets --norm-id 4
"""
import random
from collections import defaultdict
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone
from api.models import (
    Norme, Rule, Document, Validation,
    TrainingSample, RuleTrainingSample,
    aggregate_validation_metrics, extract_features, build_validation_feature_vector,
)

TARGETS = {
    'ISO9001':  200,
    'ISO27001': 300,
    'TISAX':    300,
}

# Norm key matching (partial, case-insensitive)
NORM_KEY_MAP = [
    ('9001', 'ISO9001'),
    ('27001', 'ISO27001'),
    ('tisax', 'TISAX'),
]


def _norm_key(norm_name):
    name_lower = norm_name.lower().replace(' ', '').replace('-', '')
    for fragment, key in NORM_KEY_MAP:
        if fragment in name_lower:
            return key
    return None


# ── Synthetic document titles per norm ──────────────────────────────────────
SYNTH_TITLES = {
    'ISO9001': [
        'Procédure de contrôle qualité v{i}',
        'Manuel de gestion documentaire v{i}',
        'Politique qualité entreprise v{i}',
        'Procédure archivage ISO 9001 v{i}',
        'Plan qualité projet v{i}',
        'Audit interne qualité v{i}',
        'Gestion des non-conformités v{i}',
        'Revue de direction v{i}',
        'Procédure de validation v{i}',
        'Registre des documents qualité v{i}',
    ],
    'ISO27001': [
        'Politique de sécurité SI v{i}',
        'Plan de gestion des accès v{i}',
        'Procédure gestion incidents v{i}',
        'Plan de continuité activité v{i}',
        'Politique chiffrement données v{i}',
        'Registre des risques sécurité v{i}',
        'Procédure journalisation v{i}',
        'Politique gestion fournisseurs v{i}',
        'Plan de reprise après sinistre v{i}',
        'Déclaration d applicabilité v{i}',
    ],
    'TISAX': [
        'Plan de protection prototypes v{i}',
        'Procédure contrôle visiteurs v{i}',
        'Politique sécurité physique v{i}',
        'Gestion des accès réseau v{i}',
        'Classification information confidentielle v{i}',
        'Procédure gestion prestataires v{i}',
        'Protection postes de travail v{i}',
        'Gestion des incidents sécurité v{i}',
        'Audit interne TISAX v{i}',
        'Plan de sauvegarde données v{i}',
    ],
}

USERNAMES = [
    'alice.martin', 'bob.dupont', 'claire.bernard', 'david.petit',
    'emma.robert', 'francois.simon', 'gabrielle.thomas', 'henri.blanc',
]
DEPARTMENTS = ['QUALITE', 'SECURITE', 'IT', 'RH', 'DIRECTION']


class Command(BaseCommand):
    help = 'Rebuild TrainingSample from real data + synthetic if below targets.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Preview only, no writes')
        parser.add_argument('--norm-id', type=int, default=None, help='Process specific norm id only')
        parser.add_argument('--seed', type=int, default=42)
        parser.add_argument('--force', action='store_true', help='Recreate even if target met')

    def handle(self, *args, **options):
        random.seed(options['seed'])
        dry = options['dry_run']
        force = options['force']
        norm_filter_id = options['norm_id']

        self.stdout.write(self.style.SUCCESS('=== REBUILD TRAINING DATASETS ===\n'))

        norms = Norme.objects.all()
        if norm_filter_id:
            norms = norms.filter(id=norm_filter_id)

        total_created = 0
        total_updated = 0
        total_synth = 0

        for norm in norms:
            key = _norm_key(norm.name)
            target = TARGETS.get(key, 200) if key else 200
            rules = list(norm.rules.order_by('id'))
            n_rules = len(rules)

            self.stdout.write(f'[{norm.id}] {norm.name} (key={key}, target={target}, rules={n_rules})')

            # ── Phase 1: Sync from real Documents + Validations ──────────────
            c1, u1 = self._phase1_real(norm, rules, dry)
            total_created += c1
            total_updated += u1
            self.stdout.write(f'  Phase 1 (real): created={c1} updated={u1}')

            # ── Count after Phase 1 ──────────────────────────────────────────
            ts_now = TrainingSample.objects.filter(
                document__norme=norm, label__in=['approved', 'rejected']
            ).count()
            self.stdout.write(f'  After Phase 1: TrainingSample={ts_now}')

            if ts_now >= target and not force:
                self.stdout.write(f'  ✓ Target met ({ts_now}/{target}) — skipping Phase 2.\n')
                continue

            # ── Phase 2: Create synthetic Documents + TrainingSample ─────────
            needed = target - ts_now
            self.stdout.write(f'  Phase 2 (synthetic): need {needed} more samples')

            if not dry:
                c2 = self._phase2_synthetic(norm, rules, key, needed)
                total_synth += c2
                self.stdout.write(f'  Phase 2: created {c2} synthetic TrainingSample')
            else:
                self.stdout.write(f'  DRY RUN — would create {needed} synthetic samples')

        # ── Final report ─────────────────────────────────────────────────────
        self.stdout.write('\n=== FINAL REPORT ===')
        self.stdout.write(
            f"{'Norm':<45} {'TS total':>8} {'Approved':>9} {'Rejected':>9} {'RuleTS':>7} {'Cov%':>7}"
        )
        self.stdout.write('-' * 90)

        for norm in (Norme.objects.filter(id=norm_filter_id) if norm_filter_id else Norme.objects.all()):
            ts = TrainingSample.objects.filter(document__norme=norm)
            ts_total = ts.count()
            ts_appr = ts.filter(label='approved').count()
            ts_rejt = ts.filter(label='rejected').count()
            rts = RuleTrainingSample.objects.filter(norm=norm)
            rts_total = rts.count()
            rules_n = norm.rules.count()
            covered = rts.filter(label__in=['approved','rejected']).values('rule_id').distinct().count()
            cov = round(covered / max(rules_n, 1) * 100, 1)
            marker = '✓' if ts_total > 0 else '✗'
            self.stdout.write(
                f'{marker} {norm.name:<44} {ts_total:>8} {ts_appr:>9} {ts_rejt:>9} {rts_total:>7} {cov:>6.1f}%'
            )

        self.stdout.write(f'\nTotal: TS created={total_created} updated={total_updated} synthetic={total_synth}')

        if not dry:
            self.stdout.write(self.style.SUCCESS('\n✓ Rebuild complete. Restart Django server to reflect changes.'))
        else:
            self.stdout.write(self.style.WARNING('\n[DRY RUN — no data written]'))

    # ── Phase 1: Real Documents ───────────────────────────────────────────────
    def _phase1_real(self, norm, rules, dry):
        created = updated = 0
        docs = Document.objects.filter(
            norme=norm, is_finalized=True
        ).prefetch_related('validations__rule')

        for doc in docs:
            status_source = doc.final_decision or doc.status
            if status_source not in ['approved', 'rejected', 'auto_approved']:
                continue

            label = 'approved' if status_source in ['approved', 'auto_approved'] else 'rejected'
            metrics = aggregate_validation_metrics(doc)
            features = extract_features(doc)
            fvector = build_validation_feature_vector(doc)
            approved_flag = label == 'approved'

            defaults = {
                'norm_id': norm.id,
                'features': features,
                'feature_vector': fvector,
                'label': label,
                'standard': norm.name,
                'teamlead_decision': status_source,
                'final_decision': status_source,
                'decision_reason': doc.decision_reason,
                'approved': approved_flag,
                'total_rules': metrics['total_rules'],
                'valid_rules_count': metrics['valid_rules_count'],
                'invalid_rules_count': metrics['invalid_rules_count'],
                'approved_rules': metrics['approved_rules'],
                'rejected_rules': metrics['rejected_rules'],
                'rule_results_json': metrics['rule_results_json'],
                'compliance_score': metrics['compliance_score'],
                'confidence_score': round(metrics['compliance_score'] / 100.0, 2),
            }

            if dry:
                exists = TrainingSample.objects.filter(document=doc).exists()
                if exists:
                    updated += 1
                else:
                    created += 1
                continue

            with transaction.atomic():
                _, was_created = TrainingSample.objects.update_or_create(
                    document=doc, defaults=defaults
                )
            if was_created:
                created += 1
            else:
                updated += 1

        return created, updated

    # ── Phase 2: Synthetic Documents ─────────────────────────────────────────
    def _phase2_synthetic(self, norm, rules, norm_key, needed):
        created = 0
        n_rules = len(rules)
        titles = SYNTH_TITLES.get(norm_key or 'ISO9001', SYNTH_TITLES['ISO9001'])
        approved_need = needed // 2

        # Disconnect Validation post_save signal to prevent double TrainingSample creation
        from django.db.models.signals import post_save
        from api import signals as api_signals
        post_save.disconnect(api_signals.create_training_sample_on_validation,
                             sender=Validation)
        try:
            with transaction.atomic():
                for idx in range(needed):
                    is_approved = idx < approved_need
                    label = 'approved' if is_approved else 'rejected'
                    title_template = titles[idx % len(titles)]

                    if is_approved:
                        valid_count = random.randint(max(1, n_rules * 7 // 10), n_rules)
                    else:
                        valid_count = random.randint(0, max(0, n_rules * 4 // 10))

                    # Create synthetic Document
                    doc = Document.objects.create(
                        file=f'synthetic/{norm_key or "norm"}/{label}/doc_{idx+1:04d}.pdf',
                        norme=norm,
                        employee_username=random.choice(USERNAMES),
                        employee_department=random.choice(DEPARTMENTS),
                        teamlead_username='teamlead_synth',
                        status=label,
                        final_decision=label,
                        decision_reason='Synthetic document — generated for ML training.',
                        reviewer_comment=f'Auto-generated {label} sample.',
                        approved_by='teamlead_synth',
                        approved_at=timezone.now(),
                        review_completed_at=timezone.now(),
                        is_finalized=True,
                    )

                    # Build rule results
                    shuffled_rules = list(rules)
                    random.shuffle(shuffled_rules)
                    valid_rule_ids = set(r.id for r in shuffled_rules[:valid_count])

                    rule_results = {}
                    features = {}
                    approved_rule_names = []
                    rejected_rule_names = []
                    fvector = []

                    for rule in rules:
                        is_valid = rule.id in valid_rule_ids
                        rule_results[rule.title] = 1 if is_valid else 0
                        features[rule.title] = 1 if is_valid else 0
                        fvector.append(1 if is_valid else 0)
                        if is_valid:
                            approved_rule_names.append(rule.title)
                        else:
                            rejected_rule_names.append(rule.title)

                        ev_text = (
                            f"Synthétique: règle '{rule.title}' — "
                            f"{'conforme' if is_valid else 'non-conforme'}."
                        )
                        Validation.objects.create(
                            document=doc,
                            rule=rule,
                            teamlead_username='teamlead_synth',
                            evidence_text=ev_text,
                            is_valid=is_valid,
                            comment=f"Auto-generated {'approved' if is_valid else 'rejected'} evidence.",
                        )

                        rts_label = 'approved' if is_valid else 'rejected'
                        if not RuleTrainingSample.objects.filter(
                            norm=norm, rule=rule, evidence_text=ev_text, label=rts_label
                        ).exists():
                            RuleTrainingSample.objects.create(
                                document=doc,
                                norm=norm,
                                rule=rule,
                                rule_title=rule.title,
                                rule_description=rule.description or '',
                                evidence_text=ev_text,
                                reviewer_comment=f"Synthetic {'compliant' if is_valid else 'non-compliant'} sample.",
                                recommendation='Maintain compliance.' if is_valid else 'Implement corrective action.',
                                label=rts_label,
                                final_document_decision=label,
                                confidence_score=round(random.uniform(0.70, 0.95) if is_valid else random.uniform(0.55, 0.85), 2),
                                semantic_score=round(random.uniform(0.65, 0.92) if is_valid else random.uniform(0.50, 0.80), 2),
                            )

                    compliance_score = round(valid_count / max(n_rules, 1) * 100, 1)
                    TrainingSample.objects.update_or_create(
                        document=doc,
                        defaults={
                            'norm_id': norm.id,
                            'features': features,
                            'feature_vector': fvector,
                            'label': label,
                            'standard': norm.name,
                            'teamlead_decision': label,
                            'final_decision': label,
                            'decision_reason': 'Synthetic training sample.',
                            'approved': (label == 'approved'),
                            'total_rules': n_rules,
                            'valid_rules_count': valid_count,
                            'invalid_rules_count': n_rules - valid_count,
                            'approved_rules': approved_rule_names,
                            'rejected_rules': rejected_rule_names,
                            'rule_results_json': rule_results,
                            'compliance_score': compliance_score,
                            'confidence_score': round(compliance_score / 100.0, 2),
                        }
                    )
                    created += 1
        finally:
            # Always reconnect signal
            post_save.connect(api_signals.create_training_sample_on_validation,
                              sender=Validation)

        return created
