/**
 * AI Insights — /ai-insights
 * Compliance drift, TeamLead recommendations, dataset quality, compliance assistant.
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  TrendingDown, Brain, Database, MessageSquare,
  AlertTriangle, CheckCircle2, BarChart3, Sparkles, RefreshCw,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';

/* ── KPI card ────────────────────────────────────────────────────── */
function KpiCard({ label, value, sub, color = 'text-slate-900', bg = 'bg-slate-50', loading }) {
  return (
    <div className={`rounded-2xl border border-slate-200 p-4 shadow-sm ${bg}`}>
      <p className="text-xs uppercase tracking-widest text-slate-400">{label}</p>
      <p className={`mt-2 text-2xl font-bold ${color}`}>
        {loading ? <span className="inline-block h-7 w-16 animate-pulse rounded bg-slate-200" /> : value}
      </p>
      {sub && <p className="mt-0.5 text-xs text-slate-400">{sub}</p>}
    </div>
  );
}

/* ── Drift section ───────────────────────────────────────────────── */
function DriftSection() {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/compliance/drift/?weeks=6')
       .then(r => setData(r.data))
       .catch(() => {})
       .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-40 animate-pulse rounded-2xl bg-slate-100" />;
  if (!data)   return <p className="text-sm text-slate-400">No drift data available.</p>;

  const departments = data.departments || [];
  const alerts      = data.alerts      || [];

  return (
    <div className="space-y-4">
      {alerts.length > 0 && (
        <div className="space-y-2">
          {alerts.map((a, i) => (
            <div key={i} className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm">
              <AlertTriangle size={15} className="text-amber-500 mt-0.5 flex-shrink-0" />
              <p className="text-amber-800">{a.message || JSON.stringify(a)}</p>
            </div>
          ))}
        </div>
      )}
      {alerts.length === 0 && (
        <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-700">
          <CheckCircle2 size={14} />
          No compliance drift alerts detected this week.
        </div>
      )}
      {departments.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {departments.map((dept, idx) => (
            <div key={dept.department || idx} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <p className="text-sm font-semibold text-slate-800">{dept.department}</p>
              <div className="mt-2 space-y-1">
                {(dept.weekly_rates || []).slice(-4).map((w, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-400 w-14 flex-shrink-0">Week {i+1}</span>
                    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                      <div className={`h-full rounded-full ${w >= 70 ? 'bg-emerald-500' : w >= 40 ? 'bg-amber-500' : 'bg-rose-500'}`}
                        style={{ width: `${Math.max(w, 2)}%` }} />
                    </div>
                    <span className="text-[10px] font-semibold text-slate-600 w-8 text-right">{Math.round(w)}%</span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* ── Recommendations section ─────────────────────────────────────── */
function RecommendationsSection() {
  const [data, setData]     = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get('/teamlead/recommendations/')
       .then(r => setData(r.data))
       .catch(() => {})
       .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-40 animate-pulse rounded-2xl bg-slate-100" />;
  const recs = data?.recommendations || [];
  if (recs.length === 0) return <p className="text-sm text-slate-400">No recommendations yet. More validations needed.</p>;

  const PRIORITY_COLOR = { high: 'border-rose-200 bg-rose-50', medium: 'border-amber-200 bg-amber-50', low: 'border-slate-200 bg-slate-50' };

  return (
    <div className="space-y-3">
      {recs.map((r, i) => (
        <div key={i} className={`rounded-xl border px-4 py-3 ${PRIORITY_COLOR[r.priority] || PRIORITY_COLOR.low}`}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-800">{r.rule_title || r.title || 'Rule'}</p>
              <p className="text-xs text-slate-500 mt-0.5">{r.recommendation || r.message || ''}</p>
            </div>
            {r.priority && (
              <span className={`flex-shrink-0 text-[10px] font-bold uppercase rounded-full px-2 py-0.5 ${
                r.priority === 'high' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'
              }`}>{r.priority}</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ── Dataset quality section ─────────────────────────────────────── */
function DatasetQualitySection() {
  const [d,       setD]       = useState(null);
  const [dups,    setDups]    = useState(null);
  const [models,  setModels]  = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      api.get('/dataset/quality-report/').catch(() => null),
      api.get('/evidence/duplicates/').catch(() => null),
      api.get('/ml/models/?norm_id=1').catch(() => null),
    ]).then(([q, dup, m]) => {
      setD(q?.data);
      setDups(dup?.data);
      setModels(m?.data?.models || []);
    }).finally(() => setLoading(false));
  }, []);

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {/* Evidence quality */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-100">
            <Database size={14} className="text-sky-600" />
          </div>
          <p className="text-sm font-bold text-slate-900">Evidence Quality</p>
        </div>
        {loading ? <div className="h-24 animate-pulse rounded-xl bg-slate-100" /> : d ? (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-slate-400">Total evidence</span><span className="font-semibold">{d.evidence?.total ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Quality status</span><span className={`font-bold capitalize ${d.quality_status === 'excellent' ? 'text-emerald-600' : d.quality_status === 'good' ? 'text-amber-600' : 'text-rose-600'}`}>{d.quality_status}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Avg length</span><span className="font-semibold">{d.evidence?.avg_evidence_length ?? 0} words</span></div>
          </div>
        ) : <p className="text-xs text-slate-400">No data</p>}
      </div>

      {/* Duplicates */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-100">
            <AlertTriangle size={14} className="text-amber-600" />
          </div>
          <p className="text-sm font-bold text-slate-900">Duplicates</p>
        </div>
        {loading ? <div className="h-24 animate-pulse rounded-xl bg-slate-100" /> : dups ? (
          <div className="space-y-2 text-xs">
            <div className="flex justify-between"><span className="text-slate-400">Total records</span><span className="font-semibold">{dups.total ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Duplicates</span><span className={`font-bold ${dups.duplicates > 0 ? 'text-rose-600' : 'text-emerald-600'}`}>{dups.duplicates ?? 0}</span></div>
            <div className="flex justify-between"><span className="text-slate-400">Rate</span><span className="font-semibold">{dups.duplication_rate ?? 0}%</span></div>
          </div>
        ) : <p className="text-xs text-slate-400">No data</p>}
      </div>

      {/* Model accuracy */}
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-100">
            <BarChart3 size={14} className="text-violet-600" />
          </div>
          <p className="text-sm font-bold text-slate-900">ML Models</p>
        </div>
        {loading ? <div className="h-24 animate-pulse rounded-xl bg-slate-100" /> :
          models && models.length > 0 ? (
            <div className="space-y-2">
              {models.filter(m => m.accuracy != null).slice(0, 3).map(m => (
                <div key={m.name} className="flex items-center gap-2">
                  <p className="text-xs text-slate-600 w-28 truncate">{m.name}</p>
                  <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                    <div className={`h-full rounded-full ${m.is_best ? 'bg-violet-500' : 'bg-sky-400'}`}
                      style={{ width: `${Math.round((m.accuracy || 0) * 100)}%` }} />
                  </div>
                  <span className="text-xs font-bold text-slate-600 w-10 text-right">{Math.round((m.accuracy || 0) * 100)}%</span>
                </div>
              ))}
            </div>
          ) : <p className="text-xs text-slate-400">No trained models. Go to ML Dashboard.</p>
        }
      </div>
    </div>
  );
}

/* ── Compliance Chat ─────────────────────────────────────────────── */
function ComplianceChatSection() {
  const [question, setQuestion] = useState('');
  const [answer,   setAnswer]   = useState('');
  const [loading,  setLoading]  = useState(false);
  const [llmOk,    setLlmOk]    = useState(null);

  useEffect(() => {
    api.get('/llm/status/').then(r => setLlmOk(r.data.available)).catch(() => setLlmOk(false));
  }, []);

  const handleAsk = async (e) => {
    e.preventDefault();
    if (!question.trim()) return;
    setLoading(true); setAnswer('');
    try {
      const r = await api.post('/compliance/chat/', { question, standard: 'ISO9001' });
      setAnswer(r.data.answer || r.data.response || JSON.stringify(r.data));
    } catch (err) {
      setAnswer('Error: ' + (err?.response?.data?.error || err.message));
    } finally { setLoading(false); }
  };

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-center gap-2 mb-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-violet-100">
          <MessageSquare size={14} className="text-violet-600" />
        </div>
        <p className="text-sm font-bold text-slate-900">Compliance Assistant</p>
        {llmOk !== null && (
          <span className={`ml-auto text-[10px] font-semibold rounded-full px-2 py-0.5 ${llmOk ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-100 text-slate-500'}`}>
            {llmOk ? 'LLM Online' : 'Fallback Mode'}
          </span>
        )}
      </div>
      <form onSubmit={handleAsk} className="flex gap-2 mb-4">
        <input
          value={question}
          onChange={e => setQuestion(e.target.value)}
          placeholder="Ask about ISO 27001, TISAX, ISO 9001…"
          className="flex-1 rounded-xl border border-slate-200 bg-slate-50 px-4 py-2.5 text-sm outline-none focus:border-sky-400"
        />
        <button type="submit" disabled={loading || !question.trim()}
          className="rounded-xl bg-sky-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-sky-500 disabled:opacity-50">
          {loading ? '…' : 'Ask'}
        </button>
      </form>
      {answer && (
        <div className="rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-700 whitespace-pre-wrap max-h-48 overflow-y-auto">
          {answer}
        </div>
      )}
    </div>
  );
}

/* ══════════════════════════ MAIN PAGE ═══════════════════════════ */
export default function AIInsights() {
  const [activeTab, setActiveTab] = useState('drift');

  const TABS = [
    { id: 'drift',      label: 'Compliance Drift',  icon: TrendingDown  },
    { id: 'insights',   label: 'Recommendations',   icon: Brain         },
    { id: 'quality',    label: 'Dataset Quality',   icon: Database      },
    { id: 'assistant',  label: 'AI Assistant',      icon: MessageSquare },
  ];

  return (
    <Layout>
      <div className="space-y-6 pb-10">
        {/* Header */}
        <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-violet-950 to-slate-900 px-6 py-6 shadow-xl">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-violet-500/20">
              <Sparkles size={20} className="text-violet-300" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-widest text-violet-400">Dashboard IA</p>
              <h1 className="text-2xl font-bold text-white">AI Insights</h1>
              <p className="text-sm text-slate-400">Drift detection · Recommendations · AI Assistant</p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex flex-wrap gap-2">
          {TABS.map(t => (
            <button key={t.id} type="button" onClick={() => setActiveTab(t.id)}
              className={`flex items-center gap-2 rounded-2xl px-4 py-2.5 text-sm font-semibold transition-all ${
                activeTab === t.id
                  ? 'bg-slate-900 text-white shadow-sm'
                  : 'border border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-800'
              }`}>
              <t.icon size={14} />
              {t.label}
            </button>
          ))}
        </div>

        {/* Content */}
        {activeTab === 'drift'     && <DriftSection />}
        {activeTab === 'insights'  && <RecommendationsSection />}
        {activeTab === 'quality'   && <DatasetQualitySection />}
        {activeTab === 'assistant' && <ComplianceChatSection />}
      </div>
    </Layout>
  );
}
