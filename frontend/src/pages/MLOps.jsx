/**
 * MLOps Pipeline Dashboard — /admin/mlops
 * Training jobs, drift detection, Jenkins integration.
 */
import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  GitBranch, RefreshCw, Zap, Loader2, Play,
  CheckCircle2, XCircle, Clock, AlertTriangle,
  BarChart3, Activity, ChevronDown, ChevronUp,
  WifiOff, ShieldAlert, Search,
} from 'lucide-react';
import Layout from '../components/Layout';
import { UserContext } from '../context/UserContext';
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

/* ── Jenkins health banner ───────────────────────────────────────── */
/**
 * Maps the backend 'status' string to visual config.
 *
 *  not_configured → amber  (⚠️) — token absent, local training available
 *  unreachable    → rose   (✕) — host unreachable
 *  auth_failed    → rose   (✕) — bad credentials
 *  job_not_found  → orange (⚠️) — connected but job missing
 *  connected      → green  (✓) — fully operational
 *  error          → rose   (✕) — unexpected error
 */
const JENKINS_BANNER_CONFIG = {
  not_configured: {
    border: 'border-amber-200',
    bg:     'bg-amber-50',
    text:   'text-amber-800',
    sub:    'text-amber-700',
    icon:   <AlertTriangle size={16} className="text-amber-500 flex-shrink-0 mt-0.5" />,
    badge:  'bg-amber-100 text-amber-700',
  },
  unreachable: {
    border: 'border-rose-200',
    bg:     'bg-rose-50',
    text:   'text-rose-800',
    sub:    'text-rose-700',
    icon:   <WifiOff size={16} className="text-rose-500 flex-shrink-0 mt-0.5" />,
    badge:  'bg-rose-100 text-rose-700',
  },
  auth_failed: {
    border: 'border-rose-200',
    bg:     'bg-rose-50',
    text:   'text-rose-800',
    sub:    'text-rose-700',
    icon:   <ShieldAlert size={16} className="text-rose-500 flex-shrink-0 mt-0.5" />,
    badge:  'bg-rose-100 text-rose-700',
  },
  job_not_found: {
    border: 'border-orange-200',
    bg:     'bg-orange-50',
    text:   'text-orange-800',
    sub:    'text-orange-700',
    icon:   <Search size={16} className="text-orange-500 flex-shrink-0 mt-0.5" />,
    badge:  'bg-orange-100 text-orange-700',
  },
  connected: {
    border: 'border-emerald-200',
    bg:     'bg-emerald-50',
    text:   'text-emerald-800',
    sub:    'text-emerald-700',
    icon:   <CheckCircle2 size={16} className="text-emerald-500 flex-shrink-0" />,
    badge:  'bg-emerald-100 text-emerald-700',
  },
  error: {
    border: 'border-rose-200',
    bg:     'bg-rose-50',
    text:   'text-rose-800',
    sub:    'text-rose-700',
    icon:   <XCircle size={16} className="text-rose-500 flex-shrink-0 mt-0.5" />,
    badge:  'bg-rose-100 text-rose-700',
  },
};

function JenkinsBanner({ jenkins, onTest, testing }) {
  if (!jenkins) return null;

  const status = jenkins.status || 'not_configured';
  const cfg    = JENKINS_BANNER_CONFIG[status] || JENKINS_BANNER_CONFIG.not_configured;

  // Human-readable title per status
  const TITLES = {
    not_configured: 'Jenkins not configured',
    unreachable:    'Jenkins unreachable',
    auth_failed:    'Jenkins authentication failed',
    job_not_found:  'Jenkins job not found',
    connected:      'Jenkins connected',
    error:          'Jenkins check error',
  };

  return (
    <div className={`flex items-start gap-3 rounded-2xl border ${cfg.border} ${cfg.bg} px-4 py-3 text-sm`}>
      {cfg.icon}

      <div className="flex-1 min-w-0">
        {/* Title + status badge */}
        <div className="flex items-center gap-2 flex-wrap">
          <p className={`font-semibold ${cfg.text}`}>{TITLES[status]}</p>
          <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${cfg.badge}`}>
            {status.replace('_', ' ')}
          </span>
        </div>

        {/* Message from backend */}
        <p className={`text-xs mt-0.5 ${cfg.sub}`}>{jenkins.message}</p>

        {/* Detail row: URL, job name, version */}
        {(jenkins.url || jenkins.version) && (
          <p className={`text-xs mt-1 ${cfg.sub}`}>
            {jenkins.url && (
              <a href={jenkins.url} target="_blank" rel="noreferrer"
                className="underline hover:opacity-80 mr-2">{jenkins.url}</a>
            )}
            {jenkins.job_name && (
              <span>Job: <code className={`rounded px-1 font-mono ${cfg.badge}`}>{jenkins.job_name}</code></span>
            )}
            {jenkins.version && (
              <span className="ml-2 opacity-70">v{jenkins.version}</span>
            )}
          </p>
        )}

        {/* Capabilities row */}
        <div className="flex items-center gap-3 mt-2 flex-wrap">
          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full px-2 py-0.5 ${
            jenkins.local_training ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
          }`}>
            {jenkins.local_training ? '✓' : '✕'} Local training
          </span>
          <span className={`inline-flex items-center gap-1 text-[10px] font-semibold rounded-full px-2 py-0.5 ${
            jenkins.remote_trigger ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'
          }`}>
            {jenkins.remote_trigger ? '✓' : '✕'} Remote trigger
          </span>
          {/* Checked at */}
          {jenkins.checked_at && (
            <span className="text-[10px] text-slate-400 ml-auto">
              Checked {fmt(jenkins.checked_at)}
            </span>
          )}
        </div>
      </div>

      {/* Test connection button */}
      <button
        type="button"
        onClick={onTest}
        disabled={testing}
        title="Re-run Jenkins health check"
        className="flex-shrink-0 flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition"
      >
        {testing
          ? <Loader2 size={11} className="animate-spin" />
          : <RefreshCw size={11} />
        }
        {testing ? 'Testing…' : 'Test'}
      </button>
    </div>
  );
}
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
  // Use pre-computed duration_seconds from backend (stored in TrainingJob.duration_seconds).
  // Fall back to client-side diff only when not available.
  const dur = job.duration_seconds > 0
    ? `${job.duration_seconds}s`
    : (job.start_time && job.end_time
        ? Math.round((new Date(job.end_time) - new Date(job.start_time)) / 1000) + 's'
        : '—');

  // "Docs" column shows dataset_size (samples trained on) with fallback to documents_count.
  const sampleCount = job.dataset_size || job.documents_count;

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
        <td className="px-4 py-3 text-sm text-slate-600">{sampleCount || '—'}</td>
        <td className="px-4 py-3 text-sm font-semibold text-violet-700">
          {job.f1_score != null && job.f1_score > 0 ? pct(job.f1_score) : 'N/A'}
        </td>
        <td className="px-4 py-3 text-sm text-slate-600">
          {job.drift_score != null && job.drift_score > 0 ? job.drift_score.toFixed(3) : '—'}
        </td>
        <td className="px-4 py-3 text-xs text-slate-400">{fmt(job.start_time)}</td>
        <td className="px-4 py-3 text-xs text-slate-400">{dur}</td>
        <td className="px-4 py-3 text-slate-400">{open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}</td>
      </tr>
      {open && (
        <tr className="bg-slate-50">
          <td colSpan={9} className="px-6 py-4 text-xs text-slate-600">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Metrics</p>
                <p>Accuracy: <strong>{job.accuracy != null && job.accuracy > 0 ? pct(job.accuracy) : (job.avg_similarity != null && job.avg_similarity > 0 ? pct(job.avg_similarity) : 'N/A')}</strong></p>
                <p>Precision: <strong>{job.precision_score != null && job.precision_score > 0 ? pct(job.precision_score) : 'N/A'}</strong></p>
                <p>Recall: <strong>{job.recall_score != null && job.recall_score > 0 ? pct(job.recall_score) : 'N/A'}</strong></p>
              </div>
              <div>
                <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Model</p>
                <p>Version: <strong>{job.model_version || 'N/A'}</strong></p>
                <p>Samples: <strong>{sampleCount || '—'}</strong></p>
                <p>Triggered by: <strong>{job.triggered_by || '—'}</strong></p>
              </div>
              {job.jenkins_url ? (
                <div>
                  <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Jenkins</p>
                  <a href={job.jenkins_url} target="_blank" rel="noreferrer" className="text-sky-600 hover:underline break-all">
                    View build ↗
                  </a>
                  {job.jenkins_build_id && <p className="mt-1">Build: <strong>#{job.jenkins_build_id}</strong></p>}
                </div>
              ) : (
                <div>
                  <p className="font-semibold text-slate-500 uppercase tracking-wider mb-1">Jenkins</p>
                  <p className="text-slate-400 italic">Local run (no Jenkins build)</p>
                </div>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

/* ── Drift status helpers ────────────────────────────────────────── */
// 0.00–0.10 → stable, 0.10–0.30 → warning, >0.30 → critical
function driftLabel(score) {
  if (score == null) return '—';
  if (score <= 0.10) return 'Stable';
  if (score <= 0.30) return 'Warning';
  return 'Critical';
}
function driftBarColor(status) {
  if (status === 'stable')   return 'bg-emerald-500';
  if (status === 'warning')  return 'bg-amber-500';
  if (status === 'critical') return 'bg-rose-500';
  return 'bg-slate-300';
}

/* ── Standard card ───────────────────────────────────────────────── */
function StandardCard({ std, onTrigger, triggering }) {
  const drift       = std.drift || {};
  // Use the status computed by the backend (stable/warning/critical/insufficient_data/error).
  // Fall back to deriving it from the score so the UI is never blank.
  const rawStatus   = drift.status;
  const driftScore  = drift.drift_score;
  const driftStatus = (rawStatus && rawStatus !== 'unknown')
    ? rawStatus
    : (driftScore != null ? (driftScore <= 0.10 ? 'stable' : driftScore <= 0.30 ? 'warning' : 'critical') : null);

  // Model version: show exactly what backend provides; null/empty → "Not trained"
  const modelVersion = std.current_model_version || null;

  // FIX #3: labeled_samples is now always == total_documents (unified by backend).
  // All three aliases point to the same value — no more divergence.
  const totalSamples  = std.labeled_samples ?? std.total_samples ?? std.total_documents;
  const newSamples    = std.new_samples ?? std.new_documents;
  const threshold     = std.retraining_threshold;
  const trainingCount = std.training_count ?? null;

  // F1: from last successful job (backend already resolves this).
  const f1 = std.last_f1_score;

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      {/* Header */}
      <div className="flex items-start justify-between gap-3 mb-4">
        <div>
          <p className="text-sm font-bold text-slate-900">{std.standard}</p>
          <p className="text-xs text-slate-400 mt-0.5">
            Model:{' '}
            <span className="font-semibold text-slate-600">
              {modelVersion || <span className="italic text-slate-400">Not trained</span>}
            </span>
          </p>
          {std.last_trained_at && (
            <p className="text-xs text-slate-400 mt-0.5">
              Last trained: <span className="text-slate-500">{fmt(std.last_trained_at)}</span>
            </p>
          )}
        </div>
        <button
          type="button"
          onClick={() => onTrigger(std.standard)}
          disabled={triggering}
          className="flex items-center gap-1.5 rounded-xl bg-sky-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-sky-600 disabled:opacity-50 transition"
        >
          {triggering ? <Loader2 size={11} className="animate-spin" /> : <Play size={11} />}
          {triggering ? 'Triggering…' : 'Trigger'}
        </button>
      </div>

      {/* KPI grid — 2×3 */}
      <div className="grid grid-cols-2 gap-2 text-xs mb-3">
        {/* Total samples — FIX #3: always = labeled_samples, no divergence with ML Dashboard */}
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-400">Training samples</p>
          <p className="font-bold text-slate-800">
            {totalSamples != null ? totalSamples.toLocaleString() : '—'}
          </p>
        </div>

        {/* New samples since last training */}
        <div className={`rounded-xl px-3 py-2 ${
          newSamples != null && threshold != null && newSamples >= threshold
            ? 'bg-amber-50' : 'bg-slate-50'
        }`}>
          <p className="text-slate-400">New since training</p>
          <p className={`font-bold ${
            newSamples != null && threshold != null && newSamples >= threshold
              ? 'text-amber-600' : 'text-slate-800'
          }`}>
            {newSamples != null ? newSamples : '—'}
          </p>
        </div>

        {/* Threshold — real value from MLOpsConfig */}
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-400">Threshold</p>
          <p className="font-bold text-slate-800">
            {threshold != null ? threshold : '—'}
          </p>
        </div>

        {/* F1 Score — from last successful TrainingJob */}
        <div className="rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-slate-400">F1 Score</p>
          <p className="font-bold text-slate-800">
            {f1 != null && f1 > 0 ? pct(f1) : 'N/A'}
          </p>
        </div>

        {/* Training runs — FIX #9: now reliably incremented */}
        {trainingCount != null && (
          <div className="rounded-xl bg-slate-50 px-3 py-2 col-span-2">
            <p className="text-slate-400">Training runs completed</p>
            <p className="font-bold text-slate-800">{trainingCount}</p>
          </div>
        )}
      </div>

      {/* Last job metrics row — precision / recall / accuracy
           FIX #3: prefer flat fields last_precision/last_recall/last_accuracy
           that are now always aligned with labeled_samples count. */}
      {(std.last_precision != null || (std.last_job && std.last_job.status === 'success')) && (
        <div className="grid grid-cols-3 gap-1.5 text-xs mb-3">
          {[
            { label: 'Precision', val: std.last_precision ?? std.last_job?.precision_score },
            { label: 'Recall',    val: std.last_recall    ?? std.last_job?.recall_score    },
            { label: 'Accuracy',  val: std.last_accuracy  ?? std.last_job?.accuracy ?? std.last_job?.avg_similarity },
          ].map(m => (
            <div key={m.label} className="rounded-lg bg-violet-50 px-2 py-1.5 text-center">
              <p className="text-violet-400">{m.label}</p>
              <p className="font-bold text-violet-700">
                {m.val != null && m.val > 0 ? pct(m.val) : 'N/A'}
              </p>
            </div>
          ))}
        </div>
      )}

      {/* Drift bar */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs text-slate-400">Semantic drift</p>
          <span className={`text-xs font-bold ${DRIFT_COLOR[driftStatus] || 'text-slate-500'}`}>
            {driftScore != null ? driftScore.toFixed(3) : '—'}
            {driftStatus ? ` — ${driftLabel(driftScore)}` : ''}
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
          <div
            className={`h-full rounded-full transition-all ${driftBarColor(driftStatus)}`}
            style={{ width: `${Math.min(100, (driftScore || 0) * 333)}%` }}
          />
        </div>
        {drift.computed_at && (
          <p className="mt-1 text-[10px] text-slate-400">
            Computed {fmt(drift.computed_at)}
            {drift.cosine_similarity != null && ` · cosine similarity ${drift.cosine_similarity.toFixed(3)}`}
          </p>
        )}
        {driftStatus === 'insufficient_data' && (
          <p className="mt-1 text-[10px] text-slate-400">{drift.message || 'Not enough samples to compute drift.'}</p>
        )}
      </div>

      {/* Threshold alert */}
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
  const { user } = useContext(UserContext);

  // Defense-in-depth: route is already protected in App.js
  if (user && user.role !== 'ADMIN') {
    return null;
  }

  const [data,          setData]         = useState(null);
  const [loading,       setLoading]      = useState(true);
  const [error,         setError]        = useState('');
  const [triggering,    setTriggering]   = useState('');
  const [triggerMsg,    setTriggerMsg]   = useState('');
  const [jobFilter,     setJobFilter]    = useState('');
  const [forceStandard, setForceStandard]= useState('');
  // Jenkins health is fetched separately so the on-demand "Test" button
  // doesn't reload the entire dashboard.
  const [jenkinsHealth,    setJenkinsHealth]   = useState(null);
  const [testingJenkins,   setTestingJenkins]  = useState(false);

  // ── Load main dashboard data (standards, jobs, summary) ──────────────
  const load = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const r = await api.get('/ml/mlops/status/');
      setData(r.data);
      // mlops/status/ now embeds jenkins health — use it as the initial value
      // so the banner renders immediately without a second round-trip.
      if (r.data?.jenkins) setJenkinsHealth(r.data.jenkins);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to load MLOps status.');
    } finally {
      setLoading(false);
    }
  }, []);

  // ── Dedicated Jenkins health check (on demand / "Test" button) ───────
  const testJenkins = useCallback(async () => {
    setTestingJenkins(true);
    try {
      const r = await api.get('/ml/jenkins/status/');
      setJenkinsHealth(r.data);
    } catch (e) {
      // If the endpoint itself fails (e.g. network), mark as unreachable
      setJenkinsHealth({
        configured: false,
        reachable: false,
        authenticated: false,
        connected: false,
        local_training: true,
        remote_trigger: false,
        status: 'error',
        message: e?.response?.data?.error || 'Could not reach the backend health check endpoint.',
        checked_at: new Date().toISOString(),
      });
    } finally {
      setTestingJenkins(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  // Auto-refresh every 30 s — only the dashboard data, not the Jenkins health
  // (Jenkins check makes a real network call; we don't want that on every poll)
  useEffect(() => {
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [load]);

  const standards = useMemo(() => data?.standards || [], [data]);
  // Force Retrain is always available — it runs locally regardless of Jenkins.
  // Only disable while a trigger is in progress.
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
      if (d.triggered) setTriggerMsg(`✓ Pipeline triggered for ${standard} (Job #${d.job_id})`);
      else setTriggerMsg(`Not triggered: ${d.reason}`);
      await load();
    } catch (e) {
      const d = e?.response?.data;
      setTriggerMsg(
        e?.response?.status === 503
          ? `Jenkins unavailable: ${d?.reason || 'remote trigger not configured'}. Local training is still available.`
          : `Error: ${d?.error || e.message}`
      );
    } finally {
      setTriggering('');
    }
  };

  return (
    <Layout>
      <div className="page-container">
        {/* Header */}
        <div className="overflow-hidden rounded-xl border border-slate-800 bg-gradient-to-br from-slate-900 via-indigo-950 to-slate-900 px-6 py-6 shadow-lg">
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
            triggerMsg.startsWith('✓') ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
            : triggerMsg.includes('unavailable') || triggerMsg.startsWith('Error') ? 'border-amber-200 bg-amber-50 text-amber-700'
            : 'border-sky-200 bg-sky-50 text-sky-700'
          }`}>{triggerMsg}</div>
        )}

        {/* Jenkins health banner — rendered once data is loaded */}
        {!loading && (
          <JenkinsBanner
            jenkins={jenkinsHealth}
            onTest={testJenkins}
            testing={testingJenkins}
          />
        )}

        {error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
            {error}
          </div>
        )}

        {/* KPIs */}
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <KpiCard icon={BarChart3}    label="Total Jobs"  value={summary.total_jobs ?? '—'}
            color="text-slate-700"   loading={loading} />
          <KpiCard icon={CheckCircle2} label="Successful"  value={summary.success_jobs ?? '—'}
            color="text-emerald-600" loading={loading}
            sub={summary.total_jobs
              ? `${Math.round(((summary.success_jobs || 0) / summary.total_jobs) * 100)}% success rate`
              : undefined} />
          <KpiCard icon={XCircle}      label="Failed"      value={summary.failed_jobs ?? '—'}
            color="text-rose-600"    loading={loading} />
          <KpiCard icon={Loader2}      label="Running Now" value={summary.running_jobs ?? '—'}
            color="text-sky-600"     loading={loading}
            sub={summary.last_successful_job
              ? `Last: ${fmt(summary.last_successful_job.end_time)}`
              : undefined} />
        </div>

        {/* Standards — only render if at least one standard exists in DB */}
        {!loading && standards.length === 0 && !error && (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-6 py-8 text-center text-sm text-slate-500">
            No MLOps configuration found. Run the Jenkins pipeline or trigger a local training to create the first entry.
          </div>
        )}
        {standards.length > 0 && (
          <div>
            <p className="mb-3 text-xs font-semibold uppercase tracking-widest text-slate-400">
              Standards ({standards.length})
            </p>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {standards.map(s => (
                <StandardCard
                  key={s.standard}
                  std={s}
                  onTrigger={std => handleTrigger(std)}
                  triggering={triggering === s.standard}
                />
              ))}
            </div>
          </div>
        )}

        {/* Jobs table */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <p className="text-sm font-bold text-slate-900">Training Job History</p>
              <p className="text-xs text-slate-400">
                {jobs.length} job{jobs.length !== 1 ? 's' : ''}
                {jobFilter ? ` · filter: ${jobFilter}` : ''}
              </p>
            </div>
            <select
              value={jobFilter}
              onChange={e => setJobFilter(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs outline-none"
            >
              <option value="">All statuses</option>
              {['success', 'failed', 'running', 'pending', 'cancelled'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
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
                  <tr>
                    {['ID', 'Status', 'Standard', 'Samples', 'F1', 'Drift', 'Started', 'Duration', ''].map(h => (
                      <th key={h} className="px-4 py-3 text-left font-semibold">{h}</th>
                    ))}
                  </tr>
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
