/**
 * Training Dataset — /training-dataset
 * Full MLOps module: health score, coverage, analytics, table, readiness.
 * Uses real PostgreSQL data only.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Database, CheckCircle2, XCircle, BarChart3, Shield,
  TrendingUp, RefreshCw, AlertTriangle, Target,
  ChevronDown, ChevronUp, GitBranch,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── helpers ─────────────────────────────────────────────────── */
const safeN   = (v) => (v == null ? '—' : Number(v).toLocaleString());
const safePct = (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`);
const fmtDate = (d) => d ? new Date(d).toLocaleDateString('fr-FR') : '—';

/* ── Health badge ─────────────────────────────────────────────── */
function HealthBadge({ score }) {
  const level = score >= 90 ? 'EXCELLENT' : score >= 70 ? 'GOOD' : score >= 50 ? 'WARNING' : 'CRITICAL';
  const cls = {
    EXCELLENT: 'bg-emerald-100 text-emerald-700 border-emerald-200',
    GOOD:      'bg-sky-100 text-sky-700 border-sky-200',
    WARNING:   'bg-amber-100 text-amber-700 border-amber-200',
    CRITICAL:  'bg-rose-100 text-rose-700 border-rose-200',
  }[level];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold ${cls}`}>
      {level === 'EXCELLENT' && <CheckCircle2 size={11} />}
      {level === 'CRITICAL'  && <AlertTriangle size={11} />}
      {level}  {score.toFixed(0)}%
    </span>
  );
}

/* ── KPI card ─────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, color = 'text-slate-900', bg = 'bg-white', loading }) {
  return (
    <div className={`rounded-2xl border border-slate-200 ${bg} p-5 shadow-sm`}>
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-400">{label}</p>
          <p className={`mt-2 text-3xl font-bold ${color}`}>
            {loading ? <span className="inline-block h-8 w-20 animate-pulse rounded bg-slate-100" /> : value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
        </div>
        {Icon && (
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-white/60 shadow-sm">
            <Icon size={16} className={color} />
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Quality bar ─────────────────────────────────────────────── */
function QBar({ label, value, color }) {
  const pct = Math.min(100, Math.max(0, value || 0));
  const bar = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : pct >= 40 ? 'bg-orange-500' : 'bg-rose-500';
  return (
    <div>
      <div className="flex justify-between text-xs mb-1">
        <span className="text-slate-600">{label}</span>
        <span className={`font-bold ${color || 'text-slate-700'}`}>{safePct(value)}</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full transition-all duration-700 ${bar}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

/* ── Coverage row ─────────────────────────────────────────────── */
function CoverageRow({ rule, total, approved, rejected }) {
  const [open, setOpen] = useState(false);
  const approvedPct = total > 0 ? Math.round(approved / total * 100) : 0;
  const barColor = approved === 0 ? 'bg-rose-400' : approvedPct >= 60 ? 'bg-emerald-500' : 'bg-amber-500';
  return (
    <>
      <tr
        className={`cursor-pointer hover:bg-slate-50 transition ${total === 0 ? 'bg-rose-50/40' : ''}`}
        onClick={() => setOpen(o => !o)}
      >
        <td className="px-4 py-2.5 text-xs font-medium text-slate-800 max-w-xs truncate">{rule}</td>
        <td className="px-4 py-2.5 text-xs text-center font-semibold text-slate-700">{safeN(total)}</td>
        <td className="px-4 py-2.5 text-xs text-center text-emerald-600 font-semibold">{safeN(approved)}</td>
        <td className="px-4 py-2.5 text-xs text-center text-rose-600 font-semibold">{safeN(rejected)}</td>
        <td className="px-4 py-2.5">
          <div className="flex items-center gap-2">
            <div className="flex-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full rounded-full ${barColor}`} style={{ width: `${approvedPct}%` }} />
            </div>
            <span className="text-[10px] font-semibold text-slate-500 w-8">{approvedPct}%</span>
          </div>
        </td>
        <td className="px-4 py-2.5 text-slate-400">{open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}</td>
      </tr>
      {open && (
        <tr className="bg-slate-50">
          <td colSpan={6} className="px-6 py-2 text-xs text-slate-500">
            {total === 0
              ? <span className="text-rose-600 font-semibold">⚠ No evidence for this rule</span>
              : `${approved} approved + ${rejected} rejected = ${total} total samples`
            }
          </td>
        </tr>
      )}
    </>
  );
}

/* ══════════════════════════ MAIN PAGE ═══════════════════════════ */
export default function TrainingDataset() {
  const [norms,     setNorms]     = useState([]);
  const [normId,    setNormId]    = useState('');
  const [stats,     setStats]     = useState(null);
  const [quality,   setQuality]   = useState(null);
  const [mlops,     setMlops]     = useState(null);
  const [samples,   setSamples]   = useState([]);
  const [sTotal,    setSTotal]    = useState(0);
  const [sPage,     setSPage]     = useState(1);
  const PAGE_SIZE = 10;
  const [loading,   setLoading]   = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [search,    setSearch]    = useState(''); // eslint-disable-line no-unused-vars
  const [labelFilter, setLabelFilter] = useState('');
  const [sortBy,    setSortBy]    = useState('-created_at'); // eslint-disable-line no-unused-vars

  /* Load norms */
  useEffect(() => {
    api.get('/norms/').then(r => {
      const list = Array.isArray(r.data) ? r.data : [];
      setNorms(list);
      if (list.length > 0) setNormId(String(list[0].id));
    }).catch(() => {});
  }, []);

  /* Load all data for selected norm */
  const load = useCallback(async (page = 1) => {
    if (!normId) return;
    setLoading(true);
    try {
      const [statsRes, qualityRes, mlopsRes] = await Promise.all([
        api.get(`/dataset-stats/?norm_id=${normId}&dataset_type=classification`),
        api.get(`/dataset/quality-report/?norm_id=${normId}`),
        api.get('/ml/mlops/status/'),
      ]);
      setStats(statsRes.data);
      setQuality(qualityRes.data);
      setMlops(mlopsRes.data);

      // Load samples table — use rule-memory which handles pagination correctly
      const sParams = new URLSearchParams({
        page, page_size: PAGE_SIZE, norm_id: normId,
      });
      if (labelFilter) sParams.set('label', labelFilter);
      const samplesRes = await api.get(`/rule-training-samples/?${sParams}`);
      const d = samplesRes.data || {};
      // rule-training-samples uses DRF pagination: { count, results }
      setSamples(d.results || []);
      setSTotal(d.count || 0);
      setSPage(page);
    } catch (e) {
      console.error('TrainingDataset load error:', e);
    } finally {
      setLoading(false);
    }
  }, [normId, labelFilter]);

  useEffect(() => { load(1); }, [load]);

  /* Derived stats */
  const ev      = quality?.evidence  || {};
  const cov     = quality?.coverage  || {};
  const ruleDist = quality?.rule_distribution || [];
  const qualStatus = quality?.quality_status || 'unknown';

  const approved = stats?.approved_samples ?? 0;
  const rejected = stats?.rejected_samples ?? stats?.invalid_samples ?? 0;
  const total    = stats?.total_samples ?? 0;
  const qScore   = stats?.quality_score ?? 0;
  const balance  = stats?.class_balance ?? 0;
  const dupRate  = stats?.duplicate_rate ?? 0;
  const covRate  = stats?.coverage_rate ?? 0;
  const richness = stats?.dataset_richness ?? 0;
  const trainingReady = stats?.training_enabled ?? false; // eslint-disable-line no-unused-vars

  /* Compute training readiness score */
  const readinessScore = useMemo(() => {
    if (!stats) return 0;
    const sizeScore    = Math.min(total / 200 * 100, 100);
    const balanceScore = balance;
    const covScore     = covRate;
    const cleanScore   = 100 - dupRate;
    return Math.round(0.30*sizeScore + 0.25*balanceScore + 0.25*covScore + 0.20*cleanScore);
  }, [stats, total, balance, covRate, dupRate]);

  /* MLOps status for this norm */
  const normName   = norms.find(n => String(n.id) === normId)?.name || '';
  const mlopsStd   = (mlops?.standards || []).find(s =>
    normName && s.standard && normName.toLowerCase().includes(s.standard.toLowerCase().split(' ')[0])
  ) || (mlops?.standards || [])[0];

  const TABS = [
    { id: 'overview',  label: 'Overview',       icon: BarChart3   },
    { id: 'coverage',  label: 'Coverage',        icon: Target      },
    { id: 'analytics', label: 'Analytics',       icon: TrendingUp  },
    { id: 'table',     label: 'Dataset Table',   icon: Database    },
    { id: 'mlops',     label: 'MLOps',           icon: GitBranch   },
  ];

  const totalPages = Math.max(1, Math.ceil(sTotal / PAGE_SIZE));

  return (
    <Layout>
      <div className="page-container">

        {/* ── Hero ── */}
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 via-sky-950 to-slate-900 px-6 py-6 shadow-lg">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-500/20">
                <Database size={20} className="text-sky-300" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">MLOps</p>
                <h1 className="text-2xl font-bold text-white">Training Dataset</h1>
                <p className="text-sm text-slate-400">Dataset quality · Coverage · Readiness · Analytics</p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {norms.length > 0 && (
                <select value={normId} onChange={e => setNormId(e.target.value)}
                  className="rounded-xl border border-slate-600 bg-white/10 px-3 py-2 text-sm text-white outline-none">
                  {norms.map(n => <option key={n.id} value={n.id} className="text-slate-900">{n.name}</option>)}
                </select>
              )}
              <button type="button" onClick={() => load(1)} disabled={loading}
                className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10 transition">
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>

          {/* Training readiness banner */}
          {!loading && (
            <div className={`mt-4 flex items-center gap-3 rounded-xl px-4 py-2.5 text-sm font-semibold ${
              readinessScore >= 80 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-amber-500/20 text-amber-300'
            }`}>
              {readinessScore >= 80
                ? <CheckCircle2 size={15} className="text-emerald-400" />
                : <AlertTriangle size={15} className="text-amber-400" />
              }
              {readinessScore >= 80
                ? `${readinessScore}% READY FOR TRAINING — ${safeN(total)} labelled samples`
                : `${readinessScore}% — More data needed for optimal training`
              }
              {total > 0 && <HealthBadge score={qScore || readinessScore} />}
            </div>
          )}
        </div>

        {/* ── KPIs ── */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <KpiCard icon={Database}    label="Total Samples" value={loading ? '…' : safeN(total)}    color="text-slate-900"   loading={loading} sub="Approved + Rejected" />
          <KpiCard icon={CheckCircle2}label="Approved"      value={loading ? '…' : safeN(approved)} color="text-emerald-600" bg="bg-emerald-50/50" loading={loading}
            sub={total > 0 ? `${((approved/total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard icon={XCircle}     label="Rejected"      value={loading ? '…' : safeN(rejected)} color="text-rose-600"    bg="bg-rose-50/50"     loading={loading}
            sub={total > 0 ? `${((rejected/total)*100).toFixed(0)}% of total` : undefined} />
          <KpiCard icon={Shield}      label="Rules Covered" value={loading ? '…' : `${safeN(cov.rules_with_evidence)}/${safeN(cov.total_rules)}`} color="text-sky-700" loading={loading} />
          <KpiCard icon={BarChart3}   label="Quality Score" value={loading ? '…' : safePct(qScore)} color={qScore>=80?'text-emerald-600':qScore>=60?'text-amber-600':'text-rose-600'} loading={loading}
            sub={qualStatus ? qualStatus.toUpperCase() : undefined} />
        </div>

        {/* ── Tabs ── */}
        <div className="flex flex-wrap gap-2">
          {TABS.map(t => (
            <button key={t.id} type="button" onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition-all ${
                activeTab === t.id ? 'bg-slate-900 text-white shadow-sm' : 'border border-slate-200 bg-white text-slate-500 hover:text-slate-800'
              }`}>
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </div>

        {/* ── Tab: Overview ── */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-bold text-slate-900 mb-4">Dataset Health Score</p>
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-3">
                  <QBar label="Dataset Richness"  value={richness}  color="text-indigo-700" />
                  <QBar label="Class Balance"     value={balance}   color={balance>=60?'text-emerald-700':'text-amber-700'} />
                  <QBar label="Coverage Rate"     value={covRate}   color="text-sky-700" />
                  <QBar label="Clean Rate"        value={100-dupRate} color={dupRate<5?'text-emerald-700':'text-amber-700'} />
                  <QBar label="Training Readiness" value={readinessScore} color={readinessScore>=80?'text-emerald-700':'text-amber-700'} />
                </div>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  {[
                    { l: 'Approved',       v: safeN(approved),        w: false },
                    { l: 'Rejected',       v: safeN(rejected),        w: false },
                    { l: 'Class Balance',  v: safePct(balance),       w: balance < 40 },
                    { l: 'Duplicate Rate', v: safePct(dupRate),       w: dupRate > 10 },
                    { l: 'Coverage',       v: safePct(covRate),       w: covRate < 80 },
                    { l: 'Avg Sem. Score', v: safePct(ev.avg_semantic_score), w: false },
                    { l: 'Avg Confidence', v: safePct(ev.avg_confidence_score), w: false },
                    { l: 'Vocabulary',     v: safeN(ev.vocabulary_size),  w: false },
                  ].map(m => (
                    <div key={m.l} className={`rounded-xl px-3 py-2 ${m.w ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50'}`}>
                      <p className="text-slate-400 text-[10px]">{m.l}</p>
                      <p className={`font-bold ${m.w ? 'text-amber-700' : 'text-slate-800'}`}>{m.v ?? '—'}</p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── Tab: Coverage ── */}
        {activeTab === 'coverage' && (
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
              <p className="text-sm font-bold text-slate-900">Rule Coverage Analysis</p>
              <span className="text-xs text-slate-400">{ruleDist.length} rules</span>
            </div>
            {loading ? (
              <div className="space-y-2 p-5">{[...Array(5)].map((_,i)=><div key={i} className="h-10 animate-pulse rounded bg-slate-100"/>)}</div>
            ) : ruleDist.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">No coverage data for this norm.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full text-sm">
                  <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                    <tr>
                      <th className="px-4 py-3 text-left">Rule</th>
                      <th className="px-4 py-3 text-center">Total</th>
                      <th className="px-4 py-3 text-center">Approved</th>
                      <th className="px-4 py-3 text-center">Rejected</th>
                      <th className="px-4 py-3">Approval Rate</th>
                      <th className="px-4 py-3 w-6" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {ruleDist.map(r => (
                      <CoverageRow key={r.rule_title} rule={r.rule_title} total={r.total} approved={r.approved} rejected={r.rejected} />
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Analytics ── */}
        {activeTab === 'analytics' && (
          <div className="space-y-4">
            {/* Approved vs Rejected */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-bold text-slate-900 mb-4">Class Distribution</p>
              {total > 0 ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <span className="w-20 text-xs text-slate-600">Approved</span>
                    <div className="flex-1 h-4 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-emerald-500 transition-all duration-700"
                        style={{ width: `${(approved/total)*100}%` }} />
                    </div>
                    <span className="w-24 text-right text-xs font-semibold text-slate-700">{safeN(approved)} ({((approved/total)*100).toFixed(0)}%)</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="w-20 text-xs text-slate-600">Rejected</span>
                    <div className="flex-1 h-4 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full bg-rose-500 transition-all duration-700"
                        style={{ width: `${(rejected/total)*100}%` }} />
                    </div>
                    <span className="w-24 text-right text-xs font-semibold text-slate-700">{safeN(rejected)} ({((rejected/total)*100).toFixed(0)}%)</span>
                  </div>
                </div>
              ) : <p className="text-sm text-slate-400">No data.</p>}
            </div>

            {/* Evidence per rule chart */}
            {ruleDist.length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-sm font-bold text-slate-900 mb-4">Samples per Rule (top 15)</p>
                <div className="space-y-2">
                  {ruleDist.slice(0, 15).map(r => {
                    const maxT = Math.max(...ruleDist.slice(0,15).map(x => x.total), 1);
                    return (
                      <div key={r.rule_title} className="flex items-center gap-3">
                        <p className="w-44 shrink-0 truncate text-xs font-medium text-slate-700">{r.rule_title}</p>
                        <div className="flex-1 h-2 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full bg-sky-500 transition-all"
                            style={{ width: `${(r.total/maxT)*100}%` }} />
                        </div>
                        <span className="w-8 text-right text-xs font-bold text-slate-600">{r.total}</span>
                        <span className="w-6 text-right text-[10px] text-emerald-600">{r.approved}</span>
                        <span className="w-6 text-right text-[10px] text-rose-600">{r.rejected}</span>
                      </div>
                    );
                  })}
                </div>
                <div className="mt-2 flex gap-3 text-xs text-slate-400">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500"/>Approved</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-rose-500"/>Rejected</span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Tab: Dataset Table ── */}
        {activeTab === 'table' && (
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
            <div className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-4">
              <p className="text-sm font-bold text-slate-900">Dataset Entries</p>
              <span className="text-xs text-slate-400">{safeN(sTotal)} records</span>
              <div className="flex items-center gap-2 ml-auto">
                <select value={labelFilter} onChange={e => { setLabelFilter(e.target.value); load(1); }}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs outline-none">
                  <option value="">All labels</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
              </div>
            </div>
            {loading ? (
              <div className="space-y-2 p-5">{[...Array(5)].map((_,i)=><div key={i} className="h-10 animate-pulse rounded bg-slate-100"/>)}</div>
            ) : samples.length === 0 ? (
              <p className="py-10 text-center text-sm text-slate-400">No samples found.</p>
            ) : (
              <>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                      <tr>
                        <th className="px-4 py-3 text-left">Rule</th>
                        <th className="px-4 py-3 text-left">Evidence</th>
                        <th className="px-4 py-3 text-left">Label</th>
                        <th className="px-4 py-3 text-right">Score</th>
                        <th className="px-4 py-3 text-left">Date</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {samples.map((s, i) => (
                        <tr key={s.id || i} className="hover:bg-slate-50">
                          <td className="px-4 py-2.5 font-medium text-slate-800 max-w-[150px] truncate">{s.rule_title || '—'}</td>
                          <td className="px-4 py-2.5 text-slate-500 max-w-xs truncate">{s.evidence_text || s.evidence || '—'}</td>
                          <td className="px-4 py-2.5">
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold ${
                              s.label === 'approved' ? 'bg-emerald-100 text-emerald-700'
                              : s.label === 'rejected' ? 'bg-rose-100 text-rose-700'
                              : 'bg-slate-100 text-slate-600'
                            }`}>{s.label || '—'}</span>
                          </td>
                          <td className="px-4 py-2.5 text-right font-mono text-slate-600">
                            {s.confidence_score != null ? `${(s.confidence_score*100).toFixed(0)}%` : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-slate-400">{fmtDate(s.updated_at || s.created_at)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3">
                  <span className="text-xs text-slate-400">{safeN((sPage-1)*PAGE_SIZE+1)}–{safeN(Math.min(sPage*PAGE_SIZE,sTotal))} of {safeN(sTotal)}</span>
                  <div className="flex items-center gap-1">
                    <button onClick={() => load(sPage-1)} disabled={sPage<=1} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-500 hover:bg-slate-50 disabled:opacity-40">← Prev</button>
                    <span className="text-xs text-slate-400 px-2">Page {sPage}/{totalPages}</span>
                    <button onClick={() => load(sPage+1)} disabled={sPage>=totalPages} className="rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-500 hover:bg-slate-50 disabled:opacity-40">Next →</button>
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {/* ── Tab: MLOps ── */}
        {activeTab === 'mlops' && (
          <div className="space-y-4">
            {/* MLOps status */}
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-4">
                <GitBranch size={15} className="text-slate-500" />
                <p className="text-sm font-bold text-slate-900">Pipeline Status</p>
                {mlops?.jenkins_configured === false && (
                  <span className="ml-auto text-[10px] font-semibold rounded-full bg-amber-100 text-amber-700 px-2 py-0.5">Jenkins not configured</span>
                )}
              </div>
              {mlopsStd ? (
                <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    { l: 'Current Model Version', v: mlopsStd.current_model_version || 'v0.0' },
                    { l: 'Last Training',         v: mlopsStd.last_trained_at ? new Date(mlopsStd.last_trained_at).toLocaleDateString('fr-FR') : 'Never' },
                    { l: 'Dataset Size',           v: safeN(mlopsStd.total_documents) },
                    { l: 'New Samples',            v: safeN(mlopsStd.new_documents), warn: (mlopsStd.new_documents||0) >= (mlopsStd.retraining_threshold||10) },
                    { l: 'Retraining Threshold',  v: safeN(mlopsStd.retraining_threshold) },
                    { l: 'Drift Score',           v: mlopsStd.drift?.drift_score != null ? mlopsStd.drift.drift_score.toFixed(3) : '—', warn: mlopsStd.drift?.status === 'critical' },
                    { l: 'Drift Status',          v: mlopsStd.drift?.status || '—' },
                    { l: 'Needs Training',        v: mlopsStd.needs_training ? 'YES' : 'NO', warn: mlopsStd.needs_training },
                  ].map(m => (
                    <div key={m.l} className={`rounded-xl px-3 py-2.5 ${m.warn ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50'}`}>
                      <p className="text-[10px] text-slate-400">{m.l}</p>
                      <p className={`font-bold text-sm mt-0.5 ${m.warn ? 'text-amber-700' : 'text-slate-800'}`}>{m.v}</p>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-sm text-slate-400">No MLOps data for this norm.</p>
              )}
            </div>

            {/* Recent jobs */}
            {(mlops?.recent_jobs || []).length > 0 && (
              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
                <div className="border-b border-slate-100 px-5 py-4">
                  <p className="text-sm font-bold text-slate-900">Recent Training Jobs</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full text-xs">
                    <thead className="bg-slate-50 text-[10px] uppercase tracking-wider text-slate-500">
                      <tr><th className="px-4 py-3 text-left">ID</th><th className="px-4 py-3">Status</th><th className="px-4 py-3">Standard</th><th className="px-4 py-3">F1</th><th className="px-4 py-3">Drift</th><th className="px-4 py-3">Date</th></tr>
                    </thead>
                    <tbody className="divide-y divide-slate-50">
                      {(mlops.recent_jobs || []).slice(0, 8).map(j => (
                        <tr key={j.id} className="hover:bg-slate-50">
                          <td className="px-4 py-2 font-mono text-slate-500">#{j.id}</td>
                          <td className="px-4 py-2">
                            <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${
                              j.status==='success'?'bg-emerald-100 text-emerald-700':j.status==='failed'?'bg-rose-100 text-rose-700':'bg-sky-100 text-sky-700'
                            }`}>{j.status}</span>
                          </td>
                          <td className="px-4 py-2 text-slate-600 max-w-[120px] truncate">{j.standard || '—'}</td>
                          <td className="px-4 py-2 font-semibold text-violet-700">{j.f1_score != null ? `${(j.f1_score*100).toFixed(0)}%` : '—'}</td>
                          <td className="px-4 py-2 text-slate-500">{j.drift_score != null ? j.drift_score.toFixed(3) : '—'}</td>
                          <td className="px-4 py-2 text-slate-400">{fmtDate(j.start_time)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

      </div>
    </Layout>
  );
}
