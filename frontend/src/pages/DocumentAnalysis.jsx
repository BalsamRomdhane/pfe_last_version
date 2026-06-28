import React, { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, UploadCloud, ScanSearch, X, AlertCircle } from 'lucide-react';
import Layout from '../components/Layout';
import SeverityBadge from '../components/SeverityBadge';
import EmptyState from '../components/common/EmptyState';
import api from '../services/api';

/* ─── Score card ───────────────────────────────────────────────────────── */
function ScoreCard({ label, value, color, suffix = '%' }) {
  const num = Number(value) || 0;
  const barColor =
    num >= 80 ? 'bg-emerald-500' :
    num >= 60 ? 'bg-amber-500'   : 'bg-red-500';

  return (
    <div className="kpi-card">
      <p className="kpi-label">{label}</p>
      <p className={`kpi-value mt-2 ${color}`}>{num}{suffix}</p>
      <div className="mt-3 progress-track">
        <div className={`progress-bar ${barColor}`} style={{ width: `${Math.min(100, num)}%` }} />
      </div>
    </div>
  );
}

/* ─── Detected rule card ───────────────────────────────────────────────── */
function RuleResult({ rule, index }) {
  const [open, setOpen] = useState(false);

  return (
    <div className={`rounded-xl border transition-all ${rule.is_valid ? 'border-emerald-100 bg-emerald-50/30' : 'border-red-100 bg-red-50/20'}`}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${rule.is_valid ? 'bg-emerald-100' : 'bg-red-100'}`}>
          {rule.is_valid
            ? <CheckCircle2 size={14} className="text-emerald-600" />
            : <XCircle     size={14} className="text-red-600"     />
          }
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-slate-900">{rule.title}</p>
            <SeverityBadge severity={rule.severity} />
          </div>
          {rule.evidence && (
            <p className="mt-0.5 text-xs text-slate-500 truncate">Evidence: {rule.evidence}</p>
          )}
        </div>
        <span className={`badge shrink-0 ${rule.is_valid ? 'badge-green' : 'badge-red'}`}>
          {rule.is_valid ? 'Valid' : 'Invalid'}
        </span>
      </button>

      {open && (
        <div className="border-t border-slate-100 px-4 pb-4 pt-3 space-y-2 animate-fade-in">
          {rule.description && <p className="text-xs text-slate-600">{rule.description}</p>}
          {rule.condition && (
            <div className="rounded-lg bg-slate-50 px-3 py-2">
              <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-1">Condition</p>
              <p className="text-xs text-slate-700">{rule.condition}</p>
            </div>
          )}
          {rule.evidence && (
            <div className="rounded-lg bg-white border border-slate-200 px-3 py-2">
              <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-1">Evidence detected</p>
              <p className="text-xs text-slate-700">{rule.evidence}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── DocumentAnalysis page ────────────────────────────────────────────── */
export default function DocumentAnalysis() {
  const [normes,          setNormes]          = useState([]);
  const [selectedNormeId, setSelectedNormeId] = useState(null);
  const [file,            setFile]            = useState(null);
  const [analysis,        setAnalysis]        = useState(null);
  const [loading,         setLoading]         = useState(false);
  const [error,           setError]           = useState('');

  useEffect(() => {
    api.get('/normes/').then(res => {
      const data = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setNormes(data);
      if (data.length > 0) setSelectedNormeId(data[0].id);
    }).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setAnalysis(null);
    if (!file)            return setError('Please select a PDF or DOCX file.');
    if (!selectedNormeId) return setError('Please select a standard.');

    const formData = new FormData();
    formData.append('file', file);
    formData.append('norme_id', selectedNormeId);

    setLoading(true);
    try {
      const res = await api.post('/extract-features/', formData);
      setAnalysis(res.data);
    } catch (err) {
      setError(
        err?.response?.data?.file    ||
        err?.response?.data?.norme_id||
        err?.response?.data?.detail  ||
        JSON.stringify(err?.response?.data) ||
        'Unable to analyze the document.'
      );
    } finally { setLoading(false); }
  };

  const validCount   = analysis?.valid_count   || 0;
  const invalidCount = analysis?.invalid_count || 0;
  const totalRules   = analysis?.total_rules   || 0;

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Compliance</p>
            <h1 className="page-title mt-1">Document Analysis</h1>
            <p className="page-subtitle">
              Upload a PDF or DOCX and identify rule-specific compliance evidence automatically.
            </p>
          </div>
          {/* Stats pills */}
          <div className="flex items-center gap-3 flex-wrap">
            <div className="card flex items-center gap-2 px-4 py-2.5 text-sm">
              <ScanSearch size={14} className="text-brand-500" />
              <span className="text-slate-600 font-medium">
                {normes.length > 0
                  ? normes.find(n => n.id === selectedNormeId)?.name || 'Select a standard'
                  : 'No standards'}
              </span>
            </div>
            <div className="card px-4 py-2.5 text-sm text-slate-600">
              <span className="font-medium">{file?.name || 'No file selected'}</span>
            </div>
            {analysis && (
              <div className="card px-4 py-2.5 text-sm">
                <span className="font-bold text-slate-900">{totalRules}</span>
                <span className="text-slate-500 ml-1">rules detected</span>
              </div>
            )}
          </div>
        </div>

        {/* ── Upload form ── */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Analysis Configuration</h2>
          </div>
          <div className="card-body">
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="alert alert-danger">
                  <AlertCircle size={14} className="shrink-0" />
                  <span>{error}</span>
                  <button type="button" onClick={() => setError('')} className="ml-auto"><X size={13}/></button>
                </div>
              )}

              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-[1fr_1fr_auto]">
                {/* Standard selector */}
                <div>
                  <label className="form-label">Standard</label>
                  <select
                    value={selectedNormeId || ''}
                    onChange={e => setSelectedNormeId(Number(e.target.value))}
                    disabled={normes.length === 0}
                    className="form-select"
                  >
                    {normes.length > 0
                      ? normes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)
                      : <option value="">No standards available</option>
                    }
                  </select>
                </div>

                {/* File picker */}
                <div>
                  <label className="form-label">Document</label>
                  <div className="relative rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 cursor-pointer hover:bg-slate-100 transition-colors">
                    <div className="flex items-center gap-2 text-sm text-slate-600">
                      <UploadCloud size={15} className="text-slate-400 shrink-0" />
                      <span className="truncate">{file?.name || 'Choose a PDF or DOCX file'}</span>
                    </div>
                    <input
                      type="file"
                      accept=".pdf,.docx"
                      onChange={e => { setFile(e.target.files?.[0] || null); setAnalysis(null); }}
                      className="absolute inset-0 h-full w-full opacity-0 cursor-pointer"
                    />
                  </div>
                </div>

                {/* Submit */}
                <div className="flex items-end">
                  <button
                    type="submit"
                    disabled={!file || !selectedNormeId || loading}
                    className="btn-primary w-full justify-center"
                  >
                    {loading ? (
                      <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"/>Analyzing…</>
                    ) : (
                      <><ScanSearch size={14}/>Analyze</>
                    )}
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>

        {/* ── Loading ── */}
        {loading && (
          <div className="card p-8">
            <div className="flex flex-col items-center gap-4">
              <div className="relative flex h-16 w-16 items-center justify-center">
                <div className="absolute inset-0 rounded-full border-4 border-slate-100" />
                <div className="absolute inset-0 rounded-full border-4 border-t-brand-600 animate-spin" />
                <ScanSearch size={20} className="text-brand-600" />
              </div>
              <div className="text-center">
                <p className="text-sm font-semibold text-slate-900">Analyzing document…</p>
                <p className="text-xs text-slate-500 mt-1">Extracting compliance features and matching rules</p>
              </div>
            </div>
          </div>
        )}

        {/* ── Results ── */}
        {analysis && !loading && (
          <div className="space-y-5 animate-fade-in">

            {/* Score grid */}
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <ScoreCard
                label="Compliance Score"
                value={analysis.compliance}
                color={analysis.compliance >= 80 ? 'text-emerald-600' : analysis.compliance >= 60 ? 'text-amber-600' : 'text-red-600'}
              />
              <ScoreCard label="ML Confidence"   value={analysis.confidence_score || 0}  color="text-violet-600" />
              <ScoreCard label="Semantic Score"  value={analysis.similarity_score  || 0}  color="text-brand-600"  />
            </div>

            {/* Rule counts */}
            <div className="grid grid-cols-3 gap-3">
              <div className="kpi-card bg-emerald-50 border-emerald-200">
                <p className="kpi-label text-emerald-700">Valid Rules</p>
                <p className="text-3xl font-bold text-emerald-600 mt-2 tabular-nums">{validCount}</p>
              </div>
              <div className="kpi-card bg-red-50 border-red-200">
                <p className="kpi-label text-red-700">Invalid Rules</p>
                <p className="text-3xl font-bold text-red-600 mt-2 tabular-nums">{invalidCount}</p>
              </div>
              <div className="kpi-card">
                <p className="kpi-label">Total Rules</p>
                <p className="kpi-value mt-2">{totalRules}</p>
              </div>
            </div>

            {/* Status badges */}
            <div className="card card-body flex flex-wrap items-center gap-2">
              <span className={`badge ${analysis.compliance >= 80 ? 'badge-green' : analysis.compliance >= 60 ? 'badge-amber' : 'badge-red'}`}>
                {analysis.compliance >= 80 ? 'Compliant' : analysis.compliance >= 60 ? 'Partially compliant' : 'Non-compliant'}
              </span>
              <span className="badge badge-slate">Status: {analysis.document_status || 'pending'}</span>
              <span className={`badge ${analysis.automation_ready ? 'badge-green' : 'badge-amber'}`}>
                {analysis.automation_ready ? 'Auto-approval eligible' : 'Manual review recommended'}
              </span>
              {analysis.confidence_score > 0 && (
                <span className="badge badge-purple">Confidence: {analysis.confidence_score}%</span>
              )}
            </div>

            {/* Internal diagnostics */}
            {(analysis.rule_score || analysis.structure_score || analysis.clarity_score) && (
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Internal Diagnostics</h2>
                  <span className="badge badge-slate">Model interpretation scores</span>
                </div>
                <div className="card-body grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
                  {[
                    { label: 'Rule',         value: analysis.rule_score         },
                    { label: 'Structure',    value: analysis.structure_score    },
                    { label: 'Clarity',      value: analysis.clarity_score      },
                    { label: 'Consistency',  value: analysis.consistency_score  },
                    { label: 'Similarity',   value: analysis.similarity_score   },
                    { label: 'Evidence',     value: analysis.evidence_score     },
                  ].map(d => (
                    <div key={d.label} className="rounded-lg bg-slate-50 p-3 text-center">
                      <p className="text-xs text-slate-500">{d.label}</p>
                      <p className="text-xl font-bold text-slate-900 tabular-nums mt-1">{d.value || 0}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Rule analysis */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Rule Analysis</h2>
                <span className="badge badge-slate">{(analysis.detected_rules || []).length} rules evaluated</span>
              </div>
              <div className="card-body space-y-2">
                {!analysis.detected_rules?.length ? (
                  <EmptyState icon="default" title="No rules detected" description="No compliance rules were identified in this document." />
                ) : (
                  analysis.detected_rules.map((rule, i) => (
                    <RuleResult key={rule.id || i} rule={rule} index={i} />
                  ))
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── Empty state ── */}
        {!analysis && !loading && (
          <EmptyState
            icon={ScanSearch}
            title="Ready to analyze"
            description="Select a standard, upload a PDF or DOCX document, then click Analyze to detect compliance rules automatically."
          />
        )}
      </div>
    </Layout>
  );
}
