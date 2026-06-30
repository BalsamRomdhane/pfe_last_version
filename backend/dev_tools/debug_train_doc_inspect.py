import os, json
from collections import Counter
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()
from ml.train_models import _get_labeled_document_samples, _coerce_feature_values, build_feature_vector, normalize_standard, load_dataset_with_metadata
from api.models import DocumentTrainingSample, RULES_BY_STANDARD, Norme


def sample_keys(sample):
    if isinstance(sample.feature_vector, dict):
        return list(sample.feature_vector.keys())
    if isinstance(sample.features, dict):
        return list(sample.features.keys())
    return []


def inspect_sample_lengths(sample):
    raw = sample.feature_vector if isinstance(sample.feature_vector, dict) else sample.features
    if not isinstance(raw, dict):
        return None
    keys = list(raw.keys())
    return len(keys), keys

samples = list(_get_labeled_document_samples())
print('sample count:', len(samples))
print('RULES_BY_STANDARD keys sample:', list(RULES_BY_STANDARD.keys())[:50])

standards = Counter(sample.standard for sample in samples)
print('standards:', standards)
for standard, count in standards.most_common(20):
    norm_key = normalize_standard(standard)
    rules = RULES_BY_STANDARD.get(norm_key, [])
    print(f'standard={standard!r} norm_key={norm_key} rules_count={len(rules)} first_rules={rules[:10]}')

# Check how many samples would be padded to a fixed feature width using the standard mapping.
for standard, count in standards.most_common(20):
    norm_key = normalize_standard(standard)
    rules = RULES_BY_STANDARD.get(norm_key, [])
    if rules:
        sample_rows = [sample for sample in samples if sample.standard == standard]
        lengths = Counter(len(_coerce_feature_values(sample.feature_vector or sample.features or {}, standard)) for sample in sample_rows)
        print(f'fixed-width check for {standard}: lengths={dict(lengths)} expected_len={len(rules)}')

        # show the first few unique key sets to confirm inconsistent feature coverage
        key_sets = {}
        for sample in sample_rows[:50]:
            keys = tuple(sample_keys(sample))
            key_sets[keys] = key_sets.get(keys, 0) + 1
        print('sample key-set examples:', list(key_sets.items())[:10])

        # Directly inspect whether the rule-order mapping is missing or malformed.
        print('normalized standard =>', norm_key)
        print('mapped rules count =>', len(rules))
        print('first three mapped rules =>', rules[:3])

        # Directly inspect whether the rule-order mapping is missing or malformed.
        print('normalized standard =>', norm_key)
        print('mapped rules count =>', len(rules))
        print('first three mapped rules =>', rules[:3])

for i, sample in enumerate(samples[:30]):
    print('\n--- sample', i, 'id=', sample.id, 'doc=', sample.document_id, 'label=', sample.label)
    print('feature_vector type=', type(sample.feature_vector).__name__)
    print('features type=', type(sample.features).__name__)
    print('feature_vector repr=', repr(sample.feature_vector)[:600])
    print('features repr=', repr(sample.features)[:600])
    fv = sample.feature_vector
    try:
        coerced = _coerce_feature_values(fv, sample.standard)
        print('coerced len=', len(coerced), 'first10=', coerced[:10])
    except Exception as e:
        print('coerce error:', type(e).__name__, e)
    try:
        if sample.features:
            coerced2 = _coerce_feature_values(sample.features, sample.standard)
            print('features coerced len=', len(coerced2), 'first10=', coerced2[:10])
    except Exception as e:
        print('features coerce error:', type(e).__name__, e)

    # inspect expected rule ordering for this sample
    norm_key = normalize_standard(sample.standard)
    expected_rules = RULES_BY_STANDARD.get(norm_key, [])
    if expected_rules:
        print('expected_rules_count=', len(expected_rules), 'expected_rule_names=', expected_rules)
        print('sample keys=', list((sample.feature_vector or {}).keys())[:20])

# also inspect any sample where feature_vector or features are not simple lists/dicts
bad = []
for sample in samples:
    fv = sample.feature_vector
    if isinstance(fv, list) and fv and any(isinstance(x, (list, tuple, dict, set)) for x in fv):
        bad.append((sample.id, sample.document_id, fv))
    elif isinstance(fv, dict):
        # dict is allowed for some paths, but inspect nested values
        nested = any(isinstance(v, (list, tuple, dict, set)) for v in fv.values())
        if nested:
            bad.append((sample.id, sample.document_id, fv))

print('\nPotentially problematic samples:', len(bad))
for item in bad[:10]:
    print(item)
