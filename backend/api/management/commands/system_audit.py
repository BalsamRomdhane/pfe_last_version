from django.core.management.base import BaseCommand
from api.models import Norme, Rule, Document, TrainingSample, RuleTrainingSample, Validation

class Command(BaseCommand):
    help = 'Run a system audit: print model counts and sample rows.'

    def handle(self, *args, **options):
        self.stdout.write('=== SYSTEM AUDIT ===')
        try:
            counts = {
                'Norme': Norme.objects.count(),
                'Rule': Rule.objects.count(),
                'Document': Document.objects.count(),
                'TrainingSample': TrainingSample.objects.count(),
                'RuleTrainingSample': RuleTrainingSample.objects.count(),
                'Validation': Validation.objects.count(),
            }
        except Exception as e:
            self.stderr.write(f'Error counting models: {e}')
            return

        for k, v in counts.items():
            self.stdout.write(f'{k}: {v}')

        self.stdout.write('\n=== SAMPLE Normes ===')
        for n in Norme.objects.all()[:10]:
            self.stdout.write(f'id={n.id} name={n.name!r}')

        self.stdout.write('\n=== SAMPLE TrainingSample rows (first 5) ===')
        for s in TrainingSample.objects.select_related('document__norme').all()[:5]:
            self.stdout.write(f'id={s.id} document_id={s.document_id} norm_id={s.norm_id} label={s.label} created_at={s.created_at}')
            self.stdout.write(f'  features_keys={list(s.features.keys())[:10]} feature_vector_len={len(s.feature_vector) if isinstance(s.feature_vector, (list, tuple)) else "N/A"}')

        self.stdout.write('\n=== SAMPLE RuleTrainingSample rows (first 5) ===')
        for r in RuleTrainingSample.objects.select_related('rule', 'norm', 'document').all()[:5]:
            self.stdout.write(f'id={r.id} document_id={r.document_id} rule_id={r.rule_id} norm_id={r.norm_id} label={r.label} created_at={r.created_at}')
            preview = (r.evidence_text or '').replace('\n', ' ')[:200]
            self.stdout.write(f'  evidence_preview={preview!r}')

        self.stdout.write('\nAudit complete.')
