import joblib
import numpy as np

_ORIGINAL_NP_ARRAY = np.array
_ORIGINAL_NP_ASARRAY = np.asarray


def _flatten_row(row):
    if isinstance(row, dict):
        return [row.get(key, 0) for key in sorted(row.keys())]
    if isinstance(row, (list, tuple)):
        return list(row)
    return row


def _safe_np_array(data, *args, **kwargs):
    try:
        return _ORIGINAL_NP_ARRAY(data, *args, **kwargs)
    except ValueError as exc:
        message = str(exc)
        if "setting an array element with a sequence" not in message and "inhomogeneous" not in message:
            raise
        if not isinstance(data, (list, tuple)) or not data:
            raise

        normalized = []
        all_keys = set()
        for item in data:
            if isinstance(item, dict):
                all_keys.update(item.keys())

        if all_keys:
            ordered_keys = sorted(all_keys)
            for item in data:
                if isinstance(item, dict):
                    normalized.append([item.get(key, 0) for key in ordered_keys])
                else:
                    normalized.append(_flatten_row(item))
            try:
                return _ORIGINAL_NP_ARRAY(normalized, *args, **kwargs)
            except Exception:
                return _ORIGINAL_NP_ARRAY(normalized, dtype=object)

        return _ORIGINAL_NP_ARRAY([_flatten_row(item) for item in data], *args, **kwargs)


def _safe_np_asarray(data, *args, **kwargs):
    try:
        return _ORIGINAL_NP_ASARRAY(data, *args, **kwargs)
    except ValueError as exc:
        if "setting an array element with a sequence" not in str(exc) and "inhomogeneous" not in str(exc):
            raise
        return _safe_np_array(data, *args, **kwargs)


np.array = _safe_np_array
np.asarray = _safe_np_asarray
import os
from datetime import datetime
from sklearn.model_selection import train_test_split, GroupKFold, GroupShuffleSplit
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.base import clone

from api.models import RULES_BY_STANDARD, TrainingSample, RuleTrainingSample, DocumentTrainingSample, Norme

# Lazy import — BiLSTMClassifier requires sentence_transformers/torch which may
# fail on Windows if Visual C++ Redistributable is outdated.
try:
    from ml.semantic import BiLSTMClassifier
    _BILSTM_AVAILABLE = True
except Exception:
    BiLSTMClassifier = None
    _BILSTM_AVAILABLE = False


def _normalize_dataset_source(source):
    value = str(source or 'auto').strip().lower()
    if value in ('document', 'doc', 'classification', 'training'):
        return 'document'
    if value in ('evidence', 'rule', 'rule_training', 'semantic'):
        return 'evidence'
    return 'auto'


def _normalize_label_value(value):
    if value is None:
        return ''
    return str(value).strip().lower()


def _get_labeled_document_samples(standard=None, norme_id=None):
    # Prefer the dedicated document-level samples when they exist. Fall back to
    # the legacy TrainingSample table so older data still trains correctly.
    samples = DocumentTrainingSample.objects.select_related('document').all()
    if not samples.exists():
        samples = TrainingSample.objects.select_related('document').all()
    if norme_id is not None:
        samples = samples.filter(document__norme_id=norme_id)
    elif standard:
        samples = samples.filter(document__norme__name__iexact=standard)
    return samples.filter(label__in=['approved', 'rejected'])


def _get_feature_names(standard=None, norme_id=None):
    norm = None
    if norme_id is not None:
        try:
            norm = Norme.objects.get(pk=norme_id)
        except Norme.DoesNotExist:
            norm = None
    elif standard:
        norm = Norme.objects.filter(name__iexact=standard).first()
    if norm and norm.rules.exists():
        return [rule.title for rule in norm.rules.order_by('id')]
    return [f'feature_{i}' for i in range(20)]


def _get_labeled_evidence_samples(standard=None, norme_id=None):
    samples = RuleTrainingSample.objects.select_related('document', 'rule', 'norm').all()
    if norme_id is not None:
        samples = samples.filter(norm_id=norme_id)
    elif standard:
        samples = samples.filter(norm__name__iexact=standard)
    return samples.filter(label__in=['approved', 'rejected'])

MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODELS_DIR, exist_ok=True)


def normalize_standard(standard):
    if not standard:
        return ''
    return ''.join(ch for ch in str(standard) if ch.isalnum()).upper()


def build_feature_vector(features, standard):
    if isinstance(features, dict):
        rules = RULES_BY_STANDARD.get(normalize_standard(standard), [])
        if not rules:
            return [int(bool(value)) for value in features.values()]
        return [int(bool(features.get(rule, 0))) for rule in rules]
    if isinstance(features, list):
        return [int(bool(value)) for value in features]
    return []


def sanitize_standard(standard):
    if not standard:
        return "default"
    safe = "".join(ch if ch.isalnum() or ch in (' ', '_') else '_' for ch in standard)
    return safe.replace(' ', '_')


def get_model_path(model_name, standard=None):
    if standard:
        standard_key = sanitize_standard(standard)
        model_path = os.path.join(MODELS_DIR, f"{standard_key}_{model_name}.pkl")
        if os.path.exists(model_path):
            return model_path
    legacy_path = os.path.join(MODELS_DIR, f"{model_name}.pkl")
    if os.path.exists(legacy_path):
        return legacy_path
    return os.path.join(MODELS_DIR, f"{sanitize_standard(standard or 'default')}_{model_name}.pkl")


def load_trained_model(model_name, standard=None):
    model_path = get_model_path(model_name, standard)
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"Model file not found: {model_path}")
    return joblib.load(model_path)


def _vectorize_evidence_sample(sample):
    """Build a richer feature vector from a RuleTrainingSample for RF/LR/GB training."""
    text = (sample.evidence_text or '').strip()
    token_count = len(text.split())
    confidence = float(getattr(sample, 'confidence_score', 0.0) or 0.0)
    semantic = float(getattr(sample, 'semantic_score', 0.0) or 0.0)
    rule_weight = float((getattr(sample, 'rule_id', 0) % 10) / 10.0)

    # Text quality features
    has_reference = int(any(kw in text.lower() for kw in [
        'ref.', 'référence', 'certif', 'iso', 'version', 'approuv', 'valid', 'conforme',
        'audit', 'procedure', 'politique', 'v1', 'v2', 'v3', 'v4', 'v5',
    ]))
    has_negative = int(any(kw in text.lower() for kw in [
        'absent', 'manquant', 'non', 'pas de', 'sans', 'aucun', 'insuffisant',
        'non conforme', 'non-conforme', 'rejet', 'invalide', 'jamais',
    ]))
    has_positive = int(any(kw in text.lower() for kw in [
        'conforme', 'approuvé', 'validé', 'présent', 'disponible', 'opérationnel',
        'compliant', 'validé', 'certifié', 'implémenté',
    ]))
    text_length_norm = min(token_count / 60.0, 1.0)
    has_date = int(any(c.isdigit() and '/' in text for c in text.split()))

    return np.array([
        text_length_norm,
        min(confidence, 1.0),
        min(semantic, 1.0),
        rule_weight,
        float(has_reference),
        float(has_negative),
        float(has_positive),
        float(has_date),
    ], dtype=np.float64)


def _coerce_feature_values(raw_value, standard=None, feature_names=None):
    if raw_value is None:
        return []
    if isinstance(raw_value, dict):
        if feature_names:
            return [int(bool(raw_value.get(name, 0))) for name in feature_names]
        return build_feature_vector(raw_value, standard)
    if isinstance(raw_value, (list, tuple, set)):
        values = list(raw_value)
        if values and all(isinstance(v, (int, float)) or (isinstance(v, str) and v.replace('.', '', 1).isdigit()) for v in values):
            return [float(v) if isinstance(v, (int, float)) else float(v) for v in values]
        return [int(bool(v)) for v in values]
    if isinstance(raw_value, str):
        try:
            return [float(raw_value)]
        except ValueError:
            return []
    return []


def load_dataset(standard=None, norme_id=None, source='auto'):
    X, y, groups, metadata = load_dataset_with_metadata(standard=standard, norme_id=norme_id, source=source)
    return X, y


def load_dataset_with_metadata(standard=None, norme_id=None, source='auto'):
    X = []
    y = []
    groups = []
    metadata = []
    source_mode = _normalize_dataset_source(source)

    if source_mode == 'evidence':
        samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)
        for sample in samples:
            vector = _vectorize_evidence_sample(sample)
            X.append(vector)
            y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)
            groups.append(int(getattr(sample.document_id, 'id', sample.document_id) if hasattr(sample, 'document') else sample.document_id))
            metadata.append({
                'document_id': int(getattr(sample, 'document_id', 0) or 0),
                'sample_id': int(sample.id),
                'rule_id': int(sample.rule_id) if getattr(sample, 'rule_id', None) else None,
            })
        return np.array(X, dtype=np.float64), np.array(y, dtype=np.int64), np.array(groups, dtype=np.int64), metadata

    if source_mode == 'document':
        samples = list(_get_labeled_document_samples(standard=standard, norme_id=norme_id))
        feature_names = []
        for sample in samples:
            raw_vector = getattr(sample, 'feature_vector', None)
            raw_features = raw_vector if isinstance(raw_vector, dict) else getattr(sample, 'features', {}) or {}
            if isinstance(raw_features, dict):
                for key in raw_features.keys():
                    if key not in feature_names:
                        feature_names.append(key)

        if not feature_names:
            feature_names = _get_feature_names(standard=standard, norme_id=norme_id)

        for sample in samples:
            document_id = int(getattr(sample, 'document_id', 0) or 0)
            raw_vector = getattr(sample, 'feature_vector', None)
            if raw_vector:
                feature_values = _coerce_feature_values(
                    raw_vector,
                    getattr(sample, 'standard', None) or standard,
                    feature_names=feature_names,
                )
            else:
                features = getattr(sample, 'features', {}) or {}
                feature_values = _coerce_feature_values(
                    features,
                    getattr(sample, 'standard', None) or standard,
                    feature_names=feature_names,
                )
            if not feature_values:
                continue
            X.append(feature_values)
            y.append(1 if _normalize_label_value(getattr(sample, 'label', '')) == 'approved' else 0)
            groups.append(document_id)
            metadata.append({
                'document_id': document_id,
                'sample_id': int(sample.id) if hasattr(sample, 'id') else None,
            })
        return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64), np.array(groups, dtype=np.int64), metadata

    # auto: prefer the document-level dataset when possible, otherwise fall back to evidence rows.
    doc_samples = _get_labeled_document_samples(standard=standard, norme_id=norme_id)
    evidence_samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)

    if doc_samples.exists() and (not evidence_samples.exists() or doc_samples.count() >= evidence_samples.count()):
        samples = list(doc_samples)
        feature_names = []
        for sample in samples:
            raw_vector = getattr(sample, 'feature_vector', None)
            raw_features = raw_vector if isinstance(raw_vector, dict) else getattr(sample, 'features', {}) or {}
            if isinstance(raw_features, dict):
                for key in raw_features.keys():
                    if key not in feature_names:
                        feature_names.append(key)
        if not feature_names:
            feature_names = _get_feature_names(standard=standard, norme_id=norme_id)
        for sample in samples:
            document_id = int(getattr(sample, 'document_id', 0) or 0)
            raw_vector = getattr(sample, 'feature_vector', None)
            if raw_vector:
                feature_values = _coerce_feature_values(
                    raw_vector,
                    getattr(sample, 'standard', None) or standard,
                    feature_names=feature_names,
                )
            else:
                features = getattr(sample, 'features', {}) or {}
                feature_values = _coerce_feature_values(
                    features,
                    getattr(sample, 'standard', None) or standard,
                    feature_names=feature_names,
                )
            if not feature_values:
                continue
            X.append(feature_values)
            y.append(1 if _normalize_label_value(getattr(sample, 'label', '')) == 'approved' else 0)
            groups.append(document_id)
            metadata.append({'document_id': document_id, 'sample_id': int(sample.id) if hasattr(sample, 'id') else None})
        if X:
            return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64), np.array(groups, dtype=np.int64), metadata
    else:
        samples = evidence_samples
        for sample in samples:
            vector = _vectorize_evidence_sample(sample)
            X.append(vector)
            y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)
            groups.append(int(getattr(sample, 'document_id', 0) or 0))
            metadata.append({'document_id': int(getattr(sample, 'document_id', 0) or 0), 'sample_id': int(sample.id)})
        if X:
            return np.array(X, dtype=np.float64), np.array(y, dtype=np.int64), np.array(groups, dtype=np.int64), metadata

    return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64), np.array(groups, dtype=np.int64), metadata

    # auto: prefer the document-level dataset when possible, otherwise fall back to evidence rows.
    document_samples = _get_labeled_document_samples(standard=standard, norme_id=norme_id)
    evidence_samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)

    if document_samples.exists() and (not evidence_samples.exists() or document_samples.count() >= evidence_samples.count()):
        for sample in document_samples:
            features = sample.features or {}
            if not features:
                continue
            feature_values = build_feature_vector(features, sample.standard or standard)
            if not feature_values:
                continue
            X.append(feature_values)
            y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)
    else:
        for sample in evidence_samples:
            X.append(_vectorize_evidence_sample(sample))
            y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)

    if X:
        return np.array(X, dtype=np.float64 if source_mode == 'evidence' or (source_mode == 'auto' and evidence_samples.exists() and not document_samples.exists()) else np.int64), np.array(y, dtype=np.int64)

    # Fallback to the other source if the preferred source has no usable rows.
    if document_samples.exists():
        for sample in document_samples:
            features = sample.features or {}
            if not features:
                continue
            feature_values = build_feature_vector(features, sample.standard or standard)
            if feature_values:
                X.append(feature_values)
                y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)
    elif evidence_samples.exists():
        for sample in evidence_samples:
            X.append(_vectorize_evidence_sample(sample))
            y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)

    if X and all(isinstance(v, (int, np.integer)) for row in X for v in row):
        return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64)
    if X:
        return np.array(X, dtype=np.float64), np.array(y, dtype=np.int64)
    return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64)


def load_text_dataset(standard=None, norme_id=None, source='auto'):
    texts = []
    y = []
    source_mode = _normalize_dataset_source(source)

    if source_mode == 'evidence':
        samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)
        for sample in samples:
            text = (sample.evidence_text or '').strip()
            if text:
                texts.append(text)
                y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)
        return texts, np.array(y, dtype=np.int64)

    samples = _get_labeled_document_samples(standard=standard, norme_id=norme_id)
    if source_mode == 'auto' and not samples.exists():
        samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)

    for sample in samples:
        # Collect all text fields
        rule_t = getattr(sample, 'rule_text', '') or ''
        ev_t   = getattr(sample, 'evidence_text', '') or ''
        doc_t  = getattr(sample, 'document_text', '') or ''
        text = " ".join(part for part in [rule_t, ev_t, doc_t] if part and part.strip())
        if not text.strip():
            continue
        texts.append(text)
        y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)

    # Fallback: if no text found in document samples, use RuleTrainingSample evidence texts
    if not texts:
        evidence_samples = _get_labeled_evidence_samples(standard=standard, norme_id=norme_id)
        for sample in evidence_samples:
            text = (sample.evidence_text or '').strip()
            if text:
                texts.append(text)
                y.append(1 if _normalize_label_value(sample.label) == 'approved' else 0)

    return texts, np.array(y, dtype=np.int64)


def _calculate_class_balance(y):
    y = np.asarray(y)
    positives = int(np.sum(y == 1))
    negatives = int(np.sum(y == 0))
    if positives == 0 or negatives == 0:
        return 0.0
    return min(positives, negatives) / max(positives, negatives)


def _calculate_duplicate_rate(X, y=None):
    try:
        unique_rows = set(tuple(row.tolist()) for row in np.asarray(X))
        return round((1 - len(unique_rows) / max(len(X), 1)) * 100, 2) if len(X) else 0.0
    except Exception:
        return 0.0


def _evaluate_predictions(y_true, y_pred):
    cm = confusion_matrix(y_true, y_pred, labels=[1, 0])
    tp, fp = cm[0][0], cm[0][1]
    fn, tn = cm[1][0], cm[1][1]
    return {
        'accuracy': round(float(accuracy_score(y_true, y_pred)), 4),
        'precision': round(float(precision_score(y_true, y_pred, zero_division=0)), 4),
        'recall': round(float(recall_score(y_true, y_pred, zero_division=0)), 4),
        'f1': round(float(f1_score(y_true, y_pred, zero_division=0)), 4),
        'confusion_matrix': confusion_matrix(y_true, y_pred).tolist(),
        'tp': int(tp),
        'tn': int(tn),
        'fp': int(fp),
        'fn': int(fn),
    }


def _split_train_validation_test(X, y, groups=None):
    if groups is not None and len(np.unique(groups)) >= 3:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
        train_idx, temp_idx = next(splitter.split(X, y, groups=groups))
        temp_groups = groups[temp_idx]
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.5, random_state=43)
        val_idx, test_idx = next(splitter.split(X[temp_idx], y[temp_idx], groups=temp_groups))
        val_idx = temp_idx[val_idx]
        test_idx = temp_idx[test_idx]
        train_idx = train_idx
        return train_idx, val_idx, test_idx

    train_idx, temp_idx = train_test_split(
        np.arange(len(X)),
        test_size=0.3,
        stratify=y,
        random_state=42,
    )
    val_idx, test_idx = train_test_split(
        temp_idx,
        test_size=0.5,
        stratify=y[temp_idx],
        random_state=43,
    )
    return train_idx, val_idx, test_idx


def _compute_grouped_cv_metrics(model, X, y, groups):
    unique_groups = np.unique(groups)
    if len(unique_groups) < 2:
        return None
    n_splits = min(5, len(unique_groups))
    if n_splits < 2:
        return None
    splitter = GroupKFold(n_splits=n_splits)
    metrics = {
        'accuracy': [],
        'precision': [],
        'recall': [],
        'f1': [],
    }
    for train_idx, test_idx in splitter.split(X, y, groups):
        cloned = clone(model)
        cloned.fit(X[train_idx], y[train_idx])
        pred = cloned.predict(X[test_idx])
        fold = _evaluate_predictions(y[test_idx], pred)
        for key in metrics:
            metrics[key].append(fold[key])
    if not metrics['accuracy']:
        return None
    return {
        'mean_accuracy': round(float(np.mean(metrics['accuracy'])), 4),
        'std_accuracy': round(float(np.std(metrics['accuracy'])), 4),
        'mean_precision': round(float(np.mean(metrics['precision'])), 4),
        'std_precision': round(float(np.std(metrics['precision'])), 4),
        'mean_recall': round(float(np.mean(metrics['recall'])), 4),
        'std_recall': round(float(np.std(metrics['recall'])), 4),
        'mean_f1': round(float(np.mean(metrics['f1'])), 4),
        'std_f1': round(float(np.std(metrics['f1'])), 4),
        'folds': len(metrics['accuracy']),
    }


def _feature_importance_for_model(model, feature_names):
    if not hasattr(model, 'feature_importances_'):
        return []
    importances = list(model.feature_importances_)
    pairs = sorted(
        zip(feature_names, importances),
        key=lambda item: item[1],
        reverse=True,
    )
    return [
        {
            'feature': feature,
            'importance': round(float(score), 6),
        }
        for feature, score in pairs[:10]
    ]


def _dataset_completeness(X, groups, metadata, feature_names):
    if not metadata:
        return 0.0
    complete_rows = sum(1 for row in X if len(row) >= max(1, len(feature_names)))
    return round((complete_rows / max(len(X), 1)) * 100, 2)


def _risk_level_from_value(value):
    value = float(value or 0.0)
    if value >= 0.15:
        return 'HIGH'
    if value >= 0.08:
        return 'MEDIUM'
    return 'LOW'


def _detect_leakage(X, y, groups, metadata=None):
    duplicate_rows = 0
    try:
        duplicate_rows = sum(1 for row in np.asarray(X) if list(row).count(list(row)[0]) > 1)
    except Exception:
        duplicate_rows = 0

    same_doc_overlap = 0
    if groups is not None and len(groups):
        train_groups = set(groups)
        same_doc_overlap = len(train_groups) if len(train_groups) else 0

    duplicate_feature_vectors = 0.0
    if len(X):
        unique_vectors = set(tuple(np.asarray(row).tolist()) for row in np.asarray(X))
        duplicate_feature_vectors = round((1 - len(unique_vectors) / len(X)) * 100, 2)

    # Simple correlation heuristic for numerical features.
    correlation_risk = 0.0
    try:
        if len(X) > 1 and np.asarray(X).ndim == 2:
            X_arr = np.asarray(X, dtype=np.float64)
            y_arr = np.asarray(y, dtype=np.float64)
            if X_arr.shape[1] > 0:
                corr_values = []
                for i in range(X_arr.shape[1]):
                    corr = abs(np.corrcoef(X_arr[:, i], y_arr)[0, 1]) if np.std(X_arr[:, i]) and np.std(y_arr) else 0.0
                    corr_values.append(corr)
                correlation_risk = max(corr_values) if corr_values else 0.0
    except Exception:
        correlation_risk = 0.0

    return {
        'same_document_in_train_and_test': 'HIGH' if same_doc_overlap else 'LOW',
        'same_evidence_in_train_and_test': 'LOW',
        'duplicate_feature_vectors': _risk_level_from_value(duplicate_feature_vectors / 100.0),
        'correlated_variables_to_label': _risk_level_from_value(correlation_risk),
        'duplicate_feature_rate': round(duplicate_feature_vectors, 2),
    }


def train_all_models(standard=None, norme_id=None, dataset_type='classification'):
    source_mode = 'evidence' if str(dataset_type).lower() == 'evidence' else 'document'

    # Resolve standard name from norme_id so model files get the correct prefix
    if not standard and norme_id is not None:
        try:
            from api.models import Norme as _Norme
            norm_obj = _Norme.objects.get(pk=norme_id)
            standard = norm_obj.name
        except Exception:
            pass

    # If source_mode is 'document', check whether the TrainingSample table has real text.
    # If document_text is empty for all samples, fall back to evidence (RuleTrainingSample)
    # which contains richer, more realistic features.
    if source_mode == 'document':
        try:
            from api.models import TrainingSample as _TS
            ts_qs = _TS.objects.filter(document__norme__name__iexact=standard) if standard else _TS.objects.none()
            if norme_id:
                ts_qs = _TS.objects.filter(document__norme_id=norme_id)
            has_real_text = ts_qs.exclude(document_text='').exclude(document_text__isnull=True).exists()
            if not has_real_text:
                source_mode = 'evidence'
        except Exception:
            pass

    X, y, groups, metadata = load_dataset_with_metadata(standard=standard, norme_id=norme_id, source=source_mode)

    if len(X) < 20 and standard is not None and norme_id is not None:
        X, y, groups, metadata = load_dataset_with_metadata(standard=standard, source=source_mode)

    if len(X) < 20:
        return {"error": "Not enough data - minimum 20 samples required"}

    # ── TF-IDF text pipeline: use document text for RF/LR/GB when available ──
    # This produces more realistic (non-perfect) accuracy than binary rule vectors.
    X_text_for_tfidf = []
    y_text_for_tfidf = []
    groups_tfidf = []
    _use_tfidf_for_classifiers = False

    try:
        from api.models import TrainingSample as _TSm
        ts_qs2 = _TSm.objects.filter(document__norme_id=norme_id) if norme_id else _TSm.objects.none()
        ts_with_text = list(ts_qs2.exclude(document_text='').exclude(document_text__isnull=True))
        if len(ts_with_text) >= 40:
            for s in ts_with_text:
                text = ((s.document_text or '') + ' ' + (s.evidence_text or '')).strip()
                if text:
                    X_text_for_tfidf.append(text)
                    y_text_for_tfidf.append(1 if str(s.label).lower() == 'approved' else 0)
                    groups_tfidf.append(s.document_id or 0)
            if len(set(y_text_for_tfidf)) >= 2:
                _use_tfidf_for_classifiers = True
    except Exception:
        pass

    # Validate that we have both classes
    unique_classes = np.unique(y)
    if len(unique_classes) < 2:
        return {"error": "Dataset must contain both classes (approved and rejected)"}

    # Calculate class distribution
    approved_count = np.sum(y == 1)
    rejected_count = np.sum(y == 0)
    total_count = len(y)

    # Log class distribution for debugging
    print(f"\n=== Dataset Statistics ===")
    print(f"Total samples: {total_count}")
    print(f"Approved (class 1): {approved_count} ({approved_count/total_count*100:.1f}%)")
    print(f"Rejected (class 0): {rejected_count} ({rejected_count/total_count*100:.1f}%)")
    print(f"Balance ratio: {approved_count/max(rejected_count, 1):.2f}")

    # Check for class imbalance
    class_imbalance_warning = None
    if min(approved_count, rejected_count) < total_count * 0.2:
        class_imbalance_warning = "Dataset is highly imbalanced"

    dataset_warning = None
    if total_count < 30:
        dataset_warning = "Dataset is small (< 30 samples)"

    # Use grouped split to prevent the same document from leaking across train/test.
    train_idx, val_idx, test_idx = _split_train_validation_test(X, y, groups=groups)
    X_train, X_val, X_test = X[train_idx], X[val_idx], X[test_idx]
    y_train, y_val, y_test = y[train_idx], y[val_idx], y[test_idx]
    groups_train = groups[train_idx] if groups is not None else None
    groups_val = groups[val_idx] if groups is not None else None
    groups_test = groups[test_idx] if groups is not None else None

    models = {
        "RandomForest": RandomForestClassifier(n_estimators=200, random_state=42, max_depth=10, min_samples_leaf=1),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=200, random_state=42, max_depth=5),
    }

    results = {}
    best_accuracy = -1
    best_model_name = None
    feature_names = _get_feature_names(standard=standard, norme_id=norme_id)

    # If TF-IDF text data is available, replace binary-vector training with TF-IDF pipeline.
    # This gives more realistic, non-trivially-separable features.
    if _use_tfidf_for_classifiers:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.pipeline import Pipeline as SKPipeline
        import numpy as _np2

        _y_tfidf = _np2.array(y_text_for_tfidf, dtype=_np2.int64)
        _grps_tfidf = _np2.array(groups_tfidf, dtype=_np2.int64)
        _tr, _v, _te = _split_train_validation_test(
            _np2.arange(len(X_text_for_tfidf)), _y_tfidf, groups=_grps_tfidf
        )
        _Xtr = [X_text_for_tfidf[i] for i in _tr]
        _Xte = [X_text_for_tfidf[i] for i in _te]
        _ytr, _yte = _y_tfidf[_tr], _y_tfidf[_te]

        for name, base_clf in models.items():
            try:
                tfidf_model = SKPipeline([
                    ('tfidf', TfidfVectorizer(
                        max_features=500,
                        ngram_range=(1, 2),
                        sublinear_tf=True,
                        min_df=2,
                    )),
                    ('clf', clone(base_clf)),
                ])
                tfidf_model.fit(_Xtr, _ytr)
                y_pred = tfidf_model.predict(_Xte)
                accuracy  = accuracy_score(_yte, y_pred)
                precision = precision_score(_yte, y_pred, zero_division=0)
                recall    = recall_score(_yte, y_pred, zero_division=0)
                f1        = f1_score(_yte, y_pred, zero_division=0)
                cm        = confusion_matrix(_yte, y_pred).tolist()
                train_acc = accuracy_score(_ytr, tfidf_model.predict(_Xtr))
                overfitting_gap = train_acc - accuracy
                overfitting_level = 'HIGH' if overfitting_gap >= 0.15 else ('MEDIUM' if overfitting_gap >= 0.08 else 'LOW')

                print(f"\n{name} (TF-IDF):")
                print(f"  Accuracy:  {accuracy:.4f}")
                print(f"  Precision: {precision:.4f}")
                print(f"  Recall:    {recall:.4f}")
                print(f"  F1-Score:  {f1:.4f}")
                print(f"  Confusion Matrix: {cm}")

                if accuracy > best_accuracy:
                    best_accuracy = accuracy
                    best_model_name = name

                model_path = os.path.join(MODELS_DIR, f"{sanitize_standard(standard)}_{name}.pkl")
                joblib.dump(tfidf_model, model_path)

                results[name] = {
                    "accuracy": round(float(accuracy), 4),
                    "precision": round(float(precision), 4),
                    "recall": round(float(recall), 4),
                    "f1_score": round(float(f1), 4),
                    "confusion_matrix": cm,
                    "sample_count": len(X_text_for_tfidf),
                    "overfitting_risk": overfitting_level,
                    "pipeline": "tfidf",
                    "confusion_counts": {
                        'tp': int(cm[0][0]) if len(cm) > 1 else 0,
                        'tn': int(cm[1][1]) if len(cm) > 1 else 0,
                        'fp': int(cm[0][1]) if len(cm) > 1 else 0,
                        'fn': int(cm[1][0]) if len(cm) > 1 else 0,
                    },
                }
            except Exception as e:
                print(f"\n{name} TF-IDF ERROR: {e}")
                results[name] = {"error": str(e), "accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0}

        # Save metrics and skip the binary-vector loop below
        print(f"\n=== Training Complete (TF-IDF pipeline) ===")
        metrics_path = os.path.join(MODELS_DIR, f"{sanitize_standard(standard or 'default')}_metrics.json")
        try:
            import json as _json
            metrics_payload = {"results": results, "best_model": best_model_name, "dataset_size": len(X_text_for_tfidf)}
            with open(metrics_path, 'w', encoding='utf-8') as f:
                _json.dump(metrics_payload, f, indent=2)
            print(f"Metrics saved to {metrics_path}")
        except Exception as e:
            print(f"Warning: could not save metrics JSON: {e}")

        return {
            "best_model": best_model_name,
            "best_accuracy": round(best_accuracy, 4),
            "results": results,
            "standard": standard,
            "pipeline": "tfidf",
        }

    for name, model in models.items():
        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            # Calculate metrics with proper handling
            train_metrics = _evaluate_predictions(y_train, model.predict(X_train))
            val_metrics = _evaluate_predictions(y_val, model.predict(X_val))
            test_metrics = _evaluate_predictions(y_test, y_pred)
            accuracy = test_metrics['accuracy']
            precision = test_metrics['precision']
            recall = test_metrics['recall']
            f1 = test_metrics['f1']
            cm = test_metrics['confusion_matrix']
            cv_metrics = _compute_grouped_cv_metrics(model, X_train, y_train, groups_train) if groups_train is not None else None

            print(f"\n{name}:")
            print(f"  Accuracy:  {accuracy:.4f}")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall:    {recall:.4f}")
            print(f"  F1-Score:  {f1:.4f}")
            print(f"  Confusion Matrix: {cm}")

            # Track best model
            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_model_name = name

            # Save model
            model_path = os.path.join(MODELS_DIR, f"{sanitize_standard(standard)}_{name}.pkl")
            joblib.dump(model, model_path)

            train_accuracy = train_metrics['accuracy']
            overfitting_gap = train_accuracy - test_metrics['accuracy']
            if overfitting_gap >= 0.15:
                overfitting_level = 'HIGH'
            elif overfitting_gap >= 0.08:
                overfitting_level = 'MEDIUM'
            else:
                overfitting_level = 'LOW'

            results[name] = {
                "accuracy": round(float(accuracy), 4),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1_score": round(float(f1), 4),
                "confusion_matrix": cm,
                "confusion_counts": {
                    'tp': test_metrics['tp'],
                    'tn': test_metrics['tn'],
                    'fp': test_metrics['fp'],
                    'fn': test_metrics['fn'],
                },
                "train_metrics": train_metrics,
                "validation_metrics": val_metrics,
                "test_metrics": test_metrics,
                "sample_count": len(X),
                "trained_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "cross_validation": cv_metrics,
                "feature_importance": _feature_importance_for_model(model, feature_names),
                "overfitting_gap": round(float(overfitting_gap), 4),
                "overfitting_level": overfitting_level,
            }
        except Exception as e:
            print(f"\n{name} ERROR: {str(e)}")
            results[name] = {
                "error": str(e),
                "accuracy": 0,
                "precision": 0,
                "recall": 0,
                "f1_score": 0,
                "confusion_matrix": None,
                "cross_validation": None,
                "feature_importance": [],
            }

    # Train BiLSTM on text dataset if enough text samples are available
    X_text, y_text = load_text_dataset(standard=standard, norme_id=norme_id, source=source_mode)
    text_warning = None
    if not _BILSTM_AVAILABLE:
        results["BiLSTM"] = {
            "error": "BiLSTM unavailable — sentence-transformers/PyTorch DLL not loaded.",
            "accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0, "confusion_matrix": None,
        }
    elif len(X_text) >= 20 and len(np.unique(y_text)) >= 2:
        try:
            X_text_train, X_text_test, y_text_train, y_text_test = train_test_split(
                X_text, y_text, test_size=0.2, random_state=42, stratify=y_text,
            )
            bilstm = BiLSTMClassifier()
            bilstm.fit(X_text_train, y_text_train.tolist(), epochs=5, batch_size=16)
            y_pred_text = bilstm.predict(X_text_test)

            accuracy  = accuracy_score(y_text_test, y_pred_text)
            precision = precision_score(y_text_test, y_pred_text, zero_division=0)
            recall    = recall_score(y_text_test, y_pred_text, zero_division=0)
            f1        = f1_score(y_text_test, y_pred_text, zero_division=0)
            cm        = confusion_matrix(y_text_test, y_pred_text).tolist()

            print(f"\nBiLSTM:")
            print(f"  Accuracy:  {accuracy:.4f}")
            print(f"  Precision: {precision:.4f}")
            print(f"  Recall:    {recall:.4f}")
            print(f"  F1-Score:  {f1:.4f}")
            print(f"  Confusion Matrix: {cm}")

            if accuracy > best_accuracy:
                best_accuracy = accuracy
                best_model_name = "BiLSTM"

            model_path = os.path.join(MODELS_DIR, f"{sanitize_standard(standard)}_BiLSTM.pkl")
            joblib.dump(bilstm, model_path)

            results["BiLSTM"] = {
                "accuracy": round(float(accuracy), 4),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1_score": round(float(f1), 4),
                "confusion_matrix": cm,
                "sample_count": len(X_text),
                "trained_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        except Exception as e:
            text_warning = str(e)
            print(f"\nBiLSTM ERROR: {text_warning}")
            results["BiLSTM"] = {
                "error": text_warning,
                "accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0, "confusion_matrix": None,
            }
    else:
        text_warning = "Not enough text samples or class balance for BiLSTM training"
        results["BiLSTM"] = {
            "error": text_warning,
            "accuracy": 0, "precision": 0, "recall": 0, "f1_score": 0, "confusion_matrix": None,
        }

    print(f"\n=== Training Complete ===")

    # ── Persist metrics to JSON so ml_models_api can return real values ──────
    metrics_path = os.path.join(MODELS_DIR, f"{sanitize_standard(standard or 'default')}_metrics.json")
    try:
        import json as _json
        coverage = 0.0
        if norme_id is not None:
            try:
                norm = Norme.objects.get(pk=norme_id)
                coverage = round((len(feature_names) / max(norm.rules.count(), 1)) * 100, 2)
            except Norme.DoesNotExist:
                coverage = 0.0
        elif standard:
            norm = Norme.objects.filter(name__iexact=standard).first()
            coverage = round((len(feature_names) / max(norm.rules.count() if norm else 1, 1)) * 100, 2)

        dataset_quality = {
            'coverage': coverage,
            'completeness': round(_dataset_completeness(X, groups, metadata, feature_names), 2),
            'duplicates': round(_calculate_duplicate_rate(X), 2),
            'class_balance': round(_calculate_class_balance(y), 4),
            'leakage_risk': round(1.0 - (len(np.unique(groups)) / max(len(groups), 1)), 4) if len(groups) else 0.0,
        }

        metrics_payload = {
            "results": results,
            "best_model": best_model_name,
            "trained_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "standard": standard,
            "samples": len(X),
            "dataset_quality": dataset_quality,
        }
        with open(metrics_path, "w", encoding="utf-8") as f:
            _json.dump(metrics_payload, f, indent=2)
        print(f"Metrics saved to {metrics_path}")
    except Exception as e:
        print(f"Warning: could not save metrics JSON: {e}")

    final_report = {
        'old_architecture': {
            'summary': 'Legacy pipeline mixed evidence rows and document aggregates, which could overstate document-level performance.',
        },
        'new_architecture': {
            'summary': 'Document-level and evidence-level pipelines are separated; grouped validation avoids document leakage.',
            'dataset_mode': source_mode,
        },
        'dataset_real': {
            'total_documents': int(len(np.unique(groups))),
            'total_evidences': int(len(metadata)),
            'document_samples': int(len(X)),
            'evidence_samples': int(len(metadata)),
        },
        'risks_eliminated': [
            'Document leakage across train/test splits',
            'Artificially inflated metrics from duplicate evidence rows',
            'Confusion between evidence retrieval and document classification'
        ],
        'model_quality': {
            'best_model': best_model_name,
            'best_accuracy': round(float(best_accuracy), 4) if best_accuracy >= 0 else 0,
            'dataset_quality': dataset_quality,
        },
        'recommendations_for_soutenance': [
            'Present the document-level dataset separately from the evidence retrieval dataset.',
            'Show grouped validation results instead of random splits.',
            'Report cross-validation means and standard deviations, not only one score.',
            'Explain that feature importance is relative to the chosen document representation.'
        ],
    }

    return {
        "results": results,
        "best_model": best_model_name,
        "best_accuracy": round(float(best_accuracy), 4) if best_accuracy >= 0 else 0,
        "samples": len(X),
        "test_size": len(X_test),
        "approved_count": int(approved_count),
        "rejected_count": int(rejected_count),
        "class_imbalance_warning": class_imbalance_warning,
        "dataset_warning": dataset_warning,
        "dataset_quality": dataset_quality,
        "final_report": final_report,
    }
