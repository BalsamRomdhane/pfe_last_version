# -*- coding: utf-8 -*-
import os, sys, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'enterprise_platform.settings'
sys.stdout.reconfigure(encoding='utf-8')
django.setup()

from collections import Counter
from api.models import Norme, Rule, Document, Validation, TrainingSample, RuleTrainingSample

S = "=" * 65

# ── 1. DB Counts ──────────────────────────────────────────────────
print(S); print("SECTION 1 - DATABASE STATE"); print(S)
print(f"Normes             : {Norme.objects.count()}")
print(f"Rules              : {Rule.objects.count()}")
print(f"Documents          : {Document.objects.count()}")
print(f"Validations        : {Validation.objects.count()}")
print(f"TrainingSample     : {TrainingSample.objects.count()}")
print(f"RuleTrainingSample : {RuleTrainingSample.objects.count()}")

# ── 2. Per-norm ────────────────────────────────────────────────────
print(f"\n{S}"); print("SECTION 2 - PER-NORM BREAKDOWN"); print(S)
for norm in Norme.objects.all():
    docs    = Document.objects.filter(norme=norm).count()
    vals    = Validation.objects.filter(rule__norme=norm).count()
    ts_name = TrainingSample.objects.filter(standard=norm.name).count()
    ts_id   = TrainingSample.objects.filter(norm_id=norm.id).count()
    rts     = RuleTrainingSample.objects.filter(norm=norm)
    rts_a   = rts.filter(label='approved').count()
    rts_r   = rts.filter(label='rejected').count()
    print(f"\n[{norm.id}] {norm.name}")
    print(f"  Rules         : {norm.rules.count()}")
    print(f"  Documents     : {docs}")
    print(f"  Validations   : {vals}")
    print(f"  TrainingSample: {ts_name} (by name) | {ts_id} (by norm_id)")
    print(f"  RuleTraining  : {rts.count()} (approved={rts_a} rejected={rts_r})")

# ── 3. TrainingSample quality ─────────────────────────────────────
print(f"\n{S}"); print("SECTION 3 - TRAINING SAMPLE QUALITY"); print(S)
ts_all = list(TrainingSample.objects.all())
print(f"Total         : {len(ts_all)}")
print(f"total_rules=0 : {sum(1 for s in ts_all if s.total_rules == 0)}")
print(f"compliance=0  : {sum(1 for s in ts_all if s.compliance_score == 0)}")
print(f"features empty: {sum(1 for s in ts_all if not s.features)}")
print(f"fvector empty : {sum(1 for s in ts_all if not s.feature_vector)}")
print(f"label approved: {sum(1 for s in ts_all if s.label == 'approved')}")
print(f"label rejected: {sum(1 for s in ts_all if s.label == 'rejected')}")
print(f"norm_id vals  : {sorted(set(s.norm_id for s in ts_all))}")
print(f"standard vals : {sorted(set(s.standard for s in ts_all))}")

# Sample 3 records
print("\nSample TrainingSamples:")
for s in TrainingSample.objects.all()[:3]:
    fv = s.feature_vector
    fv_len = len(fv) if isinstance(fv, (dict,list)) else 0
    f_len  = len(s.features) if isinstance(s.features, (dict,list)) else 0
    print(f"  TS#{s.id}: total_rules={s.total_rules} valid={s.valid_rules_count} "
          f"score={s.compliance_score} fv_keys={fv_len} f_keys={f_len} label={s.label}")

# ── 4. Document -> Validation -> TS flow ──────────────────────────
print(f"\n{S}"); print("SECTION 4 - DOCUMENT->VALIDATION->TS FLOW"); print(S)
for norm in Norme.objects.all():
    docs = Document.objects.filter(norme=norm)
    with_ts  = docs.filter(training_sample__isnull=False).count()
    finalized= docs.filter(is_finalized=True).count()
    approved = docs.filter(status='approved').count()
    rejected = docs.filter(status='rejected').count()
    print(f"\n[{norm.name[:40]}]")
    print(f"  Total docs   : {docs.count()}")
    print(f"  Finalized    : {finalized}")
    print(f"  Approved     : {approved}")
    print(f"  Rejected     : {rejected}")
    print(f"  Have TS      : {with_ts}")

# ── 5. Coverage rate analysis ─────────────────────────────────────
print(f"\n{S}"); print("SECTION 5 - COVERAGE ANALYSIS"); print(S)
for norm in Norme.objects.all():
    rts_qs       = RuleTrainingSample.objects.filter(norm=norm)
    covered_ids  = set(rts_qs.filter(label='approved').values_list('rule_id', flat=True).distinct())
    rule_ids     = set(norm.rules.values_list('id', flat=True))
    rules_count  = len(rule_ids)
    approved     = rts_qs.filter(label='approved').count()
    rejected     = rts_qs.filter(label='rejected').count()
    total        = approved + rejected
    covered      = len(covered_ids)
    cov_rate     = round(covered / max(rules_count, 1) * 100, 1)
    balance      = round(min(approved,rejected) / max(max(approved,rejected),1) * 100, 1)
    print(f"\n[{norm.name[:40]}]")
    print(f"  rules_count   : {rules_count}")
    print(f"  covered_rules : {covered}")
    print(f"  coverage_rate : {cov_rate}%")
    print(f"  approved      : {approved}")
    print(f"  rejected      : {rejected}")
    print(f"  class_balance : {balance}%")
    # TS counts for this norm
    ts_c = TrainingSample.objects.filter(standard=norm.name).count()
    print(f"  TrainingSample: {ts_c}")
    if ts_c > 0:
        rules_hist = Counter(s.total_rules for s in TrainingSample.objects.filter(standard=norm.name))
        print(f"  TS total_rules distribution: {dict(rules_hist.most_common(5))}")

# ── 6. compliance_chat 500 analysis ──────────────────────────────
print(f"\n{S}"); print("SECTION 6 - COMPLIANCE_CHAT 500 ANALYSIS"); print(S)
try:
    from services.llm_service import generate_compliance_answer
    import inspect
    sig = inspect.signature(generate_compliance_answer)
    src = inspect.getsource(generate_compliance_answer)
    is_generator = 'yield' in src
    print(f"generate_compliance_answer params: {list(sig.parameters.keys())}")
    print(f"Is generator function: {is_generator}")
    print(f"Returns: {'generator' if is_generator else 'value'}")
except Exception as e:
    print(f"llm_service import error: {e}")

# ── 7. Root cause summary ─────────────────────────────────────────
print(f"\n{S}"); print("SECTION 7 - ROOT CAUSE SUMMARY"); print(S)
print("""
ROOT CAUSE 1: ISO 27001 / TISAX have 0 TrainingSamples
  -> No Documents linked to these norms (Documents=0)
  -> Signal fires only on Validation.post_save -> Document required
  -> RuleTrainingSamples were SEEDED directly (no document linkage)
  -> TrainingSample.document = OneToOneField(Document, required)
  -> SOLUTION: Create a management command to build TrainingSamples
     by grouping RuleTrainingSamples by norm and creating synthetic
     document-level summaries per rule-group.

ROOT CAUSE 2: MLDashboard dataset table shows 0 rules
  -> dataset_stats_api returns 'samples' from RuleTrainingSample
  -> RuleTrainingSample fields: rule_title, evidence_text, label, confidence_score
  -> MLDashboard reads: sample.rules_count, sample.feature_vector
  -> These fields DONT EXIST in RuleTrainingSample
  -> SOLUTION: Fix MLDashboard DatasetEntries to read correct fields
     OR return TrainingSample records from dataset_stats_api

ROOT CAUSE 3: compliance_chat/ 500
  -> generate_compliance_answer may fail on LLM call
  -> Need to inspect exact error in server logs

ROOT CAUSE 4: Coverage Rate = 0% displayed somewhere
  -> dataset_stats_api correctly computes coverage_rate=100%
  -> The old DatasetStats evidence mode read undefined fields
  -> FIXED: useDatasetStats now fetches from evidence/status endpoint
""")

print(S); print("AUDIT COMPLETE"); print(S)
