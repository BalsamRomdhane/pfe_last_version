import React, { useEffect, useState } from 'react';
import { Search, Activity, Brain, X } from 'lucide-react';
import Layout from '../components/Layout';
import EmptyState from '../components/common/EmptyState';
import api from '../services/api';
/* ─── Score bar ────────────────────────────────────────────────────────── */
function ScoreBar({ value, max = 1, color = 'bg-brand-500' }) {
  const pct = Math.min(100, Math.max(0, (value / Math.max(max, 0.0001)) * 100));
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-1.5 rounded-full bg-slate-100 overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums text-slate-600 w-10 text-right">
        {(value * 100).toFixed(1)}%
      </span>
    </div>
  );
}

/* ─── Result row ───────────────────────────────────────────────────────── */
function ResultRow({ result, rank }) {
  const [expanded, setExpanded] = useState(false);

  const hybridPct = Math.round(result.hybrid_score * 100);
  const scoreColor =
    hybridPct >= 70 ? 'text-emerald-600' :
    hybridPct >= 40 ? 'text-amber-600'   : 'text-red-600';

  return (
    <div className="card overflow-hidden">
      {/* Header row */}
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        className="flex w-full items-center gap-4 p-4 text-left hover:bg-slate-50/60 transition-colors"
      >
        <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-500">
          {rank}
        </span>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-slate-900 truncate">
            {result.document_name || `Document #${result.document_id}`}
          </p>
          <p className="text-xs text-slate-500 mt-0.5">
            ID: {result.document_id} · {result.standard} · {result.status}
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <div className="text-right">
            <p className={`text-xl font-bold tabular-nums ${scoreColor}`}>{hybridPct}%</p>
            <p className="text-2xs text-slate-400">Hybrid</p>
          </div>
          <Activity size={14} className={`transition-transform ${expanded ? 'rotate-90' : ''} text-slate-400`} />
        </div>
      </button>

      {/* Expanded detail */}
      {expanded && (
        <div className="border-t border-slate-100 p-4 animate-fade-in">
          <div className="grid gap-4 sm:grid-cols-3 mb-4">
            {[
              { label: 'Semantic',  value: result.semantic_score,  color: 'bg-brand-500'   },
              { label: 'BM25',      value: result.bm25_score,      color: 'bg-violet-500'  },
              { label: 'Keywords',  value: result.keyword_score,   color: 'bg-emerald-500' },
            ].map(s => (
              <div key={s.label} className="rounded-lg bg-slate-50 px-3 py-2.5">
                <p className="text-2xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">{s.label}</p>
                <ScoreBar value={s.value} color={s.color} />
              </div>
            ))}
          </div>

          {/* Evidence */}
          {result.evidence?.length > 0 && (
            <div>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Rule Evidence</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {result.evidence.map((ev, i) => (
                  <div key={i} className="rounded-lg border border-slate-100 bg-white p-3">
                    <p className="text-xs font-semibold text-slate-700">{ev.rule}</p>
                    <p className="text-xs text-slate-400 mt-0.5">Keyword: {ev.keyword}</p>
                    {ev.snippet && (
                      <p className="mt-1.5 text-xs text-slate-600 italic truncate-2">{ev.snippet}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── SemanticSearch page ──────────────────────────────────────────────── */
export default function SemanticSearch() {
  const [query,      setQuery]     = useState('');
  const [standards,  setStandards] = useState([]);
  const [standard,   setStandard]  = useState('');
  const [topK,       setTopK]      = useState(5);
  const [results,    setResults]   = useState(null);
  const [loading,    setLoading]   = useState(false);
  const [error,      setError]     = useState(null);

  /* Load norms */
  useEffect(() => {
    api.get('/norms/').then(res => {
      const norms = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      const opts  = norms.map(n => ({ value: n.name, label: n.name }));
      setStandards(opts);
      if (opts.length > 0) setStandard(opts[0].value);
    }).catch(() => {
      setStandards([{ value: 'ISO9001', label: 'ISO 9001' }, { value: 'ISO27001', label: 'ISO 27001' }]);
      setStandard('ISO9001');
    });
  }, []);

  const handleSearch = async (e) => {
    e?.preventDefault();
    setError(null); setResults(null);
    if (!query.trim()) { setError('Please enter a search query.'); return; }
    setLoading(true);
    try {
      const res = await api.post('/semantic-search/', { query, standard, top_k: topK });
      setResults(res.data);
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.message || 'Search failed. Please try again.');
    } finally { setLoading(false); }
  };

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">AI / ML</p>
            <h1 className="page-title mt-1">Semantic Search</h1>
            <p className="page-subtitle">Hybrid ISO search — semantic similarity · BM25 · rule coverage.</p>
          </div>
        </div>

        {/* ── Search form ── */}
        <div className="card">
          <div className="card-body">
            <form onSubmit={handleSearch} className="space-y-4">
              {error && (
                <div className="alert alert-danger">
                  <span>{error}</span>
                  <button type="button" onClick={() => setError(null)} className="ml-auto"><X size={13}/></button>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-[1fr_200px_120px_auto]">
                {/* Query */}
                <div>
                  <label className="form-label">Search Query</label>
                  <div className="relative">
                    <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                    <input
                      type="text"
                      value={query}
                      onChange={e => setQuery(e.target.value)}
                      placeholder="Enter your compliance query…"
                      className="form-input pl-9"
                    />
                  </div>
                </div>

                {/* Standard */}
                <div>
                  <label className="form-label">Standard</label>
                  <select
                    value={standard}
                    onChange={e => setStandard(e.target.value)}
                    className="form-select"
                  >
                    {standards.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
                  </select>
                </div>

                {/* Top K */}
                <div>
                  <label className="form-label">Results</label>
                  <input
                    type="number"
                    min={1}
                    max={20}
                    value={topK}
                    onChange={e => setTopK(Number(e.target.value))}
                    className="form-input"
                  />
                </div>

                {/* Submit */}
                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={loading || !query.trim()}
                    className="btn-primary w-full justify-center"
                  >
                    {loading
                      ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"/>Searching…</>
                      : <><Search size={14}/>Search</>
                    }
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>

        {/* ── Summary pills ── */}
        {results && (
          <div className="grid grid-cols-3 gap-3">
            <div className="kpi-card">
              <p className="kpi-label">Results Found</p>
              <p className="kpi-value mt-2 text-brand-600">{results.results?.length ?? 0}</p>
            </div>
            <div className="kpi-card">
              <p className="kpi-label">Standard</p>
              <p className="text-lg font-bold text-slate-900 mt-2">{standard}</p>
            </div>
            <div className="kpi-card">
              <p className="kpi-label">Documents Available</p>
              <p className="kpi-value mt-2">{results.total_documents ?? '—'}</p>
            </div>
          </div>
        )}

        {/* ── Loading skeleton ── */}
        {loading && (
          <div className="space-y-3">
            {[1,2,3].map(i => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="flex items-center gap-4">
                  <div className="skeleton h-7 w-7 rounded-full shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="skeleton h-4 w-1/2" />
                    <div className="skeleton h-3 w-1/3" />
                  </div>
                  <div className="skeleton h-8 w-16 rounded-lg" />
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Results ── */}
        {!loading && results && (
          results.results?.length === 0 ? (
            <EmptyState
              icon={Search}
              title="No results found"
              description="Try a different query or select another standard."
            />
          ) : (
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <p className="text-sm font-semibold text-slate-700">
                  {results.results.length} result{results.results.length !== 1 ? 's' : ''} — ranked by hybrid score
                </p>
                <div className="flex items-center gap-3 text-2xs text-slate-400">
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-brand-500"/>Semantic</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-violet-500"/>BM25</span>
                  <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-emerald-500"/>Keywords</span>
                </div>
              </div>
              {results.results.map((item, i) => (
                <ResultRow key={item.document_id} result={item} rank={i + 1} />
              ))}
            </div>
          )
        )}

        {/* ── Empty initial state ── */}
        {!loading && !results && !error && (
          <EmptyState
            icon={Brain}
            title="Ready to search"
            description="Enter a compliance-related query and select a standard to find matching documents using hybrid semantic search."
          />
        )}
      </div>
    </Layout>
  );
}
