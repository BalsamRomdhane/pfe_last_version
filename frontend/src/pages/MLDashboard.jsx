import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, TrendingUp, ArrowRight, Target, Activity, UploadCloud, CheckCircle2, XCircle, Sparkles, AlertCircle } from "lucide-react";
import Layout from "../components/Layout";
import { UserContext } from "../context/UserContext";
import api from "../services/api";

const ALGORITHMS = ["RandomForest", "LogisticRegression", "GradientBoosting"];

const getStatusTone = (value) => {
  if (value >= 0.90) return "bg-emerald-100 text-emerald-700";
  if (value >= 0.75) return "bg-blue-100 text-blue-700";
  return "bg-amber-100 text-amber-700";
};

const formatPercent = (value) => `${Math.round(value * 100)}%`;

const normalizeModels = (data) => {
  if (!data) return [];
  if (Array.isArray(data.models)) return data.models.map((item) => ({ ...item, name: item.name || item.algorithm, id: item.id || item.name }));
  if (Array.isArray(data)) return data.map((item) => ({ ...item, id: item.id || item.name }));
  if (data.results && typeof data.results === "object") {
    return Object.entries(data.results).map(([name, metrics]) => ({
      id: metrics.id || name,
      name,
      accuracy: metrics.accuracy,
      precision: metrics.precision,
      recall: metrics.recall,
      f1_score: metrics.f1_score,
      trained_date: metrics.trained_date,
      sample_count: metrics.sample_count,
      is_best: name === data.best_model,
      status: name === data.best_model ? "Best Model" : "Trained",
      confusion_matrix: metrics.confusion_matrix,
      error: metrics.error,
    }));
  }
  return [];
};

export default function MLDashboard() {
  const { user } = useContext(UserContext);
  const navigate = useNavigate();
  
  const [norms, setNorms] = useState([]);
  const [selectedNormId, setSelectedNormId] = useState('');
  const [selectedNorm, setSelectedNorm] = useState(null);
  const [datasetStats, setDatasetStats] = useState(null);
  const [datasetSamples, setDatasetSamples] = useState([]);
  const [datasetPage, setDatasetPage] = useState(1);
  const [expandedSamples, setExpandedSamples] = useState(new Set());
  const [models, setModels] = useState([]);
  const [bestModel, setBestModel] = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);
  
  const [normsLoading, setNormsLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(false);
  const [trainLoading, setTrainLoading] = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [testLoading, setTestLoading] = useState(false);
  
  const [alert, setAlert] = useState(null);
  const [file, setFile] = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  // Load norms from database on mount
  useEffect(() => {
    if (!user || user.role !== "ADMIN") {
      navigate("/dashboard");
      return;
    }
    fetchNorms();
  }, [user, navigate]);

  // Load dataset stats and models when norm is selected
  useEffect(() => {
    if (selectedNormId) {
      fetchDatasetStats(selectedNormId);
      fetchModels(selectedNormId);
    }
  }, [selectedNormId]);

  const fetchNorms = async () => {
    setNormsLoading(true);
    setAlert(null);
    const endpoints = ["/norms/", "/normes/"];
    let normsData = [];

    try {
      for (const endpoint of endpoints) {
        try {
          const res = await api.get(endpoint);
          normsData = Array.isArray(res.data) ? res.data : res.data.results || [];
          if (normsData.length > 0) {
            break;
          }
        } catch (nestedErr) {
          if (nestedErr.response?.status === 404) {
            continue;
          }
          throw nestedErr;
        }
      }

      if (normsData.length === 0) {
        throw new Error("No norms endpoint available");
      }

      setNorms(normsData);
      setSelectedNormId(String(normsData[0].id));
      setSelectedNorm(normsData[0]);
    } catch (err) {
      console.error(err);
      setAlert({ type: "error", message: "Impossible de charger les normes." });
    } finally {
      setNormsLoading(false);
    }
  };

  const handleNormChange = (normId) => {
    const selectedId = String(normId);
    const norm = norms.find((n) => String(n.id) === selectedId) || norms[0] || null;
    setSelectedNormId(selectedId);
    setSelectedNorm(norm);
    setModels([]);
    setBestModel(null);
    setSelectedModel(null);
    setTestResult(null);
  };

  const toggleSampleExpanded = (sampleId) => {
    setExpandedSamples((current) => {
      const next = new Set(current);
      if (next.has(sampleId)) {
        next.delete(sampleId);
      } else {
        next.add(sampleId);
      }
      return next;
    });
  };

  const fetchDatasetStats = async (normId) => {
    setStatsLoading(true);
    try {
      const res = await api.get(`/dataset-stats/?norm_id=${normId}`);
      setDatasetStats(res.data);
      setDatasetSamples(res.data.samples || []);
      setDatasetPage(1);
      setExpandedSamples(new Set());
    } catch (err) {
      console.error(err);
      setDatasetStats(null);
      setDatasetSamples([]);
    } finally {
      setStatsLoading(false);
    }
  };

  const getPagedSamples = () => {
    const pageSize = 3;
    const startIndex = (datasetPage - 1) * pageSize;
    return datasetSamples.slice(startIndex, startIndex + pageSize);
  };

  const totalDatasetPages = Math.max(1, Math.ceil(datasetSamples.length / 3));

  const goToPage = (page) => {
    setDatasetPage(Math.max(1, Math.min(totalDatasetPages, page)));
  };

  const fetchModels = async (normId) => {
    setCompareLoading(true);
    setAlert(null);
    try {
      const res = await api.get(`/ml/models/?norm_id=${normId}`);
      const normalized = normalizeModels(res.data);
      setModels(normalized);
      const best = normalized.find((item) => item.is_best) || normalized[0] || null;
      setBestModel(best);
      setSelectedModel(best);
    } catch (err) {
      console.error(err);
      setAlert({ type: "error", message: err.response?.data?.error || "Impossible de récupérer les modèles." });
      setModels([]);
      setBestModel(null);
      setSelectedModel(null);
    } finally {
      setCompareLoading(false);
    }
  };

  const handleTrain = async () => {
    if (!selectedNormId) {
      setAlert({ type: "error", message: "Veuillez sélectionner une norme." });
      return;
    }
    setTrainLoading(true);
    setAlert(null);
    setTestResult(null);
    try {
      const res = await api.post("/ml/train/", { norm_id: selectedNormId });
      const normalized = normalizeModels(res.data);
      setModels(normalized);
      const best = normalized.find((item) => item.is_best) || normalized[0] || null;
      setBestModel(best);
      setSelectedModel(best);
      setAlert({ type: "success", message: `Entraînement terminé pour ${selectedNorm?.name || "la norme sélectionnée"}.` });
    } catch (err) {
      console.error(err);
      setAlert({ type: "error", message: err.response?.data?.error || "L'entraînement a échoué." });
    } finally {
      setTrainLoading(false);
    }
  };

  const handleCompare = async () => {
    if (!selectedNormId) return;
    setCompareLoading(true);
    setAlert(null);
    try {
      await fetchModels(selectedNormId);
      setAlert({ type: "success", message: "Comparaison des modèles mise à jour." });
    } catch (err) {
      console.error(err);
    } finally {
      setCompareLoading(false);
    }
  };

  const handleModelSelect = (model) => {
    setSelectedModel(model);
    setAlert({ type: "success", message: `${model.name} sélectionné.` });
  };

  const handleFileChange = (event) => {
    setUploadError(null);
    const nextFile = event.target.files?.[0] || null;
    if (nextFile) {
      setFile(nextFile);
      setTestResult(null);
    }
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragActive(false);
    const nextFile = event.dataTransfer.files?.[0] || null;
    if (nextFile) {
      setFile(nextFile);
      setUploadError(null);
      setTestResult(null);
    }
  };

  const handleAnalyze = async () => {
    if (!file) {
      setUploadError("Veuillez sélectionner un document.");
      return;
    }
    if (!selectedModel?.id) {
      setUploadError("Veuillez sélectionner un modèle actif.");
      return;
    }
    setTestLoading(true);
    setAlert(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("model_id", selectedModel.id);
      formData.append("norm_id", selectedNormId);
      const res = await api.post("/ml/test-document/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setTestResult(res.data);
      setAlert({ type: "success", message: "Document analysé avec succès." });
    } catch (err) {
      console.error(err);
      setAlert({ type: "error", message: err.response?.data?.error || "L'analyse du document a échoué." });
    } finally {
      setTestLoading(false);
    }
  };

  const activeModel = selectedModel || bestModel;

  return (
    <Layout>
      <div className="space-y-8 px-4 pb-10 pt-6 sm:px-6 lg:px-8">
        <section className="rounded-[2rem] border border-slate-200 bg-slate-950/80 shadow-xl shadow-slate-900/10 backdrop-blur-xl">
          <div className="rounded-[2rem] bg-gradient-to-r from-slate-900 via-slate-950 to-slate-900 px-6 py-8 sm:px-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-3xl">
                <p className="text-xs uppercase tracking-[0.35em] text-sky-300/80">Advanced ML Training Dashboard</p>
                <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Train, compare and validate ISO compliance models.</h1>
                <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300/90">
                  Select an ISO standard, train multiple models, compare performance, choose the winning model, and test incoming documents in a single enterprise workflow.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-[1fr_auto] lg:grid-cols-[auto_auto] xl:grid-cols-[auto_auto_auto]">
                <div className="rounded-3xl border border-slate-800 bg-slate-900/70 p-4 text-white shadow-xl shadow-slate-900/10">
                  <label className="mb-2 block text-xs font-semibold uppercase tracking-[0.3em] text-slate-400">Select Norm</label>
                  {normsLoading ? (
                    <div className="h-12 rounded-2xl bg-slate-800 animate-pulse" />
                  ) : (
                    <select
                      value={selectedNormId ?? ''}
                      onChange={(event) => handleNormChange(event.target.value)}
                      disabled={norms.length === 0}
                      className="w-full rounded-2xl border border-slate-700 bg-slate-950 px-4 py-3 text-sm text-white outline-none transition focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 disabled:opacity-50"
                    >
                      {norms.length === 0 ? (
                        <option value="">No norms available</option>
                      ) : (
                        norms.map((norm) => (
                          <option key={norm.id} value={String(norm.id)} className="bg-slate-950 text-white">
                            {norm.name}
                          </option>
                        ))
                      )}
                    </select>
                  )}
                </div>
                <button
                  type="button"
                  onClick={handleTrain}
                  disabled={trainLoading}
                  className="inline-flex items-center justify-center gap-3 rounded-3xl bg-sky-500 px-5 py-3 text-sm font-semibold text-white shadow-xl shadow-sky-500/20 transition hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <Zap size={18} />
                  {trainLoading ? "Training..." : "🚀 Train Selected Norm"}
                </button>
                <button
                  type="button"
                  onClick={handleCompare}
                  disabled={compareLoading}
                  className="inline-flex items-center justify-center gap-3 rounded-3xl border border-slate-700 bg-slate-900 px-5 py-3 text-sm font-semibold text-white shadow-xl shadow-slate-900/20 transition hover:border-sky-500 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  <TrendingUp size={18} />
                  {compareLoading ? "Comparing..." : "📊 Compare Models"}
                </button>
              </div>
            </div>
          </div>
        </section>

        <section className="grid gap-4 md:grid-cols-5">
          <div className="rounded-[2rem] border border-slate-200 bg-white/95 p-6 shadow-sm backdrop-blur-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">Total Samples</p>
            <p className="mt-4 text-4xl font-bold text-slate-950">{statsLoading ? "—" : datasetStats?.total_samples ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-500">Training dataset size</p>
          </div>
          <div className="rounded-[2rem] border border-slate-200 bg-white/95 p-6 shadow-sm backdrop-blur-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">Valid Samples</p>
            <p className="mt-4 text-4xl font-bold text-emerald-600">{statsLoading ? "—" : datasetStats?.valid_samples ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-500">{datasetStats ? `${((datasetStats.valid_samples / datasetStats.total_samples) * 100).toFixed(1)}%` : "—"}</p>
          </div>
          <div className="rounded-[2rem] border border-slate-200 bg-white/95 p-6 shadow-sm backdrop-blur-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">Invalid Samples</p>
            <p className="mt-4 text-4xl font-bold text-red-600">{statsLoading ? "—" : datasetStats?.invalid_samples ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-500">{datasetStats ? `${((datasetStats.invalid_samples / datasetStats.total_samples) * 100).toFixed(1)}%` : "—"}</p>
          </div>
          <div className="rounded-[2rem] border border-slate-200 bg-white/95 p-6 shadow-sm backdrop-blur-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-slate-500">Rules Count</p>
            <p className="mt-4 text-4xl font-bold text-slate-950">{statsLoading ? "—" : datasetStats?.rules_count ?? "—"}</p>
            <p className="mt-2 text-sm text-slate-500">Validation rules</p>
          </div>
          <div className="rounded-[2rem] border border-cyan-200 bg-cyan-50 p-6 shadow-sm backdrop-blur-xl">
            <p className="text-sm font-semibold uppercase tracking-[0.25em] text-cyan-700">Selected Norm</p>
            <p className="mt-4 text-3xl font-bold text-cyan-900">{selectedNorm?.name ?? "—"}</p>
            <p className="mt-2 text-sm text-cyan-700">Current selection</p>
          </div>
        </section>

        <section className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Models Comparison Table</h2>
                <p className="mt-1 text-sm text-slate-500">Compare accuracy, precision, recall and F1 score for each algorithm.</p>
              </div>
              <div className="inline-flex items-center gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">{models.length} models</span>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto px-6 py-6 sm:px-8">
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-[0.2em] text-slate-500">
                  <th className="px-4 py-3">Algorithm</th>
                  <th className="px-4 py-3 text-center">Accuracy</th>
                  <th className="px-4 py-3 text-center">Precision</th>
                  <th className="px-4 py-3 text-center">Recall</th>
                  <th className="px-4 py-3 text-center">F1 Score</th>
                  <th className="px-4 py-3 text-center">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {(models.length ? models : ALGORITHMS.map((name) => ({ name, accuracy: 0, precision: 0, recall: 0, f1_score: 0, sample_count: 0, status: "Pending" }))).map((model) => {
                  const isBest = model.name === bestModel?.name;
                  return (
                    <tr key={model.name} className={isBest ? "bg-slate-50" : "bg-white"}>
                      <td className="px-4 py-4 font-semibold text-slate-900">{model.name}</td>
                      <td className="px-4 py-4 text-center text-slate-700">{formatPercent(model.accuracy || 0)}</td>
                      <td className="px-4 py-4 text-center text-slate-700">{formatPercent(model.precision || 0)}</td>
                      <td className="px-4 py-4 text-center text-slate-700">{formatPercent(model.recall || 0)}</td>
                      <td className="px-4 py-4 text-center text-slate-700">{formatPercent(model.f1_score || 0)}</td>
                      <td className="px-4 py-4 text-center">
                        <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${model.status === "Best Model" ? "bg-emerald-100 text-emerald-700" : model.status === "Trained" ? "bg-blue-100 text-blue-700" : "bg-slate-100 text-slate-600"}`}>
                          {isBest ? "Best Model" : model.status || "Pending"}
                        </span>
                      </td>
                      <td className="px-4 py-4 text-right">
                        <button
                          type="button"
                          onClick={() => handleModelSelect(model)}
                          className="rounded-full border border-slate-200 bg-slate-950 px-4 py-2 text-xs font-semibold text-white transition hover:border-sky-400 hover:bg-slate-800"
                        >
                          Select Model
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>

        <section className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
            <div className="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-lg font-semibold text-slate-900">Dataset Entries</h2>
                <p className="mt-1 text-sm text-slate-500">Inspect the exact feature vector stored for training.</p>
              </div>
              <div className="inline-flex items-center gap-3">
                <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">Showing {datasetSamples?.length || 0} of {datasetStats?.total_samples || 0} samples</span>
              </div>
            </div>
          </div>

          <div className="overflow-x-auto px-6 py-6 sm:px-8">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-sm text-slate-500">Page {datasetPage} sur {totalDatasetPages}</p>
              <div className="inline-flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => goToPage(datasetPage - 1)}
                  disabled={datasetPage <= 1}
                  className="rounded-full border border-slate-200 bg-slate-950 px-3 py-2 text-xs font-semibold text-white transition hover:border-sky-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  ← Précédent
                </button>
                <button
                  type="button"
                  onClick={() => goToPage(datasetPage + 1)}
                  disabled={datasetPage >= totalDatasetPages}
                  className="rounded-full border border-slate-200 bg-slate-950 px-3 py-2 text-xs font-semibold text-white transition hover:border-sky-400 hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  Suivant →
                </button>
              </div>
            </div>
            <table className="min-w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-200 text-xs uppercase tracking-[0.2em] text-slate-500">
                  <th className="px-4 py-3">ID</th>
                  <th className="px-4 py-3">Label</th>
                  <th className="px-4 py-3 text-center">Score</th>
                  <th className="px-4 py-3 text-center">Rules</th>
                  <th className="px-4 py-3">Created</th>
                  <th className="px-4 py-3">Details</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {getPagedSamples()?.length > 0 ? (
                  getPagedSamples().map((sample, index) => {
                    const rowKey = sample.id || index;
                    const expanded = expandedSamples.has(rowKey);
                    return (
                      <React.Fragment key={rowKey}>
                        <tr className={expanded ? 'bg-slate-50' : 'hover:bg-slate-50'}>
                          <td className="px-4 py-4 font-medium text-slate-900">#{sample.id}</td>
                          <td className="px-4 py-4">
                            <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${sample.label === 'approved' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'}`}>
                              {sample.label}
                            </span>
                          </td>
                          <td className="px-4 py-4 text-center text-slate-700">{sample.score ? `${sample.score}%` : '—'}</td>
                          <td className="px-4 py-4 text-center text-slate-700">{sample.rules_count || sample.rules?.length || 0} rules</td>
                          <td className="px-4 py-4 text-slate-600">{sample.created_at ? new Date(sample.created_at).toLocaleString() : '—'}</td>
                          <td className="px-4 py-4 text-right">
                            <button
                              type="button"
                              onClick={() => toggleSampleExpanded(rowKey)}
                              className="rounded-full border border-slate-200 bg-slate-950 px-4 py-2 text-xs font-semibold text-white transition hover:border-sky-400 hover:bg-slate-800"
                            >
                              {expanded ? 'Masquer' : 'Voir'}
                            </button>
                          </td>
                        </tr>
                        {expanded && (
                          <tr className="bg-slate-50">
                            <td colSpan="6" className="px-4 py-4">
                              <div className="space-y-4">
                                <div className="grid gap-4 sm:grid-cols-3">
                                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Norme</p>
                                    <p className="mt-2 text-sm font-semibold text-slate-900">{sample.standard || selectedNorm?.name || '—'}</p>
                                  </div>
                                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Features count</p>
                                    <p className="mt-2 text-sm font-semibold text-slate-900">{Array.isArray(sample.features) ? sample.features.length : Object.keys(sample.features || {}).length}</p>
                                  </div>
                                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Feature vector</p>
                                    <p className="mt-2 text-sm font-medium text-slate-700 break-words">{Array.isArray(sample.features) ? sample.features.join(', ') : Object.values(sample.features || {}).join(', ') || '—'}</p>
                                  </div>
                                </div>
                                <div className="rounded-2xl border border-slate-200 bg-white p-4">
                                  <p className="text-sm font-semibold text-slate-900">Rule-level features</p>
                                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                                    {(sample.rules_with_evidence || []).map((ruleItem, ruleIndex) => (
                                      <div key={ruleIndex} className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                                        <p className="text-xs uppercase tracking-[0.2em] text-slate-500">{ruleItem.rule}</p>
                                        <p className="mt-2 text-sm font-semibold text-slate-900">{ruleItem.feature_value ? '1' : '0'}</p>
                                        <p className="mt-1 text-xs text-slate-500">{ruleItem.evidence || 'Aucune évidence détectée'}</p>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })
                ) : (
                  <tr>
                    <td colSpan="6" className="px-4 py-8 text-center text-slate-500">No samples available</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
              <h2 className="text-lg font-semibold text-slate-900">🏆 Best Performing Model</h2>
              <p className="mt-1 text-sm text-slate-500">Inspect the chosen model and activate it for document testing.</p>
            </div>
            <div className="space-y-6 px-6 py-8 sm:px-8">
              <div className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-6">
                <div className="flex items-start gap-4">
                  <div className="mt-1 flex h-14 w-14 items-center justify-center rounded-3xl bg-emerald-100 text-3xl text-emerald-700">🏆</div>
                  <div>
                    <p className="text-sm font-semibold uppercase tracking-[0.2em] text-slate-500">Model name</p>
                    <p className="mt-2 text-xl font-semibold text-slate-900">{activeModel?.name || "No model selected"}</p>
                  </div>
                </div>

                <div className="mt-6 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Linked Norm</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900">{selectedNorm?.name || "N/A"}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Accuracy</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900">{activeModel ? formatPercent(activeModel.accuracy || 0) : "—"}</p>
                  </div>
                </div>

                <div className="mt-4 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Trained date</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900">{activeModel?.trained_date || "N/A"}</p>
                  </div>
                  <div className="rounded-2xl border border-slate-200 bg-white p-4">
                    <p className="text-xs uppercase tracking-[0.2em] text-slate-500">Samples used</p>
                    <p className="mt-2 text-lg font-semibold text-slate-900">{activeModel?.sample_count ?? "—"}</p>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => handleModelSelect(activeModel)}
                  disabled={!activeModel}
                  className="mt-6 inline-flex w-full items-center justify-center gap-3 rounded-full bg-emerald-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <CheckCircle2 size={18} />
                  {activeModel ? "✅ ACTIVE MODEL" : "No Model Available"}
                </button>
              </div>
            </div>
          </div>

          <div className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
            <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
              <h2 className="text-lg font-semibold text-slate-900">Test Document with Selected Model</h2>
              <p className="mt-1 text-sm text-slate-500">Upload a PDF or DOCX and run compliance prediction.</p>
            </div>
            {!selectedModel ? (
              <div className="px-6 py-12 text-center sm:px-8">
                <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-100">
                  <AlertCircle size={32} className="text-amber-600" />
                </div>
                <p className="mt-4 text-lg font-semibold text-slate-900">Select a Model First</p>
                <p className="mt-2 text-sm text-slate-500">Please select an active model from the comparison table to enable document testing.</p>
              </div>
            ) : (
              <div className="space-y-6 px-6 py-8 sm:px-8">
                <div
                  onDragOver={(event) => event.preventDefault()}
                  onDragEnter={() => setIsDragActive(true)}
                  onDragLeave={() => setIsDragActive(false)}
                  onDrop={handleDrop}
                  className={`group rounded-[1.75rem] border-2 ${isDragActive ? "border-sky-400 bg-sky-50" : "border-dashed border-slate-300 bg-slate-50"} p-8 text-center transition`}
                >
                  <UploadCloud size={40} className="mx-auto text-slate-500" />
                  <p className="mt-4 text-lg font-semibold text-slate-900">Drag & drop PDF / DOCX here</p>
                  <p className="mt-2 text-sm text-slate-500">or browse to upload your compliance document</p>
                  <input type="file" accept=".pdf,.docx" onChange={handleFileChange} className="mt-6 hidden" id="upload-input" />
                  <label htmlFor="upload-input" className="mt-4 inline-flex cursor-pointer rounded-full bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800">
                    Browse file
                  </label>
                </div>

                {file ? (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                    <div className="flex items-center justify-between gap-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-900">{file.name}</p>
                        <p className="mt-1 text-sm text-slate-500">{(file.size / 1024).toFixed(1)} KB · {file.type || "unknown format"}</p>
                      </div>
                      <span className="inline-flex items-center rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] text-slate-600">Ready</span>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-5 text-center text-sm text-slate-500">
                    No document selected yet.
                  </div>
                )}

                {uploadError && (
                  <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{uploadError}</div>
                )}

                <button
                  type="button"
                  onClick={handleAnalyze}
                  disabled={testLoading || !file}
                  className="inline-flex w-full items-center justify-center gap-3 rounded-full bg-slate-950 px-5 py-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {testLoading ? "Analyzing..." : "🔍 Analyze Document"}
                </button>
              </div>
            )}
          </div>
        </section>

        <section className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 px-6 py-5 sm:px-8">
            <h2 className="text-lg font-semibold text-slate-900">Prediction Results</h2>
            <p className="mt-1 text-sm text-slate-500">Review compliance score, decision, and rule-level confidence.</p>
          </div>

          {!testResult ? (
            <div className="px-6 py-16 text-center text-slate-500 sm:px-8">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <Sparkles size={28} />
              </div>
              <p className="mt-6 text-lg font-semibold text-slate-900">No document analyzed yet</p>
              <p className="mt-2 text-sm text-slate-500">Upload a file and select a model to see the compliance prediction.</p>
            </div>
          ) : (
            <div className="space-y-6 px-6 py-8 sm:px-8">
              <div className="grid gap-4 lg:grid-cols-2">
                <div className="rounded-[1.75rem] border border-slate-200 bg-slate-50 p-6">
                  <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Compliance Score</p>
                  <p className="mt-4 text-5xl font-bold text-slate-950">{formatPercent(testResult.compliance_score / 100)}</p>
                  <div className="mt-4 h-3 overflow-hidden rounded-full bg-slate-200">
                    <div className="h-3 rounded-full bg-emerald-500" style={{ width: `${testResult.compliance_score}%` }} />
                  </div>
                </div>

                <div className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm">
                  <p className="text-sm uppercase tracking-[0.2em] text-slate-500">Prediction</p>
                  <div className="mt-4 flex items-center gap-3">
                    {testResult.prediction === "APPROVED" ? (
                      <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-4 py-2 text-sm font-semibold text-emerald-700">
                        <CheckCircle2 size={18} /> APPROVED
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-2 rounded-full bg-red-100 px-4 py-2 text-sm font-semibold text-red-700">
                        <XCircle size={18} /> REJECTED
                      </span>
                    )}
                  </div>
                  <p className="mt-4 text-sm text-slate-500">Model used: {selectedModel?.name || "—"}</p>
                </div>
              </div>

              <div className="overflow-x-auto rounded-[1.75rem] border border-slate-200 bg-white p-4 shadow-sm">
                <table className="min-w-full text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs uppercase tracking-[0.2em] text-slate-500">
                      <th className="px-4 py-3">Rule</th>
                      <th className="px-4 py-3">Prediction</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Evidence</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {testResult.rules?.map((rule) => (
                      <tr key={rule.rule} className="hover:bg-slate-50">
                        <td className="px-4 py-4 font-medium text-slate-900">{rule.rule}</td>
                        <td className="px-4 py-4 text-slate-700">{rule.prediction}</td>
                        <td className="px-4 py-4">
                          <div className="max-w-xs">
                            <div className="h-2 rounded-full bg-slate-200">
                              <div className="h-2 rounded-full bg-sky-500" style={{ width: `${rule.confidence}%` }} />
                            </div>
                            <p className="mt-2 text-xs text-slate-500">{rule.confidence}%</p>
                          </div>
                        </td>
                        <td className="px-4 py-4 text-slate-600">{rule.evidence || "No evidence provided."}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>

        {alert && (
          <div className={`rounded-[1.75rem] border px-5 py-4 text-sm shadow-sm ${alert.type === "success" ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-red-200 bg-red-50 text-red-900"}`}>
            {alert.message}
          </div>
        )}
      </div>
    </Layout>
  );
}
