/**
 * DocumentSecurity.jsx — Document Security Analysis Page
 * Enterprise ISO Compliance Platform
 */
import React, { useCallback, useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Lock, ShieldAlert, ShieldCheck, AlertTriangle,
  Key, User, FileText, RefreshCw, ChevronDown, ChevronUp,
  AlertCircle, CheckCircle2, XCircle, Info, Activity,
  Database, BarChart3, Search,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── Helpers ─────────────────────────────────────────────────────── */
const fmt = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};
const num = (v) => (v != null ? Number(v).toLocaleString('fr-FR') : '—');

/* ── Config maps ─────────────────────────────────────────────────── */
const CONF_CFG = {
  PUBLIC:       { label: 'Public',       badge: 'badge-green',  ring: '#10b981', bg: 'bg-emerald-50' },
  INTERNAL:     { label: 'Internal',     badge: 'badge-blue',   ring: '#3b82f6', bg: 'bg-blue-50' },
  CONFIDENTIAL: { label: 'Confidential', badge: 'badge-amber',  ring: '#f59e0b', bg: 'bg-amber-50' },
  RESTRICTED:   { label: 'Restricted',   badge: 'badge-red',    ring: '#ef4444', bg: 'bg-red-50' },
  SECRET:       { label: 'Secret',       badge: 'badge-purple', ring: '#8b5cf6', bg: 'bg-purple-50' },
};

const RISK_CFG = {
  LOW:      { label: 'Low',      badge: 'badge-green',  icon: CheckCircle2,  color: 'text-emerald-600' },
  MEDIUM:   { label: 'Medium',   badge: 'badge-amber',  icon: AlertTriangle, color: 'text-amber-600' },
  HIGH:     { label: 'High',     badge: 'badge-red',    icon: ShieldAlert,   color: 'text-red-600' },
  CRITICAL: { label: 'Critical', badge: 'badge-purple', icon: XCircle,       color: 'text-purple-700' },
};

const GDPR_CFG = {
  OK:            { label: 'Compliant',     badge: 'badge-green',  icon: CheckCircle2 },
  WARNING:       { label: 'Warning',       badge: 'badge-amber',  icon: AlertTriangle },
  NON_COMPLIANT: { label: 'Non-Compliant', badge: 'badge-red',    icon: XCircle },
  UNKNOWN:       { label: 'Unknown',       badge: 'badge-slate',  icon: Info },
};

const PRIO_CFG = {
  CRITICAL: { badge: 'badge-purple', color: 'text-purple-700' },
  HIGH:     { badge: 'badge-red',    color: 'text-red-600' },
  MEDIUM:   { badge: 'badge-amber',  color: 'text-amber-600' },
  LOW:      { badge: 'badge-slate',  color: 'text-slate-600' },
};

/* ── Score Ring SVG ──────────────────────────────────────────────── */
function ScoreRing({ value = 0, max = 100, color = '#3b82f6', label, size = 96 }) {
  const r = 36;
  const circ = 2 * Math.PI * r;
  const pct = Math.min(1, Math.max(0, value / Math.max(max, 1)));
  const dash = pct * circ;
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width={size} height={size} viewBox="0 0 88 88">
        <circle cx="44" cy="44" r={r} fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <circle
          cx="44" cy="44" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={`${dash} ${circ}`}
          strokeLinecap="round"
          transform="rotate(-90 44 44)"
          style={{ transition: 'stroke-dasharray 0.8s ease' }}
        />
        <text x="44" y="48" textAnchor="middle" fontSize="16" fontWeight="700" fill="#0f172a">
          {value}
        </text>
      </svg>
      <span className="text-xs font-medium text-slate-500">{label}</span>
    </div>
  );
}

/* ── Skeleton ────────────────────────────────────────────────────── */
function Sk({ h = 'h-6', w = 'w-full', rounded = 'rounded-lg' }) {
  return <div className={`${h} ${w} ${rounded} animate-pulse bg-slate-100`} />;
}

/* ── KPI Card ────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, iconColor = 'text-brand-600', iconBg = 'bg-brand-50' }) {
  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="kpi-card">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="kpi-label mb-2">{label}</p>
          <p className="kpi-value">{value ?? '—'}</p>
          {sub && <p className="text-xs text-slate-400 mt-1">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl ${iconBg}`}>
          <Icon size={18} className={iconColor} />
        </div>
      </div>
    </motion.div>
  );
}

/* ── Collapsible section ─────────────────────────────────────────── */
function Collapsible({ title, icon: Icon, badge, children, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="card-header w-full text-left hover:bg-slate-50/60 transition-colors rounded-t-xl"
      >
        <div className="flex items-center gap-2">
          {Icon && <Icon size={16} className="text-slate-500 shrink-0" />}
          <span className="card-title">{title}</span>
          {badge != null && (
            <span className="badge badge-slate ml-1">{badge}</span>
          )}
        </div>
        {open ? <ChevronUp size={16} className="text-slate-400 shrink-0" /> : <ChevronDown size={16} className="text-slate-400 shrink-0" />}
      </button>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="card-body">{children}</div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Dashboard tab ───────────────────────────────────────────────── */
function DashboardTab() {
  const [stats, setStats]   = useState(null);
  const [high, setHigh]     = useState(null);
  const [loading, setLoad]  = useState(true);
  const [error, setError]   = useState(null);

  const load = useCallback(async () => {
    setLoad(true); setError(null);
    try {
      const [s, h] = await Promise.all([
        api.get('security/dashboard/statistics/'),
        api.get('security/dashboard/high-risk/?page_size=5'),
      ]);
      setStats(s.data); setHigh(h.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Failed to load dashboard');
    } finally { setLoad(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {[...Array(8)].map((_, i) => <Sk key={i} h="h-24" rounded="rounded-xl" />)}
    </div>
  );
  if (error) return <div className="alert-danger">{error}</div>;
  if (!stats) return null;

  const confDist = stats.confidentiality_distribution || {};
  const riskDist = stats.risk_distribution || {};
  const gdprDist = stats.gdpr_distribution || {};

  return (
    <div className="space-y-6">
      {/* Distribution grids */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Confidentiality */}
        <div className="card card-body space-y-3">
          <p className="card-title text-sm">Confidentiality Levels</p>
          {Object.entries(CONF_CFG).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span className={`badge ${v.badge} text-xs`}>{v.label}</span>
              <span className="text-sm font-semibold text-slate-700 tabular-nums">{confDist[k] ?? 0}</span>
            </div>
          ))}
        </div>
        {/* Risk */}
        <div className="card card-body space-y-3">
          <p className="card-title text-sm">Risk Levels</p>
          {Object.entries(RISK_CFG).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span className={`badge ${v.badge} text-xs`}>{v.label}</span>
              <span className="text-sm font-semibold text-slate-700 tabular-nums">{riskDist[k] ?? 0}</span>
            </div>
          ))}
        </div>
        {/* GDPR */}
        <div className="card card-body space-y-3">
          <p className="card-title text-sm">GDPR Status</p>
          {Object.entries(GDPR_CFG).map(([k, v]) => (
            <div key={k} className="flex items-center justify-between gap-2">
              <span className={`badge ${v.badge} text-xs`}>{v.label}</span>
              <span className="text-sm font-semibold text-slate-700 tabular-nums">{gdprDist[k] ?? 0}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Top PII & secrets */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <div className="card card-body">
          <p className="card-title text-sm mb-3">Top PII Types</p>
          {(stats.top_pii_types || []).length === 0
            ? <p className="text-sm text-slate-400">No PII detected</p>
            : (stats.top_pii_types || []).map(({ type, count }) => (
              <div key={type} className="flex items-center justify-between py-1 border-b border-slate-50 last:border-0">
                <span className="text-xs font-medium text-slate-600">{type}</span>
                <span className="badge badge-blue text-xs">{count}</span>
              </div>
            ))}
        </div>
        <div className="card card-body">
          <p className="card-title text-sm mb-3">Top Secret Types</p>
          {(stats.top_secret_types || []).length === 0
            ? <p className="text-sm text-slate-400">No secrets detected</p>
            : (stats.top_secret_types || []).map(({ type, count }) => (
              <div key={type} className="flex items-center justify-between py-1 border-b border-slate-50 last:border-0">
                <span className="text-xs font-medium text-slate-600">{type}</span>
                <span className="badge badge-red text-xs">{count}</span>
              </div>
            ))}
        </div>
      </div>

      {/* High-risk list */}
      {high && high.total > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title flex items-center gap-2">
              <ShieldAlert size={16} className="text-red-500" /> High-Risk Documents
            </span>
            <span className="badge badge-red">{high.total}</span>
          </div>
          <div className="overflow-x-auto">
            <table className="table-enterprise">
              <thead><tr>
                <th>Document</th><th>Risk</th><th>Confidentiality</th><th>PII</th><th>Secrets</th><th>Analysed</th>
              </tr></thead>
              <tbody>
                {(high.results || []).map(r => {
                  const rCfg = RISK_CFG[r.risk_level] || RISK_CFG.LOW;
                  const cCfg = CONF_CFG[r.confidentiality_level] || CONF_CFG.PUBLIC;
                  return (
                    <tr key={r.id}>
                      <td className="font-medium">#{r.document}</td>
                      <td><span className={`badge ${rCfg.badge}`}>{rCfg.label} ({r.risk_score})</span></td>
                      <td><span className={`badge ${cCfg.badge}`}>{cCfg.label}</span></td>
                      <td className="tabular-nums">{r.pii_count}</td>
                      <td className="tabular-nums">{r.secret_count}</td>
                      <td className="text-slate-400 text-xs">{fmt(r.analysis_date)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Shared analysis result renderer ─────────────────────────────── */
function AnalysisResult({ a }) {
  if (!a) return null;
  const rCfg = RISK_CFG[a.risk_level]             || RISK_CFG.LOW;
  const cCfg = CONF_CFG[a.confidentiality_level]  || CONF_CFG.PUBLIC;
  const gCfg = GDPR_CFG[a.gdpr_status]            || GDPR_CFG.UNKNOWN;

  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-5">
      {/* Score rings + badges */}
      <div className="card card-body">
        <div className="flex flex-wrap items-center justify-between gap-6">
          <div className="flex items-center gap-8">
            <ScoreRing value={a.confidentiality_score} color={cCfg.ring} label="Confidentiality" />
            <ScoreRing
              value={a.risk_score}
              color={a.risk_score > 60 ? '#ef4444' : a.risk_score > 30 ? '#f59e0b' : '#10b981'}
              label="Risk Score"
            />
          </div>
          <div className="flex flex-wrap gap-3 items-center">
            <div className="flex flex-col items-center gap-1">
              <span className="text-xs text-slate-400 uppercase tracking-wide">Classification</span>
              <span className={`badge ${cCfg.badge} text-sm px-3 py-1`}>{cCfg.label}</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-xs text-slate-400 uppercase tracking-wide">Risk Level</span>
              <span className={`badge ${rCfg.badge} text-sm px-3 py-1`}>{rCfg.label}</span>
            </div>
            <div className="flex flex-col items-center gap-1">
              <span className="text-xs text-slate-400 uppercase tracking-wide">GDPR</span>
              <span className={`badge ${gCfg.badge} text-sm px-3 py-1`}>{gCfg.label}</span>
            </div>
            {a.has_secrets && <span className="badge badge-red text-xs">🔑 Secrets Detected</span>}
            {a.is_high_risk && <span className="badge badge-purple text-xs">⚠ High Risk</span>}
          </div>
          <div className="text-xs text-slate-400 space-y-0.5">
            {a.filename && <p>File: <span className="text-slate-600">{a.filename}</span></p>}
            {a.file_size_kb && <p>Size: <span className="text-slate-600">{a.file_size_kb} KB</span></p>}
            {a.analysis_date && <p>Analysed: <span className="text-slate-600">{fmt(a.analysis_date)}</span></p>}
            <p>Version: <span className="text-slate-600">{a.analysis_version}</span></p>
          </div>
        </div>
        {(a.score_explanation || []).length > 0 && (
          <div className="mt-4 pt-4 border-t border-slate-100">
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Score Breakdown</p>
            <ul className="space-y-1">
              {a.score_explanation.map((line, i) => (
                <li key={i} className="text-xs text-slate-600 flex items-start gap-1.5">
                  <span className="text-slate-300 mt-0.5">•</span>{line}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>

      {/* PII */}
      <Collapsible title="PII Detected" icon={User} badge={a.pii_count}>
        {a.pii_count === 0
          ? <p className="text-sm text-slate-400">No PII detected.</p>
          : (
            <div className="overflow-x-auto">
              <table className="table-enterprise">
                <thead><tr><th>Type</th><th>Value (redacted)</th><th>Context</th></tr></thead>
                <tbody>
                  {(a.pii_details || []).map((d, i) => (
                    <tr key={i}>
                      <td><span className="badge badge-blue text-xs">{d.type}</span></td>
                      <td className="font-mono text-xs text-slate-500">{d.value}</td>
                      <td className="text-xs text-slate-400 max-w-xs truncate-2">{d.context}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Collapsible>

      {/* Secrets */}
      <Collapsible title="Secrets & Credentials" icon={Key} badge={a.secret_count}>
        {a.secret_count === 0
          ? <p className="text-sm text-slate-400">No secrets or credentials detected.</p>
          : (
            <div className="overflow-x-auto">
              <table className="table-enterprise">
                <thead><tr><th>Type</th><th>Value (redacted)</th><th>Confidence</th><th>Context</th></tr></thead>
                <tbody>
                  {(a.secret_details || []).map((d, i) => (
                    <tr key={i}>
                      <td><span className="badge badge-red text-xs">{d.type}</span></td>
                      <td className="font-mono text-xs text-slate-500">{d.value}</td>
                      <td className="tabular-nums text-xs">{d.confidence != null ? `${(d.confidence * 100).toFixed(0)}%` : '—'}</td>
                      <td className="text-xs text-slate-400 max-w-xs truncate-2">{d.context}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
      </Collapsible>

      {/* Metadata */}
      <Collapsible title="Document Metadata" icon={FileText} badge={`risk: ${a.metadata_risk}`}>
        {!a.metadata_details || Object.keys(a.metadata_details).length === 0
          ? <p className="text-sm text-slate-400">No metadata extracted.</p>
          : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {Object.entries(a.metadata_details).map(([k, v]) => {
                if (v == null || v === false || (Array.isArray(v) && v.length === 0)) return null;
                return (
                  <div key={k} className="flex flex-col gap-0.5">
                    <span className="text-2xs font-semibold uppercase tracking-wide text-slate-400">{k.replace(/_/g, ' ')}</span>
                    <span className="text-sm text-slate-700 break-words">{Array.isArray(v) ? v.join(', ') : String(v)}</span>
                  </div>
                );
              })}
            </div>
          )}
      </Collapsible>

      {/* GDPR */}
      <Collapsible title="GDPR / RGPD Compliance" icon={ShieldCheck}>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-3">
            {[['PII present', a.gdpr_has_pii], ['Sensitive data', a.gdpr_has_sensitive], ['Financial data', a.gdpr_has_financial]].map(([lbl, flag]) => (
              <div key={lbl} className="flex items-center gap-2 text-sm">
                {flag ? <XCircle size={14} className="text-red-500" /> : <CheckCircle2 size={14} className="text-emerald-500" />}
                {lbl}
              </div>
            ))}
          </div>
          {a.gdpr_compliance_summary && <div className="alert-info text-sm">{a.gdpr_compliance_summary}</div>}
          {(a.gdpr_issues || []).length > 0 && (
            <ul className="space-y-1 mt-2">
              {a.gdpr_issues.map((issue, i) => (
                <li key={i} className="text-sm text-red-600 flex items-start gap-1.5">
                  <AlertCircle size={13} className="mt-0.5 shrink-0" />{issue}
                </li>
              ))}
            </ul>
          )}
        </div>
      </Collapsible>

      {/* Recommendations */}
      <Collapsible title="AI Recommendations" icon={Activity} badge={(a.recommendations || []).length}>
        {(a.recommendations || []).length === 0
          ? <p className="text-sm text-slate-400">No recommendations generated.</p>
          : (
            <div className="space-y-3">
              {a.recommendations.map((r, i) => {
                const pCfg = PRIO_CFG[r.priority] || PRIO_CFG.LOW;
                return (
                  <div key={i} className="border border-slate-100 rounded-xl p-4 hover:bg-slate-50/50 transition-colors">
                    <div className="flex items-start justify-between gap-3 mb-1.5">
                      <p className={`text-sm font-semibold ${pCfg.color}`}>{r.title}</p>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <span className={`badge ${pCfg.badge} text-xs`}>{r.priority}</span>
                        {r.category && <span className="badge badge-slate text-xs">{r.category}</span>}
                      </div>
                    </div>
                    <p className="text-xs text-slate-500 mb-2">{r.description}</p>
                    {r.action && <p className="text-xs font-medium text-slate-700"><span className="text-slate-400">Action: </span>{r.action}</p>}
                  </div>
                );
              })}
            </div>
          )}
      </Collapsible>
    </motion.div>
  );
}

/* ── Document Analysis tab ───────────────────────────────────────── */
function AnalysisTab() {
  // mode: 'existing' | 'upload'
  const [mode, setMode]         = useState('existing');

  // --- existing doc state ---
  const [docs, setDocs]         = useState([]);
  const [docsLoading, setDL]    = useState(false);
  const [docId, setDocId]       = useState('');
  const [analysis, setAnal]     = useState(null);
  const [loading, setLoad]      = useState(false);
  const [reloading, setReload]  = useState(false);
  const [error, setError]       = useState(null);

  // --- upload state ---
  const [file, setFile]         = useState(null);
  const [uploadAnal, setUAnal]  = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadErr, setUploadErr] = useState(null);
  const [dragOver, setDragOver] = useState(false);

  // Load document list for dropdown
  useEffect(() => {
    if (mode !== 'existing') return;
    setDL(true);
    api.get('security/documents/list/')
      .then(r => setDocs(r.data || []))
      .catch(() => setDocs([]))
      .finally(() => setDL(false));
  }, [mode]);

  const fetchAnalysis = useCallback(async (id) => {
    if (!id) return;
    setLoad(true); setError(null); setAnal(null);
    try {
      const res = await api.get(`/security/documents/${id}/analysis/`);
      setAnal(res.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'No analysis found. Click Reanalyze to run one.');
    } finally { setLoad(false); }
  }, []);

  const reanalyze = async () => {
    if (!docId) return;
    setReload(true); setError(null);
    try {
      const res = await api.post(`/security/documents/${docId}/reanalyze/`, { force: true });
      setAnal(res.data);
    } catch (e) {
      setError(e?.response?.data?.error || 'Reanalysis failed.');
    } finally { setReload(false); }
  };

  const handleUploadScan = async () => {
    if (!file) return;
    setUploading(true); setUploadErr(null); setUAnal(null);
    try {
      const fd = new FormData();
      fd.append('file', file);
      const res = await api.post('security/scan/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setUAnal(res.data);
    } catch (e) {
      setUploadErr(e?.response?.data?.error || 'Scan failed. Check the file format.');
    } finally { setUploading(false); }
  };

  const handleDrop = (e) => {
    e.preventDefault(); setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) { setFile(dropped); setUAnal(null); setUploadErr(null); }
  };

  return (
    <div className="space-y-5">
      {/* Mode toggle */}
      <div className="card card-body">
        <div className="flex items-center gap-1 bg-slate-100 rounded-lg p-1 w-fit mb-5">
          <button
            type="button"
            onClick={() => { setMode('existing'); setAnal(null); setError(null); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'existing' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <Database size={14} /> Existing Document
          </button>
          <button
            type="button"
            onClick={() => { setMode('upload'); setUAnal(null); setUploadErr(null); }}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              mode === 'upload' ? 'bg-white shadow text-slate-900' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            <FileText size={14} /> Upload & Scan
          </button>
        </div>

        {/* ── EXISTING DOCUMENT MODE ── */}
        {mode === 'existing' && (
          <div className="space-y-3">
            <p className="form-label">Select Document</p>
            <div className="flex flex-wrap gap-3 items-start">
              <div className="relative min-w-[280px] flex-1 max-w-md">
                <select
                  className="form-select w-full"
                  value={docId}
                  onChange={e => { setDocId(e.target.value); setAnal(null); setError(null); }}
                  disabled={docsLoading}
                >
                  <option value="">{docsLoading ? 'Loading documents…' : '— Select a document —'}</option>
                  {docs.map(d => (
                    <option key={d.id} value={d.id}>
                      #{d.id} — {d.label} ({d.status || '?'}) · {d.employee_username || ''}
                    </option>
                  ))}
                </select>
                {docsLoading && (
                  <div className="absolute right-8 top-1/2 -translate-y-1/2">
                    <RefreshCw size={13} className="animate-spin text-slate-400" />
                  </div>
                )}
              </div>
              <button
                type="button"
                className="btn-primary flex items-center gap-2"
                onClick={() => fetchAnalysis(docId)}
                disabled={!docId || loading}
              >
                <Search size={15} />
                {loading ? 'Loading…' : 'Load Analysis'}
              </button>
              <button
                type="button"
                className="btn-secondary flex items-center gap-2"
                onClick={reanalyze}
                disabled={!docId || reloading}
              >
                <RefreshCw size={15} className={reloading ? 'animate-spin' : ''} />
                {reloading ? 'Running…' : 'Reanalyze'}
              </button>
            </div>
            {error && <p className="form-error">{error}</p>}
          </div>
        )}

        {/* ── UPLOAD MODE ── */}
        {mode === 'upload' && (
          <div className="space-y-3">
            <p className="form-label">Upload a file to scan</p>
            <p className="text-xs text-slate-400 -mt-1">PDF, DOCX or TXT — max 20 MB. The file is not saved to the database.</p>

            {/* Drop zone — label wraps the hidden input for native click forwarding */}
            <label
              htmlFor="sec-file-input"
              onDragOver={e => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`relative border-2 border-dashed rounded-xl p-8 text-center transition-colors cursor-pointer block
                ${dragOver ? 'border-brand-400 bg-brand-50' : 'border-slate-200 hover:border-brand-300 hover:bg-slate-50'}`}
            >
              <input
                id="sec-file-input"
                type="file"
                className="hidden"
                accept=".pdf,.docx,.txt"
                onChange={e => { const f = e.target.files[0]; if (f) { setFile(f); setUAnal(null); setUploadErr(null); } }}
              />
              <div className="flex flex-col items-center gap-3 pointer-events-none">
                <div className={`flex h-12 w-12 items-center justify-center rounded-xl transition-colors ${dragOver ? 'bg-brand-100' : 'bg-slate-100'}`}>
                  <FileText size={22} className={dragOver ? 'text-brand-600' : 'text-slate-400'} />
                </div>
                {file ? (
                  <div>
                    <p className="text-sm font-semibold text-slate-800">{file.name}</p>
                    <p className="text-xs text-slate-400 mt-0.5">{(file.size / 1024).toFixed(1)} KB — click to change</p>
                  </div>
                ) : (
                  <div>
                    <p className="text-sm font-medium text-slate-600">Drop file here or <span className="text-brand-600 underline">browse</span></p>
                    <p className="text-xs text-slate-400 mt-0.5">PDF, DOCX, TXT</p>
                  </div>
                )}
              </div>
            </label>

            <div className="flex gap-3 items-center">
              <button
                type="button"
                className="btn-primary flex items-center gap-2"
                onClick={handleUploadScan}
                disabled={!file || uploading}
              >
                <Lock size={14} />
                {uploading ? 'Scanning…' : 'Scan File'}
              </button>
              {file && (
                <button
                  type="button"
                  className="btn-ghost text-sm"
                  onClick={() => { setFile(null); setUAnal(null); setUploadErr(null); document.getElementById('sec-file-input').value = ''; }}
                >
                  Clear
                </button>
              )}
              {uploading && (
                <div className="flex items-center gap-2 text-xs text-slate-400">
                  <RefreshCw size={13} className="animate-spin" /> Analysing content…
                </div>
              )}
            </div>
            {uploadErr && <p className="form-error">{uploadErr}</p>}
          </div>
        )}
      </div>

      {/* Loading skeletons */}
      {(loading || uploading) && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => <Sk key={i} h="h-24" rounded="rounded-xl" />)}
        </div>
      )}

      {/* Analysis result — existing doc */}
      {mode === 'existing' && <AnalysisResult a={analysis} />}

      {/* Analysis result — uploaded file */}
      {mode === 'upload' && <AnalysisResult a={uploadAnal} />}
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────── */
const TABS = [
  { id: 'dashboard', label: 'Security Dashboard', icon: BarChart3 },
  { id: 'analysis',  label: 'Document Analysis',  icon: Search },
];

export default function DocumentSecurity() {
  const [tab, setTab] = useState('dashboard');
  const [kpis, setKpis] = useState(null);

  useEffect(() => {
    api.get('security/dashboard/').then(r => setKpis(r.data)).catch(() => {});
  }, []);

  return (
    <Layout>
      <div className="page-container">
        {/* Header */}
        <div className="page-header">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-red-50">
                <Lock size={18} className="text-red-600" />
              </div>
              <h1 className="page-title">Document Security Analysis</h1>
            </div>
            <p className="page-subtitle">
              Automated PII detection, secret scanning, GDPR compliance and risk scoring
            </p>
          </div>
          <span className="badge badge-red flex items-center gap-1.5">
            <ShieldAlert size={12} /> Security Module
          </span>
        </div>

        {/* KPI row */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          {kpis ? (
            <>
              <KpiCard icon={Database}    label="Analysed"      value={num(kpis.total_analysed)}          iconColor="text-brand-600" iconBg="bg-brand-50" />
              <KpiCard icon={ShieldAlert} label="High Risk"     value={num(kpis.high_risk_count)}         iconColor="text-red-600"   iconBg="bg-red-50" />
              <KpiCard icon={XCircle}     label="Critical"      value={num(kpis.critical_risk_count)}     iconColor="text-purple-600" iconBg="bg-purple-50" />
              <KpiCard icon={User}        label="PII Detected"  value={num(kpis.total_pii_detected)}      iconColor="text-amber-600" iconBg="bg-amber-50" />
              <KpiCard icon={Key}         label="Secrets Found" value={num(kpis.total_secrets_detected)}  iconColor="text-red-600"   iconBg="bg-red-50" />
              <KpiCard icon={Activity}    label="Avg Risk"      value={`${kpis.avg_risk_score ?? '—'}`}   iconColor="text-sky-600"   iconBg="bg-sky-50" />
            </>
          ) : (
            [...Array(6)].map((_, i) => <Sk key={i} h="h-24" rounded="rounded-xl" />)
          )}
        </div>

        {/* Tabs */}
        <div className="tabs-bar">
          {TABS.map(t => {
            const Icon = t.icon;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={tab === t.id ? 'tab-btn-active' : 'tab-btn'}
              >
                <Icon size={14} />{t.label}
              </button>
            );
          })}
        </div>

        {/* Tab content */}
        <AnimatePresence mode="wait">
          <motion.div
            key={tab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            {tab === 'dashboard' && <DashboardTab />}
            {tab === 'analysis'  && <AnalysisTab />}
          </motion.div>
        </AnimatePresence>
      </div>
    </Layout>
  );
}
