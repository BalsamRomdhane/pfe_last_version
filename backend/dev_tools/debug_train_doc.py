import os
import json
from collections import Counter
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from ml.train_models import load_dataset_with_metadata, _get_labeled_document_samples, _coerce_feature_values
from api.models import DocumentTrainingSample

# Force the exact document-mode path used by the API
X, y, groups, metadata = load_dataset_with_metadata(source='document')
print('X shape:', getattr(X, 'shape', None))
print('y shape:', getattr(y, 'shape', None))
print('groups type:', type(groups), 'shape:', getattr(groups, 'shape', None))
print('groups first 20:', list(groups[:20]))

# Inspect group element types
from collections import Counter as C
print('group element types:', C(type(g).__name__ for g in groups).most_common(10))
for i, g in enumerate(groups[:30]):
    print(i, 'group=', repr(g), 'type=', type(g))

# Inspect samples that may be problematic
samples = _get_labeled_document_samples()
print('document samples count=', samples.count())
for sample in samples[:20]:
    print('sample id=', sample.id, 'document=', getattr(sample.document, 'id', None), 'label=', sample.label)
    print('feature_vector type=', type(getattr(sample, 'feature_vector', None)))
    print('features type=', type(getattr(sample, 'features', None)))
    if hasattr(sample, 'feature_vector') and sample.feature_vector:
        print('feature_vector sample=', sample.feature_vector)
    if getattr(sample, 'features', None):
        print('features sample=', sample.features)
