import React, { useEffect, useState } from 'react';
import {
  Search,
  Layers,
  ShieldCheck,
  UploadCloud,
  Brain,
  Sparkles,
} from 'lucide-react';
import Layout from '../components/Layout';
import api from '../services/api';
import AnalyzeDocumentModal from '../components/analysis/AnalyzeDocumentModal';

const formatDate = (value) => {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('en-GB', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

const StatisticCard = ({ label, value, accent }) => (
  <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/80 p-5">
    <p className="text-sm font-medium text-slate-500">{label}</p>
    <p className={`mt-3 text-3xl font-semibold tracking-tight ${accent ? accent : 'text-slate-900'}`}>{value}</p>
  </div>
);

export default function EvidenceIntelligence() {
  const [summary, setSummary] = useState({});
  const [summaryLoading, setSummaryLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [normFilter, setNormFilter] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [resultsLoading, setResultsLoading] = useState(false);
  const [searchError, setSearchError] = useState(null);
  const [expandedId, setExpandedId] = useState(null);
  const [trainLoading, setTrainLoading] = useState(false);
  const [trainStatus, setTrainStatus] = useState(null);
  const [analysisFile, setAnalysisFile] = useState(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisResults, setAnalysisResults] = useState(null);
  const [kbSamples, setKbSamples] = useState([]);
  const [ruleFilter, setRuleFilter] = useState('');
  const [decisionFilter, setDecisionFilter] = useState('');
  const [reviewerFilter, setReviewerFilter] = useState('');
  const [normOptions, setNormOptions] = useState([]);
  const [modalOpen, setModalOpen] = useState(false);

  // Load norms from API on mount
  useEffect(() => {
    const loadNorms = async () => {
      try {
        const res = await api.get('norms/');
        const norms = Array.isArray(res.data) ? res.data : res.data?.results || [];
        if (norms.length > 0) {
          const options = norms.map((n) => ({ value: n.name, label: n.name, id: n.id }));
          setNormOptions(options);
          setNormFilter(options[0].value);
        }
      } catch {
        // fallback to static options
        setNormOptions([
          { value: 'ISO9001', label: 'ISO 9001' },
          { value: 'ISO27001', label: 'ISO 27001' },
        ]);
      }
    };
    loadNorms();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const loadSummary = async () => {
    setSummaryLoading(true);
    try {
      // Load persisted index metadata
      const statusResp = await api.get('evidence/status/');
      const meta = statusResp.data || {};
      const total = meta.total_evidences ?? 0;
      const indexed = meta.indexed_evidences ?? 0;
      const coverage = meta.coverage_percent ?? (total > 0 ? Math.round((indexed / total) * 100) : 0);

      setSummary({
        total_evidences: total,
        indexed_evidences: indexed,
        rules_covered: meta.rules_covered ?? 0,
        rejected_patterns: meta.rejected_patterns ?? meta.invalid_samples ?? 0,
        approved_patterns: meta.approved_patterns ?? meta.valid_samples ?? 0,
        coverage: coverage,
        embedding_model: meta.embedding_model || 'tfidf-fallback',
        last_trained: meta.last_trained || null,
        top_rejected_rules: [],
        top_evidence_patterns: [],
        top_recommendations: [],
      });

      // Load knowledge base from the canonical endpoint
      try {
        const kbResp = await api.get('rule-memory/?page_size=100');
        const kbData = kbResp.data || {};
        // rule-memory returns {total, page, page_size, items[]}
        const samples = Array.isArray(kbData.items)
          ? kbData.items
          : Array.isArray(kbData)
          ? kbData
          : [];
        setKbSamples(samples);
        setSearchResults(samples);
      } catch (err) {
        // fallback to rule-training-samples if rule-memory not available
        try {
          const samplesResp = await api.get('rule-training-samples/?page_size=100');
          const samplesData = samplesResp.data?.results || samplesResp.data || [];
          setKbSamples(Array.isArray(samplesData) ? samplesData : []);
          setSearchResults(Array.isArray(samplesData) ? samplesData : []);
        } catch (err2) {
          setKbSamples([]);
          setSearchResults([]);
        }
      }
    } catch (error) {
      console.error('Failed to load evidence memory summary:', error);
    } finally {
      setSummaryLoading(false);
    }
  };

  useEffect(() => {
    loadSummary();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const statistics = [
    { label: 'Total evidences', value: summary.total_evidences ?? 0 },
    { label: 'Indexed evidences', value: summary.indexed_evidences ?? 0 },
    { label: 'Rules covered', value: summary.rules_covered ?? 0 },
    { label: 'Embedding model', value: summary.embedding_model || 'all-MiniLM-L6-v2', accent: 'text-slate-900' },
    { label: 'Coverage %', value: `${Math.round(summary.coverage ?? 0)}%` },
    { label: 'Rejected patterns', value: summary.rejected_patterns ?? 0 },
    { label: 'Approved patterns', value: summary.approved_patterns ?? 0 },
  ];

  const handleSearch = async (event) => {
    event.preventDefault();
    // Server-side semantic search using persisted FAISS index
    setResultsLoading(true);
    try {
      const resp = await api.post('search-evidence/', {
        query: searchQuery,
        norm_id: null,
        top_k: 10,
      });
      const data = resp.data || {};
      setSearchResults(Array.isArray(data.results) ? data.results : []);
    } catch (err) {
      console.error('Search failed', err);
      setSearchResults([]);
    } finally {
      setResultsLoading(false);
    }
  };

  const handleTrain = async () => {
    setTrainLoading(true);
    setTrainStatus({ step: 'building', message: 'Building semantic memory...' });
    try {
      // trigger server-side build/persist
      setTrainStatus({ step: 'indexing', message: 'Indexing evidences...' });
      const resp = await api.post('evidence/index/', { standard: normFilter });
      const payload = resp.data || {};
      setTrainStatus({ step: 'complete', message: 'Index built' });
      // refresh metadata
      await loadSummary();
    } catch (err) {
      console.error('Evidence index error', err);
      setTrainStatus({ step: 'error', message: err?.response?.data?.error || err.message || 'Indexing failed' });
    } finally {
      setTrainLoading(false);
    }
  };

  const handleAnalyzeDocument = async () => {
    if (!analysisFile) {
      setSearchError('Veuillez sélectionner un fichier PDF ou DOCX à analyser.');
      return;
    }

    setAnalysisLoading(true);
    setAnalysisResults(null);
    setSearchError(null);

    try {
      const formData = new FormData();
      formData.append('file', analysisFile);
      formData.append('standard', normFilter);

      const response = await api.post('compliance/analyze/', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setAnalysisResults(response.data || {});
    } catch (error) {
      console.error('Analyze document error:', error);
      setSearchError(error.response?.data?.detail || error.response?.data?.message || 'Impossible d’analyser le document.');
    } finally {
      setAnalysisLoading(false);
    }
  };

  const toggleExpand = (id) => {
    setExpandedId((current) => (current === id ? null : id));
  };

  const noIndexedData = !summaryLoading && (summary.indexed_evidences ?? 0) === 0;

  const ruleOptions = Array.from(new Set(kbSamples.map((s) => s.rule).filter(Boolean)));
  const reviewerOptions = Array.from(new Set(kbSamples.map((s) => s.reviewer || s.reviewer_name).filter(Boolean)));
  const decisionOptions = Array.from(new Set(kbSamples.map((s) => s.decision).filter(Boolean)));

  const filteredSamples = kbSamples.filter((s) => {
    if (ruleFilter && s.rule !== ruleFilter) return false;
    if (decisionFilter && s.decision !== decisionFilter) return false;
    if (reviewerFilter && (s.reviewer !== reviewerFilter && s.reviewer_name !== reviewerFilter)) return false;
    return true;
  });

  // Analytics derived from real KB samples
  const mostRejectedRule = (() => {
    const counts = {};
    kbSamples.forEach((s) => {
      const label = (s.label || s.decision || '').toString().toLowerCase();
      if (label === 'rejected' || label === 'rejeted') {
        const rule = s.rule || s.rule_title || 'unknown';
        counts[rule] = (counts[rule] || 0) + 1;
      }
    });
    const pairs = Object.entries(counts);
    if (pairs.length === 0) return null;
    pairs.sort((a, b) => b[1] - a[1]);
    return { rule: pairs[0][0], count: pairs[0][1] };
  })();

  const mostCommonEvidence = (() => {
    const counts = {};
    kbSamples.forEach((s) => {
      const txt = (s.evidence_text || s.evidence || '').toString().trim();
      if (txt) counts[txt] = (counts[txt] || 0) + 1;
    });
    const pairs = Object.entries(counts);
    if (pairs.length === 0) return null;
    pairs.sort((a, b) => b[1] - a[1]);
    return { text: pairs[0][0], count: pairs[0][1] };
  })();

  const mostCommonRecommendation = (() => {
    const counts = {};
    kbSamples.forEach((s) => {
      const rec = (s.recommendation || '').toString().trim();
      if (rec) counts[rec] = (counts[rec] || 0) + 1;
    });
    const pairs = Object.entries(counts);
    if (pairs.length === 0) return null;
    pairs.sort((a, b) => b[1] - a[1]);
    return { rec: pairs[0][0], count: pairs[0][1] };
  })();

  const reviewerPatterns = (() => {
    const map = {};
    kbSamples.forEach((s) => {
      const reviewer = s.reviewer || s.reviewer_name || 'unknown';
      if (!map[reviewer]) map[reviewer] = { approved: 0, rejected: 0, pending: 0 };
      const label = (s.label || s.decision || '').toString().toLowerCase();
      if (label === 'approved') map[reviewer].approved += 1;
      else if (label === 'rejected') map[reviewer].rejected += 1;
      else map[reviewer].pending += 1;
    });
    return map;
  })();

  return (
    <Layout>
      <div className="w-full bg-slate-50 px-8 pb-8 pt-6 2xl:px-12">
        <section className="mb-4 rounded-[1.5rem] border border-slate-200 bg-slate-950 px-6 py-5 shadow-sm text-white">
          <div className="grid gap-4 lg:grid-cols-[2fr_1fr] lg:items-center">
            <div>
              <p className="text-xs uppercase tracking-[0.35em] text-slate-400">Evidence Intelligence</p>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">Enterprise semantic memory</h1>
              <p className="mt-2 max-w-2xl text-sm text-slate-300">A modern AI knowledge base built from TeamLead evidence, reviewer reasoning and recommendations.</p>
            </div>
            <div className="flex flex-wrap items-center justify-end gap-3">
              <button onClick={async () => { setSummaryLoading(true); await loadSummary(); }} className="rounded-full border border-slate-700 bg-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/15">Refresh index</button>
              <button className="rounded-full border border-slate-700 bg-white/10 px-4 py-2 text-sm text-white transition hover:bg-white/15">Export dataset</button>
              <button
                onClick={() => setModalOpen(true)}
                className="inline-flex items-center gap-2 rounded-full bg-gradient-to-r from-sky-500 to-violet-600 px-4 py-2 text-sm font-semibold text-white shadow-lg shadow-sky-500/25 transition hover:from-sky-400 hover:to-violet-500"
              >
                <Brain size={15} />
                Analyze document
                <Sparkles size={12} className="opacity-70" />
              </button>
            </div>
          </div>
        </section>

        <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          {statistics.map((stat) => (
            <StatisticCard key={stat.label} label={stat.label} value={stat.value} accent={stat.accent} />
          ))}
        </section>

        <section className="sticky top-4 z-30 rounded-[1.5rem] border border-slate-200 bg-white/95 p-5 shadow-sm backdrop-blur-sm">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-slate-900">AI search</p>
              <p className="mt-1 text-sm text-slate-500">Search evidence, comments or rule names in the semantic memory index.</p>
            </div>
            <div className="flex w-full flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:w-[760px]">
              <div className="flex items-center gap-3">
                <span className="text-sm font-medium text-slate-500">Standard</span>
                <select
                  value={normFilter}
                  onChange={(event) => setNormFilter(event.target.value)}
                  className="rounded-full border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none shadow-sm transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
                >
                  {normOptions.map((norm) => (
                    <option key={norm.value} value={norm.value}>{norm.label}</option>
                  ))}
                </select>
              </div>
              <div className="flex flex-1 items-center gap-3">
                <Search className="h-5 w-5 text-slate-400" />
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="Search evidence..."
                  className="w-full rounded-full border border-slate-300 bg-white px-5 py-3 text-sm text-slate-900 outline-none shadow-sm transition focus:border-sky-500 focus:ring-4 focus:ring-sky-100"
                />
              </div>
              <button
                type="button"
                onClick={handleSearch}
                disabled={resultsLoading}
                className="rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {resultsLoading ? 'Searching…' : 'Search'}
              </button>
            </div>
          </div>

          <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
            {['Version document absente', 'Règle non appliquée', 'Commentaire manquant', 'Demande d’amélioration'].map((item) => (
              <button key={item} type="button" onClick={() => setSearchQuery(item)} className="rounded-full border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 transition hover:bg-slate-100">
                {item}
              </button>
            ))}
          </div>
        </section>

        {/* do not show generic 'no matches' placeholders for search; rely on results rendering */}

        {noIndexedData && (
          <section className="mt-4 rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col items-center gap-4 text-center">
              <div className="flex h-16 w-16 items-center justify-center rounded-3xl bg-slate-100 text-slate-700">
                <Layers size={28} />
              </div>
              <div>
                <p className="text-lg font-semibold text-slate-900">No semantic memory available</p>
                <p className="mt-2 text-sm text-slate-500">Train the evidence dataset first to unlock similar cases and recommendations.</p>
              </div>
              <button onClick={handleTrain} className="rounded-full bg-slate-900 px-6 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
                Train memory
              </button>
            </div>
          </section>
        )}

        <div className="mt-4 grid gap-4 xl:grid-cols-[2fr_350px]">
          <main className="space-y-4">
            <section className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
              <div className="grid gap-4 sm:grid-cols-4">
                <div className="rounded-3xl bg-slate-50 p-4 shadow-sm">
                  <p className="text-sm font-semibold text-slate-500">Indexed evidence</p>
                  <p className="mt-3 text-3xl font-semibold text-slate-900">{summary.indexed_evidences ?? 0}</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 shadow-sm">
                  <p className="text-sm font-semibold text-slate-500">Coverage</p>
                  <p className="mt-3 text-3xl font-semibold text-slate-900">{Math.round(summary.coverage ?? 0)}%</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 shadow-sm">
                  <p className="text-sm font-semibold text-slate-500">Embedding model</p>
                  <p className="mt-3 text-3xl font-semibold text-slate-900">{summary.embedding_model || 'all-MiniLM-L6-v2'}</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 shadow-sm">
                  <p className="text-sm font-semibold text-slate-500">Train status</p>
                  <p className="mt-3 text-3xl font-semibold text-slate-900">{(summary.indexed_evidences ?? 0) > 0 ? (trainStatus?.success ? 'TRAINED' : 'READY') : 'NOT INDEXED'}</p>
                </div>
              </div>
            </section>

            <section className="grid gap-4 sm:grid-cols-2">
              {searchResults.length > 0 ? searchResults.map((item) => {
                  const isKb = !!(item.evidence_text || item.reviewer_comment || item.recommendation || item.rule || item.label);
                  const title = (item.rule || item.rule_title) || '-';
                  const evidenceText = (item.evidence_text || item.evidence || '').toString();
                  const badge = (item.label || item.decision || '').toString() || '-';
                  const reviewer = item.reviewer || item.reviewer_name || item.reviewer_comment || '-';
                  const date = formatDate(item.updated_at || item.created_at);
                  const similarity = item.similarity || item.semantic_score ? Math.round((item.similarity || item.semantic_score) * 100) : null;

                  return (
                    <div key={item.id || (item.rule || '') + (item.evidence_text || '') + Math.random()} className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex flex-col gap-4">
                        <div className="flex items-start justify-between gap-4">
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-slate-900">{title}</p>
                            <p className="mt-2 text-sm text-slate-500 line-clamp-2">{evidenceText || '-'}</p>
                          </div>
                          <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${badge === 'approved' ? 'bg-emerald-100 text-emerald-700' : badge === 'rejected' ? 'bg-rose-100 text-rose-700' : 'bg-amber-100 text-amber-700'}`}>
                            {badge}
                          </span>
                        </div>

                        {similarity !== null && (
                          <div className="space-y-3">
                            <div className="flex items-center justify-between text-sm text-slate-600">
                              <span>Similarity</span>
                              <span className="font-semibold text-slate-900">{similarity}%</span>
                            </div>
                            <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                              <div className={`h-full rounded-full ${similarity >= 80 ? 'bg-emerald-500' : similarity >= 50 ? 'bg-amber-500' : 'bg-rose-500'}`} style={{ width: `${similarity}%` }} />
                            </div>
                          </div>
                        )}

                        <div className="grid gap-3 sm:grid-cols-2">
                          <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-700 shadow-sm">
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Reviewer</p>
                            <p className="mt-2 font-medium text-slate-900">{reviewer || '-'}</p>
                          </div>
                          <div className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-700 shadow-sm">
                            <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Date</p>
                            <p className="mt-2 font-medium text-slate-900">{date}</p>
                          </div>
                        </div>

                        <button
                          type="button"
                          onClick={() => toggleExpand(item.id || item.rule)}
                          className="inline-flex items-center justify-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                        >
                          {expandedId === (item.id || item.rule) ? 'Collapse details' : 'Expand details'}
                        </button>

                        {expandedId === (item.id || item.rule) && (
                          <div className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-4">
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Comment</p>
                              <p className="mt-2 text-sm text-slate-700 whitespace-pre-line">{item.reviewer_comment || item.comment || '-'}</p>
                            </div>
                            <div>
                              <p className="text-sm font-semibold text-slate-900">Recommendation</p>
                              <p className="mt-2 text-sm text-slate-700 whitespace-pre-line">{item.recommendation || '-'}</p>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                }) : (
                  <div className="col-span-full rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
                    {/* empty results (no UI placeholder message per requirements) */}
                  </div>
                )}
            </section>
          </main>

          <aside className="space-y-4">
            <div className="w-full max-w-[350px] rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-slate-900">Semantic Memory</p>
                  <p className="mt-1 text-sm text-slate-500">Knowledge base health snapshot.</p>
                </div>
                <UploadCloud size={20} className="text-slate-500" />
              </div>

              <div className="mt-6 space-y-4">
                <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Indexed vectors</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">{summary.indexed_evidences ?? 0}</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Coverage</p>
                  <p className="mt-2 text-3xl font-semibold text-slate-900">{Math.round(summary.coverage ?? 0)}%</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Embedding model</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.embedding_model || 'all-MiniLM-L6-v2'}</p>
                </div>
                <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
                  <p className="text-xs uppercase tracking-[0.15em] text-slate-400">Last training</p>
                  <p className="mt-2 text-2xl font-semibold text-slate-900">{summary.last_trained || 'N/A'}</p>
                </div>
              </div>

              <button
                type="button"
                onClick={handleTrain}
                disabled={trainLoading}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {trainLoading ? 'Training…' : 'Train semantic memory'}
              </button>
            </div>

            <div className="w-full max-w-[350px] rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-semibold text-slate-900">Analyze document</p>
                  <p className="mt-1 text-sm text-slate-500">Drag and drop a PDF or DOCX to search similar evidence.</p>
                </div>
                <Search size={20} className="text-slate-500" />
              </div>

              <div className="mt-6 rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
                <p className="mb-3 text-base font-semibold text-slate-900">Upload PDF / DOCX</p>
                <p>Drag & drop your file or select one below.</p>
                {analysisFile && (
                  <p className="mt-4 rounded-2xl bg-white px-3 py-2 text-sm text-slate-700 shadow-sm">{analysisFile.name}</p>
                )}
                <input
                  type="file"
                  accept=".pdf,.doc,.docx"
                  onChange={(event) => setAnalysisFile(event.target.files?.[0] || null)}
                  className="mt-4 w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 outline-none"
                />
              </div>

              <button
                type="button"
                onClick={handleAnalyzeDocument}
                disabled={analysisLoading}
                className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {analysisLoading ? 'Analyzing…' : 'Analyze document'}
              </button>

              {analysisResults && (
                <div className="mt-4 rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
                  <p className="font-semibold text-slate-900">Detected matches</p>
                  {Array.isArray(analysisResults) ? (
                    <p className="mt-2">{analysisResults.length} similar evidence cases found.</p>
                  ) : (
                    <pre className="mt-2 max-h-48 overflow-auto whitespace-pre-wrap text-xs text-slate-700">{JSON.stringify(analysisResults, null, 2)}</pre>
                  )}
                </div>
              )}
            </div>
          </aside>
        </div>

        <section className="rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-lg font-semibold text-slate-900">Knowledge base</p>
              <p className="mt-1 text-sm text-slate-500">Browse stored evidence samples and filter by rule, decision or reviewer.</p>
            </div>
            <div className="flex items-center gap-2">
              <select value={ruleFilter} onChange={(e) => setRuleFilter(e.target.value)} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm">
                <option value="">All rules</option>
                {ruleOptions.map((r) => (<option key={r} value={r}>{r}</option>))}
              </select>
              <select value={decisionFilter} onChange={(e) => setDecisionFilter(e.target.value)} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm">
                <option value="">All decisions</option>
                {decisionOptions.map((d) => (<option key={d} value={d}>{d}</option>))}
              </select>
              <select value={reviewerFilter} onChange={(e) => setReviewerFilter(e.target.value)} className="rounded-full border border-slate-200 bg-white px-3 py-2 text-sm">
                <option value="">All reviewers</option>
                {reviewerOptions.map((r) => (<option key={r} value={r}>{r}</option>))}
              </select>
            </div>
          </div>

          <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {filteredSamples && filteredSamples.length > 0 ? filteredSamples.slice(0, 6).map((s, idx) => (
              <div key={s.id || idx} className="rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                      <p className="text-sm font-semibold text-slate-900">{s.rule || s.rule_title || '-'}</p>
                      <p className="mt-2 text-sm text-slate-500 line-clamp-2">{(s.evidence_text || s.evidence) ? (s.evidence_text || s.evidence) : '-'}</p>
                  </div>
                  <span className="text-xs font-semibold text-slate-600">{s.decision || '—'}</span>
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-slate-600">
                  <span>{s.reviewer || s.reviewer_name || '-'}</span>
                  <span className="font-medium text-slate-900">{formatDate(s.updated_at || s.created_at)}</span>
                </div>
              </div>
            )) : (
              <div className="col-span-full rounded-[1.5rem] border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-sm text-slate-500">
                {/* If there are training samples they will be shown; otherwise this area remains minimal. */}
                {kbSamples.length === 0 && 'No knowledge base samples available.'}
              </div>
            )}
          </div>
        </section>

        <section className="rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div>
              <p className="text-lg font-semibold text-slate-900">Pattern analytics</p>
              <p className="mt-1 text-sm text-slate-500">Computed from the knowledge base samples.</p>
            </div>
            <span className="inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
              <ShieldCheck size={16} /> Evidence trends
            </span>
          </div>

          <div className="mt-6 grid gap-4 md:grid-cols-3">
            <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Most rejected rule</p>
              <p className="mt-3 text-3xl font-semibold text-slate-900">{mostRejectedRule ? mostRejectedRule.rule : '-'}</p>
              <p className="mt-1 text-sm text-slate-500">{mostRejectedRule ? `${mostRejectedRule.count} occurrences` : 'No data'}</p>
            </div>
            <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Most common evidence</p>
              <p className="mt-3 text-3xl font-semibold text-slate-900">{mostCommonEvidence ? (mostCommonEvidence.text.length > 60 ? `${mostCommonEvidence.text.slice(0, 57)}...` : mostCommonEvidence.text) : '-'}</p>
              <p className="mt-1 text-sm text-slate-500">{mostCommonEvidence ? `${mostCommonEvidence.count} occurrences` : 'No data'}</p>
            </div>
            <div className="rounded-3xl bg-slate-50 p-4 text-sm text-slate-700 shadow-sm">
              <p className="text-xs uppercase tracking-[0.18em] text-slate-400">Top recommendation</p>
              <p className="mt-3 text-3xl font-semibold text-slate-900">{mostCommonRecommendation ? (mostCommonRecommendation.rec.length > 60 ? `${mostCommonRecommendation.rec.slice(0, 57)}...` : mostCommonRecommendation.rec) : '-'}</p>
              <p className="mt-1 text-sm text-slate-500">{mostCommonRecommendation ? `${mostCommonRecommendation.count} occurrences` : 'No data'}</p>
            </div>
          </div>

          <div className="mt-6">
            <p className="text-sm font-semibold text-slate-900">Reviewer patterns</p>
            <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {Object.keys(reviewerPatterns).length === 0 ? (
                <div className="col-span-full text-sm text-slate-500">No reviewer data available.</div>
              ) : (
                Object.entries(reviewerPatterns).map(([name, counts]) => {
                  const displayName = name === 'unknown' ? '-' : name;
                  return (
                    <div key={name} className="rounded-2xl bg-slate-50 p-3 text-sm text-slate-700 shadow-sm">
                      <p className="font-medium text-slate-900">{displayName}</p>
                      <p className="text-xs text-slate-500">Approved: {counts.approved} • Rejected: {counts.rejected} • Pending: {counts.pending}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </section>
      </div>

      {/* AI Analyze Document Modal */}
      <AnalyzeDocumentModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        norms={normOptions.map((n) => ({ id: n.id || n.value, name: n.label || n.value }))}
        defaultNorm={normOptions[0]?.id || normOptions[0]?.value || ''}
      />
    </Layout>
  );
}
