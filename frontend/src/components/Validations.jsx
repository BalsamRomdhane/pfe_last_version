import React, { useContext, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import StatusBadge from './StatusBadge';
import PipelineStepper from './PipelineStepper';
import InvalidRulesList from './InvalidRulesList';
import api from '../services/api';
import { ClipboardList, FileText, ArrowRight } from 'lucide-react';

const statusLabels = {
  approved: 'Approved',
  rejected: 'Rejected',
  reviewing: 'Reviewing',
  pending: 'Pending',
};

const Validations = () => {
  const { user } = useContext(UserContext);
  const [searchParams, setSearchParams] = useSearchParams();
  const [documents, setDocuments] = useState([]);
  const [selectedDocument, setSelectedDocument] = useState(null);
  const [docSearch, setDocSearch] = useState('');
  const [debouncedDocSearch, setDebouncedDocSearch] = useState('');
  const [docOptions, setDocOptions] = useState([]);
  const [docLoading, setDocLoading] = useState(false);
  const [ruleValidations, setRuleValidations] = useState([]);
  const [finalDecision, setFinalDecision] = useState('');
  const [decisionReason, setDecisionReason] = useState('');
  const [comments, setComments] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadingRules, setLoadingRules] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  useEffect(() => {
    fetchDocuments();
  }, []);

  // Debounce document search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedDocSearch(docSearch.trim()), 300);
    return () => clearTimeout(t);
  }, [docSearch]);

  useEffect(() => {
    if (!debouncedDocSearch) return setDocOptions([]);
    let cancelled = false;
    (async () => {
      setDocLoading(true);
      try {
        const res = await api.get('/documents/', { params: { page_size: 10, search: debouncedDocSearch } });
        const list = Array.isArray(res.data.results) ? res.data.results : Array.isArray(res.data) ? res.data : [];
        if (!cancelled) setDocOptions(list);
      } catch (err) {
        console.error('Doc search error', err);
        if (!cancelled) setDocOptions([]);
      } finally {
        if (!cancelled) setDocLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [debouncedDocSearch]);

  useEffect(() => {
    const documentId = searchParams.get('document');
    if (documentId) {
      loadDocumentRules(documentId);
    }
  }, [searchParams]);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await api.get('/documents/');
      const data = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.results)
        ? response.data.results
        : [];
      setDocuments(data);
    } catch (err) {
      console.error(err);
      setError('Unable to load documents.');
    } finally {
      setLoading(false);
    }
  };

  const loadDocumentRules = async (documentId) => {
    setError('');
    setMessage('');
    setSelectedDocument(null);
    setRuleValidations([]);
    if (!documentId) {
      return;
    }

    setLoadingRules(true);
    try {
      const [documentRes, rulesRes] = await Promise.all([
        api.get(`/documents/${documentId}/`),
        api.get(`/documents/${documentId}/rules/`),
      ]);

      const documentData = documentRes.data;
      const rulesData = Array.isArray(rulesRes.data) ? rulesRes.data : [];
      const existingValidations = Array.isArray(documentData.validations) ? documentData.validations : [];
      const validationMap = Object.fromEntries(
        existingValidations.map((validation) => [validation.rule.id, validation])
      );

      setSelectedDocument(documentData);
      setRuleValidations(
        rulesData.map((rule) => {
          const existing = validationMap[rule.id];
          return {
            rule,
            is_valid: existing?.is_valid ?? false,
            evidence_text: existing?.evidence_text ?? '',
          };
        })
      );
    } catch (err) {
      console.error(err);
      setError('Unable to load norme rules for the selected document.');
    } finally {
      setLoadingRules(false);
    }
  };

  const refreshDocument = async (documentId) => {
    if (!documentId) return null;
    try {
      const response = await api.get(`/documents/${documentId}/`);
      if (response?.data) {
        setSelectedDocument(response.data);
        return response.data;
      }
    } catch (err) {
      console.error('Could not refresh document:', err);
    }
    return null;
  };

  const handleDocumentChange = (event) => {
    const documentId = event.target.value;
    if (documentId) {
      setSearchParams({ document: documentId });
    } else {
      setSearchParams({});
    }
    loadDocumentRules(documentId);
  };

  const updateRuleValidation = (index, field, value) => {
    setRuleValidations((current) =>
      current.map((item, idx) => (idx === index ? { ...item, [field]: value } : item))
    );
  };

  const validRulesCount = useMemo(
    () => ruleValidations.filter((item) => item.is_valid).length,
    [ruleValidations]
  );

  const invalidRulesCount = useMemo(
    () => ruleValidations.filter((item) => !item.is_valid).length,
    [ruleValidations]
  );

  const complianceScore = useMemo(() => {
    if (!ruleValidations.length) return 0;
    return Math.round((validRulesCount / ruleValidations.length) * 100);
  }, [ruleValidations.length, validRulesCount]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');

    if (!selectedDocument) {
      setError('Please select a document to validate.');
      return;
    }

    if (!ruleValidations.length) {
      setError('This document has no rules to validate.');
      return;
    }

    if (!finalDecision) {
      setError('Please select a final decision for this document.');
      return;
    }

    if (!decisionReason.trim()) {
      setError('Please provide a reason for the final decision.');
      return;
    }

    setSaving(true);
    try {
      // Prepare validation payload
      const validationsPayload = ruleValidations.map((item) => ({
        document: selectedDocument.id,
        rule: item.rule.id,
        is_valid: item.is_valid,
        evidence_text: item.evidence_text,
      }));

      // Use bulk endpoint with final decision to do everything at once
      const payload = {
        validations: validationsPayload,
        final_decision: finalDecision,
        decision_reason: decisionReason,
        reviewer_comment: comments,
      };

      const response = await api.post('/validations/bulk/', payload);

      console.log('Bulk submission response:', response.data);

      const newStatus = response.data.status;
      const finalDecisionConfirmed = response.data.final_decision;

      let updatedDocument = selectedDocument;
      if (response.data.document) {
        updatedDocument = response.data.document;
        setSelectedDocument(response.data.document);
      } else if (selectedDocument) {
        updatedDocument = {
          ...selectedDocument,
          status: newStatus,
          final_decision: finalDecisionConfirmed,
          decision_reason: response.data.decision_reason || selectedDocument.decision_reason,
          reviewer_comment: response.data.reviewer_comment || selectedDocument.reviewer_comment,
        };
        setSelectedDocument(updatedDocument);
      }

      if (updatedDocument?.id) {
        const refreshed = await refreshDocument(updatedDocument.id);
        if (refreshed) {
          updatedDocument = refreshed;
        }
        setDocuments((current) =>
          current.map((doc) =>
            doc.id === updatedDocument.id ? { ...doc, status: updatedDocument.status } : doc
          )
        );
      }

      if (finalDecisionConfirmed === 'approved') {
        setMessage('✅ Document has been approved successfully!');
      } else if (finalDecisionConfirmed === 'rejected') {
        setMessage('✅ Document has been rejected. Feedback sent to the employee.');
      } else {
        setMessage('✅ Validations submitted. Document is under review.');
      }

      await fetchDocuments();
      if (updatedDocument?.id) {
        await loadDocumentRules(updatedDocument.id);
      }

      // Reset form fields after refresh
      setFinalDecision('');
      setDecisionReason('');
      setComments('');

    } catch (err) {
      console.error('Submission error:', err);
      const errorMsg = err?.response?.data?.detail || 
                      err?.response?.data?.validations?.[0] ||
                      err?.response?.data?.error ||
                      err?.response?.data ||
                      'Unable to submit validation batch.';
      setError(String(errorMsg));
    } finally {
      setSaving(false);
    }
  };

  const selectedDocumentStatus = selectedDocument?.status;
  const invalidRules = useMemo(
    () => (selectedDocument?.validations || []).filter((validation) => validation.is_valid === false),
    [selectedDocument]
  );
  const invalidSubmittedRulesCount = invalidRules.length;
  const isEmployee = user?.role === 'EMPLOYEE';

  const rejectedFeedback = useMemo(() => {
    if (user?.role !== 'EMPLOYEE' || selectedDocumentStatus !== 'rejected') {
      return [];
    }

    return invalidRules;
  }, [invalidRules, selectedDocumentStatus, user]);

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-sky-600">Review workflow</p>
            <h1 className="mt-2 text-3xl font-bold text-slate-900">Validations</h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-600">
              Validate submitted documents rule by rule and provide evidence per requirement.
            </p>
          </div>
          <div className="rounded-3xl bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <ClipboardList size={18} />
              Rule-based validation for documents.
            </div>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[1.4fr_0.9fr]">
          <section className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Review session</p>
                <h2 className="mt-2 text-xl font-semibold text-slate-900">Rule validation</h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-3xl bg-slate-50 px-4 py-2 text-sm text-slate-700">
                <FileText size={16} /> Document rules
              </div>
            </div>

            {error && <div className="rounded-3xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}
            {message && (
              <div className="rounded-3xl bg-emerald-50 p-4 text-sm text-emerald-700 border border-emerald-200">
                <div className="font-semibold">{message}</div>
              </div>
            )}

            <div className="space-y-4">
              <label className="space-y-2 text-sm text-slate-700">
                Document
                <div>
                  <input
                    placeholder="Search documents (id, employee, filename...)"
                    value={docSearch}
                    onChange={(e) => setDocSearch(e.target.value)}
                    className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                  />
                  {docLoading && <div className="mt-2 text-sm text-slate-500">Searching…</div>}
                  {docOptions.length > 0 && (
                    <div className="mt-2 max-h-48 overflow-auto rounded-lg border bg-white">
                      {docOptions.map((doc) => (
                        <button
                          key={doc.id}
                          onClick={() => {
                            setSearchParams({ document: doc.id });
                            loadDocumentRules(doc.id);
                          }}
                          className="w-full text-left px-4 py-2 hover:bg-slate-50 text-sm"
                        >
                          {doc.employee_username} — #{doc.id} — {doc.file ? doc.file.split('/').pop() : (doc.file_url || 'file')}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </label>

              {selectedDocument && (
                <div className="space-y-4 rounded-3xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="font-semibold text-slate-900">Norme:</p>
                      <p>{selectedDocument.norme?.name || 'Unknown norme'}</p>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      <StatusBadge status={selectedDocument.status} />
                      {typeof selectedDocument.compliance_score === 'number' && (
                        <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700">
                          Score: {selectedDocument.compliance_score}%
                        </span>
                      )}
                    </div>
                  </div>

                  <PipelineStepper currentStatus={selectedDocument.status || 'pending'} />

                  {selectedDocumentStatus === 'rejected' && invalidSubmittedRulesCount > 0 && (
                    <div className="rounded-3xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
                      <p className="font-semibold">{invalidSubmittedRulesCount} invalid {invalidSubmittedRulesCount === 1 ? 'rule' : 'rules'} found</p>
                      <p className="mt-2 text-slate-700">Only the failing validations are shown to employees for faster remediation.</p>
                    </div>
                  )}
                </div>
              )}
            </div>

            {loadingRules ? (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-500">
                Loading rules…
              </div>
            ) : selectedDocument ? (
              isEmployee ? (
                <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                  {selectedDocumentStatus === 'rejected' ? (
                    <p>
                      This document has been rejected with {invalidSubmittedRulesCount} invalid {invalidSubmittedRulesCount === 1 ? 'rule' : 'rules'}. Review the invalid items below to understand the missing requirements.
                    </p>
                  ) : (
                    <p>
                      Select a rejected document to see the missing rules and resubmit a corrected file from the Documents page.
                    </p>
                  )}
                </div>
              ) : (
                <form onSubmit={handleSubmit} className="space-y-6">
                  {ruleValidations.map((item, index) => (
                    <div key={item.rule.id} className="rounded-3xl border border-slate-200 bg-white p-5 shadow-sm">
                      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-sky-100 text-sky-700">{index + 1}</span>
                            {item.rule.title}
                          </div>
                          {item.rule.description && (
                            <p className="mt-2 text-sm text-slate-600">{item.rule.description}</p>
                          )}
                        </div>
                        <label className="inline-flex items-center gap-2 rounded-full border border-slate-300 bg-slate-100 px-4 py-2 text-sm text-slate-700">
                          <input
                            type="checkbox"
                            checked={item.is_valid}
                            onChange={(e) => updateRuleValidation(index, 'is_valid', e.target.checked)}
                            className="h-4 w-4 rounded border-slate-300 bg-white text-sky-600 focus:ring-sky-500"
                          />
                          Valid
                        </label>
                      </div>

                      <div className="grid gap-4 mt-4">
                        <label className="space-y-2 text-sm text-slate-700">
                          Evidence text
                          <textarea
                            value={item.evidence_text}
                            onChange={(e) => updateRuleValidation(index, 'evidence_text', e.target.value)}
                            className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                            rows={3}
                          />
                        </label>
                      </div>
                    </div>
                  ))}

                  <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5 space-y-5">
                    <div className="grid gap-4 sm:grid-cols-3">
                      <div className="rounded-3xl bg-white p-4 text-center shadow-sm">
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Valid rules</p>
                        <p className="mt-3 text-3xl font-semibold text-emerald-700">{validRulesCount}</p>
                      </div>
                      <div className="rounded-3xl bg-white p-4 text-center shadow-sm">
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Invalid rules</p>
                        <p className="mt-3 text-3xl font-semibold text-rose-600">{invalidRulesCount}</p>
                      </div>
                      <div className="rounded-3xl bg-white p-4 text-center shadow-sm">
                        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Compliance</p>
                        <p className="mt-3 text-3xl font-semibold text-sky-700">{complianceScore}%</p>
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-200 bg-white p-5">
                      <p className="text-sm font-semibold text-slate-900">Final decision</p>
                      <div className="mt-4 space-y-3">
                        <label className="flex items-center gap-3 rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 cursor-pointer">
                          <input
                            type="radio"
                            name="final_decision"
                            value="approved"
                            checked={finalDecision === 'approved'}
                            onChange={(e) => setFinalDecision(e.target.value)}
                            className="h-4 w-4 rounded border-slate-300 bg-white text-sky-600 focus:ring-sky-500"
                          />
                          <span className="text-sm font-medium text-slate-900">Approve document</span>
                        </label>
                        <label className="flex items-center gap-3 rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 cursor-pointer">
                          <input
                            type="radio"
                            name="final_decision"
                            value="rejected"
                            checked={finalDecision === 'rejected'}
                            onChange={(e) => setFinalDecision(e.target.value)}
                            className="h-4 w-4 rounded border-slate-300 bg-white text-sky-600 focus:ring-sky-500"
                          />
                          <span className="text-sm font-medium text-slate-900">Reject document</span>
                        </label>
                      </div>

                      <div className="mt-5 space-y-4">
                        <label className="space-y-2 text-sm text-slate-700">
                          Reason for decision
                          <textarea
                            value={decisionReason}
                            onChange={(e) => setDecisionReason(e.target.value)}
                            rows={4}
                            placeholder="Explain why you approved or rejected this document"
                            className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                          />
                        </label>
                        <label className="space-y-2 text-sm text-slate-700">
                          Comments
                          <textarea
                            value={comments}
                            onChange={(e) => setComments(e.target.value)}
                            rows={3}
                            placeholder="Optional review comments"
                            className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                          />
                        </label>
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={saving}
                    className="inline-flex items-center gap-2 rounded-3xl bg-sky-600 px-6 py-3 text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <ArrowRight size={18} />
                    {saving ? 'Submitting...' : 'Submit final validation'}
                  </button>
                </form>
              )
            ) : (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                Select a document to load its norme rules and validate them in batch.
              </div>
            )}
          </section>

          <section className="space-y-4 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Workflow guidance</p>
            <div className="space-y-3 text-sm text-slate-600">
              <p>Team leads validate every rule for a selected document and submit the full rule set in a single flow.</p>
              <p>Approved documents require every rule to be marked valid; any invalid rule rejects the document.</p>
              <p>Employees can review rejected items and re-upload corrected documents from the Documents page.</p>
            </div>
          </section>
        </div>

        {user?.role === 'EMPLOYEE' && selectedDocumentStatus === 'rejected' && (
          <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Rejection feedback</p>
                <h2 className="mt-2 text-xl font-semibold text-slate-900">Invalid rules</h2>
              </div>
              <Link
                to="/documents"
                className="inline-flex items-center justify-center rounded-3xl bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                Re-upload corrected document
              </Link>
            </div>

            <InvalidRulesList invalidRules={rejectedFeedback} />
          </section>
        )}

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Review history</p>
              <h2 className="mt-2 text-xl font-semibold text-slate-900">Existing validations</h2>
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Document</th>
                  <th className="px-4 py-3 text-left font-semibold">Rule</th>
                  <th className="px-4 py-3 text-left font-semibold">Result</th>
                  <th className="px-4 py-3 text-left font-semibold">Reviewer</th>
                  <th className="px-4 py-3 text-left font-semibold">Updated</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {loading ? (
                  <tr><td colSpan="5" className="px-4 py-6 text-center text-slate-500">Loading validations...</td></tr>
                ) : !selectedDocument || !(selectedDocument.validations?.length > 0) ? (
                  <tr><td colSpan="5" className="px-4 py-6 text-center text-slate-500">No validations recorded yet.</td></tr>
                ) : (
                  selectedDocument.validations.map((validation) => (
                    <tr key={validation.id} className="hover:bg-slate-50">
                      <td className="px-4 py-4">{selectedDocument.employee_username}</td>
                      <td className="px-4 py-4">{validation.rule.title}</td>
                      <td className="px-4 py-4">{validation.is_valid ? 'Valid' : 'Invalid'}</td>
                      <td className="px-4 py-4">{validation.teamlead_username}</td>
                      <td className="px-4 py-4">{new Date(validation.updated_at).toLocaleDateString()}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Validations;
