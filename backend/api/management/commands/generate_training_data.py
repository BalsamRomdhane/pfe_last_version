import csv
import os
import random
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from api.models import (
    Norme,
    Rule,
    Document,
    Validation,
    TrainingSample,
    RuleTrainingSample,
    aggregate_validation_metrics,
)

OUTPUT_ROOT = Path(__file__).resolve().parent.parent.parent.parent / 'data' / 'ISO9001'
RULE_DEFINITIONS = [
    {
        'title': 'Identification obligatoire',
        'description': 'Le document doit contenir un identifiant unique, un auteur et une date de création.',
        'severity': Rule.Severity.HIGH,
        'condition': 'identification_missing',
        'action': 'Reject',
    },
    {
        'title': 'Gestion versions',
        'description': 'Le document doit indiquer une version et conserver l historique des révisions.',
        'severity': Rule.Severity.HIGH,
        'condition': 'version_missing',
        'action': 'Reject',
    },
    {
        'title': 'Approbation obligatoire',
        'description': 'Le document doit être validé et signé par le responsable qualité.',
        'severity': Rule.Severity.CRITICAL,
        'condition': 'approval_missing',
        'action': 'Reject',
    },
    {
        'title': 'Révision périodique',
        'description': 'Le document doit être revu à intervalles réguliers (moins de 12 mois).',
        'severity': Rule.Severity.MEDIUM,
        'condition': 'revision_overdue',
        'action': 'Recommend',
    },
    {
        'title': 'Pièces justificatives',
        'description': 'Les annexes et preuves (audit, formation, action corrective) doivent être jointes.',
        'severity': Rule.Severity.MEDIUM,
        'condition': 'evidence_missing',
        'action': 'Reject',
    },
    {
        'title': 'Traçabilité modifications',
        'description': 'L historique des modifications doit être conservé et accessible.',
        'severity': Rule.Severity.MEDIUM,
        'condition': 'traceability_missing',
        'action': 'Reject',
    },
    {
        'title': 'Blocage documents obsolètes',
        'description': 'Les documents périmés doivent être archivés ou bloqués à la diffusion.',
        'severity': Rule.Severity.HIGH,
        'condition': 'obsolete_document_used',
        'action': 'Reject',
    },
]

EVIDENCE_TEMPLATES = {
    'Identification obligatoire': {
        True: [
            'Identifiant DOC-QA-2026-014 détecté ; auteur Qualité ; date création 14/05/2026.',
            'Document référencé PRO-45-2026 avec code unique, rédacteur identifié et date 12/03/2026.',
            'Fiche technique TC-1025 et numéro de version V2.0 présents, auteur Marie Dubois confirmé.',
        ],
        False: [
            'Titre présent mais propriétaire absent ; aucun identifiant unique détecté dans l en-tête.',
            'Document sans code interne ; l auteur n est pas mentionné, la date de création est manquante.',
            'Page de garde vide sur l identifiant ; seulement le titre est visible, pas de référence documentaire.',
        ],
    },
    'Gestion versions': {
        True: [
            'Version V4.1 présente ; historique V1→V4 archivé et dates de mise à jour indiquées.',
            'Indication de version 3.2 avec registre des révisions et commentaires des modifications.',
            'Fiche versionnée V5.0, versions antérieures conservées dans l annexe de suivi.',
        ],
        False: [
            'Aucune version indiquée ; anciennes versions introuvables dans le document.',
            'La mention version est absente et le contrôle des modifications ne peut pas être vérifié.',
            'Le document ne précise pas sa version actuelle, le suivi des révisions est inachevé.',
        ],
    },
    'Approbation obligatoire': {
        True: [
            'Signature Responsable Qualité présente ; statut APPROUVÉ et cachet interne visible.',
            'Validation ISO réalisée par le chef de service, bon de validation daté et signé.',
            'Approbation formelle documentée avec nom du validateur et date de signature.',
        ],
        False: [
            'Document diffusé sans validation qualité ni signature du responsable.',
            'Absence de preuve d approbation ; aucun tampon ou signature retrouvée.',
            'Statut de validation manquant, le document semble encore en phase de brouillon.',
        ],
    },
    'Révision périodique': {
        True: [
            'Dernière révision : 04/2026 (<12 mois) ; prochaine revue planifiée 04/2027.',
            'Document révisé le 10/05/2026, cycle annuel respecté et journal de révision complet.',
            'Mise à jour du contenu validée en 05/2026, révision périodique documentée.',
        ],
        False: [
            'Dernière révision : 01/2023 (>12 mois) ; délai de mise à jour non respecté.',
            'Aucune révision récente : dernier contrôle effectué il y a 18 mois.',
            'Cycle de revue dépassé, la périodicité annuelle n est pas suivie.',
        ],
    },
    'Pièces justificatives': {
        True: [
            'Rapport audit + preuve formation + action corrective joints dans les annexes.',
            'Annexes de formation et résultats d audit présents, preuve de conformité disponible.',
            'Dossier complet avec justificatif de test, formation et retour d action corrective.',
        ],
        False: [
            'Annexe formation absente ; preuve de validation des compétences manquante.',
            'Aucun justificatif d audit fourni pour la modification récente.',
            'Document non accompagné des pièces justificatives requises.',
        ],
    },
    'Traçabilité modifications': {
        True: [
            'Historique complet modifications V1→V5 disponible dans l annexe.',
            'Journal des changements présent avec dates, auteurs et raisons de modification.',
            'Traçabilité assurée : chaque version est documentée avec son motif de mise à jour.',
        ],
        False: [
            'Aucun journal changements, l origine des modifications n est pas traçable.',
            'Historique absent, les versions précédentes ne sont pas répertoriées.',
            'La trace des modifications est incomplète et ne permet pas d audit.',
        ],
    },
    'Blocage documents obsolètes': {
        True: [
            'Document expiré déplacé archive et bloqué à la diffusion ; référence archivage visible.',
            'Version obsolète identifiée et retirée du circuit de diffusion.',
            'Procédure périmée isolée, accès bloqué par le système documentaire.',
        ],
        False: [
            'PROC-002 expirée encore utilisée dans les opérations quotidiennes.',
            'Ancienne version active sans blocage ; document obsolète non isolé.',
            'Document périmé accessible malgré la présence d une version plus récente.',
        ],
    },
}

TEAMLEAD_COMMENTS = {
    True: [
        'Conforme aux exigences ISO, les points clefs sont bien documentés.',
        'Validation satisfaisante, la version et les preuves sont correctement gérées.',
        'Approche documentaire cohérente et traçabilité assurée.',
    ],
    False: [
        'Historique insuffisant, la gestion des versions doit être améliorée.',
        'Version manquante, la révision périodique n est pas respectée.',
        'Validation qualité absente pour ce document.',
    ],
}

RECOMMENDATIONS = [
    'Ajouter historique versions',
    'Mettre à jour révision',
    'Bloquer diffusion',
    'Compléter les pièces justificatives',
    'Renforcer traçabilité modifications',
]

COLUMN_NAMES = [
    'document_id',
    'identification',
    'version',
    'approval',
    'revision',
    'attachments',
    'traceability',
    'obsolete',
    'compliance',
    'decision',
]


def _ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def _rule_feature_key(title: str) -> str:
    mapping = {
        'Identification obligatoire': 'identification',
        'Gestion versions': 'version',
        'Approbation obligatoire': 'approval',
        'Révision périodique': 'revision',
        'Pièces justificatives': 'attachments',
        'Traçabilité modifications': 'traceability',
        'Blocage documents obsolètes': 'obsolete',
    }
    return mapping.get(title, title.lower().replace(' ', '_'))


def _sample_comment(is_valid: bool) -> str:
    return random.choice(TEAMLEAD_COMMENTS[is_valid])


def _sample_recommendation(is_valid: bool) -> str:
    if is_valid:
        return random.choice(['Maintenir le suivi', 'Vérifier périodiquement', 'Conserver dans le dossier qualité'])
    return random.choice(RECOMMENDATIONS)


def _create_norme_and_rules(norm_name: str):
    # Use filter+get_or_create pattern to support case-insensitive lookup
    existing = Norme.objects.filter(name__iexact=norm_name).first()
    if existing:
        norme = existing
        created = False
    else:
        norme = Norme.objects.create(
            name=norm_name,
            description='ISO 9001 standard for document control and validation.',
        )
        created = True

    existing_rules = {rule.title: rule for rule in norme.rules.all()}
    for rule_def in RULE_DEFINITIONS:
        rule = existing_rules.get(rule_def['title'])
        if rule is None:
            rule = Rule.objects.create(
                norme=norme,
                title=rule_def['title'],
                description=rule_def['description'],
                severity=rule_def['severity'],
                condition=rule_def['condition'],
                action=rule_def['action'],
            )
        else:
            updated = False
            if rule.description != rule_def['description']:
                rule.description = rule_def['description']
                updated = True
            if rule.severity != rule_def['severity']:
                rule.severity = rule_def['severity']
                updated = True
            if rule.condition != rule_def['condition']:
                rule.condition = rule_def['condition']
                updated = True
            if rule.action != rule_def['action']:
                rule.action = rule_def['action']
                updated = True
            if updated:
                rule.save()

    return norme


def _create_document_row(document_id: str, rule_values: dict, compliance_score: int, decision: str) -> dict:
    row = {
        'document_id': document_id,
        'identification': rule_values['identification'],
        'version': rule_values['version'],
        'approval': rule_values['approval'],
        'revision': rule_values['revision'],
        'attachments': rule_values['attachments'],
        'traceability': rule_values['traceability'],
        'obsolete': rule_values['obsolete'],
        'compliance': compliance_score,
        'decision': decision,
    }
    return row


class Command(BaseCommand):
    help = 'Generate ISO9001 training datasets, CSV exports and ML training records.'

    def add_arguments(self, parser):
        parser.add_argument('--norm', type=str, default='ISO9001', help='Norme cible à générer.')
        parser.add_argument('--documents', type=int, default=50, help='Nombre de documents à générer.')
        parser.add_argument('--seed', type=int, default=42, help='Seed aléatoire pour reproductibilité.')

    def handle(self, *args, **options):
        norm_name = options['norm']
        document_count = options['documents']
        seed = options['seed']

        random.seed(seed)
        _ensure_dir(OUTPUT_ROOT)

        norme = _create_norme_and_rules(norm_name)
        rules = list(norme.rules.order_by('id'))
        if len(rules) != len(RULE_DEFINITIONS):
            self.stdout.write(self.style.WARNING('La norme ISO9001 doit contenir exactement 7 règles.'))

        approved_target = int(round(document_count * 0.52))
        rejected_target = document_count - approved_target

        document_rows = []
        evidence_rows = []
        created_documents = 0
        created_rules = 0

        with transaction.atomic():
            for index in range(1, document_count + 1):
                document_id = f'DOC{index:03d}'
                if index <= approved_target:
                    valid_count = random.randint(5, 7)
                    decision = 'APPROVED'
                else:
                    valid_count = random.randint(0, 4)
                    decision = 'REJECTED'

                rule_values = { _rule_feature_key(rule.title): 0 for rule in rules }
                truth_values = [1] * valid_count + [0] * (len(rules) - valid_count)
                random.shuffle(truth_values)

                for rule, value in zip(rules, truth_values):
                    feature_key = _rule_feature_key(rule.title)
                    rule_values[feature_key] = int(value)

                compliance_score = int(round(sum(rule_values.values()) / len(rules) * 100))

                document = Document.objects.create(
                    file=f'documents/2026/05/25/{document_id}.pdf',
                    norme=norme,
                    employee_username=f'user_{index:03d}',
                    employee_department='QUALITE',
                    teamlead_username='teamlead_ds',
                    status=Document.Status.APPROVED if decision == 'APPROVED' else Document.Status.REJECTED,
                    final_decision=Document.Status.APPROVED if decision == 'APPROVED' else Document.Status.REJECTED,
                    decision_reason=f'Décision finale basée sur {compliance_score}% de conformité documentée.',
                    reviewer_comment=_sample_comment(decision == 'APPROVED'),
                    approved_by='teamlead_ds',
                    approved_at=timezone.now(),
                    review_completed_at=timezone.now(),
                    is_finalized=True,
                )
                created_documents += 1

                validation_texts = []
                for rule in rules:
                    is_valid = bool(rule_values[_rule_feature_key(rule.title)])
                    evidence_text = random.choice(EVIDENCE_TEMPLATES[rule.title][is_valid])
                    reviewer_comment = _sample_comment(is_valid)
                    recommendation = _sample_recommendation(is_valid)
                    Validation.objects.create(
                        document=document,
                        rule=rule,
                        teamlead_username='teamlead_ds',
                        evidence_text=evidence_text,
                        is_valid=is_valid,
                        comment=reviewer_comment,
                        decision_reason=document.decision_reason,
                        reviewer_comment=reviewer_comment,
                    )
                    RuleTrainingSample.objects.create(
                        document=document,
                        norm=norme,
                        rule=rule,
                        rule_title=rule.title,
                        rule_description=rule.description,
                        document_text=f'Texte synthétique du document {document_id}.',
                        evidence_text=evidence_text,
                        reviewer_comment=reviewer_comment,
                        recommendation=recommendation,
                        semantic_score=round(random.uniform(0.60, 0.92), 2),
                        confidence_score=round(random.uniform(0.55, 0.95), 2),
                        label='approved' if is_valid else 'rejected',
                        final_document_decision='approved' if decision == 'APPROVED' else 'rejected',
                    )
                    created_rules += 1
                    evidence_rows.append({
                        'rule': rule.title,
                        'evidence': evidence_text,
                        'reviewer_comment': reviewer_comment,
                        'recommendation': recommendation,
                        'label': 'approved' if is_valid else 'rejected',
                    })
                    validation_texts.append(evidence_text)

                metrics = aggregate_validation_metrics(document)
                TrainingSample.objects.update_or_create(
                    document=document,
                    defaults={
                        'norm_id': norme.id,
                        'rule_id': rules[0].id if rules else None,
                        'features': metrics['rule_results_json'],
                        'feature_vector': [metrics['rule_results_json'].get(rule.title, 0) for rule in rules],
                        'confidence_score': round(random.uniform(0.7, 0.95), 2),
                        'semantic_score': round(random.uniform(0.65, 0.93), 2),
                        'teamlead_decision': 'approved' if decision == 'APPROVED' else 'rejected',
                        'final_decision': 'approved' if decision == 'APPROVED' else 'rejected',
                        'decision_reason': document.decision_reason,
                        'approved': decision == 'APPROVED',
                        'label': 'approved' if decision == 'APPROVED' else 'rejected',
                        'standard': norm_name,
                        'valid_rules_count': metrics['valid_rules_count'],
                        'invalid_rules_count': metrics['invalid_rules_count'],
                        'total_rules': metrics['total_rules'],
                        'rule_results_json': metrics['rule_results_json'],
                        'compliance_score': metrics['compliance_score'],
                        'approved_rules': metrics['approved_rules'],
                        'rejected_rules': metrics['rejected_rules'],
                        'rule_text': ' ; '.join([f"{rule.title}:{rule_values[_rule_feature_key(rule.title)]}" for rule in rules]),
                        'document_text': f'Texte synthétique du document {document_id}.',
                        'evidence_text': ' ; '.join(validation_texts),
                    },
                )
                document_rows.append(_create_document_row(document_id, rule_values, compliance_score, decision))

        csv_paths = {
            'documents': OUTPUT_ROOT / 'ISO9001_documents.csv',
            'evidences': OUTPUT_ROOT / 'ISO9001_evidences.csv',
        }
        with open(csv_paths['documents'], 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=COLUMN_NAMES)
            writer.writeheader()
            for row in document_rows:
                writer.writerow(row)

        with open(csv_paths['evidences'], 'w', newline='', encoding='utf-8') as fh:
            writer = csv.DictWriter(fh, fieldnames=['rule', 'evidence', 'reviewer_comment', 'recommendation', 'label'])
            writer.writeheader()
            for row in evidence_rows:
                writer.writerow(row)

        approved_docs = sum(1 for row in document_rows if row['decision'] == 'APPROVED')
        rejected_docs = sum(1 for row in document_rows if row['decision'] == 'REJECTED')
        rule_distribution = {rule.title: 0 for rule in rules}
        for row in document_rows:
            for rule in rules:
                rule_distribution[rule.title] += int(row[_rule_feature_key(rule.title)])

        self.stdout.write(self.style.SUCCESS('=== Génération ISO9001 terminée ==='))
        self.stdout.write(f'Norme : {norme.name}')
        self.stdout.write(f'Documents générés : {created_documents}')
        self.stdout.write(f'Evidences générées : {len(evidence_rows)}')
        self.stdout.write(f'Approved : {approved_docs} ({approved_docs / created_documents * 100:.1f}%)')
        self.stdout.write(f'Rejected : {rejected_docs} ({rejected_docs / created_documents * 100:.1f}%)')
        self.stdout.write('Distribution règles (valid count par règle) :')
        for title, count in rule_distribution.items():
            self.stdout.write(f'  - {title}: {count}/{created_documents}')
        self.stdout.write(f'Fichiers CSV : {csv_paths["documents"]} et {csv_paths["evidences"]}')
        self.stdout.write(self.style.SUCCESS('TrainingSample et RuleTrainingSample créés avec succès.'))
