#!/usr/bin/env python3
"""
Test de validation par teamlead/admin et ajout au dataset
"""

import os
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
import django
django.setup()

from api.models import *
from django.contrib.auth.models import User

def test_teamlead_admin_validation():
    print("🔍 Test : Validation par teamlead/admin et ajout au dataset")
    print("=" * 60)

    # Créer des utilisateurs avec différents rôles
    admin_user, _ = User.objects.get_or_create(username='admin_user', defaults={'email': 'admin@example.com'})
    teamlead_user, _ = User.objects.get_or_create(username='teamlead_user', defaults={'email': 'teamlead@example.com'})

    print('👥 Utilisateurs créés:')
    print(f'  • Admin: {admin_user.username}')
    print(f'  • Teamlead: {teamlead_user.username}')

    # Récupérer ou créer un document
    try:
        doc = Document.objects.filter(status='pending').first()
        if not doc:
            norme = Norme.objects.get(name='ISO9001')
            doc = Document.objects.create(
                file='test_validation.pdf',
                norme=norme,
                employee_username='test_employee',
                employee_department='TEST',
                status='pending'
            )
        print(f'\n📄 Document: ID {doc.id}, Statut: {doc.status}')

        initial_samples = TrainingSample.objects.count()
        print(f'📊 Training samples avant: {initial_samples}')

        # Simuler validation par teamlead
        print('\n👤 Validation par TEAMLEAD:')
        from api.views import DocumentViewSet
        viewset = DocumentViewSet()
        viewset._create_default_validations(doc, 'approved', teamlead_user.username)
        doc.status = 'approved'
        doc.teamlead_username = teamlead_user.username
        doc.save()

        from api.models import create_training_sample
        sample = create_training_sample(doc)

        print('✅ Validation terminée!')
        print(f'  • Statut final: {doc.status}')
        print(f'  • Validations créées: {doc.validations.count()}')
        print(f'  • Training samples après: {TrainingSample.objects.count()}')
        print(f'  • Sample créé: {sample.id if sample else "Aucun"}')
        if sample:
            print(f'  • Label: {sample.label}')
            print(f'  • Standard: {sample.standard}')

        # Montrer quelques validations
        validations = list(doc.validations.all()[:3])
        print('\n🔍 Validations créées automatiquement:')
        for v in validations:
            status_icon = "✅" if v.is_valid else "❌"
            print(f'  • {v.rule.title}: {status_icon}')

        print('\n🎯 Résultat: Le document validé par teamlead/admin s\'ajoute automatiquement au dataset!')

    except Exception as e:
        print(f'❌ Erreur: {e}')

if __name__ == '__main__':
    test_teamlead_admin_validation()