#!/usr/bin/env python3
"""
Seed the Django database with synthetic ISO 9001 training samples.

This script creates companion Document and TrainingSample records for each
generated sample so the admin dataset page can display them.
"""

import os
import sys
from pathlib import Path

# Ensure the backend package is importable
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')

import django
django.setup()

from django.utils import timezone
from api.models import Norme, Document, TrainingSample, Rule, Validation, RULES_BY_STANDARD

# Load the ISO 9001 generator from the local scripts folder.
sys.path.insert(0, str(SCRIPT_DIR))
from generate_iso9001_dataset import generate_dataset


# Evidence templates for each ISO 9001 rule
EVIDENCE_TEMPLATES = {
    "Identification du document": [
        "Le document comporte une référence unique REF-{id} et une date d'édition clairement indiquée.",
        "Numéro de référence absent, impossible d'identifier le document de manière unique.",
        "La fiche dispose d'une référence unique et d'une édition correctement renseignées.",
    ],
    "Version du document": [
        "Version 1.{n} documentée avec historique des modifications sur 3 niveaux.",
        "La version n'est pas renseignée, suivi de document impossible.",
        "Version clairement indiquée avec date de révision et motif de mise à jour.",
    ],
    "Approbation du document": [
        "Approuvé officiellement par le Responsable QSE, signé et daté.",
        "Signature manquante malgré une mention d'approbation en attente.",
        "Validation formalisée par la direction avec date d'approbation.",
    ],
    "Lisibilité et format": [
        "Document bien structuré avec titres hiérarchisés et mise en page professionnelle.",
        "Format texte brut sans structure, difficile à lire et comprendre.",
        "Sections claires avec numérotation et polices cohérentes.",
    ],
    "Contrôle des modifications": [
        "Historique complet des versions avec dates et détails de chaque changement.",
        "Aucun historique de modifications ne permet la traçabilité.",
        "Modifications tracées et cohérentes avec les versions antérieures.",
    ],
    "Accessibilité": [
        "Document disponible sur l'intranet avec chemin d'accès clairement communiqué.",
        "Accès restreint à un support papier, non conforme à l'accessibilité attendue.",
        "Disponibilité explicitement documentée pour les utilisateurs concernés.",
    ],
    "Protection du document": [
        "Document classé confidentialité interne avec accès restreint.",
        "Aucune protection mentionnée pour ce document sensible.",
        "Niveau de confidentialité explicitement défini et respect des restrictions.",
    ],
    "Archivage": [
        "Archivage sur serveur DMS interne avec durée de conservation définie à 7 ans.",
        "Processus d'archivage non documenté, conservation non spécifiée.",
        "Emplacement d'archivage bien défini et durée de stockage clairement indiquée.",
    ],
    "Validité du contenu": [
        "Contenu conforme aux exigences clients 2025 et normes actuelles ISO 9001:2015.",
        "Contenu obsolète référençant des normes dépassées, non applicable.",
        "Données à jour et validées pour l'activité en cours.",
    ],
    "Signature ou validation officielle": [
        "Document signé par le Responsable Qualité avec date officielle.",
        "Validation absent de signature officielle, document non formellement validé.",
        "Signature électronique présente et validée par le responsable compétent.",
    ],
}


def create_dummy_file_path(index: int) -> str:
    """Return a stable dummy file path for each synthetic document."""
    date_path = timezone.now().strftime('documents/%Y/%m/%d')
    return f"{date_path}/seeded_document_{index}.pdf"


def get_or_create_norme() -> Norme:
    norme_name = 'ISO 9001'
    norme, created = Norme.objects.get_or_create(name=norme_name, defaults={'description': 'ISO 9001 standard'})
    if created:
        print(f"Created norme: {norme_name}")
    return norme


def get_or_create_rules(norme: Norme):
    """Get or create all ISO 9001 rules."""
    rules = []
    rule_titles = RULES_BY_STANDARD.get('ISO9001', [])
    
    for title in rule_titles:
        rule, created = Rule.objects.get_or_create(
            norme=norme,
            title=title,
            defaults={'description': f'ISO 9001 rule: {title}'}
        )
        rules.append(rule)
    
    return {rule.title: rule for rule in rules}


def get_evidence_for_rule(rule_title: str, feature_value: bool, sample_index: int) -> str:
    """Return appropriate evidence text for a rule."""
    import random
    templates = EVIDENCE_TEMPLATES.get(rule_title, [])
    if not templates:
        return ""
    
    if feature_value:
        # Valid rule - use positive evidence
        idx = min(0, len(templates) - 1)
    else:
        # Invalid rule - use negative evidence
        idx = min(1, len(templates) - 1)
    
    evidence = templates[idx] if idx < len(templates) else ""
    # Add slight variation with index
    return evidence.format(id=sample_index, n=sample_index % 10)


def seed_training_samples(num_samples: int = 100):
    norme = get_or_create_norme()
    rules_dict = get_or_create_rules(norme)
    dataset = generate_dataset(num_samples)

    created_count = 0
    skipped_count = 0

    for index, sample in enumerate(dataset, start=1):
        file_path = create_dummy_file_path(index)
        status = Document.Status.APPROVED if sample['label'] == 'approved' else Document.Status.REJECTED
        document = Document.objects.create(
            file=file_path,
            norme=norme,
            employee_username=f"dataset_user_{index}",
            employee_department='DATASET',
            teamlead_username='system',
            status=status,
        )

        # Create validations with evidence for each rule
        rule_titles = RULES_BY_STANDARD.get('ISO9001', [])
        for rule_idx, rule_title in enumerate(rule_titles):
            if rule_idx < len(sample['features']):
                feature_value = sample['features'][rule_idx]
                rule = rules_dict.get(rule_title)
                if rule:
                    evidence_text = get_evidence_for_rule(rule_title, bool(feature_value), index)
                    Validation.objects.get_or_create(
                        document=document,
                        rule=rule,
                        defaults={
                            'teamlead_username': 'system',
                            'evidence_text': evidence_text,
                            'is_valid': bool(feature_value),
                        }
                    )

        training_sample, created = TrainingSample.objects.get_or_create(
            document=document,
            defaults={
                'features': sample['features'],
                'label': sample['label'],
                'standard': 'ISO9001',
            },
        )

        if created:
            created_count += 1
        else:
            skipped_count += 1

    print(f"Seeded {created_count} training samples with validations and evidence.")
    if skipped_count:
        print(f"Skipped {skipped_count} duplicate training samples.")


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Seed Django DB with synthetic ISO 9001 training samples')
    parser.add_argument('--count', type=int, default=100, help='Number of samples to generate')
    args = parser.parse_args()

    seed_training_samples(args.count)
    print('Done.')
