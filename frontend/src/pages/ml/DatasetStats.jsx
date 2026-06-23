/**
 * DatasetStats — ML Dashboard statistics panel.
 *
 * Sources data from RuleTrainingSample (the evidence repository).
 * Shows: counts, dataset quality metrics, sync warning, training readiness.
 */
import React from 'react';
import {
  AlertTriangle, CheckCircle2, RefreshCw,
  BarChart3, Layers, Target, Zap,
} from 'lucide-react';

const safeN  = (v) => (v == null ? '—' : Number(v).toLocaleString());
const safePct = (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`);

/* ── KPI card ─────────────────────────────────────────────────────────── */
function KpiCard({ label, value, color, border, bg, icon: Icon, loading, sub }) {
  return (
    <div className={`rounded-2xl border ${border || 'border-slate-200'} ${bg || 'bg-white'} p-5 shadow-sm`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-widest text-slate-500">{label}</p>
          <p className={`mt-3 text-4xl font-bold ${color || 'text-slate-900'}`}>
            {loading
              ? <span className="inline-block h-9 w-20 animate-pulse rounded-lg bg-slate-100" />
              : value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
        </div>
        {Icon && (
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${bg ? bg.replace('bg-', 'bg-').replace('-50', '-100') : 'bg-slate-100'}`}>
            <Icon size={18} className={color || 'text-slate-600'} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Quality bar ─────────────────────────────────────────────────────── */
function QualityBar({ label, value, color }) {
  const pct = Math.min(100, Math.max(0, value || 0));
  const barColor =
    pct >= 80 ? 'bg-emerald-500'
    : pct >= 60 ? 'bg-amber-500'
    : pct >= 40 ? 'bg-orange-500'
    : 'bg-rose-500';

  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs text-slate-600">{label}</span>
        <span className={`text-xs font-bold ${color || 'text-slate-700'}`}>{safePct(value)}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div
          className={`h-full rounded-full transition-all duration-700 ${barColor}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

/* ── Main component ───────────────────────────────────────────────────── */
export default function DatasetStats({ stats, loading, datasetType, selectedNorm, onSync }) {
  if (datasetType === 'evidence') {
    const approved = stats?.approved_samples ?? 0;
    const rejected = stats?.rejected_samples ?? 0;
    const total    = stats?.total_samples ?? 0;
    const covered  = stats?.rules_covered ?? 0;
    const totalRules = stats?.total_rules ?? 0;
    const embModel = stats?.embedding_model || 'tfidf-fallback';
    const embDim   = stats?.embedding_dim;

    return (
      <div className="space-y-4">
        {/* Training readiness */}
        {!loading && (
          <div className={`flex items-center gap-3 rounded-2xl border px-4 py-2.5 text-sm ${
            total >= 20
              ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
              : 'border-rose-200 bg-rose-50 text-rose-700'
          }`}>
            {total >= 20
              ? <CheckCircle2 size={15} className="text-emerald-600 shrink-0" />
              : <AlertTriangle size={15} className="text-rose-500 shrink-0" />
            }
            <span className="font-medium">
              {total >= 20
                ? `Evidence training enabled — ${total.toLocaleString()} records indexed`
                : `Need at least 20 evidence records (currently ${total})`
              }
            </span>
          </div>
        )}

        <section className="grid gap-4 md:grid-cols-5">
          <KpiCard label="Total Evidence"   value={loading ? '—' : safeN(total)}    color="text-slate-900"   border="border-slate-200"   icon={Layers}      loading={loading} />
          <KpiCard label="Approved"         value={loading ? '—' : safeN(approved)} color="text-emerald-600" border="border-emerald-200" bg="bg-emerald-50" icon={CheckCircle2} loading={loading}
            sub={total > 0 ? `${((approved/total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard label="Rejected"         value={loading ? '—' : safeN(rejected)} color="text-rose-600"    border="border-rose-200"    bg="bg-rose-50"    icon={AlertTriangle} loading={loading}
            sub={total > 0 ? `${((rejected/total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard label="Rules Covered"    value={loading ? '—' : `${safeN(covered)}/${safeN(totalRules)}`} color="text-sky-700" border="border-sky-200" bg="bg-sky-50" icon={Target} loading={loading} />
          <KpiCard label="Embedding Model"  value={loading ? '—' : (embDim ? `dim=${embDim}` : embModel)} color="text-cyan-900" border="border-cyan-200" bg="bg-cyan-50" icon={BarChart3} loading={loading}
            sub={embModel} />
        </section>

        {/* Norm badge */}
        {selectedNorm && (
          <div className="inline-flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-1.5 text-xs font-semibold text-cyan-800">
            <Target size={11} />
            {selectedNorm.name || selectedNorm}
          </div>
        )}
      </div>
    );
  }

  // ── Classification mode — sourced from RuleTrainingSample ─────────────────
  const totalSamples    = stats?.total_samples ?? 0;
  const approved        = stats?.approved_samples ?? 0;
  const rejected        = stats?.rejected_samples ?? stats?.invalid_samples ?? 0;
  const rulesCount      = stats?.rules_count ?? 0;
  const coveredRules    = stats?.covered_rules_count ?? 0;
  const trainingEnabled = stats?.training_enabled ?? (totalSamples >= 20);
  const syncRequired    = stats?.sync_required ?? false;
  const legacySamples   = stats?.legacy_samples ?? 0;
  const qualityScore    = stats?.quality_score ?? 0;
  const classBalance    = stats?.class_balance ?? 0;
  const duplicateRate   = stats?.duplicate_rate ?? 0;
  const coverageRate    = stats?.coverage_rate ?? 0;
  const avgLength       = stats?.avg_evidence_length ?? 0;
  const richness        = stats?.dataset_richness ?? 0;

  return (
    <div className="space-y-4">

      {/* ── Sync warning ──────────────────────────────────────────────── */}
      {!loading && syncRequired && (
        <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertTriangle size={16} className="mt-0.5 shrink-0 text-amber-500" />
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-amber-800">Dataset synchronization required</p>
            <p className="text-xs text-amber-700 mt-0.5">
              Evidence repository has {safeN(totalSamples)} labelled samples, while the legacy ML dataset currently has {safeN(legacySamples)} rows.
            </p>
          </div>
          {onSync && (
            <button
              type="button"
              onClick={onSync}
              className="flex-shrink-0 flex items-center gap-1.5 rounded-xl bg-amber-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-amber-700 transition"
            >
              <RefreshCw size={11} />
              Sync Dataset
            </button>
          )}
        </div>
      )}

      {/* ── Training readiness ────────────────────────────────────────── */}
      {!loading && (
        <div className={`flex items-center gap-3 rounded-2xl border px-4 py-2.5 text-sm ${
          trainingEnabled
            ? 'border-emerald-200 bg-emerald-50 text-emerald-800'
            : 'border-rose-200 bg-rose-50 text-rose-700'
        }`}>
          {trainingEnabled
            ? <CheckCircle2 size={15} className="text-emerald-600 shrink-0" />
            : <AlertTriangle size={15} className="text-rose-500 shrink-0" />
          }
          <span className="font-medium">
            {trainingEnabled
              ? `Training enabled — ${safeN(totalSamples)} labelled samples available`
              : `Training disabled — need at least 20 labelled samples (currently ${totalSamples})`
            }
          </span>
        </div>
      )}

      {/* ── KPI cards ─────────────────────────────────────────────────── */}
      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          label="Total Samples"
          value={safeN(totalSamples)}
          color="text-slate-900"
          border="border-slate-200"
          icon={Layers}
          loading={loading}
          sub="Approved + Rejected"
        />
        <KpiCard
          label="Approved"
          value={safeN(approved)}
          color="text-emerald-600"
          border="border-emerald-200"
          bg="bg-emerald-50"
          icon={CheckCircle2}
          loading={loading}
          sub={totalSamples > 0 ? `${((approved / totalSamples) * 100).toFixed(0)}% of total` : undefined}
        />
        <KpiCard
          label="Rejected"
          value={safeN(rejected)}
          color="text-rose-600"
          border="border-rose-200"
          bg="bg-rose-50"
          icon={AlertTriangle}
          loading={loading}
          sub={totalSamples > 0 ? `${((rejected / totalSamples) * 100).toFixed(0)}% of total` : undefined}
        />
        <KpiCard
          label="Rules Count"
          value={safeN(rulesCount)}
          color="text-slate-900"
          border="border-slate-200"
          icon={Target}
          loading={loading}
          sub={coveredRules > 0 ? `${safeN(coveredRules)} covered` : undefined}
        />
        <KpiCard
          label="Quality Score"
          value={loading ? '—' : `${qualityScore.toFixed(0)}%`}
          color={qualityScore >= 80 ? 'text-emerald-600' : qualityScore >= 60 ? 'text-amber-600' : 'text-rose-600'}
          border={qualityScore >= 80 ? 'border-emerald-200' : qualityScore >= 60 ? 'border-amber-200' : 'border-rose-200'}
          bg={qualityScore >= 80 ? 'bg-emerald-50' : qualityScore >= 60 ? 'bg-amber-50' : 'bg-rose-50'}
          icon={BarChart3}
          loading={loading}
          sub="Dataset quality"
        />
      </section>

      {/* ── Dataset quality metrics panel ─────────────────────────────── */}
      {!loading && totalSamples > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <Zap size={15} className="text-indigo-600" />
            <p className="text-sm font-bold text-slate-900">Dataset Quality Metrics</p>
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-3">
              <QualityBar label="Dataset Richness"  value={richness}      color="text-indigo-700" />
              <QualityBar label="Class Balance"     value={classBalance}  color={classBalance >= 60 ? 'text-emerald-700' : 'text-amber-700'} />
              <QualityBar label="Coverage Rate"     value={coverageRate}  color="text-sky-700" />
              <QualityBar label="Clean Rate"        value={100 - duplicateRate} color={duplicateRate < 10 ? 'text-emerald-700' : 'text-amber-700'} />
            </div>
            <div className="grid grid-cols-2 gap-3 text-xs">
              {[
                { label: 'Duplicate Rate',        value: safePct(duplicateRate),   warn: duplicateRate > 15 },
                { label: 'Avg Evidence Length',   value: `${avgLength} words`,     warn: avgLength < 10 },
                { label: 'Covered Rules',         value: `${coveredRules}/${rulesCount}`, warn: coveredRules < rulesCount },
                { label: 'Training Ready',        value: trainingEnabled ? 'Yes ✓' : 'No ✗', warn: !trainingEnabled },
              ].map(m => (
                <div key={m.label} className={`rounded-xl px-3 py-2 ${m.warn ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50'}`}>
                  <p className="text-slate-400">{m.label}</p>
                  <p className={`font-bold mt-0.5 ${m.warn ? 'text-amber-700' : 'text-slate-800'}`}>{m.value}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Norm badge ────────────────────────────────────────────────── */}
      {selectedNorm && (
        <div className="inline-flex items-center gap-2 rounded-xl border border-cyan-200 bg-cyan-50 px-3 py-1.5 text-xs font-semibold text-cyan-800">
          <Target size={11} />
          {selectedNorm.name}
        </div>
      )}
    </div>
  );
}
