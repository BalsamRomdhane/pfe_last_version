import React, { useEffect, useState } from 'react';
import { CheckCircle2, XCircle, UploadCloud } from 'lucide-react';
import Layout from '../components/Layout';
import SeverityBadge from '../components/SeverityBadge';
import api from '../services/api';

export default function DocumentAnalysis() {
  const [normes, setNormes] = useState([]);
  const [selectedNormeId, setSelectedNormeId] = useState(null);
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchNormes = async () => {
      try {
        const response = await api.get('/normes/');
        const normesData = Array.isArray(response.data)
          ? response.data
          : Array.isArray(response.data?.results)
          ? response.data.results
          : [];
        setNormes(normesData);
        if (normesData.length > 0) {
          setSelectedNormeId(normesData[0].id);
        }
      } catch (err) {
        console.error('Unable to load normes:', err);
      }
    };

    fetchNormes();
  }, []);

  const handleFileChange = (event) => {
    const selectedFile = event.target.files?.[0] || null;
    setFile(selectedFile);
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setAnalysis(null);

    if (!file) {
      setError('Please select a PDF or DOCX file to analyze.');
      return;
    }

    if (!selectedNormeId) {
      setError('Please select a norm.');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('norme_id', selectedNormeId);

    setLoading(true);
    try {
      const response = await api.post('/extract-features/', formData);
      setAnalysis(response.data);
    } catch (err) {
      setError(
        err?.response?.data?.file ||
        err?.response?.data?.norme_id ||
        err?.response?.data?.standard ||
        err?.response?.data?.detail ||
        JSON.stringify(err?.response?.data) ||
        'Unable to analyze the document.'
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6 px-4 pb-8 pt-6 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-gradient-to-r from-slate-950 via-blue-950 to-sky-800 px-6 py-7 text-white sm:px-8">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <p className="text-xs uppercase tracking-[0.35em] text-slate-300/75">ISO compliance</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Document Analysis</h1>
                <p className="mt-3 text-sm leading-7 text-slate-200">
                  Upload a PDF or DOCX and identify rule-specific evidence automatically using explainable rule-based extraction.
                </p>
              </div>
            </div>
          </div>

          <div className="grid gap-4 px-6 py-6 md:grid-cols-3 md:px-8">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Supported norme</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">
                {normes.length > 0
                  ? normes.find((item) => item.id === selectedNormeId)?.name || 'Select a norme'
                  : 'No normes available'}
              </p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Uploaded file</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{file?.name || 'No file selected'}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Detected rules</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{analysis?.total_rules || 0}</p>
            </div>
          </div>
        </header>

        <div className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
          <form className="space-y-6" onSubmit={handleSubmit}>
            {error && <div className="rounded-3xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

            <div className="grid gap-6 lg:grid-cols-3">
              <label className="space-y-2 text-sm text-slate-700">
                Norme
                <select
                  value={selectedNormeId || ''}
                  onChange={(event) => setSelectedNormeId(Number(event.target.value))}
                  className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                  disabled={normes.length === 0}
                >
                  {normes.length > 0 ? (
                    normes.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))
                  ) : (
                    <option value="">No normes available</option>
                  )}
                </select>
              </label>

              <label className="space-y-2 text-sm text-slate-700">
                Document
                <div className="relative rounded-3xl border border-slate-300 bg-slate-50 px-4 py-4 text-slate-600">
                  <div className="flex items-center gap-3">
                    <UploadCloud size={20} className="text-slate-500" />
                    <span>{file?.name || 'Choose a PDF or DOCX file'}</span>
                  </div>
                  <input
                    type="file"
                    accept=".pdf,.docx"
                    onChange={handleFileChange}
                    className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
                  />
                </div>
              </label>

              <div className="flex items-end justify-end">
                <button
                  type="submit"
                  disabled={!file || !selectedNormeId || loading}
                  className="inline-flex w-full items-center justify-center rounded-3xl bg-sky-600 px-6 py-3 text-sm font-semibold text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {loading ? 'Analyzing…' : 'Analyze document'}
                </button>
              </div>
            </div>
          </form>
        </div>

        {analysis && (
          <div className="space-y-6 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <div className="grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Real compliance</p>
                <p className="mt-4 text-5xl font-semibold text-slate-900">{analysis.compliance}%</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">ML confidence</p>
                <p className="mt-4 text-5xl font-semibold text-slate-900">{analysis.confidence_score || 0}%</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Semantic score</p>
                <p className="mt-4 text-5xl font-semibold text-slate-900">{analysis.similarity_score || 0}%</p>
              </div>
            </div>
            <div className="mt-4 grid gap-4 md:grid-cols-3">
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Valid rules</p>
                <p className="mt-4 text-4xl font-semibold text-emerald-700">{analysis.valid_count || 0}</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Invalid rules</p>
                <p className="mt-4 text-4xl font-semibold text-red-600">{analysis.invalid_count || 0}</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Total rules</p>
                <p className="mt-4 text-4xl font-semibold text-slate-900">{analysis.total_rules || 0}</p>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <div className="mb-4 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <h2 className="text-xl font-semibold text-slate-900">Rule Analysis</h2>
                  <p className="text-sm text-slate-500">Each rule is evaluated against the uploaded document.</p>
                </div>
                <div className="flex flex-wrap items-center gap-3">
                  <span className="rounded-full bg-emerald-100 px-3 py-2 text-sm font-semibold text-emerald-700">
                    Confidence {analysis.confidence_score || 0}%
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                    Status {analysis.document_status || 'pending'}
                  </span>
                  <span className="rounded-full bg-slate-100 px-3 py-2 text-sm font-semibold text-slate-700">
                    {analysis.automation_ready ? 'Eligible for auto approval' : 'Manual review recommended'}
                  </span>
                </div>
              </div>

              <div className="mt-6 rounded-3xl border border-slate-200 bg-white p-5">
                <h3 className="text-lg font-semibold text-slate-900">Internal analysis diagnostics</h3>
                <p className="mt-2 text-sm text-slate-500">Additional internal scores used for model interpretation, not as rule validation labels.</p>

                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Rule score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.rule_score || 0}</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Structure score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.structure_score || 0}</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Clarity score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.clarity_score || 0}</p>
                  </div>
                </div>
                <div className="mt-4 grid gap-4 md:grid-cols-3">
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Consistency score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.consistency_score || 0}</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Similarity score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.similarity_score || 0}</p>
                  </div>
                  <div className="rounded-3xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Evidence score</p>
                    <p className="mt-3 text-3xl font-semibold text-slate-900">{analysis.evidence_score || 0}</p>
                  </div>
                </div>
              </div>
              <div className="space-y-3">
                {analysis.detected_rules && analysis.detected_rules.length > 0 ? (
                  analysis.detected_rules.map((rule) => (
                    <div key={rule.id} className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-3">
                            <p className="text-base font-semibold text-slate-900">{rule.title}</p>
                            <SeverityBadge severity={rule.severity} />
                          </div>
                          {rule.description && (
                            <p className="mt-2 text-sm text-slate-600">{rule.description}</p>
                          )}
                          {rule.condition && (
                            <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Condition</p>
                              <p className="mt-1 text-sm text-slate-700">{rule.condition}</p>
                            </div>
                          )}
                          {rule.evidence && (
                            <div className="mt-3 rounded-2xl bg-slate-50 px-3 py-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence detected</p>
                              <p className="mt-1 text-sm text-slate-700">{rule.evidence}</p>
                            </div>
                          )}
                        </div>
                        <div
                          className={`inline-flex shrink-0 items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ${
                            rule.is_valid ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                          }`}
                        >
                          {rule.is_valid ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                          {rule.is_valid ? 'Valid' : 'Invalid'}
                        </div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center text-slate-500">
                    No rules detected
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
