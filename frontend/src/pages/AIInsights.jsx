/**
 * AI Insights — Centre d'Intelligence IA
 * Enterprise ISO Compliance Platform
 * Toutes les données proviennent des API backend réelles.
 */
import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Brain, Sparkles, Activity, Database, BarChart3, MessageSquare,
  TrendingDown, AlertTriangle, CheckCircle2, XCircle, Zap, Clock,
  RefreshCw, Layers, Search, Send, Star,
  Download, Trash2, GitBranch, Target, Award, Eye,
  Play, Wifi, WifiOff, History,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';
import { UserContext } from '../context/UserContext';

/* ── Constantes ──────────────────────────────────────────────────── */
const TABS = [
  { id: 'overview',     label: 'AI Overview',          icon: Brain         },
  { id: 'health',       label: 'AI Health',             icon: Activity      },
  { id: 'drift',        label: 'Drift Detection',       icon: TrendingDown  },
  { id: 'explainable',  label: 'Explainable AI',        icon: Eye           },
  { id: 'dataset',      label: 'Dataset Quality',       icon: Database      },
  { id: 'reco',         label: 'AI Recommendations',    icon: Sparkles      },
  { id: 'comparison',   label: 'Model Comparison',      icon: BarChart3     },
  { id: 'timeline',     label: 'AI Timeline',           icon: GitBranch     },
  { id: 'semantic',     label: 'Semantic Analytics',    icon: Layers        },
  { id: 'assistant',    label: 'AI Assistant',          icon: MessageSquare },
];

const fmt = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

const pct = (v, decimals = 1) =>
  v != null ? `${typeof v === 'number' ? v.toFixed(decimals) : v}%` : '—';

const num = (v) => (v != null ? Number(v).toLocaleString('fr-FR') : '—');


/* ── Skeleton loader ────────────────────────────────────────────── */
function Skeleton({ h = 'h-24', w = 'w-full', rounded = 'rounded-2xl' }) {
  return <div className={`${h} ${w} ${rounded} animate-pulse bg-slate-100`} />;
}

/* ── Stat Card ───────────────────────────────────────────────────── */
function StatCard({ icon: Icon, label, value, sub, color = 'text-sky-600', bg = 'bg-sky-50', border = 'border-sky-100' }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex items-center gap-3 rounded-2xl border ${border} ${bg} px-4 py-3`}
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm">
        <Icon size={17} className={color} />
      </div>
      <div className="min-w-0">
        <p className="text-xs font-medium text-slate-500 truncate">{label}</p>
        <p className={`text-xl font-bold ${color} truncate`}>{value}</p>
        {sub && <p className="text-[10px] text-slate-400 truncate">{sub}</p>}
      </div>
    </motion.div>
  );
}

/* ── Progress bar ────────────────────────────────────────────────── */
function ProgressBar({ value = 0, max = 100, color = 'bg-sky-500', h = 'h-2' }) {
  const pctVal = Math.min(100, Math.max(0, (value / Math.max(max, 1)) * 100));
  return (
    <div className={`w-full ${h} rounded-full bg-slate-100 overflow-hidden`}>
      <motion.div
        initial={{ width: 0 }}
        animate={{ width: `${pctVal}%` }}
        transition={{ duration: 0.6, ease: 'easeOut' }}
        className={`h-full rounded-full ${color}`}
      />
    </div>
  );
}

/* ── Health score ring ───────────────────────────────────────────── */
function HealthRing({ score = 0, label = '' }) {
  const color = score >= 90 ? '#10b981' : score >= 75 ? '#f59e0b' : score >= 50 ? '#f97316' : '#ef4444';
  const r = 36, circ = 2 * Math.PI * r;
  const dash = circ * (score / 100);
  return (
    <div className="flex flex-col items-center gap-1">
      <svg width="96" height="96" viewBox="0 0 96 96">
        <circle cx="48" cy="48" r={r} fill="none" stroke="#e2e8f0" strokeWidth="8" />
        <motion.circle
          cx="48" cy="48" r={r} fill="none" stroke={color} strokeWidth="8"
          strokeLinecap="round" strokeDasharray={circ}
          initial={{ strokeDashoffset: circ }}
          animate={{ strokeDashoffset: circ - dash }}
          transition={{ duration: 1, ease: 'easeOut' }}
          transform="rotate(-90 48 48)"
        />
        <text x="48" y="48" textAnchor="middle" dominantBaseline="middle" fontSize="18" fontWeight="bold" fill={color}>{score}</text>
      </svg>
      <p className="text-xs font-semibold text-slate-600">{label}</p>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 1 — AI OVERVIEW
══════════════════════════════════════════════════════════════════ */
function OverviewTab({ data, loading }) {
  if (loading) return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {[...Array(8)].map((_, i) => <Skeleton key={i} />)}
    </div>
  );
  if (!data) return <p className="text-sm text-slate-400">No data available.</p>;

  const { summary, best_model, jobs, llm, health, drift } = data;
  const globalDriftPct = drift?.global != null ? Math.round(drift.global * 100) : 0;

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Brain} label="Modèles disponibles" value={summary?.total_models ?? 0}
          sub={`Standards: ${(summary?.available_standards || []).join(', ')}`}
          color="text-violet-600" bg="bg-violet-50" border="border-violet-100" />
        <StatCard icon={Database} label="Total Evidence" value={num(summary?.total_evidence)}
          sub={`${num(summary?.rules_covered)} règles couvertes`}
          color="text-sky-600" bg="bg-sky-50" border="border-sky-100" />
        <StatCard icon={Award} label="Meilleur modèle" value={best_model?.name ?? '—'}
          sub={best_model ? `F1: ${pct(best_model.f1_score * 100)} — ${best_model.standard}` : 'Non entraîné'}
          color="text-amber-600" bg="bg-amber-50" border="border-amber-100" />
        <StatCard icon={TrendingDown} label="Drift global" value={pct(globalDriftPct, 0)}
          sub={drift?.global > 0.3 ? 'CRITIQUE' : drift?.global > 0.15 ? 'Avertissement' : 'Stable'}
          color={drift?.global > 0.3 ? 'text-rose-600' : drift?.global > 0.15 ? 'text-amber-600' : 'text-emerald-600'}
          bg={drift?.global > 0.3 ? 'bg-rose-50' : drift?.global > 0.15 ? 'bg-amber-50' : 'bg-emerald-50'}
          border={drift?.global > 0.3 ? 'border-rose-100' : drift?.global > 0.15 ? 'border-amber-100' : 'border-emerald-100'} />
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Zap} label="Jobs réussis" value={`${jobs?.success ?? 0}/${jobs?.total ?? 0}`}
          sub={jobs?.last_success ? `Dernier: ${fmt(jobs.last_success.end_time)}` : 'Aucun'}
          color="text-emerald-600" bg="bg-emerald-50" border="border-emerald-100" />
        <StatCard icon={CheckCircle2} label="Approuvés" value={num(summary?.approved_evidence)}
          sub={`${pct(summary?.approved_evidence / Math.max(summary?.total_evidence, 1) * 100, 0)} du dataset`}
          color="text-emerald-600" bg="bg-emerald-50" border="border-emerald-100" />
        <StatCard icon={XCircle} label="Rejetés" value={num(summary?.rejected_evidence)}
          sub={`Taux: ${pct(summary?.rejected_evidence / Math.max(summary?.total_evidence, 1) * 100, 0)}`}
          color="text-rose-600" bg="bg-rose-50" border="border-rose-100" />
        <StatCard icon={llm?.available ? Wifi : WifiOff} label="Statut LLM"
          value={llm?.available ? 'En ligne' : 'Hors ligne'}
          sub={llm?.model ?? 'Non configuré'}
          color={llm?.available ? 'text-emerald-600' : 'text-slate-500'}
          bg={llm?.available ? 'bg-emerald-50' : 'bg-slate-50'}
          border={llm?.available ? 'border-emerald-100' : 'border-slate-200'} />
      </div>

      {/* Health + Quality overview */}
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm flex flex-col items-center gap-3">
          <p className="text-sm font-bold text-slate-900 self-start">Santé IA globale</p>
          <HealthRing score={health?.score ?? 0} label={health?.label ?? '—'} />
          {health?.issues?.length > 0 && (
            <div className="w-full space-y-1">
              {health.issues.map((issue, i) => (
                <div key={i} className="flex items-start gap-2 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" /> {issue}
                </div>
              ))}
            </div>
          )}
          {health?.issues?.length === 0 && (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-50 px-3 py-2 text-xs text-emerald-700 w-full">
              <CheckCircle2 size={12} /> Aucun problème détecté
            </div>
          )}
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-900 mb-4">Dataset Quality</p>
          <div className="space-y-3">
            {[
              { label: 'Couverture règles', value: summary?.rules_covered, max: summary?.total_rules, color: 'bg-sky-500' },
              { label: 'Données approuvées', value: summary?.approved_evidence, max: summary?.total_evidence, color: 'bg-emerald-500' },
              { label: 'Données rejetées', value: summary?.rejected_evidence, max: summary?.total_evidence, color: 'bg-rose-500' },
              { label: 'Qualité moy.', value: summary?.avg_confidence, max: 100, color: 'bg-violet-500' },
            ].map(row => (
              <div key={row.label}>
                <div className="flex justify-between mb-1">
                  <span className="text-xs text-slate-500">{row.label}</span>
                  <span className="text-xs font-semibold text-slate-700">
                    {row.max ? `${num(row.value)}/${num(row.max)}` : pct(row.value)}
                  </span>
                </div>
                <ProgressBar value={row.value} max={row.max ?? 100} color={row.color} />
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-900 mb-4">Drift par Standard</p>
          <div className="space-y-3">
            {Object.entries(drift?.by_standard ?? {}).map(([std, d]) => {
              const dPct = d?.drift_score != null ? Math.round(d.drift_score * 100) : null;
              const status = d?.status ?? 'unknown';
              return (
                <div key={std}>
                  <div className="flex justify-between mb-1">
                    <span className="text-xs font-semibold text-slate-700">{std}</span>
                    <span className={`text-xs font-bold ${status === 'critical' ? 'text-rose-600' : status === 'warning' ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {dPct != null ? pct(dPct, 0) : '—'} — {status}
                    </span>
                  </div>
                  <ProgressBar
                    value={dPct ?? 0} max={100}
                    color={status === 'critical' ? 'bg-rose-500' : status === 'warning' ? 'bg-amber-500' : 'bg-emerald-500'}
                  />
                </div>
              );
            })}
            {Object.keys(drift?.by_standard ?? {}).length === 0 && (
              <p className="text-xs text-slate-400">Aucune donnée de drift disponible.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 2 — AI HEALTH
══════════════════════════════════════════════════════════════════ */
function HealthTab({ data, loading, mlopsData, mlopsLoading }) {
  if (loading || mlopsLoading) return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[...Array(6)].map((_, i) => <Skeleton key={i} />)}
    </div>
  );

  const { faiss, llm, health, summary } = data || {};
  const jenkinsInfo = mlopsData?.jenkins ?? {};
  const jobs = mlopsData?.summary ?? {};

  const healthItems = [
    { label: 'Model Health', value: health?.score >= 75 ? 'Bon' : health?.score >= 50 ? 'Dégradé' : 'Critique', icon: Brain, ok: health?.score >= 75, detail: `Score: ${health?.score ?? 0}/100` },
    { label: 'Dataset Health', value: summary?.duplication_rate < 5 ? 'Bon' : 'Avertissement', icon: Database, ok: summary?.duplication_rate < 5, detail: `Duplication: ${summary?.duplication_rate ?? 0}%` },
    { label: 'Embedding Health', value: faiss?.index_built ? 'Indexé' : 'Non indexé', icon: Layers, ok: faiss?.index_built, detail: faiss?.embedding_model ?? '—' },
    { label: 'FAISS Index', value: faiss?.index_built ? 'Opérationnel' : 'Non construit', icon: Target, ok: faiss?.index_built, detail: `${num(faiss?.vector_count)} vecteurs` },
    { label: 'LLM / Ollama', value: llm?.available ? 'En ligne' : 'Hors ligne', icon: llm?.available ? Wifi : WifiOff, ok: llm?.available, detail: llm?.model ?? 'Non configuré' },
    { label: 'Jenkins Pipeline', value: jenkinsInfo?.connected ? 'Connecté' : jenkinsInfo?.status ?? 'Non configuré', icon: GitBranch, ok: jenkinsInfo?.connected, detail: jenkinsInfo?.message ?? '—' },
  ];

  return (
    <div className="space-y-6">
      {/* Health cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {healthItems.map(item => (
          <motion.div
            key={item.label}
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            className={`rounded-2xl border p-5 ${item.ok ? 'border-emerald-100 bg-emerald-50' : 'border-rose-100 bg-rose-50'}`}
          >
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <div className={`flex h-8 w-8 items-center justify-center rounded-xl ${item.ok ? 'bg-emerald-100' : 'bg-rose-100'}`}>
                  <item.icon size={15} className={item.ok ? 'text-emerald-600' : 'text-rose-600'} />
                </div>
                <p className="text-sm font-semibold text-slate-800">{item.label}</p>
              </div>
              {item.ok
                ? <CheckCircle2 size={16} className="text-emerald-500" />
                : <XCircle size={16} className="text-rose-500" />}
            </div>
            <p className={`text-lg font-bold ${item.ok ? 'text-emerald-700' : 'text-rose-700'}`}>{item.value}</p>
            <p className="text-xs text-slate-500 mt-1">{item.detail}</p>
          </motion.div>
        ))}
      </div>

      {/* Metrics détaillées */}
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-900 mb-4">FAISS / Embedding Details</p>
          <div className="space-y-2 text-sm">
            {[
              ['Modèle d\'embedding', faiss?.embedding_model ?? '—'],
              ['Vecteurs indexés', num(faiss?.vector_count)],
              ['Dimension', faiss?.vector_dim ?? '—'],
              ['Dernier indexage', fmt(faiss?.last_indexed)],
              ['Index construit', faiss?.index_built ? '✓ Oui' : '✗ Non'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 pb-1">
                <span className="text-slate-500">{k}</span>
                <span className="font-semibold text-slate-800 text-right max-w-[200px] truncate">{v}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-900 mb-4">Training Pipeline Stats</p>
          <div className="space-y-2 text-sm">
            {[
              ['Total jobs', num(jobs?.total_jobs)],
              ['Réussis', num(jobs?.success_jobs)],
              ['Échoués', num(jobs?.failed_jobs)],
              ['En cours', num(jobs?.running_jobs)],
              ['Dernier succès', jobs?.last_successful_job ? fmt(jobs.last_successful_job.end_time) : '—'],
              ['Version modèle', jobs?.last_successful_job?.model_version || '—'],
            ].map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-slate-100 pb-1">
                <span className="text-slate-500">{k}</span>
                <span className="font-semibold text-slate-800">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Issues list */}
      {(health?.issues?.length ?? 0) > 0 && (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4">
          <p className="text-sm font-bold text-amber-800 mb-3">⚠ Problèmes détectés</p>
          <div className="space-y-2">
            {health.issues.map((issue, i) => (
              <div key={i} className="flex items-start gap-2 text-sm text-amber-700">
                <AlertTriangle size={14} className="mt-0.5 shrink-0" />
                {issue}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 3 — DRIFT DETECTION
══════════════════════════════════════════════════════════════════ */
function DriftTab() {
  const [range, setRange] = useState('today');
  const [driftData, setDriftData] = useState(null);
  const [compDrift, setCompDrift] = useState({});
  const [loading, setLoading] = useState(true);
  const [standards, setStandards] = useState([]);
  const [selected, setSelected] = useState('');

  const RANGES = [
    { id: 'today', label: 'Aujourd\'hui', weeks: 1 },
    { id: '7d', label: '7 jours', weeks: 2 },
    { id: '30d', label: '30 jours', weeks: 5 },
    { id: '90d', label: '90 jours', weeks: 13 },
  ];

  useEffect(() => {
    api.get('/normes/').then(r => {
      const norms = Array.isArray(r.data) ? r.data : r.data?.results ?? [];
      setStandards(norms.map(n => n.name));
      if (norms.length > 0) setSelected(norms[0].name);
    }).catch(() => {});
  }, []);

  const loadDrift = useCallback(async () => {
    setLoading(true);
    try {
      const weeks = RANGES.find(r => r.id === range)?.weeks ?? 6;
      const [compRes, deptRes] = await Promise.all([
        selected ? api.get(`/ml/drift/?standard=${selected}`).catch(() => null) : Promise.resolve(null),
        api.get(`/compliance/drift/?weeks=${weeks}`).catch(() => null),
      ]);
      if (compRes?.data) setCompDrift(prev => ({ ...prev, [selected]: compRes.data }));
      if (deptRes?.data) setDriftData(deptRes.data);
    } catch(e) { console.error(e); }
    finally { setLoading(false); }
  }, [range, selected]); // eslint-disable-line

  useEffect(() => { loadDrift(); }, [loadDrift]);

  const driftInfo = compDrift[selected];
  const driftPct = driftInfo?.drift_score != null ? Math.round(driftInfo.drift_score * 100) : null;

  return (
    <div className="space-y-5">
      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex gap-1 rounded-2xl border border-slate-200 bg-white p-1">
          {RANGES.map(r => (
            <button key={r.id} onClick={() => setRange(r.id)}
              className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition ${range === r.id ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-50'}`}>
              {r.label}
            </button>
          ))}
        </div>
        <select value={selected} onChange={e => setSelected(e.target.value)}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 outline-none">
          {standards.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
        <button onClick={loadDrift} disabled={loading}
          className="inline-flex items-center gap-1 rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-50">
          <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Actualiser
        </button>
      </div>

      {/* ML Drift (semantic) */}
      {driftInfo && (
        <div className={`rounded-2xl border p-5 ${driftInfo.status === 'critical' ? 'border-rose-200 bg-rose-50' : driftInfo.status === 'warning' ? 'border-amber-200 bg-amber-50' : 'border-emerald-200 bg-emerald-50'}`}>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <p className="text-sm font-bold text-slate-900">Drift sémantique — {selected}</p>
              <p className="text-xs text-slate-500 mt-0.5">Comparaison historique vs récent (TF-IDF cosinus)</p>
            </div>
            <span className={`text-2xl font-bold ${driftInfo.status === 'critical' ? 'text-rose-600' : driftInfo.status === 'warning' ? 'text-amber-600' : 'text-emerald-600'}`}>
              {driftPct != null ? `${driftPct}%` : '—'}
            </span>
          </div>
          <div className="mt-3">
            <ProgressBar value={driftPct ?? 0} max={100}
              color={driftInfo.status === 'critical' ? 'bg-rose-500' : driftInfo.status === 'warning' ? 'bg-amber-500' : 'bg-emerald-500'}
              h="h-3" />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-3 text-xs">
            {[
              ['Échantillons total', num(driftInfo.total_samples)],
              ['Historiques', num(driftInfo.historical_count)],
              ['Récents', num(driftInfo.recent_count)],
              ['Similarité cosinus', driftInfo.cosine_similarity != null ? driftInfo.cosine_similarity.toFixed(4) : '—'],
              ['Statut', driftInfo.status ?? '—'],
              ['Calculé le', fmt(driftInfo.computed_at)],
            ].map(([k, v]) => (
              <div key={k} className="rounded-xl bg-white/70 px-3 py-2">
                <p className="text-slate-400">{k}</p>
                <p className="font-semibold text-slate-800 mt-0.5">{v}</p>
              </div>
            ))}
          </div>
          {driftInfo.historical_distribution && driftInfo.recent_distribution && (
            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              {[['Historique', driftInfo.historical_distribution], ['Récent', driftInfo.recent_distribution]].map(([name, dist]) => (
                <div key={name} className="rounded-xl bg-white/70 px-3 py-2">
                  <p className="text-xs font-semibold text-slate-600 mb-1">{name}</p>
                  <div className="flex gap-3 text-xs">
                    <span className="text-emerald-600">✓ {dist.approved_pct}%</span>
                    <span className="text-rose-600">✗ {dist.rejected_pct}%</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Compliance drift by dept */}
      {loading ? <Skeleton h="h-40" /> : driftData && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <p className="text-sm font-bold text-slate-900 mb-4">Drift de conformité par département</p>
          {(driftData.alerts ?? []).length > 0 && (
            <div className="mb-4 space-y-2">
              {driftData.alerts.map((a, i) => (
                <div key={i} className={`flex items-start gap-2 rounded-xl border px-3 py-2 text-xs ${a.severity === 'critical' ? 'border-rose-200 bg-rose-50 text-rose-700' : 'border-amber-200 bg-amber-50 text-amber-700'}`}>
                  <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                  <span>{a.dept} — {a.message}</span>
                  {a.current_rate != null && <span className="ml-auto font-bold">{a.current_rate}%</span>}
                </div>
              ))}
            </div>
          )}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {(driftData.departments ?? []).map(dept => {
              const rates = (dept.weekly ?? []).map(w => w.rate).filter(r => r != null);
              const latest = rates[rates.length - 1] ?? 0;
              return (
                <div key={dept.dept} className="rounded-xl border border-slate-100 p-3">
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-bold text-slate-800">{dept.dept}</p>
                    <span className={`text-xs font-semibold ${dept.trend === 'declining' ? 'text-rose-600' : dept.trend === 'improving' ? 'text-emerald-600' : 'text-slate-500'}`}>
                      {dept.trend === 'declining' ? '↓' : dept.trend === 'improving' ? '↑' : '→'} {dept.trend}
                    </span>
                  </div>
                  <div className="flex items-end gap-1 h-12">
                    {rates.map((r, i) => (
                      <div key={i} className="flex-1 relative" title={`${r}%`}>
                        <div className={`absolute bottom-0 w-full rounded-sm ${r >= 70 ? 'bg-emerald-500' : r >= 40 ? 'bg-amber-400' : 'bg-rose-500'}`}
                          style={{ height: `${Math.max(4, r)}%` }} />
                      </div>
                    ))}
                  </div>
                  <div className="flex justify-between mt-1">
                    <span className="text-[10px] text-slate-400">Latest: {latest}%</span>
                    <span className={`text-[10px] font-bold ${dept.trend_delta > 0 ? 'text-emerald-600' : dept.trend_delta < 0 ? 'text-rose-600' : 'text-slate-400'}`}>
                      {dept.trend_delta > 0 ? '+' : ''}{dept.trend_delta}%
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
          {(driftData.departments ?? []).length === 0 && (
            <p className="text-sm text-slate-400 text-center py-8">Aucune donnée de département disponible.</p>
          )}
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 4 — EXPLAINABLE AI
══════════════════════════════════════════════════════════════════ */
function ExplainableTab({ data, loading }) {
  const [selectedModel, setSelectedModel] = useState(null);

  const models = (data?.models ?? []).filter(m => !m.error && m.feature_importance?.length > 0);

  useEffect(() => {
    if (models.length > 0 && !selectedModel) setSelectedModel(models[0]);
  }, [models]); // eslint-disable-line

  if (loading) return <div className="grid gap-4 sm:grid-cols-2">{[...Array(4)].map((_, i) => <Skeleton key={i} />)}</div>;
  if (!data) return <p className="text-sm text-slate-400">No data.</p>;

  const currentModel = selectedModel;
  const features = currentModel?.feature_importance ?? [];
  const maxImp = Math.max(...features.map(f => f[1] ?? f.importance ?? 0), 0.001);

  return (
    <div className="space-y-5">
      {/* Model selector */}
      <div className="flex flex-wrap gap-2">
        {(data.models ?? []).map(m => (
          <button key={`${m.standard}-${m.name}`}
            onClick={() => setSelectedModel(m)}
            className={`rounded-xl px-3 py-2 text-xs font-semibold transition border ${
              selectedModel?.name === m.name && selectedModel?.standard === m.standard
                ? 'bg-slate-900 text-white border-transparent'
                : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'
            }`}>
            {m.name} <span className="opacity-60 ml-1">{m.standard}</span>
            {m.error && <span className="ml-1 text-rose-400">⚠</span>}
          </button>
        ))}
      </div>

      {currentModel && (
        <div className="grid gap-4 lg:grid-cols-2">
          {/* Feature importance */}
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-bold text-slate-900 mb-4">
              Feature Importance — {currentModel.name}
              <span className="text-xs font-normal text-slate-400 ml-2">{currentModel.standard}</span>
            </p>
            {features.length > 0 ? (
              <div className="space-y-2">
                {features.slice(0, 15).map((f, i) => {
                  const name = Array.isArray(f) ? f[0] : f.feature || f.name || `Feature ${i}`;
                  const imp = Array.isArray(f) ? f[1] : f.importance ?? 0;
                  const pctVal = Math.round((imp / maxImp) * 100);
                  return (
                    <div key={name} className="flex items-center gap-2">
                      <span className="w-4 text-[10px] text-slate-400 text-right">{i + 1}</span>
                      <span className="w-36 truncate text-xs font-medium text-slate-700">{name.replace(/_/g, ' ')}</span>
                      <div className="flex-1">
                        <ProgressBar value={pctVal} max={100}
                          color={i < 3 ? 'bg-violet-500' : i < 6 ? 'bg-sky-500' : 'bg-slate-300'} h="h-2.5" />
                      </div>
                      <span className="w-10 text-right text-xs font-semibold text-slate-600">
                        {typeof imp === 'number' ? imp.toFixed(3) : imp}
                      </span>
                    </div>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-slate-200 py-8 text-center">
                <p className="text-xs text-slate-400">Aucune feature importance disponible pour ce modèle.</p>
                <p className="text-xs text-slate-400 mt-1">Entraîner RandomForest ou GradientBoosting pour obtenir ces données.</p>
              </div>
            )}
          </div>

          {/* Model metrics */}
          <div className="space-y-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-bold text-slate-900 mb-4">Métriques du modèle</p>
              <div className="grid gap-3 grid-cols-2">
                {[
                  { label: 'Accuracy', value: currentModel.accuracy, color: 'text-sky-700', bg: 'bg-sky-50' },
                  { label: 'F1 Score', value: currentModel.f1_score, color: 'text-violet-700', bg: 'bg-violet-50' },
                  { label: 'Precision', value: currentModel.precision, color: 'text-emerald-700', bg: 'bg-emerald-50' },
                  { label: 'Recall', value: currentModel.recall, color: 'text-amber-700', bg: 'bg-amber-50' },
                ].map(m => (
                  <div key={m.label} className={`rounded-xl ${m.bg} p-3`}>
                    <p className="text-xs text-slate-500">{m.label}</p>
                    <p className={`text-2xl font-bold ${m.color}`}>
                      {m.value != null ? pct(m.value * 100, 1) : '—'}
                    </p>
                    {m.value != null && (
                      <ProgressBar value={m.value * 100} max={100}
                        color={m.value >= 0.8 ? 'bg-emerald-500' : m.value >= 0.6 ? 'bg-amber-500' : 'bg-rose-500'}
                        h="h-1.5" />
                    )}
                  </div>
                ))}
              </div>
              <div className="mt-3 space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-400">Training time</span>
                  <span className="font-medium">{currentModel.training_time != null ? `${currentModel.training_time.toFixed(2)}s` : '—'}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Samples</span>
                  <span className="font-medium">{num(currentModel.sample_count)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-400">Dernière formation</span>
                  <span className="font-medium">{fmt(currentModel.trained_at)}</span>
                </div>
                {currentModel.error && (
                  <div className="flex items-start gap-1 text-rose-600 mt-2">
                    <AlertTriangle size={12} className="mt-0.5" />
                    <span>{currentModel.error}</span>
                  </div>
                )}
              </div>
            </div>

            {/* Confusion matrix */}
            {currentModel.confusion_matrix && (
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-sm font-bold text-slate-900 mb-3">Matrice de confusion</p>
                <div className="overflow-x-auto">
                  <table className="text-xs text-center w-full">
                    <thead>
                      <tr>
                        <th className="text-slate-400 px-2 py-1">Prédit ↓ / Réel →</th>
                        <th className="bg-emerald-50 text-emerald-700 px-3 py-1 rounded-tl">Approuvé</th>
                        <th className="bg-rose-50 text-rose-700 px-3 py-1 rounded-tr">Rejeté</th>
                      </tr>
                    </thead>
                    <tbody>
                      {currentModel.confusion_matrix.map((row, i) => (
                        <tr key={i}>
                          <td className={`${i === 0 ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'} px-2 py-1 font-semibold`}>
                            {i === 0 ? 'Approuvé' : 'Rejeté'}
                          </td>
                          {row.map((cell, j) => (
                            <td key={j} className={`px-3 py-2 font-bold ${i === j ? 'bg-slate-100 text-slate-900' : 'text-rose-600'}`}>{cell}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
      {(data?.models ?? []).length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-200 py-16 text-center">
          <Brain size={32} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm font-semibold text-slate-500">Aucun modèle entraîné</p>
          <p className="text-xs text-slate-400 mt-1">Allez dans le ML Dashboard pour entraîner des modèles.</p>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 5 — DATASET QUALITY
══════════════════════════════════════════════════════════════════ */
function DatasetQualityTab() {
  const [data, setData] = useState(null);
  const [dupData, setDupData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [norm, setNorm] = useState('');
  const [norms, setNorms] = useState([]);

  useEffect(() => {
    api.get('/normes/').then(r => {
      const arr = Array.isArray(r.data) ? r.data : r.data?.results ?? [];
      setNorms(arr);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    setLoading(true);
    const params = norm ? `?norm_name=${norm}` : '';
    Promise.all([
      api.get(`/dataset/quality-report/${params}`).catch(() => null),
      api.get(`/evidence/duplicates/`).catch(() => null),
    ]).then(([q, dup]) => {
      setData(q?.data ?? null);
      setDupData(dup?.data ?? null);
    }).finally(() => setLoading(false));
  }, [norm]);

  const ev = data?.evidence ?? {};
  const cl = data?.classification ?? {}; // eslint-disable-line no-unused-vars
  const cov = data?.coverage ?? {};
  const quality = data?.quality ?? {};

  const qualityScore = Math.round(
    0.3 * (cov.coverage_pct ?? 0) +
    0.3 * (100 - (ev.duplication_rate ?? 0)) +
    0.2 * (quality.class_balance != null ? quality.class_balance * 100 : 0) +
    0.2 * (quality.completeness ?? 0)
  );

  const recommendations = [];
  if ((ev.duplication_rate ?? 0) > 5) recommendations.push({ label: 'Doublons élevés', severity: 'high', msg: `${ev.duplication_rate}% de doublons — nettoyer le dataset` });
  if ((cov.coverage_pct ?? 0) < 80) recommendations.push({ label: 'Couverture faible', severity: 'medium', msg: `${cov.coverage_pct}% — ajouter des preuves pour les règles manquantes` });
  if (quality.class_balance != null && quality.class_balance < 0.25) recommendations.push({ label: 'Déséquilibre de classes', severity: 'high', msg: 'Ratio approuvé/rejeté déséquilibré — augmenter la classe minoritaire' });
  if ((ev.avg_evidence_length ?? 0) < 10) recommendations.push({ label: 'Preuves trop courtes', severity: 'medium', msg: `Longueur moy: ${ev.avg_evidence_length} mots — ajouter des preuves plus détaillées` });

  return (
    <div className="space-y-5">
      <div className="flex items-center gap-2">
        <select value={norm} onChange={e => setNorm(e.target.value)}
          className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 outline-none">
          <option value="">Toutes les normes</option>
          {norms.map(n => <option key={n.id} value={n.name}>{n.name}</option>)}
        </select>
      </div>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-3">{[...Array(6)].map((_, i) => <Skeleton key={i} />)}</div>
      ) : (
        <>
          {/* Score quality */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm col-span-full lg:col-span-1 flex flex-col items-center justify-center">
              <HealthRing score={qualityScore} label="Score Qualité" />
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:col-span-3">
              <p className="text-xs font-bold text-slate-900 mb-3">Dimensions de qualité</p>
              <div className="space-y-2">
                {[
                  { label: 'Couverture règles', value: cov.coverage_pct ?? 0, color: 'bg-sky-500' },
                  { label: 'Absence de doublons', value: 100 - (ev.duplication_rate ?? 0), color: 'bg-emerald-500' },
                  { label: 'Équilibre des classes', value: (quality.class_balance ?? 0) * 100, color: 'bg-violet-500' },
                  { label: 'Complétude', value: quality.completeness ?? 0, color: 'bg-amber-500' },
                ].map(d => (
                  <div key={d.label}>
                    <div className="flex justify-between mb-1">
                      <span className="text-xs text-slate-500">{d.label}</span>
                      <span className="text-xs font-bold text-slate-700">{pct(d.value, 1)}</span>
                    </div>
                    <ProgressBar value={d.value} max={100} color={d.color} />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Stats grid */}
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { label: 'Total evidence', value: num(ev.total), color: 'text-slate-900', bg: 'bg-slate-50' },
              { label: 'Approuvés', value: num(ev.approved), color: 'text-emerald-700', bg: 'bg-emerald-50' },
              { label: 'Rejetés', value: num(ev.rejected), color: 'text-rose-700', bg: 'bg-rose-50' },
              { label: 'Doublons', value: num(ev.duplicates), color: ev.duplicates > 0 ? 'text-amber-700' : 'text-emerald-700', bg: ev.duplicates > 0 ? 'bg-amber-50' : 'bg-emerald-50' },
              { label: 'Vocabulaire', value: num(ev.vocabulary_size), color: 'text-violet-700', bg: 'bg-violet-50' },
              { label: 'Règles couvertes', value: `${cov.rules_with_evidence ?? 0}/${cov.total_rules ?? 0}`, color: 'text-sky-700', bg: 'bg-sky-50' },
            ].map(k => (
              <div key={k.label} className={`rounded-2xl border border-slate-100 ${k.bg} p-3`}>
                <p className="text-xs text-slate-500">{k.label}</p>
                <p className={`text-xl font-bold ${k.color} mt-0.5`}>{k.value}</p>
              </div>
            ))}
          </div>

          {/* Duplicates */}
          {dupData && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <p className="text-sm font-bold text-slate-900 mb-3">Analyse des doublons</p>
              <div className="grid gap-3 sm:grid-cols-4 mb-4">
                {[
                  { label: 'Total', value: dupData.total, color: 'text-slate-700' },
                  { label: 'Uniques', value: dupData.unique, color: 'text-emerald-700' },
                  { label: 'Doublons', value: dupData.duplicates, color: dupData.duplicates > 0 ? 'text-rose-700' : 'text-emerald-700' },
                  { label: 'Taux', value: `${dupData.duplication_rate}%`, color: dupData.duplication_rate > 10 ? 'text-rose-700' : 'text-emerald-700' },
                ].map(s => (
                  <div key={s.label} className="rounded-xl bg-slate-50 p-3">
                    <p className="text-xs text-slate-400">{s.label}</p>
                    <p className={`text-2xl font-bold ${s.color}`}>{s.value}</p>
                  </div>
                ))}
              </div>
              <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${
                dupData.status === 'clean' ? 'bg-emerald-100 text-emerald-700'
                : dupData.status === 'warning' ? 'bg-amber-100 text-amber-700'
                : 'bg-rose-100 text-rose-700'
              }`}>
                {dupData.status === 'clean' ? '✓ Dataset propre' : dupData.status === 'warning' ? '⚠ Doublons mineurs' : '✗ Duplication élevée'}
              </span>
            </div>
          )}

          {/* Recommendations */}
          {recommendations.length > 0 && (
            <div className="rounded-2xl border border-violet-200 bg-violet-50 p-5">
              <p className="text-sm font-bold text-violet-800 mb-3">💡 Recommandations automatiques</p>
              <div className="space-y-2">
                {recommendations.map((r, i) => (
                  <div key={i} className={`flex items-start gap-2 rounded-xl px-3 py-2 text-xs ${r.severity === 'high' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>
                    <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                    <span><strong>{r.label}:</strong> {r.msg}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 6 — AI RECOMMENDATIONS
══════════════════════════════════════════════════════════════════ */
function RecommendationsTab({ data, loading }) {
  const [teamRecs, setTeamRecs] = useState(null);
  const [teamLoading, setTeamLoading] = useState(true);

  useEffect(() => {
    api.get('/teamlead/recommendations/').then(r => setTeamRecs(r.data)).catch(() => {})
      .finally(() => setTeamLoading(false));
  }, []);

  if (loading || teamLoading) return (
    <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} h="h-16" />)}</div>
  );

  const aiRecs = data?.recommendations ?? [];
  const tlRecs = teamRecs?.recommendations ?? [];

  const PRIORITY_STYLE = {
    high:   { border: 'border-rose-200 bg-rose-50', badge: 'bg-rose-100 text-rose-700', icon: 'text-rose-500' },
    medium: { border: 'border-amber-200 bg-amber-50', badge: 'bg-amber-100 text-amber-700', icon: 'text-amber-500' },
    low:    { border: 'border-slate-200 bg-slate-50', badge: 'bg-slate-100 text-slate-600', icon: 'text-slate-400' },
  };

  const ACTION_LABELS = {
    deduplicate: 'Nettoyer les doublons → Evidence Intelligence',
    retrain: 'Relancer l\'entraînement → ML Dashboard',
    balance: 'Ajouter des exemples → Evidence Intelligence',
    start_llm: 'Démarrer Ollama',
    add_evidence: 'Ajouter des preuves → Evidence Intelligence',
    build_index: 'Construire l\'index → Evidence Intelligence',
    train: 'Lancer un entraînement → ML Dashboard',
  };

  return (
    <div className="space-y-6">
      {/* AI-generated recommendations */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-100">
            <Sparkles size={14} className="text-violet-600" />
          </div>
          <p className="text-sm font-bold text-slate-900">Recommandations IA</p>
          <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
            {aiRecs.length} recommandation{aiRecs.length !== 1 ? 's' : ''}
          </span>
        </div>
        {aiRecs.length === 0 ? (
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-700 flex items-center gap-2">
            <CheckCircle2 size={16} /> Aucune recommandation critique — votre système IA est en bonne santé.
          </div>
        ) : (
          <div className="space-y-3">
            {aiRecs.map((r, i) => {
              const style = PRIORITY_STYLE[r.priority] ?? PRIORITY_STYLE.low;
              return (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.05 }}
                  className={`rounded-2xl border ${style.border} px-4 py-4`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3 min-w-0">
                      <AlertTriangle size={16} className={`${style.icon} mt-0.5 shrink-0`} />
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-900">{r.title}</p>
                        <p className="text-xs text-slate-600 mt-0.5">{r.message}</p>
                        {r.action && ACTION_LABELS[r.action] && (
                          <p className="text-xs font-medium text-violet-600 mt-1">→ {ACTION_LABELS[r.action]}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col items-end gap-1 shrink-0">
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${style.badge}`}>{r.priority}</span>
                      <span className="text-[10px] text-slate-400 bg-white rounded-full px-2 py-0.5">{r.type}</span>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* TeamLead recommendations */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-sky-100">
            <Target size={14} className="text-sky-600" />
          </div>
          <p className="text-sm font-bold text-slate-900">Recommandations TeamLead</p>
        </div>
        {tlRecs.length === 0 ? (
          <p className="text-sm text-slate-400">Aucune recommandation TeamLead disponible.</p>
        ) : (
          <div className="space-y-3">
            {tlRecs.map((r, i) => {
              const style = PRIORITY_STYLE[r.priority] ?? PRIORITY_STYLE.low;
              return (
                <div key={i} className={`rounded-2xl border ${style.border} px-4 py-4`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900">{r.rule_title || r.title || 'Règle'}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{r.recommendation || r.message || ''}</p>
                      {r.approval_rate != null && (
                        <div className="mt-2">
                          <div className="flex justify-between text-xs mb-1">
                            <span className="text-slate-400">Taux d'approbation</span>
                            <span className="font-semibold">{r.approval_rate}%</span>
                          </div>
                          <ProgressBar value={r.approval_rate} max={100}
                            color={r.approval_rate >= 70 ? 'bg-emerald-500' : r.approval_rate >= 40 ? 'bg-amber-500' : 'bg-rose-500'} />
                        </div>
                      )}
                    </div>
                    {r.priority && (
                      <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase shrink-0 ${style.badge}`}>{r.priority}</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 7 — MODEL COMPARISON
══════════════════════════════════════════════════════════════════ */
function ComparisonTab({ data, loading }) {
  const [triggerLoading, setTriggerLoading] = useState({});
  const [triggerResult, setTriggerResult] = useState({});

  const handleTrigger = async (standard) => {
    setTriggerLoading(p => ({ ...p, [standard]: true }));
    try {
      // Try Jenkins pipeline first
      const r = await api.post('/ml/trigger-training/', { standard, force: true });
      setTriggerResult(p => ({ ...p, [standard]: r.data }));
    } catch (e) {
      const data = e?.response?.data;
      const status = e?.response?.status;
      // 503 = Jenkins not configured → fallback to local training
      if (status === 503 || (data && !data.triggered)) {
        try {
          const localR = await api.post('/ml/train/', { standard, norm_name: standard });
          setTriggerResult(p => ({
            ...p,
            [standard]: {
              triggered: true,
              reason: 'Local training started (Jenkins not configured)',
              local: true,
              ...localR.data,
            },
          }));
        } catch (localErr) {
          const localMsg = localErr?.response?.data?.error || localErr?.message || 'Local training failed';
          setTriggerResult(p => ({ ...p, [standard]: { error: localMsg } }));
        }
      } else {
        const msg = data?.reason || data?.error || data?.message || 'Trigger failed';
        setTriggerResult(p => ({ ...p, [standard]: { error: msg } }));
      }
    } finally {
      setTriggerLoading(p => ({ ...p, [standard]: false }));
    }
  };

  if (loading) return (
    <div className="space-y-3">{[...Array(4)].map((_, i) => <Skeleton key={i} h="h-20" />)}</div>
  );
  if (!data) return <p className="text-sm text-slate-400">No data.</p>;

  const models = data.models ?? [];
  const configs = data.mlops_configs ?? [];

  // Group models by algorithm
  const algos = ['RandomForest', 'LogisticRegression', 'GradientBoosting', 'BiLSTM'];
  const standards = [...new Set(models.map(m => m.standard))];

  const METRICS = [
    { key: 'accuracy', label: 'Accuracy' },
    { key: 'f1_score', label: 'F1' },
    { key: 'precision', label: 'Precision' },
    { key: 'recall', label: 'Recall' },
  ];

  const getModel = (std, algo) => models.find(m => m.standard === std && m.name === algo);

  return (
    <div className="space-y-5">
      {/* MLOps config table */}
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <p className="text-sm font-bold text-slate-900">Configuration MLOps par standard</p>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider">
              <tr>
                {['Standard', 'Dernier entraînement', 'Version modèle', 'F1', 'Drift', 'Samples', 'Runs', 'Action'].map(h => (
                  <th key={h} className="px-4 py-2 text-left font-semibold">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {configs.map(cfg => (
                <tr key={cfg.standard} className="hover:bg-slate-50 transition">
                  <td className="px-4 py-3 font-semibold text-slate-800">{cfg.standard}</td>
                  <td className="px-4 py-3 text-slate-600">{fmt(cfg.last_trained_at)}</td>
                  <td className="px-4 py-3">
                    <span className="rounded-full bg-slate-100 px-2 py-0.5 font-mono text-[10px] text-slate-700">
                      {cfg.current_model_version || '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-bold ${cfg.last_f1_score >= 0.8 ? 'text-emerald-600' : cfg.last_f1_score >= 0.6 ? 'text-amber-600' : 'text-rose-600'}`}>
                      {cfg.last_f1_score ? pct(cfg.last_f1_score * 100, 1) : '—'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`font-medium ${cfg.last_drift_score > 0.3 ? 'text-rose-600' : cfg.last_drift_score > 0.15 ? 'text-amber-600' : 'text-emerald-600'}`}>
                      {cfg.last_drift_score ? pct(cfg.last_drift_score * 100, 1) : '—'}
                    </span>
                  </td>
                  {/* FIX #3/#9: dataset_size and training_count now reliably set */}
                  <td className="px-4 py-3 text-slate-600">{num(cfg.dataset_size)}</td>
                  <td className="px-4 py-3 text-slate-600 text-center">{cfg.training_count ?? '—'}</td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => handleTrigger(cfg.standard)}
                      disabled={triggerLoading[cfg.standard]}
                      className="inline-flex items-center gap-1 rounded-full bg-sky-600 px-3 py-1 text-[10px] font-semibold text-white hover:bg-sky-500 disabled:opacity-50"
                    >
                      <Play size={10} /> {triggerLoading[cfg.standard] ? 'En cours...' : 'Reentrainer'}
                    </button>
                    {triggerResult[cfg.standard] && (
                      <p className={`mt-1 text-[10px] ${
                        triggerResult[cfg.standard].error
                          ? 'text-rose-600'
                          : triggerResult[cfg.standard].triggered
                            ? 'text-emerald-600'
                            : 'text-amber-600'
                      }`}>
                        {triggerResult[cfg.standard].error
                          ? `✗ ${triggerResult[cfg.standard].error}`
                          : triggerResult[cfg.standard].triggered
                            ? `✓ ${triggerResult[cfg.standard].local ? 'Local' : 'Jenkins'} declenche`
                            : `⚠ ${triggerResult[cfg.standard].reason}`}
                      </p>
                    )}
                  </td>
                </tr>
              ))}
              {configs.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-slate-400">Aucune configuration MLOps</td></tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Model comparison matrix */}
      {standards.length > 0 && algos.some(a => models.find(m => m.name === a)) && (
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-100">
            <p className="text-sm font-bold text-slate-900">Comparaison des algorithmes</p>
          </div>
          <div className="overflow-x-auto">
            {standards.map(std => (
              <div key={std} className="p-5 border-b border-slate-100 last:border-b-0">
                <p className="text-xs font-bold text-slate-600 uppercase tracking-wider mb-3">{std}</p>
                <div className="grid gap-3" style={{ gridTemplateColumns: `repeat(${Math.min(algos.length, 4)}, 1fr)` }}>
                  {algos.map(algo => {
                    const m = getModel(std, algo);
                    const isSupect = m && !m.error && (m.accuracy >= 0.99 || m.f1_score >= 0.99);
                    return (
                      <div key={algo} className={`rounded-2xl border p-3 ${m?.is_best ? 'border-violet-300 bg-violet-50' : isSupect ? 'border-amber-300 bg-amber-50' : 'border-slate-100 bg-slate-50'}`}>
                        <div className="flex items-center justify-between mb-2">
                          <p className="text-xs font-bold text-slate-800">{algo}</p>
                          {m?.is_best && !isSupect && <Star size={12} className="text-violet-500 fill-violet-500" />}
                          {isSupect && <span title="Métriques ≥99% — possible leakage" className="text-amber-500 text-[10px]">⚠️</span>}
                        </div>
                        {m && !m.error ? (
                          <div className="space-y-1">
                            {METRICS.map(met => (
                              <div key={met.key}>
                                <div className="flex justify-between text-[10px] mb-0.5">
                                  <span className="text-slate-400">{met.label}</span>
                                  <span className={`font-semibold ${isSupect ? 'text-amber-700' : ''}`}>
                                    {m[met.key] != null ? pct(m[met.key] * 100, 1) : '—'}
                                  </span>
                                </div>
                                <ProgressBar value={(m[met.key] ?? 0) * 100} max={100}
                                  color={isSupect ? 'bg-amber-400' : m[met.key] >= 0.8 ? 'bg-emerald-500' : m[met.key] >= 0.6 ? 'bg-amber-400' : 'bg-rose-400'}
                                  h="h-1" />
                              </div>
                            ))}
                            {/* Anti-leakage validation badges */}
                            <div className="mt-2 flex flex-wrap gap-1">
                              {m.split_strategy && (
                                <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${m.split_strategy === 'grouped' ? 'bg-sky-100 text-sky-700' : 'bg-slate-200 text-slate-600'}`}>
                                  {m.split_strategy}
                                </span>
                              )}
                              {m.overfitting_gap != null && (
                                <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-semibold ${
                                  Math.abs(m.overfitting_gap) >= 0.15 ? 'bg-red-100 text-red-700' :
                                  Math.abs(m.overfitting_gap) >= 0.08 ? 'bg-amber-100 text-amber-700' :
                                  'bg-emerald-100 text-emerald-700'
                                }`}>
                                  ovf: {m.overfitting_gap >= 0 ? '+' : ''}{(m.overfitting_gap * 100).toFixed(1)}%
                                </span>
                              )}
                              {m.train_size != null && m.test_size != null && (
                                <span className="rounded-full bg-slate-200 px-1.5 py-0.5 text-[9px] text-slate-600">
                                  {m.train_size.toLocaleString()}/{m.test_size.toLocaleString()}
                                </span>
                              )}
                            </div>
                          </div>
                        ) : (
                          <p className="text-[10px] text-slate-400">{m?.error || 'Non entraîné'}</p>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 8 — AI TIMELINE
══════════════════════════════════════════════════════════════════ */
function TimelineTab({ data, loading }) {
  if (loading) return <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} h="h-16" />)}</div>;

  const timeline = data?.timeline ?? [];

  const STATUS_COLOR = {
    success: { dot: 'bg-emerald-500', line: 'border-emerald-200', badge: 'bg-emerald-100 text-emerald-700' },
    failed:  { dot: 'bg-rose-500',    line: 'border-rose-200',    badge: 'bg-rose-100 text-rose-700'    },
    running: { dot: 'bg-sky-500 animate-pulse', line: 'border-sky-200', badge: 'bg-sky-100 text-sky-700' },
    pending: { dot: 'bg-amber-400',   line: 'border-amber-200',   badge: 'bg-amber-100 text-amber-700'  },
  };

  return (
    <div className="space-y-4">
      {timeline.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-slate-200 py-16 text-center">
          <Clock size={28} className="mx-auto text-slate-300 mb-3" />
          <p className="text-sm font-semibold text-slate-500">Aucun événement dans la timeline</p>
          <p className="text-xs text-slate-400 mt-1">Les entraînements, drifts et mises à jour apparaîtront ici.</p>
        </div>
      ) : (
        <div className="relative">
          {/* Vertical line */}
          <div className="absolute left-5 top-0 bottom-0 w-px bg-slate-200" />
          <div className="space-y-4">
            {timeline.map((job, i) => {
              const style = STATUS_COLOR[job.status] ?? STATUS_COLOR.pending;
              return (
                <motion.div
                  key={job.id}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.04 }}
                  className="relative flex items-start gap-4 pl-12"
                >
                  {/* Dot */}
                  <div className={`absolute left-3 top-2 h-4 w-4 rounded-full ${style.dot} ring-4 ring-white`} />

                  <div className="flex-1 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition">
                    <div className="flex items-start justify-between gap-2 flex-wrap">
                      <div className="flex items-center gap-2">
                        <span className={`rounded-full px-2 py-0.5 text-[10px] font-bold uppercase ${style.badge}`}>
                          {job.status}
                        </span>
                        <p className="text-sm font-semibold text-slate-900">
                          Entraînement #{job.id} — {job.standard}
                        </p>
                      </div>
                      <p className="text-xs text-slate-400">{fmt(job.start_time)}</p>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
                      {job.f1_score > 0 && <span>F1: <strong>{pct(job.f1_score * 100, 1)}</strong></span>}
                      {job.drift_score > 0 && <span>Drift: <strong>{pct(job.drift_score * 100, 1)}</strong></span>}
                      {job.documents_count > 0 && <span>Samples: <strong>{num(job.documents_count)}</strong></span>}
                      {job.model_version && <span>Version: <strong className="font-mono">{job.model_version}</strong></span>}
                      {job.jenkins_build_id && <span>Jenkins: <strong>{job.jenkins_build_id}</strong></span>}
                      {job.triggered_by && <span>Par: <strong>{job.triggered_by}</strong></span>}
                    </div>
                    {job.end_time && (
                      <p className="mt-1 text-[10px] text-slate-400">Terminé: {fmt(job.end_time)}</p>
                    )}
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════
   TAB 9 — SEMANTIC SEARCH ANALYTICS
══════════════════════════════════════════════════════════════════ */
function SemanticTab({ data, loading }) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResult, setSearchResult] = useState(null);
  const [searching, setSearching] = useState(false);
  const [standard, setStandard] = useState('');
  const standards = data?.summary?.available_standards ?? [];

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setSearching(true);
    try {
      const r = await api.post('/compliance/chat/', { question: searchQuery, standard, top_k: 8 });
      setSearchResult(r.data);
    } catch (err) {
      setSearchResult({ error: err?.response?.data?.error || 'Erreur' });
    } finally { setSearching(false); }
  };

  const faiss = data?.faiss ?? {};

  return (
    <div className="space-y-5">
      {/* FAISS stats */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? [...Array(4)].map((_, i) => <Skeleton key={i} />) : [
          { label: 'Vecteurs indexés', value: num(faiss.vector_count), icon: Database, color: 'text-sky-600', bg: 'bg-sky-50', border: 'border-sky-100' },
          { label: 'Dimension', value: faiss.vector_dim ?? '—', icon: Layers, color: 'text-violet-600', bg: 'bg-violet-50', border: 'border-violet-100' },
          { label: 'Modèle', value: faiss.embedding_model ?? '—', icon: Brain, color: 'text-slate-600', bg: 'bg-slate-50', border: 'border-slate-200' },
          { label: 'Dernier indexage', value: faiss.last_indexed ? new Date(faiss.last_indexed).toLocaleDateString('fr-FR') : '—', icon: Clock, color: 'text-amber-600', bg: 'bg-amber-50', border: 'border-amber-100' },
        ].map(s => <StatCard key={s.label} {...s} />)}
      </div>

      {/* Semantic search test */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <p className="text-sm font-bold text-slate-900 mb-3">Test de recherche sémantique</p>
        <form onSubmit={handleSearch} className="flex gap-2 mb-4">
          <select value={standard} onChange={e => setStandard(e.target.value)}
            className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs outline-none">
            <option value="">Tous standards</option>
            {standards.map(s => <option key={s} value={s}>{s}</option>)}
          </select>
          <input value={searchQuery} onChange={e => setSearchQuery(e.target.value)}
            placeholder="Rechercher dans la base de connaissances…"
            className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm outline-none focus:border-sky-400" />
          <button type="submit" disabled={searching || !searchQuery.trim()}
            className="rounded-xl bg-sky-600 px-4 py-2 text-sm font-semibold text-white hover:bg-sky-500 disabled:opacity-50">
            {searching ? '…' : <Search size={16} />}
          </button>
        </form>

        {searchResult && !searchResult.error && (
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <p className="text-xs font-semibold text-slate-700">{searchResult.source_count} résultats trouvés</p>
              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${searchResult.llm_used ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-600'}`}>
                {searchResult.model}
              </span>
            </div>
            {(searchResult.sources ?? []).slice(0, 5).map((src, i) => (
              <div key={i} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
                <div className="flex items-start justify-between gap-2">
                  <p className="text-xs font-semibold text-slate-800">{src.rule || '—'}</p>
                  <div className="flex gap-1 shrink-0">
                    <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${src.decision === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                      {src.decision}
                    </span>
                    {src.score != null && (
                      <span className="rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-semibold text-sky-700">{src.score}%</span>
                    )}
                  </div>
                </div>
                <p className="text-xs text-slate-600 mt-1 line-clamp-2">{src.evidence || src.evidence_text || '—'}</p>
              </div>
            ))}
          </div>
        )}
        {searchResult?.error && (
          <p className="text-sm text-rose-600">{searchResult.error}</p>
        )}
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   TAB 10 — AI ASSISTANT (RAG Chat)
══════════════════════════════════════════════════════════════════ */

const SUGGESTIONS = [
  'Pourquoi ce document est-il rejeté ?',
  'Montre les règles ISO 27001 les plus fréquentes.',
  'Compare ISO 9001 et TISAX.',
  'Quels documents présentent un risque élevé ?',
  'Explique la règle d\'identification du document.',
  'Comment améliorer le score de conformité ?',
];

function AssistantTab({ llmAvailable, standards }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [standard, setStandard] = useState('');
  const [history, setHistory] = useState(() => {
    try { return JSON.parse(localStorage.getItem('ai_chat_history') || '[]'); } catch { return []; }
  });
  const [showHistory, setShowHistory] = useState(false);
  const [streaming, setStreaming] = useState(false); // eslint-disable-line no-unused-vars
  const [streamStatus, setStreamStatus] = useState('');
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamStatus]);

  const saveToHistory = (q, a) => {
    const entry = { id: Date.now(), question: q, answer: a, timestamp: new Date().toISOString(), standard };
    const next = [entry, ...history].slice(0, 30);
    setHistory(next);
    localStorage.setItem('ai_chat_history', JSON.stringify(next));
  };

  const handleSend = async (question) => {
    const q = (question || input).trim();
    if (!q) return;
    setInput('');
    setStreamStatus('Thinking...');
    setLoading(true);

    const userMsg = { role: 'user', content: q, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);

    try {
      setStreamStatus('Searching knowledge...');
      await new Promise(r => setTimeout(r, 300));
      setStreamStatus('Generating answer...');

      const r = await api.post('/compliance/chat/', { question: q, standard, top_k: 7 });
      const answer = r.data?.answer || r.data?.response || JSON.stringify(r.data);
      const sources = r.data?.sources ?? [];
      const model = r.data?.model;
      const confidence = r.data?.confidence;

      const aiMsg = {
        role: 'ai',
        content: answer,
        sources,
        model,
        confidence,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, aiMsg]);
      saveToHistory(q, answer);
    } catch (err) {
      const errMsg = {
        role: 'ai',
        content: 'Erreur: ' + (err?.response?.data?.error || err.message),
        error: true,
        timestamp: new Date().toISOString(),
      };
      setMessages(prev => [...prev, errMsg]);
    } finally {
      setLoading(false);
      setStreamStatus('');
    }
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem('ai_chat_history');
  };

  const exportChat = (format) => {
    const data = format === 'json'
      ? JSON.stringify(messages, null, 2)
      : messages.map(m => `[${m.role.toUpperCase()}] ${m.content}`).join('\n\n');
    const blob = new Blob([data], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url;
    a.download = `chat_export.${format}`; a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-[calc(100vh-320px)] min-h-[500px] gap-4">
      {/* History sidebar */}
      <AnimatePresence>
        {showHistory && (
          <motion.div
            initial={{ width: 0, opacity: 0 }} animate={{ width: 280, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            className="shrink-0 rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden"
          >
            <div className="flex items-center justify-between px-4 py-3 border-b border-slate-100">
              <p className="text-xs font-bold text-slate-900">Historique</p>
              <button onClick={clearHistory} className="text-rose-400 hover:text-rose-600">
                <Trash2 size={13} />
              </button>
            </div>
            <div className="overflow-y-auto h-full pb-16">
              {history.length === 0 ? (
                <p className="text-xs text-slate-400 text-center py-8">Aucun historique</p>
              ) : (
                history.map(h => (
                  <button key={h.id} onClick={() => { setInput(h.question); setShowHistory(false); }}
                    className="w-full text-left px-4 py-3 border-b border-slate-100 hover:bg-slate-50 transition">
                    <p className="text-xs font-medium text-slate-800 line-clamp-2">{h.question}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">{fmt(h.timestamp)}</p>
                  </button>
                ))
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Chat area */}
      <div className="flex flex-1 flex-col rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
        {/* Chat header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-slate-100">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-100">
              <Brain size={14} className="text-violet-600" />
            </div>
            <div>
              <p className="text-xs font-bold text-slate-900">Assistant IA Compliance</p>
              <p className="text-[10px] text-slate-400">RAG · FAISS · {llmAvailable ? 'Ollama Online' : 'Fallback Mode'}</p>
            </div>
            <span className={`ml-2 rounded-full px-2 py-0.5 text-[10px] font-semibold ${llmAvailable ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
              {llmAvailable ? '● En ligne' : '● Fallback'}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <select value={standard} onChange={e => setStandard(e.target.value)}
              className="rounded-xl border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] outline-none">
              <option value="">Tous</option>
              {standards.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
            <button onClick={() => setShowHistory(h => !h)}
              className="rounded-xl border border-slate-200 p-1.5 hover:bg-slate-50 text-slate-500">
              <History size={13} />
            </button>
            <button onClick={() => exportChat('md')}
              className="rounded-xl border border-slate-200 p-1.5 hover:bg-slate-50 text-slate-500">
              <Download size={13} />
            </button>
            <button onClick={() => setMessages([])}
              className="rounded-xl border border-slate-200 p-1.5 hover:bg-slate-50 text-rose-400">
              <Trash2 size={13} />
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center h-full gap-4 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-violet-100">
                <MessageSquare size={24} className="text-violet-600" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-700">Posez une question sur les normes ISO</p>
                <p className="text-xs text-slate-400 mt-1">L'assistant utilise votre base de connaissances interne</p>
              </div>
              <div className="grid gap-2 grid-cols-2 max-w-md">
                {SUGGESTIONS.map(s => (
                  <button key={s} onClick={() => handleSend(s)}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-left text-slate-700 hover:border-violet-300 hover:bg-violet-50 transition">
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <motion.div key={i} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
                msg.role === 'user'
                  ? 'bg-slate-900 text-white'
                  : msg.error
                    ? 'border border-rose-200 bg-rose-50 text-rose-700'
                    : 'border border-slate-200 bg-white text-slate-800 shadow-sm'
              }`}>
                <p className="whitespace-pre-wrap leading-relaxed">{msg.content}</p>
                {msg.sources?.length > 0 && (
                  <div className="mt-3 pt-2 border-t border-slate-100">
                    <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Sources utilisées</p>
                    <div className="space-y-1">
                      {msg.sources.slice(0, 3).map((src, j) => (
                        <div key={j} className="flex items-center gap-1.5 text-[10px]">
                          <span className={`rounded-full px-1.5 py-0.5 font-semibold ${src.decision === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
                            {src.decision}
                          </span>
                          <span className="text-slate-500 truncate">{src.rule}</span>
                          {src.score != null && <span className="text-sky-600 font-semibold ml-auto">{src.score}%</span>}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                <div className="flex items-center justify-between mt-1 gap-2">
                  <p className="text-[10px] opacity-50">{fmt(msg.timestamp)}</p>
                  {msg.model && <span className="text-[10px] opacity-50">{msg.model}</span>}
                  {msg.confidence && <span className="text-[10px] opacity-50">conf: {msg.confidence}</span>}
                </div>
              </div>
            </motion.div>
          ))}

          {/* Stream status indicator */}
          {loading && streamStatus && (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <div className="flex gap-1">
                {[0,1,2].map(i => (
                  <motion.div key={i} animate={{ scale: [1, 1.5, 1] }}
                    transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.2 }}
                    className="h-1.5 w-1.5 rounded-full bg-violet-400" />
                ))}
              </div>
              <span>{streamStatus}</span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-slate-100 px-4 py-3">
          <form onSubmit={e => { e.preventDefault(); handleSend(); }} className="flex gap-2">
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Posez votre question sur les normes ISO…"
              className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-violet-400 transition"
              disabled={loading}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-violet-500 disabled:opacity-50 transition flex items-center gap-1.5"
            >
              {loading ? (
                <motion.div animate={{ rotate: 360 }} transition={{ repeat: Infinity, duration: 1 }}>
                  <RefreshCw size={15} />
                </motion.div>
              ) : <Send size={15} />}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}


/* ══════════════════════════════════════════════════════════════════
   MAIN PAGE
══════════════════════════════════════════════════════════════════ */
export default function AIInsights() {
  const { user } = useContext(UserContext);
  const canViewMlops = user?.role === 'ADMIN' || user?.role === 'TEAMLEAD';

  const [activeTab, setActiveTab] = useState('overview');
  const [overviewData, setOverviewData] = useState(null);
  const [overviewLoading, setOverviewLoading] = useState(true);
  const [mlopsData, setMlopsData] = useState(null);
  const [mlopsLoading, setMlopsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState(null);

  const loadOverview = useCallback(async () => {
    setOverviewLoading(true);
    try {
      const r = await api.get('/ai/overview/');
      setOverviewData(r.data);
      setLastRefresh(new Date());
    } catch (e) {
      console.error('AI overview failed:', e);
    } finally {
      setOverviewLoading(false);
    }
  }, []);

  const loadMlops = useCallback(async () => {
    setMlopsLoading(true);
    try {
      const r = await api.get('/ml/mlops/status/');
      setMlopsData(r.data);
    } catch (e) {
      console.error('MLOps status failed:', e);
    } finally {
      setMlopsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadOverview();
    if (canViewMlops) loadMlops();
    else setMlopsLoading(false);
  }, [loadOverview, loadMlops, canViewMlops]);

  const handleRefresh = () => {
    loadOverview();
    if (canViewMlops) loadMlops();
  };

  const llmAvailable = overviewData?.llm?.available ?? false;
  const standards = overviewData?.summary?.available_standards ?? [];
  const healthScore = overviewData?.health?.score ?? 0;

  return (
    <Layout>
      <div className="page-container">

        {/* ── Page Header ─────────────────────────────────────────── */}
        <div className="page-header">
          <div>
            <p className="section-label">AI / Machine Learning</p>
            <h1 className="page-title mt-1">AI Insights</h1>
            <p className="page-subtitle">
              Model health · Drift detection · Explainable AI · Dataset quality · Assistant
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!overviewLoading && (
              <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs font-semibold ${
                healthScore >= 90 ? 'border-emerald-200 bg-emerald-50 text-emerald-700' :
                healthScore >= 75 ? 'border-amber-200 bg-amber-50 text-amber-700' :
                'border-red-200 bg-red-50 text-red-700'
              }`}>
                <span className={`h-2 w-2 rounded-full ${
                  healthScore >= 90 ? 'bg-emerald-500' :
                  healthScore >= 75 ? 'bg-amber-500' : 'bg-red-500'
                }`} />
                {overviewData?.health?.label ?? 'Unknown'} · {healthScore}/100
              </div>
            )}
            {lastRefresh && (
              <span className="text-2xs text-slate-400">
                Updated {lastRefresh.toLocaleTimeString('fr-FR')}
              </span>
            )}
            <button
              onClick={handleRefresh}
              disabled={overviewLoading}
              className="btn-secondary btn-sm"
            >
              <RefreshCw size={13} className={overviewLoading ? 'animate-spin' : ''} />
              Refresh
            </button>
          </div>
        </div>

        {/* ── Tab navigation ──────────────────────────────────────── */}
        <div className="card p-1.5">
          <div className="flex flex-wrap gap-1">
            {TABS.map(t => (
              <button
                key={t.id}
                onClick={() => setActiveTab(t.id)}
                className={`flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-semibold transition-all ${
                  activeTab === t.id
                    ? 'bg-slate-900 text-white shadow-sm'
                    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
                }`}
              >
                <t.icon size={12} />
                <span className="hidden sm:inline">{t.label}</span>
                <span className="sm:hidden">{t.label.split(' ')[0]}</span>
              </button>
            ))}
          </div>
        </div>

        {/* ── Tab Content ─────────────────────────────────────────── */}
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={{ opacity: 0, y: 6 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -6 }}
            transition={{ duration: 0.15 }}
          >
            {activeTab === 'overview' && (
              <OverviewTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'health' && (
              <HealthTab data={overviewData} loading={overviewLoading} mlopsData={mlopsData} mlopsLoading={mlopsLoading} />
            )}
            {activeTab === 'drift' && (
              <DriftTab />
            )}
            {activeTab === 'explainable' && (
              <ExplainableTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'dataset' && (
              <DatasetQualityTab />
            )}
            {activeTab === 'reco' && (
              <RecommendationsTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'comparison' && (
              <ComparisonTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'timeline' && (
              <TimelineTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'semantic' && (
              <SemanticTab data={overviewData} loading={overviewLoading} />
            )}
            {activeTab === 'assistant' && (
              <AssistantTab llmAvailable={llmAvailable} standards={standards} />
            )}
          </motion.div>
        </AnimatePresence>

      </div>
    </Layout>
  );
}
