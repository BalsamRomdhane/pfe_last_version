import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Search, Brain, Sparkles, RefreshCw, Database,
  CheckCircle2, XCircle, Zap, ChevronLeft, ChevronRight,
  BarChart2, Layers, AlertTriangle, Plus, Download, X,
  ShieldCheck, Clock, TrendingUp,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';
import AnalyzeDocumentModal from '../components/analysis/AnalyzeDocumentModal';

/* ── Helpers ─────────────────────────────────────────────────────────────── */
const fmt = (v) => {
  if (!v) return '—';
  return new Date(v).toLocaleDateString('en-GB', { year: 'numeric', month: 'short', day: 'numeric' });
};

const BADGE = {
  approved: 'bg-emerald-100 text-emerald-700 ring-1 ring-emerald-200',
  rejected:  'bg-red-100 text-red-700 ring-1 ring-red-200',
  pending:   'bg-amber-100 text-amber-700 ring-1 ring-amber-200',
};
const BAR_COLOR = { approved: 'bg-emerald-400', rejected: 'bg-red-400', pending: 'bg-amber-400' };

const TABS = [
  { id: 'overview',   label: 'Overview',        icon: BarChart2    },
  { id: 'analytics',  label: 'Analytics',       icon: TrendingUp   },
  { id: 'duplicates', label: 'Duplicates',      icon: AlertTriangle },
  { id: 'semantic',   label: 'Semantic Memory', icon: Layers       },
];

/* ── EvidenceCard ────────────────────────────────────────────────────────── */
function EvidenceCard({ item }) {
  const [open, setOpen] = useState(false);
  const label   = (item.label || item.decision || '').toLowerCase();
  const title   = item.rule || item.rule_title || '—';
  const text    = item.evidence_text || item.evidence || '';
  const comment = item.reviewer_comment || item.comment || '';
  const rec     = item.recommendation || '';
  const sim     = item.similarity != null
    ? (item.similarity > 1 ? Math.round(item.similarity) : Math.round(item.similarity * 100))
    : null;

  return (
    <div className={`flex flex-col overflow-hidden rounded-2xl border bg-white shadow-sm transition hover:shadow-md ${
      label === 'approved' ? 'border-emerald-100' : label === 'rejected' ? 'border-red-100' : 'border-slate-200'
    }`}>
      <div className={`h-0.5 w-full ${BAR_COLOR[label] || 'bg-slate-300'}`} />
      <div className="flex flex-1 flex-col gap-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <p className="text-xs font-bold text-slate-900 leading-snug line-clamp-2">{title}</p>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold capitalize ${BADGE[label] || BADGE.pending}`}>
              {label || '—'}
            </span>
            {item.norm && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-semibold text-slate-500 truncate max-w-[90px]">
                {item.norm}
              </span>
            )}
          </div>
        </div>
        <p className="text-xs text-slate-600 line-clamp-3 leading-relaxed">
          {text || <span className="italic text-slate-400">No evidence text</span>}
        </p>
        {sim !== null && (
          <div className="flex items-center gap-2">
            <div className="h-1 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className={`h-full rounded-full ${sim >= 80 ? 'bg-emerald-500' : sim >= 50 ? 'bg-amber-500' : 'bg-red-500'}`}
                style={{ width: `${sim}%` }} />
            </div>
            <span className="text-xs font-semibold text-slate-500">{sim}%</span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-xs text-slate-400">{fmt(item.updated_at || item.created_at)}</span>
          {(comment || rec) && (
            <button type="button" onClick={() => setOpen(o => !o)}
              className="text-xs font-semibold text-sky-600 hover:text-sky-800">
              {open ? '▲ Hide' : '▼ Details'}
            </button>
          )}
        </div>
        {open && (comment || rec) && (
          <div className="space-y-2 rounded-xl border border-slate-100 bg-slate-50 p-3">
            {comment && <div><p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Comment</p>
              <p className="mt-0.5 text-xs text-slate-700">{comment}</p></div>}
            {rec && <div><p className="text-xs font-semibold text-violet-500 uppercase tracking-wider">Recommendation</p>
              <p className="mt-0.5 text-xs font-medium text-violet-800">{rec}</p></div>}
          </div>
        )}
      </div>
    </div>
  );
}

/* ── Pagination ──────────────────────────────────────────────────────────── */
function Pagination({ page, pages, total, pageSize, onPage }) {
  const start = (page - 1) * pageSize + 1;
  const end   = Math.min(page * pageSize, total);
  const lo = Math.max(1, page - 2);
  const hi = Math.min(pages, page + 2);
  const nums = [];
  for (let i = lo; i <= hi; i++) nums.push(i);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3">
      <p className="text-xs text-slate-500">
        Showing <strong>{total === 0 ? 0 : start}–{end}</strong> of <strong>{total}</strong> records
      </p>
      <div className="flex items-center gap-1">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1}
          className="flex h-8 items-center gap-1 rounded-lg border border-slate-200 px-2 text-xs text-slate-500 transition hover:bg-slate-50 disabled:opacity-40">
          <ChevronLeft size={13} /> Previous
        </button>
        {lo > 1 && (
          <React.Fragment key="start-ellipsis">
            <button onClick={() => onPage(1)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-xs text-slate-600 hover:bg-slate-50">1</button>
            <span className="text-xs text-slate-400">…</span>
          </React.Fragment>
        )}
        {nums.map(n => (
          <button key={n} onClick={() => onPage(n)}
            className={`flex h-8 w-8 items-center justify-center rounded-lg border text-xs font-semibold transition ${
              n === page ? 'border-sky-500 bg-sky-500 text-white' : 'border-slate-200 text-slate-600 hover:bg-slate-50'
            }`}>{n}</button>
        ))}
        {hi < pages && (
          <React.Fragment key="end-ellipsis">
            <span className="text-xs text-slate-400">…</span>
            <button onClick={() => onPage(pages)} className="flex h-8 w-8 items-center justify-center rounded-lg border border-slate-200 text-xs text-slate-600 hover:bg-slate-50">{pages}</button>
          </React.Fragment>
        )}
        <button onClick={() => onPage(page + 1)} disabled={page >= pages}
          className="flex h-8 items-center gap-1 rounded-lg border border-slate-200 px-2 text-xs text-slate-500 transition hover:bg-slate-50 disabled:opacity-40">
          Next <ChevronRight size={13} />
        </button>
      </div>
    </div>
  );
}

/* ── Analytics Tab — données GLOBALES via API ────────────────────────────── */
function AnalyticsTab({ normFilter }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    if (normFilter) params.set('norm_name', normFilter);
    api.get(`/dataset/quality-report/?${params}`)
      .then(r => setData(r.data))
      .catch(() => setData(null))
      .finally(() => setLoading(false));
  }, [normFilter]);

  if (loading) return (
    <div className="grid gap-3 sm:grid-cols-3">
      {[...Array(6)].map((_, i) => <div key={i} className="h-24 animate-pulse rounded-2xl bg-slate-100" />)}
    </div>
  );
  if (!data) return <p className="text-sm text-slate-400">No analytics data available.</p>;

  const ev = data.evidence || {};
  const cl = data.classification || {};
  const cov = data.coverage || {};

  const distItems = (data.rule_distribution || []).slice(0, 10);
  const maxDist = Math.max(...distItems.map(r => r.total), 1);

  return (
    <div className="space-y-6">
      {/* KPI row */}
      <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        {[
          { label: 'Total Evidence',   value: ev.total ?? 0,            color: 'text-slate-900',    bg: 'bg-slate-50'    },
          { label: 'Approved',         value: ev.approved ?? 0,         color: 'text-emerald-700',  bg: 'bg-emerald-50'  },
          { label: 'Rejected',         value: ev.rejected ?? 0,         color: 'text-red-700',      bg: 'bg-red-50'      },
          { label: 'Unique Texts',     value: ev.unique ?? 0,           color: 'text-sky-700',      bg: 'bg-sky-50'      },
          { label: 'Vocabulary',       value: ev.vocabulary_size ?? 0,  color: 'text-violet-700',   bg: 'bg-violet-50'   },
          { label: 'Rules Covered',    value: `${cov.rules_with_evidence ?? 0}/${cov.total_rules ?? 0}`, color: 'text-teal-700', bg: 'bg-teal-50' },
        ].map(k => (
          <div key={k.label} className={`rounded-2xl border border-slate-100 ${k.bg} p-4`}>
            <p className="text-xs font-medium text-slate-500">{k.label}</p>
            <p className={`mt-1 text-2xl font-bold ${k.color}`}>{k.value}</p>
          </div>
        ))}
      </div>

      {/* Coverage bar */}
      <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-slate-600">Rule coverage</p>
          <span className="text-xs font-bold text-teal-700">{cov.coverage_pct ?? 0}%</span>
        </div>
        <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200">
          <div className="h-full rounded-full bg-teal-500 transition-all duration-700"
            style={{ width: `${cov.coverage_pct ?? 0}%` }} />
        </div>
        <p className="mt-1 text-xs text-slate-400">
          {cov.rules_with_evidence ?? 0} of {cov.total_rules ?? 0} rules have evidence
        </p>
      </div>

      {/* Distribution by rule */}
      {distItems.length > 0 && (
        <div>
          <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
            Evidence distribution by rule (global dataset)
          </p>
          <div className="space-y-2">
            {distItems.map(r => (
              <div key={r.rule_title} className="flex items-center gap-3">
                <p className="w-44 shrink-0 truncate text-xs font-medium text-slate-700">{r.rule_title || 'Unknown'}</p>
                <div className="flex-1 overflow-hidden rounded-full bg-slate-100 h-2">
                  <div className="h-full rounded-full bg-sky-500"
                    style={{ width: `${(r.total / maxDist) * 100}%` }} />
                </div>
                <span className="w-8 text-right text-xs font-bold text-slate-600">{r.total}</span>
                <span className="w-6 text-right text-xs text-emerald-600">{r.approved}</span>
                <span className="w-6 text-right text-xs text-red-600">{r.rejected}</span>
              </div>
            ))}
          </div>
          <div className="mt-2 flex gap-4 text-xs text-slate-400">
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500" />Approved</span>
            <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" />Rejected</span>
          </div>
        </div>
      )}

      {/* Classification stats */}
      <div className="rounded-2xl border border-slate-100 bg-white p-4">
        <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500">Classification dataset</p>
        <div className="grid gap-3 sm:grid-cols-4">
          {[
            { label: 'Total Samples',    value: cl.total ?? 0,           color: 'text-slate-900'   },
            { label: 'Approved',         value: cl.approved ?? 0,        color: 'text-emerald-700' },
            { label: 'Rejected',         value: cl.rejected ?? 0,        color: 'text-red-700'     },
            { label: 'Avg Compliance',   value: `${cl.avg_compliance ?? 0}%`, color: 'text-sky-700' },
          ].map(k => (
            <div key={k.label} className="rounded-xl border border-slate-100 bg-slate-50 p-3">
              <p className="text-xs text-slate-500">{k.label}</p>
              <p className={`mt-1 text-xl font-bold ${k.color}`}>{k.value}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ── Main Page ───────────────────────────────────────────────────────────── */
export default function EvidenceIntelligence() {
  /* ── State ── */
  const [summary, setSummary]             = useState({});
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [normOptions, setNormOptions]     = useState([]);
  const [modalOpen, setModalOpen]         = useState(false);
  const [activeTab, setActiveTab]         = useState('overview');
  const [trainLoading, setTrainLoading]   = useState(false);
  const [trainError, setTrainError]       = useState('');

  /* ── Selected norm — persisted in localStorage ── */
  const [selectedNorm, setSelectedNorm] = useState(
    () => localStorage.getItem('ei_selected_norm') || ''
  );
  const handleNormChange = (val) => {
    setSelectedNorm(val);
    localStorage.setItem('ei_selected_norm', val);
    // Reset KB filters when norm changes
    setKbRuleFilter('');
    setKbLabelFilter('');
    setKbSearch('');
  };

  /* KB */
  const [kbSamples, setKbSamples]         = useState([]);
  const [kbTotal, setKbTotal]             = useState(0);
  const [kbPage, setKbPage]               = useState(1);
  const [kbPages, setKbPages]             = useState(1);
  const [kbPageSize]                      = useState(10);
  const [kbLoading, setKbLoading]         = useState(false);
  const [kbRuleFilter, setKbRuleFilter]   = useState('');
  const [kbLabelFilter, setKbLabelFilter] = useState('');
  const [kbSearch, setKbSearch]           = useState('');
  const [kbSort, setKbSort]               = useState('newest');
  const [kbRuleOptions, setKbRuleOptions] = useState([]);

  /* Duplicates */
  const [dupReport, setDupReport]         = useState(null);
  const [dupLoading, setDupLoading]       = useState(false);
  const [dedupLoading, setDedupLoading]   = useState(false);
  const [dedupResult, setDedupResult]     = useState(null);

  /* Add form */
  const [showAddForm, setShowAddForm]     = useState(false);
  const [addForm, setAddForm]             = useState({ norm_id: '', rule_id: '', evidence_text: '', reviewer_comment: '', recommendation: '', label: 'approved' });
  const [addLoading, setAddLoading]       = useState(false);
  const [addResult, setAddResult]         = useState(null);
  const [ruleOptions, setRuleOptions]     = useState([]);

  /* ── Load norms (single endpoint) ── */
  useEffect(() => {
    api.get('/normes/').then(res => {
      const norms = Array.isArray(res.data) ? res.data : res.data?.results || [];
      if (norms.length > 0) {
        setNormOptions(norms.map(n => ({ value: n.name, label: n.name, id: n.id, rules_count: n.rules_count ?? 0 })));
        // Only auto-select if no preference is stored
        if (!localStorage.getItem('ei_selected_norm') && norms[0]) {
          setAddForm(f => ({ ...f, norm_id: String(norms[0].id) }));
          setRuleOptions(norms[0].rules || []);
          if (norms[0].rules?.length > 0) {
            setAddForm(f => ({ ...f, rule_id: String(norms[0].rules[0].id) }));
          }
        } else {
          // Set add form to selected norm
          const sel = norms.find(n => n.name === selectedNorm) || norms[0];
          if (sel) {
            setAddForm(f => ({ ...f, norm_id: String(sel.id) }));
            setRuleOptions(sel.rules || []);
            if (sel.rules?.length > 0) {
              setAddForm(f => ({ ...f, rule_id: String(sel.rules[0].id) }));
            }
          }
        }
      }
    }).catch(() => {});
  }, []); // eslint-disable-line

  /* ── Load summary — filtered by selected norm ── */
  const loadSummary = useCallback(async () => {
    setSummaryLoading(true);
    try {
      const params = new URLSearchParams();
      if (selectedNorm) params.set('norm_name', selectedNorm);
      const res = await api.get(`/evidence/status/?${params}`);
      const m = res.data || {};
      setSummary({
        total_evidences:   m.total_evidences ?? 0,
        indexed_evidences: m.indexed_evidences ?? 0,
        coverage:          m.coverage_percent ?? 0,
        approved_patterns: m.approved_patterns ?? 0,
        rejected_patterns: m.rejected_patterns ?? 0,
        rules_covered:     m.rules_covered ?? 0,
        total_rules:       m.total_rules ?? 0,
        embedding_model:   m.embedding_model || 'tfidf-fallback',
        last_trained:      m.last_trained || null,
        train_status:      m.train_status || 'UNKNOWN',
      });
    } catch (e) { console.error(e); }
    finally { setSummaryLoading(false); }
  }, [selectedNorm]);

  useEffect(() => { loadSummary(); }, [loadSummary]);

  /* ── Load KB — stable, reads current filter values via closure ── */
  const loadKB = useCallback(async (page = 1, opts = {}) => {
    setKbLoading(true);
    try {
      const p = new URLSearchParams();
      p.set('page', page);
      p.set('page_size', kbPageSize);

      // opts override takes priority; fall back to current state captured in closure
      const rule  = opts.rule   !== undefined ? opts.rule   : kbRuleFilter;
      const label = opts.label  !== undefined ? opts.label  : kbLabelFilter;
      const srch  = opts.search !== undefined ? opts.search : kbSearch;
      const sort  = opts.sort   !== undefined ? opts.sort   : kbSort;
      const norm  = opts.norm   !== undefined ? opts.norm   : selectedNorm;

      if (rule)  p.set('rule', rule);
      if (label) p.set('label', label);
      if (srch)  p.set('search', srch);
      if (sort && sort !== 'newest') p.set('sort', sort);
      if (norm)  p.set('norm_name', norm);

      const res = await api.get(`rule-memory/?${p.toString()}`);
      const d = res.data || {};
      setKbSamples(Array.isArray(d.items) ? d.items : []);
      setKbTotal(d.total || 0);
      setKbPage(d.page || 1);
      setKbPages(d.pages || 1);
      if (Array.isArray(d.filters?.rules)) setKbRuleOptions(d.filters.rules);
    } catch (e) { console.error('loadKB error:', e); }
    finally { setKbLoading(false); }
  // We intentionally list all filter deps so React knows when to recreate this callback.
  // The useEffect below only fires when loadKB identity changes (i.e., when a filter changes).
  }, [kbRuleFilter, kbLabelFilter, kbSearch, kbSort, kbPageSize, selectedNorm]); // eslint-disable-line react-hooks/exhaustive-deps

  // Re-run loadKB when filters or selectedNorm change
  useEffect(() => { loadKB(1); }, [loadKB]); // eslint-disable-line react-hooks/exhaustive-deps

  /* ── Handlers ── */
  const handleTrain = async () => {
    setTrainLoading(true);
    setTrainError('');
    try {
      await api.post('/evidence/index/', { standard: selectedNorm });
      await loadSummary();
    } catch (e) {
      const msg = e?.response?.data?.error || e?.message || 'Indexing failed.';
      setTrainError(msg);
    } finally {
      setTrainLoading(false);
    }
  };

  const handleAnalyzeDuplicates = async () => {
    setDupLoading(true); setDupReport(null); setDedupResult(null);
    try {
      const r = await api.get('/evidence/duplicates/');
      setDupReport(r.data);
      setActiveTab('duplicates');
    } catch (e) {
      console.error(e);
    } finally {
      setDupLoading(false);
    }
  };

  const handleDeduplicate = async () => {
    if (!window.confirm('Remove all duplicate rows and rebuild FAISS index?')) return;
    setDedupLoading(true);
    try {
      const r = await api.post('/evidence/deduplicate/');
      setDedupResult(r.data);
      setDupReport(null);
      await loadSummary();
      loadKB(1);
    } catch (e) {
      const msg = e?.response?.data?.error || e?.response?.data?.detail || e?.message || 'Deduplication failed.';
      setDedupResult({ error: msg });
    } finally {
      setDedupLoading(false);
    }
  };

  const handleExport = async (fmt) => {
    try {
      const p = new URLSearchParams({ export: fmt, page_size: 9999 });
      if (kbRuleFilter) p.set('rule', kbRuleFilter);
      if (kbLabelFilter) p.set('label', kbLabelFilter);
      if (kbSearch) p.set('search', kbSearch);
      if (selectedNorm) p.set('norm_name', selectedNorm);
      const res = await api.get(`rule-memory/?${p.toString()}`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a'); a.href = url; a.download = `evidence.${fmt}`; a.click();
      URL.revokeObjectURL(url);
    } catch (e) { console.error(e); }
  };

  const handleAddEvidence = async (e) => {
    e.preventDefault(); setAddLoading(true); setAddResult(null);
    try {
      const res = await api.post('/rule-memory/add/', addForm);
      setAddResult({ type: 'success', message: res.data.message });
      setAddForm(f => ({ ...f, evidence_text: '', reviewer_comment: '', recommendation: '' }));
      loadKB(1);
    } catch (err) {
      setAddResult({ type: 'error', message: err.response?.data?.error || 'Failed to add evidence' });
    } finally { setAddLoading(false); }
  };

  const handleSearch = () => loadKB(1, { search: kbSearch });
  const handleReset  = () => {
    setKbSearch(''); setKbRuleFilter(''); setKbLabelFilter(''); setKbSort('newest');
    loadKB(1, { search: '', rule: '', label: '', sort: 'newest', norm: selectedNorm });
  };
  const goPage = (p) => { setKbPage(p); loadKB(p); };

  /* ── KPI cards config — per-norm when selected, global otherwise ── */
  const kpiCards = useMemo(() => {
    const cards = [
      {
        label: 'Indexed Evidence',
        value: summaryLoading ? '—' : (summary.indexed_evidences ?? 0),
        icon: Database,
        color: 'text-sky-600', bg: 'bg-sky-50', border: 'border-sky-100',
      },
      {
        label: selectedNorm ? 'Rule Coverage' : 'Coverage',
        value: summaryLoading ? '—' : (
          selectedNorm && summary.total_rules > 0
            ? `${summary.rules_covered ?? 0}/${summary.total_rules}`
            : `${Math.round(summary.coverage ?? 0)}%`
        ),
        icon: BarChart2,
        color: 'text-violet-600', bg: 'bg-violet-50', border: 'border-violet-100',
      },
      {
        label: 'Approved',
        value: summaryLoading ? '—' : (summary.approved_patterns ?? 0),
        icon: CheckCircle2,
        color: 'text-emerald-600', bg: 'bg-emerald-50', border: 'border-emerald-100',
      },
      {
        label: 'Rejected',
        value: summaryLoading ? '—' : (summary.rejected_patterns ?? 0),
        icon: XCircle,
        color: 'text-red-600', bg: 'bg-red-50', border: 'border-red-100',
      },
    ];
    return cards;
  }, [summary, summaryLoading, selectedNorm]);

  /* ── Render ── */
  return (
    <Layout>
      <div className="space-y-5 px-4 pb-10 pt-5 sm:px-6 lg:px-8">

        {/* ══ Hero Header ══ */}
        <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-6 py-5 shadow-xl">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/20">
                  <Brain size={16} className="text-sky-400" />
                </div>
                <p className="text-xs font-semibold uppercase tracking-widest text-sky-400">Evidence Intelligence</p>
              </div>
              <h1 className="mt-1.5 text-2xl font-bold text-white">Enterprise Semantic Memory</h1>
              <p className="mt-1 text-sm text-slate-400">
                AI knowledge base built from TeamLead validations and ISO compliance evidence.
              </p>
              {/* ── Norm selector ── */}
              <div className="mt-3 flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-400">Norme :</span>
                <select
                  value={selectedNorm}
                  onChange={e => handleNormChange(e.target.value)}
                  className="rounded-xl border border-slate-600 bg-slate-800 px-3 py-1.5 text-xs font-semibold text-white outline-none transition focus:border-sky-500"
                >
                  <option value="">Toutes les normes</option>
                  {normOptions.map(n => (
                    <option key={n.id} value={n.value}>{n.label}</option>
                  ))}
                </select>
                {selectedNorm && (
                  <button
                    type="button"
                    onClick={() => handleNormChange('')}
                    className="rounded-lg px-2 py-1 text-[10px] font-semibold text-slate-500 transition hover:text-slate-300"
                  >
                    ✕ Clear
                  </button>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => { loadSummary(); loadKB(1); }}
                className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-white/5 px-3 py-2 text-xs font-semibold text-slate-300 transition hover:bg-white/10">
                <RefreshCw size={13} /> Refresh
              </button>
              <button onClick={handleAnalyzeDuplicates} disabled={dupLoading}
                className="inline-flex items-center gap-1.5 rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 transition hover:bg-amber-500/20 disabled:opacity-60">
                <AlertTriangle size={13} /> {dupLoading ? 'Analyzing…' : 'Duplicates'}
              </button>
              <button onClick={() => setModalOpen(true)}
                className="inline-flex items-center gap-1.5 rounded-full bg-gradient-to-r from-sky-500 to-violet-600 px-3 py-2 text-xs font-semibold text-white shadow-lg transition hover:from-sky-400 hover:to-violet-500">
                <Sparkles size={13} /> Analyze Doc
              </button>
              <button onClick={handleTrain} disabled={trainLoading}
                className="inline-flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-2 text-xs font-semibold text-emerald-300 transition hover:bg-emerald-500/20 disabled:opacity-60">
                <Zap size={13} /> {trainLoading ? 'Training…' : 'Train Memory'}
              </button>
            </div>
          </div>
        </div>

        {/* Train error banner */}
        {trainError && (
          <div className="flex items-start gap-2 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-800">
            <AlertTriangle size={14} className="mt-0.5 shrink-0 text-amber-500" />
            <div>
              <p className="font-semibold">Indexing indisponible</p>
              <p className="mt-0.5 text-amber-700">{trainError}</p>
            </div>
            <button type="button" onClick={() => setTrainError('')}
              className="ml-auto shrink-0 text-amber-400 hover:text-amber-600">
              <X size={13} />
            </button>
          </div>
        )}

        {/* ══ KPI Cards ══ */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {kpiCards.map(k => (
            <div key={k.label} className={`flex items-center gap-3 rounded-2xl border ${k.border} ${k.bg} px-4 py-3`}>
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm">
                <k.icon size={16} className={k.color} />
              </div>
              <div>
                <p className="text-xs font-medium text-slate-500">{k.label}</p>
                <p className={`text-xl font-bold ${k.color}`}>{k.value}</p>
              </div>
            </div>
          ))}
        </div>

        {/* ══ Knowledge Base ══ */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <div>
              <p className="text-sm font-bold text-slate-900">Knowledge Base</p>
              <div className="flex items-center gap-2 mt-0.5">
                <p className="text-xs text-slate-500">{kbTotal} evidence records</p>
                {selectedNorm && (
                  <span className="inline-flex rounded-full bg-sky-100 px-2 py-0.5 text-[10px] font-bold text-sky-700">
                    {selectedNorm}
                  </span>
                )}
              </div>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <button onClick={() => setShowAddForm(v => !v)}
                className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition ${showAddForm ? 'bg-slate-200 text-slate-700' : 'bg-emerald-600 text-white hover:bg-emerald-500'}`}>
                {showAddForm ? <X size={12} /> : <Plus size={12} />} {showAddForm ? 'Cancel' : 'Add'}
              </button>
              <button onClick={() => handleExport('csv')}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                <Download size={12} /> CSV
              </button>
              <button onClick={() => handleExport('json')}
                className="inline-flex items-center gap-1 rounded-full border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50">
                <Download size={12} /> JSON
              </button>
            </div>
          </div>

          {/* Add form */}
          {showAddForm && (
            <div className="border-b border-slate-100 bg-emerald-50/40 px-5 py-4">
              <p className="mb-3 text-xs font-bold text-slate-700">Add new evidence record</p>
              <form onSubmit={handleAddEvidence} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <select value={addForm.rule_id} onChange={e => setAddForm(f => ({ ...f, rule_id: e.target.value }))}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400">
                  <option value="">— Select rule —</option>
                  {ruleOptions.map(r => <option key={r.id} value={r.id}>{r.title}</option>)}
                </select>
                <select value={addForm.label} onChange={e => setAddForm(f => ({ ...f, label: e.target.value }))}
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400">
                  <option value="approved">✓ Approved</option>
                  <option value="rejected">✗ Rejected</option>
                  <option value="pending">⏳ Pending</option>
                </select>
                <input type="text" required value={addForm.evidence_text}
                  onChange={e => setAddForm(f => ({ ...f, evidence_text: e.target.value }))}
                  placeholder="Evidence text *"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400" />
                <input type="text" value={addForm.reviewer_comment}
                  onChange={e => setAddForm(f => ({ ...f, reviewer_comment: e.target.value }))}
                  placeholder="Reviewer comment (optional)"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400" />
                <input type="text" value={addForm.recommendation}
                  onChange={e => setAddForm(f => ({ ...f, recommendation: e.target.value }))}
                  placeholder="Recommendation (optional)"
                  className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-emerald-400" />
                <button type="submit" disabled={addLoading || !addForm.evidence_text.trim()}
                  className="rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white transition hover:bg-emerald-500 disabled:opacity-60">
                  {addLoading ? 'Adding…' : 'Add to KB'}
                </button>
              </form>
              {addResult && (
                <p className={`mt-2 text-xs font-medium ${addResult.type === 'success' ? 'text-emerald-700' : 'text-red-700'}`}>
                  {addResult.type === 'success' ? '✓' : '✗'} {addResult.message}
                </p>
              )}
            </div>
          )}

          {/* Filters */}
          <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-5 py-3">
            <div className="flex flex-1 items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 min-w-[180px]">
              <Search size={13} className="shrink-0 text-slate-400" />
              <input type="text" value={kbSearch}
                onChange={e => setKbSearch(e.target.value)}
                onKeyDown={e => { if (e.key === 'Enter') handleSearch(); }}
                placeholder="Search evidence…" className="flex-1 bg-transparent text-xs outline-none" />
            </div>
            <select value={kbRuleFilter}
              onChange={e => { setKbRuleFilter(e.target.value); loadKB(1, { rule: e.target.value }); }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none">
              <option value="">All rules</option>
              {kbRuleOptions.map(r => <option key={r} value={r}>{r}</option>)}
            </select>
            <select value={kbLabelFilter}
              onChange={e => { setKbLabelFilter(e.target.value); loadKB(1, { label: e.target.value }); }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none">
              <option value="">All labels</option>
              <option value="approved">✓ Approved</option>
              <option value="rejected">✗ Rejected</option>
            </select>
            <select value={kbSort}
              onChange={e => { setKbSort(e.target.value); loadKB(1, { sort: e.target.value }); }}
              className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs outline-none">
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
              <option value="rule">By rule</option>
              <option value="label">By label</option>
            </select>
            <button onClick={handleSearch}
              className="rounded-xl bg-slate-900 px-3 py-2 text-xs font-semibold text-white hover:bg-slate-800">
              Search
            </button>
            <button onClick={handleReset}
              className="rounded-xl border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-500 hover:bg-slate-50">
              Reset
            </button>
          </div>

          {/* Top pagination */}
          <div className="border-b border-slate-100 px-5">
            <Pagination page={kbPage} pages={kbPages} total={kbTotal} pageSize={kbPageSize} onPage={goPage} />
          </div>

          {/* Cards grid */}
          <div className="p-5">
            {kbLoading ? (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="h-36 animate-pulse rounded-2xl bg-slate-100" />
                ))}
              </div>
            ) : kbSamples.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-slate-200 py-12 text-center">
                <Database size={28} className="mx-auto text-slate-300" />
                <p className="mt-3 text-sm font-medium text-slate-500">No evidence records found</p>
                <p className="mt-1 text-xs text-slate-400">Try adjusting your filters or search query</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {kbSamples.map((s, i) => <EvidenceCard key={s.id || i} item={s} />)}
              </div>
            )}
          </div>

          {/* Bottom pagination */}
          <div className="border-t border-slate-100 px-5">
            <Pagination page={kbPage} pages={kbPages} total={kbTotal} pageSize={kbPageSize} onPage={goPage} />
          </div>
        </div>

        {/* ══ Analytics Tabs ══ */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
          {/* Tab bar */}
          <div className="flex items-center gap-1 border-b border-slate-100 px-4 py-2">
            {TABS.map(t => (
              <button key={t.id} onClick={() => setActiveTab(t.id)}
                className={`inline-flex items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold transition ${
                  activeTab === t.id ? 'bg-slate-900 text-white' : 'text-slate-500 hover:bg-slate-100'
                }`}>
                <t.icon size={13} /> {t.label}
                {t.id === 'duplicates' && dupReport && dupReport.duplicates > 0 && (
                  <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-white text-xs">{dupReport.duplicates}</span>
                )}
              </button>
            ))}
          </div>

          <div className="p-5">
            {/* Overview tab */}
            {activeTab === 'overview' && (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {[
                  { label: 'Total Records',    value: kbTotal,                                  bg: 'bg-slate-50',    color: 'text-slate-900'   },
                  { label: 'Approved',         value: summary.approved_patterns ?? 0,           bg: 'bg-emerald-50',  color: 'text-emerald-700' },
                  { label: 'Rejected',         value: summary.rejected_patterns ?? 0,           bg: 'bg-red-50',      color: 'text-red-700'     },
                  { label: 'Indexed',          value: summary.indexed_evidences ?? 0,           bg: 'bg-sky-50',      color: 'text-sky-700'     },
                  { label: selectedNorm ? 'Rule Coverage' : 'Coverage',
                    value: selectedNorm && summary.total_rules > 0
                      ? `${summary.rules_covered ?? 0}/${summary.total_rules}`
                      : `${Math.round(summary.coverage ?? 0)}%`,
                                                                                                bg: 'bg-violet-50', color: 'text-violet-700' },
                  { label: 'Rules Covered',    value: summary.rules_covered ?? 0,              bg: 'bg-slate-50',    color: 'text-slate-900'   },
                ].map(k => (
                  <div key={k.label} className={`rounded-2xl border border-slate-100 ${k.bg} p-4`}>
                    <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">{k.label}</p>
                    <p className={`mt-2 text-3xl font-bold ${k.color}`}>{k.value}</p>
                  </div>
                ))}
              </div>
            )}

            {/* Analytics tab — données globales */}
            {activeTab === 'analytics' && (
              <AnalyticsTab normFilter={selectedNorm} />
            )}

            {/* Duplicates tab */}
            {activeTab === 'duplicates' && (
              <div className="space-y-4">
                {!dupReport && !dedupResult && (
                  <div className="rounded-2xl border border-dashed border-amber-200 bg-amber-50 py-10 text-center">
                    <AlertTriangle size={28} className="mx-auto text-amber-400" />
                    <p className="mt-3 text-sm font-semibold text-slate-700">No analysis run yet</p>
                    <p className="mt-1 text-xs text-slate-500">Click the button below to analyze duplicates</p>
                    <button onClick={handleAnalyzeDuplicates} disabled={dupLoading}
                      className="mt-4 inline-flex items-center gap-2 rounded-full bg-amber-500 px-5 py-2 text-xs font-semibold text-white hover:bg-amber-400 disabled:opacity-60">
                      <AlertTriangle size={13} /> {dupLoading ? 'Analyzing…' : 'Analyze Duplicates'}
                    </button>
                  </div>
                )}
                {dedupResult && (
                  <div className={`rounded-2xl border px-4 py-3 ${dedupResult.error ? 'border-rose-200 bg-rose-50' : 'border-emerald-200 bg-emerald-50'}`}>
                    {dedupResult.error ? (
                      <p className="text-sm font-semibold text-rose-700">✗ {dedupResult.error}</p>
                    ) : (
                      <>
                        <p className="text-sm font-semibold text-emerald-800">✓ {dedupResult.message}</p>
                        {dedupResult.index_rebuilt && <p className="mt-1 text-xs text-emerald-600">FAISS index rebuilt.</p>}
                      </>
                    )}
                  </div>
                )}
                {dupReport && (
                  <>
                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                      {[
                        { label: 'Total rows',       value: dupReport.total,            color: 'text-slate-900',   bg: 'bg-slate-50'   },
                        { label: 'Unique texts',      value: dupReport.unique,           color: 'text-emerald-700', bg: 'bg-emerald-50' },
                        { label: 'Duplicate rows',    value: dupReport.duplicates,       color: dupReport.duplicates > 0 ? 'text-red-700' : 'text-emerald-700', bg: dupReport.duplicates > 0 ? 'bg-red-50' : 'bg-emerald-50' },
                        { label: 'Duplication rate',  value: `${dupReport.duplication_rate}%`, color: dupReport.duplication_rate === 0 ? 'text-emerald-700' : 'text-red-700', bg: dupReport.duplication_rate === 0 ? 'bg-emerald-50' : 'bg-red-50' },
                      ].map(s => (
                        <div key={s.label} className={`rounded-2xl p-3 ${s.bg}`}>
                          <p className="text-xs font-medium text-slate-500">{s.label}</p>
                          <p className={`mt-1 text-2xl font-bold ${s.color}`}>{s.value}</p>
                        </div>
                      ))}
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${dupReport.status === 'clean' ? 'bg-emerald-100 text-emerald-700' : dupReport.status === 'warning' ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
                        {dupReport.status === 'clean' ? '✓ Dataset is clean' : dupReport.status === 'warning' ? '⚠ Minor duplicates' : '✗ High duplication'}
                      </span>
                      <span className="rounded-full bg-violet-50 px-3 py-1 text-xs font-medium text-violet-700">📚 {dupReport.vocabulary_size} unique words</span>
                      <span className="rounded-full bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">📏 avg {dupReport.avg_evidence_length} words</span>
                    </div>
                    <div className="overflow-x-auto rounded-2xl border border-slate-200">
                      <table className="min-w-full text-xs">
                        <thead className="bg-slate-50 text-slate-500 uppercase tracking-wider">
                          <tr>{['Rule','Total','Unique','Dupes','Rate','✓','✗'].map(h => <th key={h} className="px-3 py-2 text-left font-semibold">{h}</th>)}</tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {(dupReport.by_rule || []).map(r => (
                            <tr key={r.rule} className="hover:bg-slate-50">
                              <td className="px-3 py-2 font-medium text-slate-800 max-w-[160px] truncate">{r.rule}</td>
                              <td className="px-3 py-2 text-slate-600">{r.total}</td>
                              <td className="px-3 py-2 font-semibold text-emerald-700">{r.unique}</td>
                              <td className="px-3 py-2"><span className={`rounded-full px-2 py-0.5 font-semibold ${r.duplicates > 0 ? 'bg-red-100 text-red-700' : 'bg-emerald-100 text-emerald-700'}`}>{r.duplicates}</span></td>
                              <td className="px-3 py-2">
                                <div className="flex items-center gap-1.5">
                                  <div className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-200">
                                    <div className={`h-full rounded-full ${r.duplication_rate === 0 ? 'bg-emerald-500' : 'bg-red-500'}`} style={{ width: `${r.duplication_rate}%` }} />
                                  </div>
                                  <span>{r.duplication_rate}%</span>
                                </div>
                              </td>
                              <td className="px-3 py-2 text-emerald-700">{r.approved}</td>
                              <td className="px-3 py-2 text-red-700">{r.rejected}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <div className="flex gap-2">
                      {dupReport.duplicates > 0 ? (
                        <button onClick={handleDeduplicate} disabled={dedupLoading}
                          className="inline-flex items-center gap-2 rounded-full bg-red-600 px-4 py-2 text-xs font-semibold text-white hover:bg-red-500 disabled:opacity-60">
                          {dedupLoading ? 'Removing…' : `🗑 Remove ${dupReport.duplicates} duplicates`}
                        </button>
                      ) : <span className="rounded-full bg-emerald-100 px-4 py-2 text-xs font-semibold text-emerald-700">✓ No duplicates to remove</span>}
                      <button onClick={handleAnalyzeDuplicates} disabled={dupLoading}
                        className="rounded-full border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-60">
                        {dupLoading ? 'Analyzing…' : '↻ Re-analyze'}
                      </button>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* Semantic Memory tab */}
            {activeTab === 'semantic' && (
              <div className="grid gap-4 sm:grid-cols-2">
                {[
                  { label: 'Indexed Vectors',  value: summary.indexed_evidences ?? 0,                    icon: Database,    color: 'text-sky-700',    bg: 'bg-sky-50'    },
                  { label: 'Coverage',         value: `${Math.round(summary.coverage ?? 0)}%`,           icon: BarChart2,   color: 'text-violet-700', bg: 'bg-violet-50' },
                  { label: 'Embedding Model',  value: summary.embedding_model || 'tfidf-fallback',       icon: Brain,       color: 'text-slate-700',  bg: 'bg-slate-50'  },
                  { label: 'Last Training',    value: summary.last_trained ? fmt(summary.last_trained) : 'Never', icon: Clock, color: 'text-slate-700', bg: 'bg-slate-50' },
                  { label: 'Train Status',     value: summary.train_status || '—',                       icon: Zap,         color: summary.train_status === 'READY' ? 'text-emerald-700' : 'text-amber-700', bg: summary.train_status === 'READY' ? 'bg-emerald-50' : 'bg-amber-50' },
                  { label: 'Rules Covered',    value: summary.rules_covered ?? 0,                        icon: ShieldCheck, color: 'text-emerald-700', bg: 'bg-emerald-50' },
                ].map(s => (
                  <div key={s.label} className={`flex items-center gap-3 rounded-2xl border border-slate-100 ${s.bg} p-4`}>
                    <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white shadow-sm">
                      <s.icon size={18} className={s.color} />
                    </div>
                    <div>
                      <p className="text-xs font-medium text-slate-500">{s.label}</p>
                      <p className={`text-lg font-bold ${s.color}`}>{s.value}</p>
                    </div>
                  </div>
                ))}
                <div className="sm:col-span-2">
                  <button onClick={handleTrain} disabled={trainLoading}
                    className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-60">
                    <Zap size={15} /> {trainLoading ? 'Training…' : 'Rebuild Semantic Index'}
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>

      </div>

      {/* Analyze Document Modal */}
      <AnalyzeDocumentModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        norms={normOptions.map(n => ({ id: n.id || n.value, name: n.label || n.value }))}
        defaultNorm={
          selectedNorm
            ? (normOptions.find(n => n.value === selectedNorm)?.id || '')
            : (normOptions[0]?.id || '')
        }
      />
    </Layout>
  );
}
