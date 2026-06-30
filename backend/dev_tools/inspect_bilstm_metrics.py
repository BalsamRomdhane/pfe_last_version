"""
inspect_bilstm_metrics.py
--------------------------
Analyse complète des métriques BiLSTM dans tous les fichiers JSON
disponibles. Compare les valeurs BiLSTM avec les autres algorithmes
et vérifie si les 100% sont plausibles ou non.
"""
import os
import sys
import json
import glob

MODELS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'ml', 'models')
ARTIFACTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'artifacts')

ALGOS = ['RandomForest', 'LogisticRegression', 'GradientBoosting', 'BiLSTM']

def analyse_metrics_file(path):
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n{'='*70}")
    print(f"FILE: {os.path.basename(path)}")
    print(f"{'='*70}")
    print(f"  best_model  : {data.get('best_model')}")
    print(f"  standard    : {data.get('standard')}")
    print(f"  trained_at  : {data.get('trained_at')}")
    print(f"  samples     : {data.get('samples')} / dataset_size={data.get('dataset_size')}")
    print(f"  train_size  : {data.get('train_size')} / val_size={data.get('val_size')} / test_size={data.get('test_size')}")

    results = data.get('results', {})
    print()
    print(f"  {'ALGO':<25} {'ACC':>8} {'PREC':>8} {'REC':>8} {'F1':>8}  {'SAMPLES':>8}  {'PIPELINE':<12}  ERROR?")
    print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8}  {'-'*8}  {'-'*12}  {'------'}")

    for algo in ALGOS:
        if algo not in results:
            print(f"  {algo:<25} {'N/A':>8} {'N/A':>8} {'N/A':>8} {'N/A':>8}  {'N/A':>8}  {'N/A':<12}  [NOT IN JSON]")
            continue
        m = results[algo]
        err = m.get('error')
        acc   = m.get('accuracy')
        prec  = m.get('precision')
        rec   = m.get('recall')
        f1    = m.get('f1_score')
        n     = m.get('sample_count')
        pipe  = m.get('pipeline', '?')
        tr_sz = m.get('train_size', '?')
        te_sz = m.get('test_size', '?')

        acc_s  = f"{acc*100:.2f}%" if acc  is not None else 'None'
        prec_s = f"{prec*100:.2f}%" if prec is not None else 'None'
        rec_s  = f"{rec*100:.2f}%" if rec  is not None else 'None'
        f1_s   = f"{f1*100:.2f}%" if f1   is not None else 'None'
        n_s    = str(n) if n is not None else 'None'

        print(f"  {algo:<25} {acc_s:>8} {prec_s:>8} {rec_s:>8} {f1_s:>8}  {n_s:>8}  {str(pipe):<12}  {'YES: '+str(err)[:40] if err else 'No'}")

        # Show split details for BiLSTM
        if algo == 'BiLSTM' and not err:
            print(f"    └─ BiLSTM train_size={tr_sz}  test_size={te_sz}")
            # Check for data leakage indicators
            total_algo = (tr_sz if isinstance(tr_sz, int) else 0) + (te_sz if isinstance(te_sz, int) else 0)
            global_total = data.get('samples', 0) or 0
            if total_algo and global_total and total_algo > global_total * 1.1:
                print(f"    ⚠  POSSIBLE LEAK: BiLSTM uses {total_algo} rows but global dataset has {global_total}")
            # 100% check
            if acc is not None and acc >= 0.999 and f1 is not None and f1 >= 0.999:
                print(f"    ⚠  SUSPICIOUS: BiLSTM shows 100% on all metrics")
                if n is not None and n < 50:
                    print(f"    ⚠  TINY DATASET: only {n} samples → very likely overfitting")
                    print(f"    ⚠  With {n} samples and simple shuffled split, perfect scores are common")

    # Cross-check BiLSTM vs others
    bilstm = results.get('BiLSTM', {})
    others = {k: v for k, v in results.items() if k != 'BiLSTM' and not v.get('error')}
    if bilstm and not bilstm.get('error') and others:
        b_acc = bilstm.get('accuracy')
        b_f1  = bilstm.get('f1_score')
        b_n   = bilstm.get('sample_count')
        avg_acc = sum(v.get('accuracy', 0) for v in others.values()) / max(len(others), 1)
        avg_f1  = sum(v.get('f1_score',  0) for v in others.values()) / max(len(others), 1)
        print()
        print(f"  CROSS-CHECK:")
        print(f"    Scikit-learn avg accuracy : {avg_acc*100:.2f}%")
        print(f"    Scikit-learn avg F1       : {avg_f1*100:.2f}%")
        print(f"    BiLSTM accuracy           : {b_acc*100:.2f}% (n={b_n})" if b_acc is not None else "    BiLSTM accuracy: None")
        print(f"    BiLSTM F1                 : {b_f1*100:.2f}%" if b_f1 is not None else "    BiLSTM F1: None")

        if b_acc is not None and b_acc >= 0.999:
            gap = b_acc - avg_acc
            print()
            print(f"  VERDICT:")
            if b_n is not None and b_n < 50:
                print(f"    ⚠  BiLSTM 100% is SUSPICIOUS — dataset too small ({b_n} samples)")
                print(f"    ⚠  With {b_n} samples, a simple model can easily memorize all training data")
                print(f"    ⚠  The split may not have been grouped (different from RF/LR/GB)")
            elif gap > 0.05:
                print(f"    ⚠  BiLSTM outperforms Scikit-learn by {gap*100:.1f}% — unusual gap, verify split")
            else:
                print(f"    ✓  100% may be valid — dataset is very simple/separable")


print("BILSTM METRICS AUDIT")
print("====================")

# Main metrics files
for pattern in ['*.json']:
    for path in sorted(glob.glob(os.path.join(MODELS_DIR, pattern))):
        if 'evidence' in os.path.basename(path).lower():
            continue
        analyse_metrics_file(path)

# Artifacts
eval_path = os.path.join(ARTIFACTS_DIR, 'evaluation_summary.json')
if os.path.exists(eval_path):
    print(f"\n{'='*70}")
    print(f"ARTIFACTS/evaluation_summary.json")
    print(f"{'='*70}")
    with open(eval_path) as f:
        print(json.dumps(json.load(f), indent=2))
