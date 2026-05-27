import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Dict, List

from .models import Norme, TrainingSample, RuleTrainingSample, aggregate_validation_metrics

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _norm_slug(norme: Norme) -> str:
    return '_'.join(norme.name.lower().split())[:60]


def _export_prefix(norme: Norme) -> str:
    normalized = unicodedata.normalize('NFKD', norme.name).encode('ascii', 'ignore').decode('ascii').lower()
    if 'iso' in normalized and '9001' in normalized:
        return 'ISO9001'
    return re.sub(r'[^A-Za-z0-9]+', '_', norme.name).strip('_') or f'norm_{norme.id}'


def _rule_feature_name(rule_title: str) -> str:
    normalized = unicodedata.normalize('NFKD', rule_title).encode('ascii', 'ignore').decode('ascii').lower()
    aliases = [
        ('identification', 'rule_identification'),
        ('version', 'rule_versions'),
        ('approbation', 'rule_approval'),
        ('revision', 'rule_revision'),
        ('justific', 'rule_evidence'),
        ('evidence', 'rule_evidence'),
        ('tracabil', 'rule_traceability'),
        ('traceability', 'rule_traceability'),
        ('obsolete', 'rule_obsolete'),
        ('archiv', 'rule_archivage'),
    ]
    for needle, column in aliases:
        if needle in normalized:
            return column
    slug = re.sub(r'[^a-z0-9]+', '_', normalized).strip('_')
    return f'rule_{slug}' if slug else 'rule_unknown'


def export_datasets_for_norm(norme: Norme) -> Dict:
    """Generate datasets and CSV exports for a single norme."""
    norm_slug = _norm_slug(norme)
    out_dir = DATA_DIR / norm_slug
    _ensure_dir(out_dir)
    export_name = _export_prefix(norme)
    rules = list(norme.rules.order_by('id'))
    rule_columns = [_rule_feature_name(rule.title) for rule in rules]

    samples = TrainingSample.objects.filter(norm_id=norme.id).select_related('document')
    document_rows = []
    for sample in samples:
        metrics = aggregate_validation_metrics(sample.document) if sample.document_id else {
            'rule_results_json': sample.rule_results_json or {},
        }
        rule_results = metrics['rule_results_json'] if isinstance(metrics.get('rule_results_json'), dict) else {}
        row = {
            'document_id': sample.document_id,
            'label': sample.label or '',
        }
        for rule, column in zip(rules, rule_columns):
            row[column] = int(rule_results.get(rule.title, 0) or 0)
        document_rows.append(row)

    evidence_rows = []
    evidence_samples = RuleTrainingSample.objects.filter(norm=norme).select_related('rule')
    for evidence in evidence_samples:
        evidence_rows.append({
            'rule': evidence.rule_title or getattr(evidence.rule, 'title', ''),
            'evidence': evidence.evidence_text or '',
            'reviewer_comment': evidence.reviewer_comment or '',
            'recommendation': evidence.recommendation or '',
            'label': evidence.label or '',
        })

    def write_csv(path: Path, rows: List[Dict], fieldnames: List[str]):
        with open(path, 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                writer.writerow(r)

    if document_rows:
        write_csv(
            out_dir / f'{export_name}_documents.csv',
            document_rows,
            ['document_id', *rule_columns, 'label'],
        )

    if evidence_rows:
        write_csv(out_dir / f'{export_name}_evidences.csv', evidence_rows, [
            'rule',
            'evidence',
            'reviewer_comment',
            'recommendation',
            'label',
        ])

    return {
        'norm_id': norme.id,
        'norm_name': norme.name,
        'documents_exported': len(document_rows),
        'evidences_exported': len(evidence_rows),
        'path': str(out_dir),
    }


def generate_all_iso9001_datasets():
    keywords = ['iso9001', 'iso 9001', 'document control', 'quality management']
    # Use icontains matching across keywords
    qs = Norme.objects.none()
    for kw in keywords:
        qs = qs | Norme.objects.filter(name__icontains=kw)
    normes = qs.distinct()
    results = []
    for norme in normes:
        stats = export_datasets_for_norm(norme)
        results.append(stats)
    return results
