#!/usr/bin/env python3
"""Regenerate TrainingSample with standard field."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import TrainingSample, Document, create_training_sample

# Get finalized documents
finalized_docs = Document.objects.filter(status__in=['approved', 'rejected'])
print(f'Found {finalized_docs.count()} finalized documents\n')

# Regenerate samples
sample_count = 0
for doc in finalized_docs:
    sample = create_training_sample(doc)
    if sample:
        standard_name = doc.norme.name if doc.norme else 'Unknown'
        print(f'✓ Document {doc.id}: {standard_name} ({doc.status})')
        sample_count += 1

print(f'\n✓ Total TrainingSample: {TrainingSample.objects.count()}')
print('\nBy standard:')
standards = TrainingSample.objects.values('standard').distinct()
for std_dict in standards:
    std_name = std_dict['standard']
    count = TrainingSample.objects.filter(standard=std_name).count()
    print(f'  - {std_name}: {count} samples')
