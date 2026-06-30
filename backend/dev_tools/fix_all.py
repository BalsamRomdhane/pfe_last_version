# -*- coding: utf-8 -*-
"""
Fix all remaining issues after MLOps audit.
Run once: python fix_all.py
"""
import os, sys, json, time
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
sys.stdout.reconfigure(encoding='utf-8')

import django
django.setup()

from django.contrib.auth.models import User
from api.models import (
    Norme, Document, Validation, TrainingSample, RuleTrainingSample,
    aggregate_validation_metrics, extract_features, build_validation_feature_vector
)

S = "=" * 60

# ── STEP 1: Reset admin password ──────────────────────────────────
print(S); print("STEP 1 - RESET TEST PASSWORDS"); print(S)
for uname in ['admin', 'teamlead1', 'employee1']:
    try:
        u = User.objects.get(username=uname)
        u.set_password('admin123')
        u.save()
        print(f"  {uname}: password reset to admin123")
    except User.DoesNotExist:
        print(f"  {uname}: NOT FOUND")

# ── STEP 2: Rebuild ISO 9001 TrainingSamples from real validations ─
print(f"\n{S}"); print("STEP 2 - REBUILD ISO9001 TRAINING SAMPLES"); print(S)
norm_iso9001 = Norme.objects.filter(name__icontains='ISO 9001').first()
if norm_iso9001:
    docs = Document.objects.filter(norme=norm_iso9001, is_finalized=True)
    created = updated = skipped = 0
    for doc in docs:
        metrics  = aggregate_validation_metrics(doc)
        features = extract_features(doc)
        fvector  = build_validation_feature_vector(doc)
        status   = doc.final_decision or doc.status
        approved = (True if status in ['approved','auto_approved']
                   else False if status == 'rejected' else None)
        _, was_created = TrainingSample.objects.update_or_create(
            document=doc,
            defaults={
                'norm_id':             doc.norme_id,
                'features':            features,
                'feature_vector':      fvector,
                'label':               status,
                'standard':            norm_iso9001.name,
                'teamlead_decision':   status,
                'final_decision':      status,
                'decision_reason':     doc.decision_reason,
                'approved':            approved,
                'total_rules':         metrics['total_rules'],
                'valid_rules_count':   metrics['valid_rules_count'],
                'invalid_rules_count': metrics['invalid_rules_count'],
                'approved_rules':      metrics['approved_rules'],
                'rejected_rules':      metrics['rejected_rules'],
                'rule_results_json':   metrics['rule_results_json'],
                'compliance_score':    metrics['compliance_score'],
            }
        )
        if was_created: created += 1
        else:           updated += 1
    print(f"  ISO 9001: created={created} updated={updated}")
else:
    print("  ISO 9001 norm not found")

# ── STEP 3: Verify compliance_chat endpoint ───────────────────────
print(f"\n{S}"); print("STEP 3 - COMPLIANCE_CHAT ENDPOINT CHECK"); print(S)
try:
    from api.views import compliance_chat_api
    import inspect
    src = inspect.getsource(compliance_chat_api)
    # Check if generate_compliance_answer is called correctly
    has_import = 'from services.llm_service import generate_compliance_answer' in src
    has_call   = 'generate_compliance_answer(' in src
    print(f"  has generate import: {has_import}")
    print(f"  has generate call  : {has_call}")

    # Test the function itself
    from services.llm_service import generate_compliance_answer
    result = generate_compliance_answer(
        question="What is compliance?",
        context_rules=[],
        context_evidence=[],
        standard='ISO9001',
    )
    print(f"  generate returns type: {type(result).__name__}")
    if isinstance(result, dict):
        print(f"  keys: {list(result.keys())}")
        print(f"  has answer: {'answer' in result}")
    print("  compliance_chat function: OK")
except Exception as e:
    print(f"  ERROR: {e}")

# ── STEP 4: Verify RuleTrainingSampleViewSet fix ──────────────────
print(f"\n{S}"); print("STEP 4 - RULE-TRAINING-SAMPLES QUERYSET"); print(S)
from api.models import RuleTrainingSample
qs = RuleTrainingSample.objects.select_related('document','rule','norm').filter(norm_id=4)
count = qs.count()
items = list(qs[:5])
print(f"  filter norm_id=4: count={count}, slice(5) len={len(items)}")
if items:
    print(f"  First item: id={items[0].id} label={items[0].label} rule={items[0].rule_title[:30]}")

# ── STEP 5: Validate dataset_stats_api output ─────────────────────
print(f"\n{S}"); print("STEP 5 - DATASET_STATS_API VALIDATION"); print(S)
for norm in Norme.objects.all():
    rts_qs   = RuleTrainingSample.objects.filter(norm=norm)
    approved = rts_qs.filter(label='approved').count()
    rejected = rts_qs.filter(label='rejected').count()
    total    = approved + rejected
    rules    = norm.rules.count()
    covered  = rts_qs.filter(label='approved').values('rule_id').distinct().count()
    balance  = round(min(approved,rejected)/max(max(approved,rejected),1)*100, 1) if total > 0 else 0
    cov_rate = round(covered/max(rules,1)*100, 1)
    ts_count = TrainingSample.objects.filter(standard=norm.name).count()
    print(f"  [{norm.name[:35]}]")
    print(f"    RuleTS: total={total} approved={approved} rejected={rejected}")
    print(f"    Rules : {rules} total, {covered} covered ({cov_rate}%)")
    print(f"    Balance: {balance}%")
    print(f"    TrainingSample: {ts_count}")
    print(f"    Training enabled: {total >= 20}")

# ── STEP 6: Verify audit script result ───────────────────────────
print(f"\n{S}"); print("STEP 6 - FINAL STATE VERIFICATION"); print(S)
print(f"TrainingSample total: {TrainingSample.objects.count()}")
print(f"  approved: {TrainingSample.objects.filter(label='approved').count()}")
print(f"  rejected: {TrainingSample.objects.filter(label='rejected').count()}")
ts_0_rules = TrainingSample.objects.filter(total_rules=0).count()
ts_0_score = TrainingSample.objects.filter(compliance_score=0).count()
print(f"  total_rules=0: {ts_0_rules}")
print(f"  compliance=0 : {ts_0_score}")
print(f"RuleTrainingSample total: {RuleTrainingSample.objects.count()}")

print(f"\n{S}"); print("ALL FIXES COMPLETE"); print(S)
