import os

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

from api.models import TrainingSample

MODEL_FILENAME = os.path.join(os.path.dirname(__file__), "model.pkl")


def load_dataset(standard=None):
    X = []
    y = []

    samples = TrainingSample.objects.all()
    if standard:
        samples = samples.filter(standard=standard)

    for sample in samples:
        features = sample.features or {}
        if not features:
            continue

        # Handle both dict and list formats for features
        if isinstance(features, dict):
            feature_values = [int(value) for value in features.values()]
        elif isinstance(features, list):
            feature_values = [int(value) for value in features]
        else:
            continue

        X.append(feature_values)
        y.append(1 if sample.label == "approved" else 0)

    return np.array(X, dtype=np.int64), np.array(y, dtype=np.int64)


def train_model(standard=None):
    X, y = load_dataset(standard)

    if len(X) < 20:
        return {"error": "Not enough data"}

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    model = RandomForestClassifier(n_estimators=100)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    acc = accuracy_score(y_test, y_pred)

    joblib.dump(model, MODEL_FILENAME)

    return {
        "accuracy": round(float(acc), 2),
        "samples": len(X),
        "model_path": MODEL_FILENAME,
    }
