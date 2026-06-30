"""
audit_bilstm_split.py
----------------------
Reproduit l'évaluation BiLSTM avec les données réelles pour vérifier
si les 100% viennent d'une évaluation sur le jeu d'entraînement.

Teste les hypothèses :
1. BiLSTM évalue sur le train set (data leakage)
2. BiLSTM surapprend sur un dataset synthétique trop simple
3. Les labels sont tous identiques dans le test set
"""
import os
import sys
import django

_HERE    = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
sys.path.insert(0, _BACKEND)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'enterprise_platform.settings')
django.setup()

from ml.train_models import (
    load_text_dataset,
    _split_train_validation_test,
    _evaluate_predictions,
)
import numpy as np

NORMS_TO_CHECK = [
    'ISO 9001 - Controle et validation des documents',
    'ISO 27001 - Securite de l information',
    'TISAX - Information Security Assessment',
]

for std in NORMS_TO_CHECK:
    print(f"\n{'='*65}")
    print(f"STANDARD: {std}")
    print(f"{'='*65}")

    texts, y = load_text_dataset(standard=std, source='auto')
    n = len(texts)
    print(f"  Total text samples : {n}")
    if n == 0:
        print("  → No text data available")
        continue

    y_arr = np.array(y, dtype=np.int64)
    classes, counts = np.unique(y_arr, return_counts=True)
    for cls, cnt in zip(classes, counts):
        lbl = 'approved' if cls == 1 else 'rejected'
        print(f"  Class {lbl}: {cnt} ({cnt/n*100:.1f}%)")

    # Reproduce the split used by the current code (from train_models.py)
    tr, vl, te = _split_train_validation_test(np.arange(n), y_arr)
    X_tr_texts = [texts[i] for i in tr]
    X_te_texts = [texts[i] for i in te]
    y_tr = y_arr[tr]
    y_te = y_arr[te]

    print(f"  Train size: {len(tr)}  Val: {len(vl)}  Test: {len(te)}")

    # ── Hypothesis 1: all test labels are the same class ─────────────────
    te_classes, te_counts = np.unique(y_te, return_counts=True)
    print(f"  Test set classes: {dict(zip(te_classes.tolist(), te_counts.tolist()))}")
    if len(te_classes) < 2:
        print("  ⚠  ONLY ONE CLASS IN TEST SET → trivially 100% precision or recall!")

    # ── Hypothesis 2: simulate a trivial classifier ───────────────────────
    # If majority class ≥ 95% → a dummy classifier predicts 100% accuracy
    maj_class = int(te_classes[np.argmax(te_counts)])
    dummy_preds = [maj_class] * len(y_te)
    dummy_m = _evaluate_predictions(y_te, dummy_preds)
    print(f"  Dummy (majority={maj_class}) accuracy: {dummy_m['accuracy']*100:.2f}%")
    print(f"  Dummy F1: {dummy_m['f1']*100:.2f}%")
    if dummy_m['accuracy'] >= 0.98:
        print(f"  ⚠  Dataset is highly imbalanced → DUMMY CLASSIFIER gets ≥98% accuracy")
        print(f"  ⚠  BiLSTM 100% may be trivially correct — not a sign of good learning")

    # ── Hypothesis 3: check if train and test sets overlap ────────────────
    overlap_texts = set(X_tr_texts) & set(X_te_texts)
    overlap_pct = len(overlap_texts) / max(len(X_te_texts), 1) * 100
    print(f"  Exact text overlap (train ∩ test): {len(overlap_texts)} rows = {overlap_pct:.1f}% of test")
    if overlap_pct > 10:
        print(f"  ⚠  HIGH OVERLAP: {overlap_pct:.1f}% of test texts also in train → DATA LEAKAGE")

print("\nDone.")
