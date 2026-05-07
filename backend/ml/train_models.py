import joblib
import numpy as np
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
)
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
import os

from api.models import RULES_BY_STANDARD, TrainingSample

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


def load_dataset(standard=None, norme_id=None):
    X = []
    y = []

    samples = TrainingSample.objects.all()
    if norme_id is not None:
        samples = samples.filter(document__norme_id=norme_id)
        if not samples.exists() and standard:
            samples = TrainingSample.objects.filter(standard__iexact=standard)
            if not samples.exists():
                samples = TrainingSample.objects.filter(standard__iexact=standard.replace(' ', ''))
    elif standard:
        samples = samples.filter(standard__iexact=standard)
        if not samples.exists():
            samples = samples.filter(standard__iexact=standard.replace(' ', ''))

    for sample in samples:
        features = sample.features or {}
        if not features:
            continue

        feature_values = build_feature_vector(features, sample.standard)
        if not feature_values:
            continue

        X.append(feature_values)
        y.append(1 if str(sample.label).strip().lower() == "approved" else 0)

    return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64)


def train_all_models(standard=None, norme_id=None):
    X, y = load_dataset(standard, norme_id)

    if len(X) < 20 and standard is not None and norme_id is not None:
        X, y = load_dataset(standard=standard)

    if len(X) < 20:
        return {"error": "Not enough data - minimum 20 samples required"}

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

    # Use stratified split to maintain class distribution
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
        stratify=y,  # IMPORTANT: maintain class proportions
    )

    models = {
        "RandomForest": RandomForestClassifier(n_estimators=100, random_state=42, max_depth=10),
        "LogisticRegression": LogisticRegression(max_iter=1000, random_state=42),
        "GradientBoosting": GradientBoostingClassifier(n_estimators=100, random_state=42, max_depth=5),
    }

    results = {}
    best_accuracy = -1
    best_model_name = None

    for name, model in models.items():
        try:
            model.fit(X_train, y_train)
            y_pred = model.predict(X_test)

            # Calculate metrics with proper handling
            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred, zero_division=0)
            recall = recall_score(y_test, y_pred, zero_division=0)
            f1 = f1_score(y_test, y_pred, zero_division=0)
            cm = confusion_matrix(y_test, y_pred).tolist()

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

            results[name] = {
                "accuracy": round(float(accuracy), 4),
                "precision": round(float(precision), 4),
                "recall": round(float(recall), 4),
                "f1_score": round(float(f1), 4),
                "confusion_matrix": cm,
                "sample_count": len(X),
                "trained_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            }

    print(f"\n=== Training Complete ===")

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
    }
