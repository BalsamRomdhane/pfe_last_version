#!/usr/bin/env python3
"""Regenerate TrainingSample for all finalized documents."""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from api.models import Document, TrainingSample, create_training_sample


def main():
    # Get all documents with final status
    finalized_docs = Document.objects.filter(
        status__in=[Document.Status.APPROVED, Document.Status.REJECTED]
    )
    
    count = finalized_docs.count()
    print(f"Found {count} finalized documents")
    
    created_count = 0
    for doc in finalized_docs:
        sample = create_training_sample(doc)
        if sample:
            created_count += 1
            print(f"✓ Created TrainingSample for Document {doc.id} (status: {doc.status})")
    
    total_samples = TrainingSample.objects.count()
    print(f"\n✓ Success! Total TrainingSample: {total_samples}")


if __name__ == '__main__':
    main()
