/**
 * Compliance Dashboard — /compliance-dashboard
 * Executive overview: maturity, coverage, readiness, risks, reviews, audit log.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  ShieldCheck, ShieldAlert, Shield, AlertTriangle, RefreshCw,
  BarChart3, Clock, FileWarning, Activity, TrendingUp, BookOpen,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── helpers ─────────────────────────────────────────────────────── */
const safeN  = (v) => (v == null ? '—' : Number(v).toLocaleString());
const safePct= (v) => (v == null ? '—' : `${Number(v).toFixed(1)}%`);

const READINESS_ICON  = { READY: ShieldCheck, PARTIAL: ShieldAlert, NOT_READY: Shield };
const READINESS_COLOR = {
  READY:     'text-emerald-600 bg-emerald-50 border-emerald-200',
  PARTIAL:   'text-amber-600   bg-amber-50   border-amber-200',
  NOT_READY: 'text-rose-600    bg-rose-50    border-rose-200',
};
const MATURITY_COLOR  = {
  OPTIMIZED:  'bg-emerald-500',
  MANAGED:    'bg-sky-500',
  DEVELOPING: 'bg-amber-500',
  INITIAL:    'bg-rose-500',
};
const SEVERITY_COLOR = {
  CRITICAL: 'bg-rose-100 text-rose-700',
  HIGH:     'bg-orange-100 text-orange-700',
  MEDIUM:   'bg-amber-100 text-amber-700',
  LOW:      'bg-slate-100 text-slate-600',
};

/* ── Score ring ──────────────────────────────────────────────────── */
function ScoreRing({ score = 0, color = '#6366f1', size = 80 }) {
  const R    = size * 0.38;
  const circ = 2 * Math.PI * R;
  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90">
        <circle cx={size/2} cy={size/2} r={R} fill="none" stroke="#e2e8f0" strokeWidth={size*0.09} strokeLinecap="round"/>
        <circle cx={size/2} cy={size/2} r={R} fill="none" stroke={color} strokeWidth={size*0.09}
          strokeLinecap="round" strokeDasharray={circ}
          strokeDashoffset={circ * (1 - Math.min(100, Math.max(0, score)) / 100)}
          style={{ transition: 'stroke-dashoffset 1s ease' }} />
      </svg>
      <div className="absolute flex flex-col items-center justify-center">
        <span className="font-bold text-slate-900" style={{ fontSize: size * 0.19 }}>{Math.round(score)}</span>
        <span className="text-slate-400 uppercase tracking-wider" style={{ fontSize: size * 0.1 }}>/100</span>
      </div>
    </div>
  );
}

/* ── KPI card ────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, color, bg, loading }) {
  return (
    <div className={`rounded-2xl border border-slate-200 bg-white p-5 shadow-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs uppercase tracking-widest text-slate-400">{label}</p>
          <p className={`mt-2 text-3xl font-bold ${color}`}>
            {loading ? <span className="inline-block h-8 w-20 animate-pulse rounded bg-slate-100" /> : value}
          </p>
          {sub && <p className="mt-1 text-xs text-slate-400">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 items-center justify-center rounded-xl ${bg}`}>
          <Icon size={18} className={color} />
        </div>
      </div>
    </div>
  );
}

/* ── Norm card ───────────────────────────────────────────────────── */
function NormCard({ norm }) {
  const ReadinessIcon = READINESS_ICON[norm.readiness_status] || Shield;
  const readinessCls  = READINESS_COLOR[norm.readiness_status] || READINESS_COLOR.NOT_READY;
  const maturityColor = MATURITY_COLOR[norm.maturity_level]    || MATURITY_COLOR.INITIAL;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-sm font-bold text-slate-900 leading-tight">{norm.norme_name}</p>
          <span className={`mt-1.5 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-bold ${readinessCls}`}>
            <ReadinessIcon size={10} />
            {(norm.readiness_status || '').replace('_', ' ')}
          </span>
        </div>
        <span className={`inline-block h-2 w-2 rounded-full mt-2 ${maturityColor}`} title={norm.maturity_level} />
      </div>

      <div className="flex items-center justify-around gap-1 mb-4">
        {[
          { label: 'Maturity',  score: norm.maturity_score,  color: '#6366f1', size: 64 },
          { label: 'Coverage',  score: norm.coverage_pct,    color: '#0ea5e9', size: 64 },
          { label: 'Readiness', score: norm.readiness_score, color: '#10b981', size: 64 },
        ].map(r => (
          <div key={r.label} className="flex flex-col items-center">
            <ScoreRing score={r.score || 0} color={r.color} size={r.size} />
            <p className="mt-1 text-[9px] text-slate-400 uppercase tracking-wide">{r.label}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-1.5 text-xs">
        {[
          { label: 'Avg Quality',   value: safePct(norm.avg_quality),       warn: (norm.avg_quality || 0) < 70 },
          { label: 'Open Risks',    value: safeN(norm.open_risks),           warn: norm.open_risks > 0 },
          { label: 'Critical Gaps', value: safeN(norm.critical_gaps),        warn: norm.critical_gaps > 0 },
          { label: 'Expired',       value: safeN(norm.expired_evidence),     warn: norm.expired_evidence > 0 },
        ].map(s => (
          <div key={s.label} className={`rounded-lg px-2 py-1.5 ${s.warn ? 'bg-amber-50 border border-amber-100' : 'bg-slate-50'}`}>
            <p className="text-slate-400 text-[9px]">{s.label}</p>
            <p className={`font-bold ${s.warn ? 'text-amber-700' : 'text-slate-800'}`}>{s.value}</p>
          </div>
        ))}
      </div>

      {(norm.uncovered_rules || []).length > 0 && (
        <div className="mt-3">
          <p className="text-[9px] font-bold uppercase tracking-wider text-rose-500 mb-1">
            {norm.uncovered_rules.length} uncovered rules
          </p>
          <div className="flex flex-wrap gap-1">
            {norm.uncovered_rules.slice(0, 3).map(r => (
              <span key={r} className="rounded bg-rose-50 border border-rose-100 px-1.5 py-0.5 text-[9px] text-rose-700">{r}</span>
            ))}
            {norm.uncovered_rules.length > 3 && (
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[9px] text-slate-500">+{norm.uncovered_rules.length - 3} more</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Sub-module tabs ─────────────────────────────────────────────── */
function SubModules() {
  const [tab, setTab] = useState('risks');
  const [data, setData] = useState({});
  const [loading, setLoading] = useState(false);

  const TABS = [
    { id: 'risks',    label: 'Risk Register',    icon: AlertTriangle },
    { id: 'reviews',  label: 'Periodic Reviews', icon: Clock         },
    { id: 'auditlog', label: 'Audit Log',         icon: BookOpen      },
  ];

  const load = useCallback(async (t) => {
    if (data[t]) return;
    setLoading(true);
    try {
      const urls = {
        risks:    'compliance-os/risks/?status=OPEN',
        reviews:  'compliance-os/reviews/',
        auditlog: 'compliance-os/audit-log/?limit=20',
      };
      const r = await api.get('/' + urls[t]);
      setData(prev => ({ ...prev, [t]: r.data }));
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [data]);

  useEffect(() => { load(tab); }, [tab, load]);

  const items = data[tab];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="flex border-b border-slate-100">
        {TABS.map(t => (
          <button key={t.id} type="button" onClick={() => setTab(t.id)}
            className={`flex items-center gap-1.5 px-5 py-3 text-xs font-semibold transition ${
              tab === t.id ? 'border-b-2 border-sky-500 text-sky-600' : 'text-slate-500 hover:text-slate-700'
            }`}>
            <t.icon size={13} />
            {t.label}
          </button>
        ))}
      </div>

      <div className="min-h-[200px] p-4">
        {loading && (
          <div className="space-y-2">
            {[...Array(4)].map((_, i) => <div key={i} className="h-10 animate-pulse rounded-xl bg-slate-100" />)}
          </div>
        )}

        {/* Risks */}
        {!loading && tab === 'risks' && (
          (items?.risks || []).length === 0
            ? <p className="text-sm text-slate-400 py-6 text-center">No open risks.</p>
            : <div className="space-y-2 max-h-64 overflow-y-auto">
                {(items.risks || []).map(r => (
                  <div key={r.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2.5 text-xs">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-800 truncate">{r.title}</p>
                      <p className="text-slate-400 text-[10px]">{r.standard__name}</p>
                    </div>
                    <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${SEVERITY_COLOR[r.severity] || SEVERITY_COLOR.LOW}`}>
                      {r.severity}
                    </span>
                  </div>
                ))}
              </div>
        )}

        {/* Reviews */}
        {!loading && tab === 'reviews' && (
          (items?.reviews || []).length === 0
            ? <p className="text-sm text-slate-400 py-6 text-center">No reviews configured.</p>
            : <div className="space-y-2 max-h-64 overflow-y-auto">
                {(items.reviews || []).map(r => (
                  <div key={r.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2.5 text-xs">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-800 truncate">{r.rule__title}</p>
                      <p className="text-slate-400 text-[10px]">{r.rule__norme__name} · {r.review_frequency}</p>
                    </div>
                    <span className={`flex-shrink-0 rounded-full px-2 py-0.5 text-[10px] font-bold ${
                      r.review_status === 'OVERDUE' ? 'bg-rose-100 text-rose-700'
                      : r.review_status === 'NEEDS_REVIEW' ? 'bg-amber-100 text-amber-700'
                      : 'bg-emerald-100 text-emerald-700'
                    }`}>{(r.review_status || '').replace('_', ' ')}</span>
                  </div>
                ))}
              </div>
        )}

        {/* Audit log */}
        {!loading && tab === 'auditlog' && (
          (items?.items || []).length === 0
            ? <p className="text-sm text-slate-400 py-6 text-center">No audit entries.</p>
            : <div className="space-y-2 max-h-64 overflow-y-auto">
                {(items.items || []).map(e => (
                  <div key={e.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-100 px-3 py-2.5 text-xs">
                    <div className="min-w-0">
                      <p className="font-semibold text-slate-800 truncate">[{e.action}] {e.entity_type} #{e.entity_id}</p>
                      <p className="text-slate-400 text-[10px]">by {e.performed_by}</p>
                    </div>
                    <span className="flex-shrink-0 text-[10px] text-slate-400">
                      {e.performed_at ? new Date(e.performed_at).toLocaleDateString('fr-FR') : '—'}
                    </span>
                  </div>
                ))}
              </div>
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════ MAIN PAGE ═══════════════════════════ */
export default function ComplianceDashboard() {
  const [data,       setData]       = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState('');
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await api.get('/compliance-os/executive-dashboard/');
      setData(r.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to load compliance dashboard.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRefresh = async () => {
    setRefreshing(true);
    try { await api.post('/compliance-os/refresh/'); await load(); }
    catch { setError('Refresh failed.'); }
    finally { setRefreshing(false); }
  };

  const norms            = data?.norms || [];
  const overall          = data?.overall_compliance_score ?? 0;
  const overallReadiness = data?.overall_readiness_status || 'NOT_READY';
  const ReadinessIcon    = READINESS_ICON[overallReadiness] || Shield;
  const readinessCls     = READINESS_COLOR[overallReadiness] || READINESS_COLOR.NOT_READY;
  const totalRisks  = norms.reduce((s, n) => s + (n.open_risks || 0), 0);
  const totalExpired= norms.reduce((s, n) => s + (n.expired_evidence || 0), 0);
  const totalGaps   = norms.reduce((s, n) => s + (n.critical_gaps || 0), 0);
  const totalDups   = data?.total_duplicate_evidence ?? 0;

  return (
    <Layout>
      <div className="page-container">
        {/* Hero */}
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-6 py-6 shadow-lg">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20">
                <ShieldCheck size={20} className="text-indigo-300" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400">Compliance OS</p>
                <h1 className="text-2xl font-bold text-white">Executive Dashboard</h1>
                <p className="text-sm text-slate-400">ISO 27001 · TISAX · ISO 9001 · Audit Readiness</p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-bold ${readinessCls}`}>
                <ReadinessIcon size={12} />
                {overallReadiness.replace('_', ' ')}
              </span>
              <button type="button" onClick={handleRefresh} disabled={refreshing || loading}
                className="flex items-center gap-1.5 rounded-xl border border-slate-700 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-white/10 disabled:opacity-50 transition">
                <RefreshCw size={12} className={refreshing ? 'animate-spin' : ''} />
                {refreshing ? 'Refreshing…' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>

        {error && <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

        {/* Overall + KPIs */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <div className="xl:col-span-1 flex flex-col items-center justify-center rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-bold uppercase tracking-widest text-slate-400 mb-3">Overall Score</p>
            <ScoreRing score={loading ? 0 : overall} color="#6366f1" size={110} />
            <p className="mt-2 text-xs font-bold text-slate-600">Compliance Maturity</p>
            {data?.computed_at && <p className="text-[10px] text-slate-400 mt-0.5">{new Date(data.computed_at).toLocaleString('fr-FR')}</p>}
          </div>
          <div className="xl:col-span-4 grid grid-cols-2 gap-3 xl:grid-cols-4">
            <KpiCard icon={BarChart3}    label="Coverage"         value={loading ? '…' : safePct(data?.overall_coverage_pct)}  color="text-sky-700"     bg="bg-sky-50"     loading={loading} />
            <KpiCard icon={AlertTriangle}label="Open Risks"       value={loading ? '…' : safeN(totalRisks)}     color={totalRisks>0?'text-rose-600':'text-emerald-600'}  bg="bg-rose-50"   loading={loading} sub={totalRisks > 0 ? 'Require attention' : 'All clear'} />
            <KpiCard icon={FileWarning}  label="Critical Gaps"    value={loading ? '…' : safeN(totalGaps)}      color={totalGaps>0?'text-rose-700':'text-emerald-600'}   bg="bg-rose-50"   loading={loading} />
            <KpiCard icon={Clock}        label="Expired Evidence" value={loading ? '…' : safeN(totalExpired)}   color={totalExpired>0?'text-amber-600':'text-emerald-600'} bg="bg-amber-50" loading={loading} />
            <KpiCard icon={AlertTriangle}label="Duplicate Evid."  value={loading ? '…' : safeN(totalDups)}     color={totalDups>10?'text-amber-600':'text-emerald-600'}  bg="bg-amber-50"  loading={loading} />
            <KpiCard icon={Activity}     label="Norms Monitored"  value={loading ? '…' : safeN(norms.length)}  color="text-violet-700" bg="bg-violet-50" loading={loading} />
            <KpiCard icon={TrendingUp}   label="Maturity Score"   value={loading ? '…' : `${Math.round(data?.overall_maturity_score ?? 0)}`} color="text-indigo-700" bg="bg-indigo-50" loading={loading} />
            <KpiCard icon={ShieldCheck}  label="Audit Status"     value={loading ? '…' : overallReadiness.replace('_',' ')} color={overallReadiness==='READY'?'text-emerald-700':'text-amber-700'} bg="bg-emerald-50" loading={loading} />
          </div>
        </div>

        {/* Per-norm cards */}
        {loading ? (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {[...Array(3)].map((_, i) => <div key={i} className="h-64 animate-pulse rounded-2xl bg-slate-100" />)}
          </div>
        ) : norms.length > 0 ? (
          <div>
            <p className="mb-3 text-xs font-bold uppercase tracking-widest text-slate-400">Standards breakdown</p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {norms.map(n => <NormCard key={n.norme_id} norm={n} />)}
            </div>
          </div>
        ) : (
          <p className="py-10 text-center text-sm text-slate-400">No compliance data available.</p>
        )}

        {/* Sub-modules with real data */}
        <SubModules />
      </div>
    </Layout>
  );
}
