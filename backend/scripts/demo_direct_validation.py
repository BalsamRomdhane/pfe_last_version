#!/usr/bin/env python3
"""
Démonstration : Validation directe d'un document et ajout au dataset d'entraînement

Ce script montre comment un teamlead peut valider un document directement
sans passer par les validations individuelles, et comment ce document
s'ajoute automatiquement au dataset d'entraînement ML.
"""

import os
import sys
from pathlib import Path

# Configuration Django
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django
django.setup()

from api.models import Norme, Rule, Document, Validation, TrainingSample
from django.contrib.auth.models import User


def demo_direct_validation():
    """Démontre la validation directe d'un document."""
    print("🚀 Démonstration : Validation directe d'un document")
    print("=" * 60)

    # 1. Créer un utilisateur teamlead
    user, created = User.objects.get_or_create(
        username='demo_teamlead',
        defaults={'email': 'demo@example.com'}
    )
    if created:
        user.set_password('demo123')
        user.save()
        print("✅ Utilisateur teamlead créé")

    # 2. Récupérer ou créer la norme ISO 9001
    norme, created = Norme.objects.get_or_create(
        name='ISO9001',
        defaults={'description': 'Norme ISO 9001 pour la qualité'}
    )
    if created:
        print("✅ Norme ISO 9001 créée")

    # 3. Créer les règles si elles n'existent pas
    rules_data = [
        'Identification du document',
        'Version du document',
        'Approbation du document',
        'Lisibilité et format',
        'Contrôle des modifications',
        'Accessibilité',
        'Protection du document',
        'Archivage',
        'Validité du contenu',
        'Signature ou validation officielle'
    ]

    rules_created = 0
    for rule_title in rules_data:
        rule, created = Rule.objects.get_or_create(
            norme=norme,
            title=rule_title,
            defaults={'description': f'Règle ISO 9001: {rule_title}'}
        )
        if created:
            rules_created += 1

    if rules_created > 0:
        print(f"✅ {rules_created} règles ISO 9001 créées")

    # 4. Créer un document soumis par un employé
    doc = Document.objects.create(
        file='demo_document.pdf',
        norme=norme,
        employee_username='demo_employee',
        employee_department='DEMO',
        status=Document.Status.PENDING
    )
    print(f"✅ Document créé (ID: {doc.id})")
    print(f"   Statut initial: {doc.status}")
    print(f"   Validations: {doc.validations.count()}")
    print(f"   Training samples avant: {TrainingSample.objects.count()}")

    # 5. Simuler la validation directe par le teamlead
    print("\n🔄 Validation directe par le teamlead...")

    # Créer les validations par défaut
    from api.views import DocumentViewSet
    viewset = DocumentViewSet()
    viewset._create_default_validations(doc, Document.Status.APPROVED, user.username)

    # Mettre à jour le statut du document
    doc.status = Document.Status.APPROVED
    doc.teamlead_username = user.username
    doc.save()

    # Créer automatiquement le training sample
    from api.models import create_training_sample
    training_sample = create_training_sample(doc)

    print("✅ Validation directe terminée!")
    print(f"   Nouveau statut: {doc.status}")
    print(f"   Validations créées: {doc.validations.count()}")
    print(f"   Training samples après: {TrainingSample.objects.count()}")

    # 6. Afficher les détails du training sample créé
    if training_sample:
        print("\n📊 Training Sample créé:")
        print(f"   ID: {training_sample.id}")
        print(f"   Label: {training_sample.label}")
        print(f"   Standard: {training_sample.standard}")
        print(f"   Features: {dict(list(training_sample.features.items())[:3])}...")

        # Afficher quelques validations
        validations = list(doc.validations.all()[:3])
        print("\n🔍 Validations créées automatiquement:")
        for v in validations:
            print(f"   • {v.rule.title}: {'✅ Valid' if v.is_valid else '❌ Invalid'}")
            print(f"     Evidence: {v.evidence_text}")

    print("\n🎯 Résultat:")
    print("   Le document validé directement s'ajoute automatiquement")
    print("   au dataset d'entraînement pour améliorer le modèle ML!")

    # 7. Nettoyer (optionnel)
    cleanup = input("\n🧹 Voulez-vous nettoyer les données de démonstration ? (y/N): ")
    if cleanup.lower() == 'y':
        doc.delete()
        user.delete()
        print("✅ Données de démonstration nettoyées")


if __name__ == '__main__':
    demo_direct_validation()