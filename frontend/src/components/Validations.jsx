import React, { useContext, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import StatusBadge from './StatusBadge';
import PipelineStepper from './PipelineStepper';
import InvalidRulesList from './InvalidRulesList';
import EmptyState from './common/EmptyState';
import api from '../services/api';
import {
  ClipboardList, FileText, ArrowRight, Search, CheckCircle2,
  XCircle, AlertCircle, X, ChevronRight,
} from 'lucide-react';

const STATUS_DISPLAY = { approved: 'Approved', rejected: 'Rejected', reviewing: 'Reviewing', pending: 'Pending' }; // eslint-disable-line no-unused-vars

/* ─── Rule validation row ──────────────────────────────────────────────── */
function RuleRow({ item, index, onChange }) {
  return (
    <div className={`rounded-xl border p-4 transition-colors ${item.is_valid ? 'border-emerald-200 bg-emerald-50/30' : 'border-slate-200 bg-white'}`}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
            {index + 1}
          </span>
          <div>
            <p className="text-sm font-semibold text-slate-900">{item.rule.title}</p>
            {item.rule.description && (
              <p className="mt-1 text-xs text-slate-500">{item.rule.description}</p>
            )}
          </div>
        </div>

        <label className="flex items-center gap-2 cursor-pointer shrink-0">
          <div
            onClick={() => onChange(index, 'is_valid', !item.is_valid)}
            className={`relative h-5 w-9 rounded-full transition-colors cursor-pointer ${item.is_valid ? 'bg-emerald-500' : 'bg-slate-300'}`}
          >
            <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-transform ${item.is_valid ? 'translate-x-4' : 'translate-x-0.5'}`} />
          </div>
          <span className={`text-xs font-semibold ${item.is_valid ? 'text-emerald-600' : 'text-slate-500'}`}>
            {item.is_valid ? 'Valid' : 'Invalid'}
          </span>
        </label>
      </div>

      <div className="mt-3">
        <label className="form-label text-xs">Evidence text</label>
        <textarea
          value={item.evidence_text}
          onChange={e => onChange(index, 'evidence_text', e.target.value)}
          rows={2}
          placeholder="Describe the evidence found in the document…"
          className="form-textarea text-xs"
        />
      </div>
    </div>
  );
}

/* ─── Validations page ─────────────────────────────────────────────────── */
const Validations = () => {
  const { user }            = useContext(UserContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const [selectedDocument,  setSelectedDocument]  = useState(null);
  const [docSearch,         setDocSearch]          = useState('');
  const [debouncedSearch,   setDebouncedSearch]    = useState('');
  const [docOptions,        setDocOptions]         = useState([]);
  const [docLoading,        setDocLoading]         = useState(false);
  const [ruleValidations,   setRuleValidations]    = useState([]);
  const [finalDecision,     setFinalDecision]      = useState('');
  const [decisionReason,    setDecisionReason]     = useState('');
  const [comments,          setComments]           = useState('');
  const [loading,           setLoading]            = useState(false); // eslint-disable-line no-unused-vars
  const [loadingRules,      setLoadingRules]       = useState(false);
  const [saving,            setSaving]             = useState(false);
  const [error,             setError]              = useState('');
  const [message,           setMessage]            = useState('');

  /* Debounce */
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(docSearch.trim()), 300);
    return () => clearTimeout(t);
  }, [docSearch]);

  /* Search docs */
  useEffect(() => {
    if (!debouncedSearch) return setDocOptions([]);
    let cancelled = false;
    setDocLoading(true);
    api.get('/documents/', { params: { page_size: 10, search: debouncedSearch } })
      .then(res => {
        if (!cancelled) {
          const list = Array.isArray(res.data?.results) ? res.data.results : (Array.isArray(res.data) ? res.data : []);
          setDocOptions(list);
        }
      })
      .catch(() => { if (!cancelled) setDocOptions([]); })
      .finally(() => { if (!cancelled) setDocLoading(false); });
    return () => { cancelled = true; };
  }, [debouncedSearch]);

  /* Load rules from URL param */
  useEffect(() => {
    const id = searchParams.get('document');
    if (id) loadDocumentRules(id);
  }, [searchParams]); // eslint-disable-line

  const loadDocumentRules = async (docId) => {
    setError(''); setMessage(''); setSelectedDocument(null); setRuleValidations([]);
    if (!docId) return;
    setLoadingRules(true);
    try {
      const [docRes, rulesRes] = await Promise.all([
        api.get(`/documents/${docId}/`),
        api.get(`/documents/${docId}/rules/`),
      ]);
      const docData   = docRes.data;
      const rulesData = Array.isArray(rulesRes.data) ? rulesRes.data : [];
      const valMap    = Object.fromEntries((docData.validations || []).map(v => [v.rule.id, v]));
      setSelectedDocument(docData);
      setRuleValidations(rulesData.map(rule => {
        const ex = valMap[rule.id];
        return { rule, is_valid: ex?.is_valid ?? false, evidence_text: ex?.evidence_text ?? '' };
      }));
    } catch { setError('Unable to load rules for this document.'); }
    finally { setLoadingRules(false); }
  };

  const refreshDocument = async (id) => {
    if (!id) return null;
    try {
      const res = await api.get(`/documents/${id}/`);
      if (res?.data) { setSelectedDocument(res.data); return res.data; }
    } catch {}
    return null;
  };

  const updateRuleValidation = (index, field, value) => {
    setRuleValidations(prev => prev.map((item, idx) => idx === index ? { ...item, [field]: value } : item));
  };

  const validCount     = useMemo(() => ruleValidations.filter(i => i.is_valid).length,  [ruleValidations]);
  const invalidCount   = useMemo(() => ruleValidations.filter(i => !i.is_valid).length, [ruleValidations]);
  const complianceScore= useMemo(() => ruleValidations.length ? Math.round(validCount / ruleValidations.length * 100) : 0, [ruleValidations.length, validCount]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setMessage('');
    if (!selectedDocument) return setError('Please select a document.');
    if (!ruleValidations.length) return setError('This document has no rules to validate.');
    if (!finalDecision) return setError('Please select a final decision.');
    if (!decisionReason.trim()) return setError('Please provide a reason for your decision.');

    setSaving(true);
    try {
      const payload = {
        validations: ruleValidations.map(i => ({
          document: selectedDocument.id,
          rule: i.rule.id,
          is_valid: i.is_valid,
          evidence_text: i.evidence_text,
        })),
        final_decision: finalDecision,
        decision_reason: decisionReason,
        reviewer_comment: comments,
      };
      const res = await api.post('/validations/bulk/', payload);
      const confirmed = res.data.final_decision;

      let updated = selectedDocument;
      if (res.data.document) { updated = res.data.document; setSelectedDocument(updated); }
      else {
        updated = { ...selectedDocument, status: res.data.status, final_decision: confirmed };
        setSelectedDocument(updated);
      }
      if (updated?.id) updated = (await refreshDocument(updated.id)) || updated;

      setMessage(
        confirmed === 'approved' ? '✅ Document approved successfully.' :
        confirmed === 'rejected' ? '✅ Document rejected. Feedback sent to the employee.' :
        '✅ Validations submitted.'
      );
      if (updated?.id) await loadDocumentRules(updated.id);
      setFinalDecision(''); setDecisionReason(''); setComments('');
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.response?.data?.validations?.[0] || err?.response?.data?.error || err?.response?.data || 'Unable to submit validation.';
      setError(String(msg));
    } finally { setSaving(false); }
  };

  const isEmployee          = user?.role === 'EMPLOYEE';
  const docStatus           = selectedDocument?.status;
  const invalidSubmitted    = useMemo(() => (selectedDocument?.validations || []).filter(v => !v.is_valid), [selectedDocument]);
  const rejectedFeedback    = useMemo(() => isEmployee && docStatus === 'rejected' ? invalidSubmitted : [], [isEmployee, docStatus, invalidSubmitted]);

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Review Workflow</p>
            <h1 className="page-title mt-1">Validations</h1>
            <p className="page-subtitle">Validate submitted documents rule by rule and provide evidence.</p>
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-500 card px-4 py-2.5">
            <ClipboardList size={14} />
            Rule-based validation for compliance documents
          </div>
        </div>

        {/* ── Alerts ── */}
        {error   && <div className="alert alert-danger"><AlertCircle size={14} className="shrink-0" /><span>{error}</span><button onClick={() => setError('')} className="ml-auto"><X size={13}/></button></div>}
        {message && <div className="alert alert-success"><CheckCircle2 size={14} className="shrink-0" /><span>{message}</span><button onClick={() => setMessage('')} className="ml-auto"><X size={13}/></button></div>}

        {/* ── Main grid ── */}
        <div className="grid gap-5 xl:grid-cols-[1fr_300px]">

          {/* ── Left: Validation form ── */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Review Session</h2>
              <div className="flex items-center gap-1.5 text-xs text-slate-500">
                <FileText size={13} />
                Document rules
              </div>
            </div>

            <div className="card-body space-y-5">

              {/* Document search */}
              <div>
                <label className="form-label">Select Document</label>
                <div className="relative">
                  <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
                  <input
                    placeholder="Search by ID, employee, filename…"
                    value={docSearch}
                    onChange={e => setDocSearch(e.target.value)}
                    className="form-input pl-9"
                  />
                </div>
                {docLoading && <p className="mt-1 text-xs text-slate-400 animate-pulse">Searching…</p>}
                {docOptions.length > 0 && (
                  <div className="mt-1.5 max-h-48 overflow-y-auto rounded-lg border border-slate-200 bg-white shadow-dropdown">
                    {docOptions.map(doc => (
                      <button
                        key={doc.id}
                        onClick={() => {
                          setSearchParams({ document: doc.id });
                          setDocOptions([]);
                          setDocSearch('');
                        }}
                        className="flex w-full items-center gap-2 px-3 py-2.5 text-left text-sm hover:bg-slate-50 border-b border-slate-50 last:border-0 transition-colors"
                      >
                        <FileText size={12} className="text-slate-400 shrink-0" />
                        <span className="font-medium text-slate-800">{doc.employee_username}</span>
                        <span className="text-slate-400">—</span>
                        <span className="text-slate-600 truncate">{doc.file ? doc.file.split('/').pop() : '—'}</span>
                        <span className="ml-auto font-mono text-2xs text-slate-400">#{doc.id}</span>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              {/* Selected document info */}
              {selectedDocument && (
                <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs text-slate-500 font-medium">Standard</p>
                      <p className="text-sm font-semibold text-slate-900">{selectedDocument.norme?.name || 'Unknown standard'}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <StatusBadge status={selectedDocument.status} />
                      {typeof selectedDocument.compliance_score === 'number' && (
                        <span className="badge badge-slate">
                          Score: {selectedDocument.compliance_score}%
                        </span>
                      )}
                    </div>
                  </div>
                  <PipelineStepper currentStatus={selectedDocument.status || 'pending'} />
                  {docStatus === 'rejected' && invalidSubmitted.length > 0 && (
                    <div className="alert alert-danger py-2.5">
                      <AlertCircle size={13} className="shrink-0" />
                      <span className="text-xs">{invalidSubmitted.length} invalid rule{invalidSubmitted.length>1?'s':''} found. Only failing validations are shown to employees.</span>
                    </div>
                  )}
                </div>
              )}

              {/* Rules or loading */}
              {loadingRules ? (
                <div className="space-y-3">
                  {[1,2,3].map(i => <div key={i} className="skeleton h-24 rounded-xl" />)}
                </div>
              ) : selectedDocument ? (
                isEmployee ? (
                  <div className="rounded-xl border border-slate-200 bg-slate-50 p-5 text-sm text-slate-600">
                    {docStatus === 'rejected' ? (
                      <p>This document was rejected with <strong>{invalidSubmitted.length}</strong> invalid rule{invalidSubmitted.length>1?'s':''}. Review the feedback below and re-upload a corrected file.</p>
                    ) : (
                      <p>Select a rejected document to see missing rules, then re-upload from the Documents page.</p>
                    )}
                  </div>
                ) : (
                  <form onSubmit={handleSubmit} className="space-y-4">
                    <div className="space-y-3">
                      {ruleValidations.map((item, i) => (
                        <RuleRow key={item.rule.id} item={item} index={i} onChange={updateRuleValidation} />
                      ))}
                    </div>

                    {/* Score summary */}
                    <div className="grid grid-cols-3 gap-3 rounded-xl bg-slate-50 p-4">
                      {[
                        { label: 'Valid',       value: validCount,      cls: 'text-emerald-600' },
                        { label: 'Invalid',     value: invalidCount,    cls: 'text-red-600'     },
                        { label: 'Compliance',  value: `${complianceScore}%`, cls: 'text-brand-600' },
                      ].map(s => (
                        <div key={s.label} className="text-center rounded-lg bg-white py-3 shadow-card">
                          <p className={`text-2xl font-bold tabular-nums ${s.cls}`}>{s.value}</p>
                          <p className="text-xs text-slate-500 mt-0.5">{s.label}</p>
                        </div>
                      ))}
                    </div>

                    {/* Final decision */}
                    <div className="rounded-xl border border-slate-200 bg-white p-4 space-y-4">
                      <p className="text-sm font-semibold text-slate-900">Final Decision</p>
                      <div className="grid grid-cols-2 gap-2">
                        {['approved','rejected'].map(val => (
                          <label
                            key={val}
                            className={`flex items-center gap-3 rounded-lg border p-3 cursor-pointer transition-all ${
                              finalDecision === val
                                ? val === 'approved'
                                  ? 'border-emerald-400 bg-emerald-50'
                                  : 'border-red-400 bg-red-50'
                                : 'border-slate-200 hover:bg-slate-50'
                            }`}
                          >
                            <input
                              type="radio"
                              name="final_decision"
                              value={val}
                              checked={finalDecision === val}
                              onChange={e => setFinalDecision(e.target.value)}
                              className="hidden"
                            />
                            {val === 'approved'
                              ? <CheckCircle2 size={16} className={finalDecision === 'approved' ? 'text-emerald-500' : 'text-slate-300'} />
                              : <XCircle size={16} className={finalDecision === 'rejected' ? 'text-red-500' : 'text-slate-300'} />
                            }
                            <span className="text-sm font-medium capitalize">{val}</span>
                          </label>
                        ))}
                      </div>

                      <div className="space-y-3">
                        <div>
                          <label className="form-label">Reason for decision <span className="text-red-500">*</span></label>
                          <textarea
                            value={decisionReason}
                            onChange={e => setDecisionReason(e.target.value)}
                            rows={3}
                            placeholder="Explain your decision…"
                            className="form-textarea"
                          />
                        </div>
                        <div>
                          <label className="form-label">Additional comments</label>
                          <textarea
                            value={comments}
                            onChange={e => setComments(e.target.value)}
                            rows={2}
                            placeholder="Optional reviewer notes…"
                            className="form-textarea"
                          />
                        </div>
                      </div>
                    </div>

                    <button
                      type="submit"
                      disabled={saving || !finalDecision}
                      className="btn-primary w-full justify-center"
                    >
                      {saving ? (
                        <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />Submitting…</>
                      ) : (
                        <><ArrowRight size={15} />Submit Validation</>
                      )}
                    </button>
                  </form>
                )
              ) : (
                <EmptyState
                  icon="search"
                  title="No document selected"
                  description="Search for a document above to begin rule-by-rule validation."
                />
              )}
            </div>
          </div>

          {/* ── Right: Guidance ── */}
          <div className="space-y-4">
            {/* Workflow guide */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Workflow Guide</h2>
              </div>
              <div className="card-body space-y-3">
                {[
                  { step: '1', text: 'Search and select a pending document.' },
                  { step: '2', text: 'Mark each rule as valid or invalid and add evidence text.' },
                  { step: '3', text: 'Choose a final decision: Approve or Reject.' },
                  { step: '4', text: 'Provide a reason and submit the validation batch.' },
                ].map(s => (
                  <div key={s.step} className="flex items-start gap-3">
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-bold text-brand-700">
                      {s.step}
                    </span>
                    <p className="text-xs text-slate-600">{s.text}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Compliance score visual */}
            {selectedDocument && ruleValidations.length > 0 && (
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Live Score</h2>
                </div>
                <div className="card-body">
                  <div className="flex items-center justify-center">
                    <div className="relative flex h-24 w-24 items-center justify-center">
                      <svg viewBox="0 0 80 80" className="-rotate-90 h-24 w-24">
                        <circle cx="40" cy="40" r="32" fill="none" stroke="#e2e8f0" strokeWidth="7" strokeLinecap="round"/>
                        <circle
                          cx="40" cy="40" r="32" fill="none"
                          stroke={complianceScore >= 80 ? '#10b981' : complianceScore >= 60 ? '#f59e0b' : '#ef4444'}
                          strokeWidth="7" strokeLinecap="round"
                          strokeDasharray={`${2 * Math.PI * 32}`}
                          strokeDashoffset={`${2 * Math.PI * 32 * (1 - complianceScore/100)}`}
                          style={{ transition: 'stroke-dashoffset 0.6s ease' }}
                        />
                      </svg>
                      <div className="absolute inset-0 flex flex-col items-center justify-center">
                        <span className="text-2xl font-bold text-slate-900">{complianceScore}</span>
                        <span className="text-2xs text-slate-400">%</span>
                      </div>
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-center">
                    <div className="rounded-lg bg-emerald-50 py-2">
                      <p className="text-lg font-bold text-emerald-600">{validCount}</p>
                      <p className="text-2xs text-slate-500">Valid</p>
                    </div>
                    <div className="rounded-lg bg-red-50 py-2">
                      <p className="text-lg font-bold text-red-600">{invalidCount}</p>
                      <p className="text-2xs text-slate-500">Invalid</p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* ── Rejection feedback for employees ── */}
        {isEmployee && docStatus === 'rejected' && rejectedFeedback.length > 0 && (
          <div className="card animate-slide-up">
            <div className="card-header">
              <div>
                <p className="section-label">Rejection Feedback</p>
                <h2 className="card-title mt-0.5">Invalid Rules</h2>
              </div>
              <Link
                to="/documents"
                className="btn-primary btn-sm"
              >
                Re-upload Document
                <ChevronRight size={13} />
              </Link>
            </div>
            <div className="card-body">
              <InvalidRulesList invalidRules={rejectedFeedback} />
            </div>
          </div>
        )}

        {/* ── Validation history ── */}
        <div className="card">
          <div className="card-header">
            <div>
              <p className="section-label">History</p>
              <h2 className="card-title mt-0.5">Existing Validations</h2>
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="table-enterprise">
              <thead>
                <tr>
                  <th>Document</th>
                  <th>Rule</th>
                  <th>Result</th>
                  <th>Reviewer</th>
                  <th>Date</th>
                </tr>
              </thead>
              <tbody>
                {!selectedDocument || !selectedDocument.validations?.length ? (
                  <tr>
                    <td colSpan={5} className="px-4 py-10">
                      <EmptyState title="No validations yet" description="Select a document to view its validation history." />
                    </td>
                  </tr>
                ) : (
                  selectedDocument.validations.map(v => (
                    <tr key={v.id}>
                      <td className="font-medium">{selectedDocument.employee_username}</td>
                      <td className="text-xs text-slate-600">{v.rule.title}</td>
                      <td><StatusBadge status={v.is_valid ? 'approved' : 'rejected'} /></td>
                      <td className="text-sm">{v.teamlead_username || '—'}</td>
                      <td className="text-xs text-slate-500">{new Date(v.updated_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Validations;
