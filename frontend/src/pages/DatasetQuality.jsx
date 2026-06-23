/**
 * Dataset Quality — /dataset-quality
 * Evidence quality report, duplicates, per-rule distribution.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Database, AlertTriangle, CheckCircle2, RefreshCw,
  BarChart3, Shield, TrendingUp,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── helpers ─────────────────────────────────────────────────────── */
const safeN  = (v) => (v == null ? '—' : Number(v).toLocaleString());
const safePct= (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`);

/* ── KPI card ─────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, color, bg, loading }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-400">{label}</p>
          <p className={`mt-2 text-3xl font-bold ${color}`}>
            {loading ? <span className="inline-block h-8 w-20 animate-pulse rounded bg-slate-100" /> : value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${bg}`}>
          <Icon size={17} className={color} />
        </div>
      </div>
    </div>
  );
}

/* ── Quality bar ──────────────────────────────────────────────────── */
function QualityBar({ label, value, max = 100 }) {
  const pct = Math.min(100, Math.max(0, (value / Math.max(max, 1)) * 100));
  const color = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : pct >= 40 ? 'bg-orange-500' : 'bg-rose-500';
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-600">{label}</span>
        <span className="font-semibold text-slate-800">{safeN(value)}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-all duration-700 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* ══════════════════════════ MAIN PAGE ═══════════════════════════ */
export default function DatasetQuality() {
  const [report,   setReport]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');
  const [normId,   setNormId]   = useState('');
  const [norms,    setNorms]    = useState([]);
  const [deduping, setDeduping] = useState(false);
  const [dedupMsg, setDedupMsg] = useState('');

  // Load norms
  useEffect(() => {
    api.get('/norms/').then(r => {
      const list = Array.isArray(r.data) ? r.data : [];
      setNorms(list);
      if (list.length > 0) setNormId(String(list[0].id));
    }).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const params = normId ? `?norm_id=${normId}` : '';
      const r = await api.get(`/dataset/quality-report/${params}`);
      setReport(r.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to load quality report.');
    } finally { setLoading(false); }
  }, [normId]);

  useEffect(() => { if (normId) load(); }, [load, normId]);

  const handleDeduplicate = async () => {
    setDeduping(true); setDedupMsg('');
    try {
      const r = await api.post('/evidence/deduplicate/', { norm_id: normId });
      setDedupMsg(`Removed ${r.data.removed ?? 0} duplicate(s).`);
      load();
    } catch (e) {
      setDedupMsg('Deduplication failed: ' + (e?.response?.data?.error || e.message));
    } finally { setDeduping(false); }
  };

  const ev         = report?.evidence || {};
  const dups       = {
    total:           ev.total ?? 0,
    unique:          ev.unique ?? 0,
    duplicates:      ev.duplicates ?? 0,
    duplication_rate: ev.duplication_rate ?? 0,
    status:          (ev.duplicates ?? 0) === 0 ? 'clean' : (ev.duplication_rate ?? 0) < 10 ? 'warning' : 'critical',
  };
  const coverage   = report?.coverage || {};
  const perRule    = report?.rule_distribution || [];
  const qualStatus = report?.quality_status || 'unknown';

  const qualColor = qualStatus === 'excellent' ? 'text-emerald-600 bg-emerald-50 border-emerald-200'
                  : qualStatus === 'good'       ? 'text-amber-600 bg-amber-50 border-amber-200'
                  : 'text-rose-600 bg-rose-50 border-rose-200';

  return (
    <Layout>
      <div className="space-y-6 pb-10">
        {/* Header */}
        <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-sky-950 to-slate-900 px-6 py-6 shadow-xl">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/20">
                <Database size={20} className="text-sky-300" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">Analytics</p>
                <h1 className="text-2xl font-bold text-white">Dataset Quality</h1>
                <p className="text-sm text-slate-400">Evidence analysis · Duplicate detection · Coverage</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {/* Norm selector */}
              {norms.length > 0 && (
                <select value={normId} onChange={e => setNormId(e.target.value)}
                  className="rounded-xl border border-slate-600 bg-white/10 px-3 py-2 text-sm text-white outline-none">
                  {norms.map(n => <option key={n.id} value={n.id} className="text-slate-900">{n.name}</option>)}
                </select>
              )}
              <button type="button" onClick={load} disabled={loading}
                className="flex items-center gap-1.5 rounded-2xl border border-slate-700 bg-white/5 px-3 py-2.5 text-xs font-semibold text-slate-300 hover:bg-white/10 transition">
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}
        {dedupMsg && <div className={`rounded-xl border px-4 py-3 text-sm ${dedupMsg.includes('failed') ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-emerald-200 bg-emerald-50 text-emerald-700'}`}>{dedupMsg}</div>}

        {/* Quality status banner */}
        {!loading && report && (
          <div className={`flex items-center gap-3 rounded-2xl border px-4 py-3 ${qualColor}`}>
            {qualStatus === 'excellent' ? <CheckCircle2 size={15} /> : <AlertTriangle size={15} />}
            <span className="font-semibold capitalize">Dataset Quality: {qualStatus.replace('_', ' ')}</span>
          </div>
        )}

        {/* KPI cards */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard icon={Database}    label="Total Evidence"      value={loading ? '…' : safeN(ev.total)}                    color="text-slate-900"   bg="bg-slate-100"   loading={loading} />
          <KpiCard icon={CheckCircle2}label="Approved"            value={loading ? '…' : safeN(ev.approved)}                 color="text-emerald-600" bg="bg-emerald-50"  loading={loading}
            sub={ev.total > 0 ? `${((ev.approved/ev.total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard icon={AlertTriangle}label="Rejected"           value={loading ? '…' : safeN(ev.rejected)}                 color="text-rose-600"    bg="bg-rose-50"     loading={loading}
            sub={ev.total > 0 ? `${((ev.rejected/ev.total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard icon={BarChart3}   label="Duplicate Rate"      value={loading ? '…' : safePct(ev.duplication_rate)}       color={ev.duplication_rate > 15 ? 'text-rose-600' : 'text-emerald-600'} bg={ev.duplication_rate > 15 ? 'bg-rose-50' : 'bg-emerald-50'} loading={loading} />
        </div>

        {/* Dataset Health Score */}
        {!loading && report && (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard icon={TrendingUp} label="Avg Evidence Length" value={`${Math.round(ev.avg_evidence_length ?? 0)} words`} color="text-sky-700" bg="bg-sky-50" loading={loading}
              sub={ev.avg_evidence_length < 10 ? 'Too short' : 'Good'} />
            <KpiCard icon={BarChart3}  label="Vocabulary Size"     value={safeN(ev.vocabulary_size)}                         color="text-violet-700" bg="bg-violet-50" loading={loading} />
            <KpiCard icon={BarChart3}  label="Avg Semantic Score"  value={`${Math.round(ev.avg_semantic_score ?? 0)}%`}      color="text-indigo-700" bg="bg-indigo-50" loading={loading} />
            <KpiCard icon={Shield}     label="Rules Covered"       value={`${safeN(coverage.rules_with_evidence)}/${safeN(coverage.total_rules)}`} color="text-teal-700" bg="bg-teal-50" loading={loading}
              sub={`${safePct(coverage.coverage_pct)} coverage`} />
          </div>
        )}

        {/* Coverage + Duplicates side by side */}
        <div className="grid gap-4 xl:grid-cols-2">
          {/* Coverage */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <Shield size={15} className="text-slate-500" />
                <p className="text-sm font-bold text-slate-900">Rule Coverage</p>
              </div>
              <span className="text-sm font-bold text-indigo-600">{safePct(coverage.coverage_pct)}</span>
            </div>
            {loading ? (
              <div className="space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-6 animate-pulse rounded bg-slate-100" />)}</div>
            ) : (
              <div className="space-y-3">
                <QualityBar label="Rules with evidence"     value={coverage.rules_with_evidence ?? 0}    max={coverage.total_rules ?? 1} />
                <QualityBar label="Rules with approved evidence" value={coverage.rules_with_approved ?? 0} max={coverage.total_rules ?? 1} />
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  {[
                    { label: 'Total rules',    value: safeN(coverage.total_rules) },
                    { label: 'Covered',        value: safeN(coverage.rules_with_evidence) },
                    { label: 'Uncovered',      value: safeN((coverage.total_rules || 0) - (coverage.rules_with_evidence || 0)) },
                  ].map(s => (
                    <div key={s.label} className="rounded-lg bg-slate-50 px-2 py-2">
                      <p className="text-slate-400 text-[10px]">{s.label}</p>
                      <p className="font-bold text-slate-800">{s.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Duplicates */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex items-center justify-between gap-3 mb-4">
              <div className="flex items-center gap-2">
                <AlertTriangle size={15} className="text-slate-500" />
                <p className="text-sm font-bold text-slate-900">Duplicate Analysis</p>
              </div>
              <button type="button" onClick={handleDeduplicate} disabled={deduping || loading || (dups.duplicates || 0) === 0}
                className="flex items-center gap-1.5 rounded-xl bg-rose-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-rose-600 disabled:opacity-40 transition">
                {deduping ? <RefreshCw size={11} className="animate-spin" /> : <AlertTriangle size={11} />}
                Deduplicate
              </button>
            </div>
            {loading ? (
              <div className="space-y-3">{[...Array(3)].map((_, i) => <div key={i} className="h-6 animate-pulse rounded bg-slate-100" />)}</div>
            ) : (
              <div className="space-y-3">
                <QualityBar label="Unique texts"    value={dups.unique ?? 0}     max={dups.total ?? 1} />
                <QualityBar label="Duplicate texts" value={dups.duplicates ?? 0} max={dups.total ?? 1} />
                <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
                  {[
                    { label: 'Total',      value: safeN(dups.total) },
                    { label: 'Unique',     value: safeN(dups.unique) },
                    { label: 'Duplicates', value: safeN(dups.duplicates), warn: (dups.duplicates || 0) > 0 },
                  ].map(s => (
                    <div key={s.label} className={`rounded-lg px-2 py-2 ${s.warn ? 'bg-rose-50' : 'bg-slate-50'}`}>
                      <p className="text-slate-400 text-[10px]">{s.label}</p>
                      <p className={`font-bold ${s.warn ? 'text-rose-700' : 'text-slate-800'}`}>{s.value}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Per-rule distribution */}
        {!loading && perRule.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center gap-2 border-b border-slate-100 px-5 py-4">
              <TrendingUp size={15} className="text-slate-500" />
              <p className="text-sm font-bold text-slate-900">Per-Rule Evidence Distribution</p>
              <span className="ml-auto text-xs text-slate-400">{perRule.length} rules</span>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-xs">
                <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                  <tr>
                    <th className="px-4 py-3 text-left">Rule</th>
                    <th className="px-4 py-3 text-right">Total</th>
                    <th className="px-4 py-3 text-right">Approved</th>
                    <th className="px-4 py-3 text-right">Rejected</th>
                    <th className="px-4 py-3 text-right">Coverage</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {perRule.map((r, i) => {
                    const total   = r.total || 0;
                    const appPct  = total > 0 ? Math.round((r.approved || 0) / total * 100) : 0;
                    return (
                      <tr key={i} className="hover:bg-slate-50">
                        <td className="px-4 py-2.5 text-slate-700 max-w-xs truncate">{r.rule_title || r.rule || '—'}</td>
                        <td className="px-4 py-2.5 text-right font-semibold text-slate-800">{safeN(r.total)}</td>
                        <td className="px-4 py-2.5 text-right text-emerald-600 font-semibold">{safeN(r.approved)}</td>
                        <td className="px-4 py-2.5 text-right text-rose-600 font-semibold">{safeN(r.rejected)}</td>
                        <td className="px-4 py-2.5 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                              <div className={`h-full rounded-full ${appPct >= 80 ? 'bg-emerald-500' : appPct >= 40 ? 'bg-amber-500' : 'bg-rose-500'}`}
                                style={{ width: `${appPct}%` }} />
                            </div>
                            <span className="font-semibold text-slate-600 w-8">{appPct}%</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
