import React, { useContext, useState } from 'react';
import { CheckCircle2, XCircle, UploadCloud } from 'lucide-react';
import Layout from '../components/Layout';
import { UserContext } from '../context/UserContext';
import api from '../services/api';

const standards = [
  { value: 'ISO9001', label: 'ISO 9001' },
  { value: 'ISO27001', label: 'ISO 27001' },
];

const highlightEvidence = (evidence, keyword) => {
  if (!evidence) {
    return '—';
  }

  if (!keyword) {
    return evidence;
  }

  const regex = new RegExp(`(${keyword})`, 'gi');
  return evidence.split(regex).map((segment, index) => (
    regex.test(segment) ? (
      <mark key={index} className="rounded-sm bg-amber-100 px-1 text-slate-900">
        {segment}
      </mark>
    ) : (
      <span key={index}>{segment}</span>
    )
  ));
};

export default function DocumentAnalysis() {
  const { user } = useContext(UserContext);
  const [standard, setStandard] = useState('ISO9001');
  const [file, setFile] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

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

    const formData = new FormData();
    formData.append('file', file);
    formData.append('standard', standard);

    setLoading(true);
    try {
      const response = await api.post('/extract-features/', formData);
      setAnalysis(response.data);
    } catch (err) {
      setError(
        err?.response?.data?.file ||
        err?.response?.data?.standard ||
        err?.response?.data?.detail ||
        JSON.stringify(err?.response?.data) ||
        'Unable to analyze the document.'
      );
    } finally {
      setLoading(false);
    }
  };

  const getRuleCount = () => {
    const values = analysis?.features ? Object.values(analysis.features) : [];
    return values.length;
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
              <p className="text-sm font-medium text-slate-500">Supported standard</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{standards.find((item) => item.value === standard)?.label}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Uploaded file</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{file?.name || 'No file selected'}</p>
            </div>
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <p className="text-sm font-medium text-slate-500">Detected rules</p>
              <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{getRuleCount()}</p>
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
                  value={standard}
                  onChange={(event) => setStandard(event.target.value)}
                  className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                >
                  {standards.map((item) => (
                    <option key={item.value} value={item.value}>
                      {item.label}
                    </option>
                  ))}
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
                  disabled={!file || loading}
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
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Compliance score</p>
                <p className="mt-4 text-5xl font-semibold text-slate-900">{analysis.compliance}%</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Valid rules</p>
                <p className="mt-4 text-4xl font-semibold text-emerald-700">{analysis.valid_rules}</p>
              </div>
              <div className="rounded-3xl border border-slate-200 p-5">
                <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Invalid rules</p>
                <p className="mt-4 text-4xl font-semibold text-red-600">{analysis.invalid_rules}</p>
              </div>
            </div>

            <div className="rounded-3xl border border-slate-200 bg-slate-50 p-5">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <h2 className="text-xl font-semibold text-slate-900">Feature extraction results</h2>
                  <p className="text-sm text-slate-500">Each rule is evaluated with evidence snippets extracted from the document.</p>
                </div>
                <div className="rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-slate-700">
                  {Object.keys(analysis.features).length} rules
                </div>
              </div>

              <div className="space-y-3">
                {Object.entries(analysis.features).map(([rule, result]) => (
                  <div key={rule} className="rounded-3xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                      <div>
                        <p className="text-base font-semibold text-slate-900">{rule}</p>
                        <p className="text-sm text-slate-500">Keyword: {result.keyword || '—'}</p>
                      </div>
                      <div
                        className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ${
                          result.status === 1 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'
                        }`}
                      >
                        {result.status === 1 ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
                        {result.status === 1 ? 'Valid' : 'Invalid'}
                      </div>
                    </div>

                    <div className="mt-4 rounded-3xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
                      <span className="font-semibold text-slate-700">Evidence:</span>{' '}
                      {highlightEvidence(result.evidence, result.keyword)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
