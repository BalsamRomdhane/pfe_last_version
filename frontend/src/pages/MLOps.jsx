/**
 * MLOps Pipeline Dashboard — /admin/mlops
 * Training jobs, drift detection, Jenkins integration.
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  GitBranch, RefreshCw, Zap, Loader2, Play,
  CheckCircle2, XCircle, Clock, AlertTriangle,
  BarChart3, TrendingDown, Activity, ChevronDown, ChevronUp,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── helpers ─────────────────────────────────────────────────────── */
const fmt = (iso) => {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('fr-FR', { day:'2-digit', month:'short', year:'numeric', hour:'2-digit', minute:'2-digit' });
};
const pct = (v) => v != null ? `${Math.round(v * 100)}%` : '—';

const STATUS_STYLE = {
  success:   'bg-emerald-100 text-emerald-700',
  failed:    'bg-rose-100 text-rose-700',
  running:   'bg-sky-100 text-sky-700',
  pending:   'bg-amber-100 text-amber-700',
  cancelled: 'bg-slate-100 text-slate-600',
};
const STATUS_ICON = {
  success:   <CheckCircle2 size={12} className="text-emerald-600" />,
  failed:    <XCircle      size={12} className="text-rose-600"    />,
  running:   <Loader2      size={12} className="text-sky-500 animate-spin" />,
  pending:   <Clock        size={12} className="text-amber-500"   />,
  cancelled: <XCircle      size={12} className="text-slate-400"   />,
};
const DRIFT_COLOR = {
  stable:            'text-emerald-600',
  warning:           'text-amber-600',
  critical:          'text-rose-600',
  error:             'text-slate-500',
  insufficient_data: 'text-slate-400',
};

/* ── KPI card ─────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, color, loading }) {
  const bg = color.replace('text-', 'bg-').replace('-600', '-50').replace('-700', '-50');
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
        <div className={`flex h-11 w-11 items-center justify-center rounded-2xl ${bg}`}>
          <Icon size={20} className={color} />
        </div>
      </div>
    </div>
  );
}

/* ── Job row ─────────────────────────────────────────────────────── */
function JobRow({ job }) {
  const [open, setOpen] = useState(false);
  const dur = job.start_time && job.end_time
    ? Math.round((new Date(job.end_time) - new Date(job.start_time)) / 1000) + 's'
    : '—';
  return (
    <>
      <tr className="cursor-pointer hover:bg-slate-50 transition" onClick={() => setOpen(o => !o)}>
        <td className="px-4 py-3 font-mono text-xs text-slate-500">#{job.id}</td>
        <td className="px-4 py-3">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_STYLE[job.status] || STATUS_STYLE.pending}`}>
            {STATUS_ICON[job.status]}
            {job.status}
          </span>
        </td>
        <td className="px-4 py-3 text-sm text-slate-700">{job.standard || '—'}</td>
        <td className="px-4 py-3 text-sm text-slate-600">{job.documents_count ?? '—'}</td>
        <td className="px-4 py-3 text-sm font-semibold text-violet-700">{job.f1_score != null ? pct(job.f1_score) : '—'}</td>
        <td className="px-4 py-3 text-sm text-slate-600">{job.drift_score != null ? job.drift_score.toFixed(3) : '—'}</td>
        <td className="px-4 py-3 text-xs text-slate-400">{fmt(job.start_time)}</td>
        <td className="px-4 py-3 text-xs text-slate-400">{dur}</td>
        <td className="px-4 py-3 text-slate-400">{open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}</td>
      </tr>
      {open && (
        <tr className="bg-slate-50">
          <td colSpan={9} className="px-6 py-4 text-xs text-slate-600">
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Metrics</p>
                <p>Precision: <strong>{pct(job.precision_score)}</strong></p>
                <p>Recall: <strong>{pct(job.recall_score)}</strong></p>
                <p>Model: <strong>{job.model_version || '—'}</strong></p>
                <p>Triggered by: <strong>{job.triggered_by || '—'}</strong></p>
              </div>
              {job.jenkins_url && (
                <div>
                  <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Jenkins</p>
                  <a href={job.jenkins_url} target="_blank" rel="noreferrer" className="text-sky-600 hover:underline break-all">
                    View build ↗
                  </a>
                  {job.jenkins_build_id && <p className="mt-1">Build: <strong>#{job.jenkins_build_id}</strong></p>}
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ── Standard card ───────────────────────────────────────────────── */
function StandardCard({ std, onTrigger, triggering }) {
  const drift = std.drift || {};
  const driftStatus = drift.status || 'unknown';
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-sm font-bold text-slate-900">{std.standard}</p>
          <p className="text-xs text-slate-400 mt-0.5">Model: <span className="font-semibold text-slate-600">{std.current_model_version || 'v0.0'}</span></p>
        </div>
        <button type="button" onClick={() => onTrigger(std.standard)} disabled={triggering}
          className="flex items-center gap-1.5 rounded-xl bg-sky-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-50 transition">
          {triggering ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
          {triggering ? 'Triggering…' : 'Trigger'}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        {[
          { label: 'Total docs',    value: std.total_documents ?? '—' },
          { label: 'New docs',      value: std.new_documents ?? '—', warn: (std.new_documents || 0) >= (std.retraining_threshold || 10) },
          { label: 'Threshold',     value: std.retraining_threshold ?? 10 },
          { label: 'F1 Score',      value: std.last_f1_score != null ? pct(std.last_f1_score) : '—' },
        ].map(k => (
          <div key={k.label} className={`rounded-xl px-3 py-2 ${k.warn ? 'bg-amber-50' : 'bg-slate-50'}`}>
            <p className="text-slate-400">{k.label}</p>
            <p className={`font-bold ${k.warn ? 'text-amber-600' : 'text-slate-800'}`}>{k.value}</p>
          </div>
        ))}
      </div>
      {/* Drift bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs text-slate-400">Drift</p>
          <span className={`text-xs font-bold ${DRIFT_COLOR[driftStatus] || 'text-slate-500'}`}>
            {drift.drift_score != null ? drift.drift_score.toFixed(3) : '—'} ({driftStatus})
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div className={`h-full rounded-full transition-all ${
            driftStatus === 'stable' ? 'bg-emerald-500' : driftStatus === 'warning' ? 'bg-amber-500' : driftStatus === 'critical' ? 'bg-rose-500' : 'bg-slate-300'
          }`} style={{ width: `${Math.min(100, (drift.drift_score || 0) * 333)}%` }} />
        </div>
      </div>
      {std.needs_training && (
        <div className="mt-3 flex items-center gap-1.5 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <AlertTriangle size={11} />
          Threshold reached — training recommended.
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════ MAIN PAGE ═══════════════════════════ */
export default function MLOps() {
  const [data,         setData]         = useState(null);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');
  const [triggering,   setTriggering]   = useState('');
  const [triggerMsg,   setTriggerMsg]   = useState('');
  const [jobFilter,    setJobFilter]    = useState('');
  const [forceStandard,setForceStandard]= useState('');

  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await api.get('/ml/mlops/status/');
      setData(r.data);
    } catch (e) { setError(e?.response?.data?.error || 'Failed to load MLOps status.'); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, 30000);
    return () => clearInterval(id);
  }, [load]);

  const standards = useMemo(() => data?.standards || [], [data]);
  const jobs      = (data?.recent_jobs || []).filter(j => !jobFilter || j.status === jobFilter);
  const summary   = data?.summary || {};

  useEffect(() => {
    if (!forceStandard && standards.length > 0) setForceStandard(standards[0].standard);
  }, [standards, forceStandard]);

  const handleTrigger = async (standard, force = false) => {
    setTriggering(standard); setTriggerMsg('');
    try {
      const r = await api.post('/ml/trigger-training/', { standard, force });
      const d = r.data;
      if (d.triggered) setTriggerMsg(`Pipeline triggered for ${standard} (Job #${d.job_id})`);
      else setTriggerMsg(`Not triggered: ${d.reason}`);
      await load();
    } catch (e) {
      const d = e?.response?.data;
      if (e?.response?.status === 503) setTriggerMsg(`Jenkins unavailable: ${d?.reason || 'JENKINS_TOKEN not configured'}. Set JENKINS_TOKEN in backend/.env.`);
      else setTriggerMsg(`Error: ${d?.error || e.message}`);
    } finally { setTriggering(''); }
  };

  return (
    <Layout>
      <div className="space-y-6 pb-10">
        {/* Header */}
        <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-6 py-6 shadow-xl">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-500/20">
                <GitBranch size={20} className="text-indigo-300" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-widest text-indigo-400">MLOps</p>
                <h1 className="text-2xl font-bold text-white">ML Pipeline Dashboard</h1>
                <p className="text-sm text-slate-400">Automated retraining · Drift detection · Jenkins</p>
              </div>
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              {standards.length > 1 && (
                <select value={forceStandard} onChange={e => setForceStandard(e.target.value)}
                  className="rounded-xl border border-slate-600 bg-white/10 px-3 py-2 text-xs text-white outline-none">
                  {standards.map(s => <option key={s.standard} value={s.standard} className="text-slate-900">{s.standard}</option>)}
                </select>
              )}
              <button type="button"
                onClick={() => handleTrigger(forceStandard || standards[0]?.standard || 'ISO9001', true)}
                disabled={!!triggering || standards.length === 0}
                className="flex items-center gap-2 rounded-2xl bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-500 disabled:opacity-50 transition">
                {triggering ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                Force Retrain
              </button>
              <button type="button" onClick={load} disabled={loading}
                className="flex items-center gap-1.5 rounded-2xl border border-slate-700 bg-white/5 px-3 py-2.5 text-xs font-semibold text-slate-300 hover:bg-white/10 transition">
                <RefreshCw size={12} className={loading ? 'animate-spin' : ''} />
                Refresh
              </button>
            </div>
          </div>
        </div>

        {/* Banners */}
        {triggerMsg && (
          <div className={`rounded-2xl border px-4 py-3 text-sm font-medium ${
            triggerMsg.includes('triggered') ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : triggerMsg.includes('unavailable') || triggerMsg.includes('Error') ? 'border-amber-200 bg-amber-50 text-amber-700'
            : 'border-sky-200 bg-sky-50 text-sky-700'
          }`}>{triggerMsg}</div>
        )}
        {!loading && data?.jenkins_configured === false && (
          <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
            <AlertTriangle size={15} className="mt-0.5 flex-shrink-0 text-amber-500" />
            <div>
              <p className="font-semibold">Jenkins not configured</p>
              <p className="text-xs mt-0.5 text-amber-700">Set <code className="rounded bg-amber-100 px-1 font-mono">JENKINS_TOKEN</code> in <code className="rounded bg-amber-100 px-1 font-mono">backend/.env</code> to enable CI/CD pipeline triggering.</p>
            </div>
          </div>
        )}
        {error && <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</div>}

        {/* KPIs */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard icon={BarChart3}    label="Total Jobs"  value={summary.total_jobs ?? '—'}   color="text-slate-700"   loading={loading} />
          <KpiCard icon={CheckCircle2} label="Successful"  value={summary.success_jobs ?? '—'} color="text-emerald-600" loading={loading}
            sub={summary.total_jobs ? `${Math.round((summary.success_jobs||0)/summary.total_jobs*100)}% success` : ''} />
          <KpiCard icon={XCircle}      label="Failed"      value={summary.failed_jobs ?? '—'}  color="text-rose-600"    loading={loading} />
          <KpiCard icon={Loader2}      label="Running Now" value={summary.running_jobs ?? '—'} color="text-sky-600"     loading={loading} />
        </div>

        {/* Standards */}
        {standards.length > 0 && (
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">Standards</p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {standards.map(s => (
                <StandardCard key={s.standard} std={s}
                  onTrigger={std => handleTrigger(std)}
                  triggering={triggering === s.standard} />
              ))}
            </div>
          </div>
        )}

        {/* Jobs table */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <p className="text-sm font-bold text-slate-900">Training Job History</p>
              <p className="text-xs text-slate-400">{jobs.length} jobs</p>
            </div>
            <select value={jobFilter} onChange={e => setJobFilter(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs outline-none">
              <option value="">All statuses</option>
              {['success','failed','running','pending','cancelled'].map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          {loading ? (
            <div className="space-y-2 p-5">
              {[...Array(4)].map((_, i) => <div key={i} className="h-12 animate-pulse rounded-xl bg-slate-100" />)}
            </div>
          ) : jobs.length === 0 ? (
            <p className="py-10 text-center text-sm text-slate-400">No training jobs yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="bg-slate-50 text-xs uppercase tracking-wider text-slate-500">
                  <tr>{['ID','Status','Standard','Docs','F1','Drift','Started','Duration',''].map(h => (
                    <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                  ))}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {jobs.map(j => <JobRow key={j.id} job={j} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Monitoring links */}
        <div className="grid gap-4 sm:grid-cols-2">
          {[
            { title: 'Prometheus', url: 'http://localhost:9090', desc: 'Metrics & queries',  color: 'border-orange-200 bg-orange-50' },
            { title: 'Grafana',    url: 'http://localhost:3001', desc: 'Visual dashboards',  color: 'border-violet-200 bg-violet-50' },
          ].map(m => (
            <a key={m.title} href={m.url} target="_blank" rel="noreferrer"
              className={`flex items-center justify-between rounded-2xl border p-4 transition hover:shadow-md ${m.color}`}>
              <div>
                <p className="text-sm font-bold text-slate-900">{m.title}</p>
                <p className="text-xs text-slate-500">{m.desc}</p>
              </div>
              <Activity size={18} className="text-slate-400" />
            </a>
          ))}
        </div>
      </div>
    </Layout>
  );
}
