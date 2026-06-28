import React, { useCallback, useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Zap, TrendingUp, UploadCloud, CheckCircle2, Sparkles, AlertCircle, X } from "lucide-react";
import Layout from "../components/Layout";
import { UserContext } from "../context/UserContext";
import api from "../services/api";
import {
  safePercent, formatPercent, safeCount,
  isModelTrained, getBestModel, getModelStatus,
} from "../utils/dashboardUtils";

const CLASSIFICATION_ALGORITHMS = ["RandomForest","LogisticRegression","GradientBoosting","BiLSTM"];
const EVIDENCE_ALGORITHMS = ["SentenceTransformer"];
const ALL_ALGORITHMS = [...CLASSIFICATION_ALGORITHMS, ...EVIDENCE_ALGORITHMS];

const DATASET_LABELS = {
  classification: "Classification Dataset",
  evidence: "Evidence Dataset",
};
const DATASET_DESCRIPTIONS = {
  classification: "Train compliance prediction models from labeled ISO rule vectors.",
  evidence: "Train semantic memory from TeamLead evidence, rules and recommendations.",
};

const normalizeAlgorithmName = (rawName) => {
  if (!rawName) return rawName;
  const cleaned = rawName.replace(/^(?:ISO[_-]?9001[_-]?)/i, '');
  if (ALL_ALGORITHMS.includes(cleaned)) return cleaned;
  if (ALL_ALGORITHMS.includes(rawName)) return rawName;
  const parts = cleaned.split('_');
  return parts.length > 1 && ALL_ALGORITHMS.includes(parts[parts.length - 1])
    ? parts[parts.length - 1] : rawName;
};

const normalizeModels = (data) => {
  if (!data) return [];
  const normalizeItem = (item) => {
    const rawName = item.name || item.algorithm || item.id;
    const name = normalizeAlgorithmName(rawName);
    return { ...item, id: item.id || name, name, algorithm: name,
      cross_validation: item.cross_validation || item.cv_metrics || null,
      feature_importance: Array.isArray(item.feature_importance) ? item.feature_importance : [] };
  };
  const items = Array.isArray(data.models) ? data.models.map(normalizeItem)
    : Array.isArray(data) ? data.map(normalizeItem)
    : data.results && typeof data.results === 'object'
    ? Object.entries(data.results).map(([name, metrics]) => {
        const n = normalizeAlgorithmName(name);
        return { id: metrics.id || n, name: n, algorithm: n,
          accuracy: metrics.accuracy, precision: metrics.precision,
          recall: metrics.recall, f1_score: metrics.f1_score,
          trained_date: metrics.trained_date, sample_count: metrics.sample_count,
          train_size: metrics.train_size, val_size: metrics.val_size, test_size: metrics.test_size,
          is_best: n === data.best_model,
          confusion_matrix: metrics.confusion_matrix, confusion_counts: metrics.confusion_counts,
          train_metrics: metrics.train_metrics, validation_metrics: metrics.validation_metrics,
          test_metrics: metrics.test_metrics, overfitting_gap: metrics.overfitting_gap,
          overfitting_level: metrics.overfitting_level, split_strategy: metrics.split_strategy,
          unique_documents: metrics.unique_documents, cross_validation: metrics.cross_validation,
          feature_importance: metrics.feature_importance, pipeline: metrics.pipeline,
          training_time: metrics.training_time, error: metrics.error };
      }) : [];
  return items
    .filter(item => ALL_ALGORITHMS.includes(item.algorithm) && item.exists !== false)
    .reduce((acc, item) => { if (!acc.some(e => e.algorithm === item.algorithm)) acc.push(item); return acc; }, []);
};

export default function MLDashboard() {
  const { user } = useContext(UserContext);
  const navigate = useNavigate();

  const [norms, setNorms]               = useState([]);
  const [selectedNormId, setSelectedNormId] = useState('');
  const [selectedNorm, setSelectedNorm] = useState(null);
  const [datasetType, setDatasetType]   = useState('classification');
  const [datasetStats, setDatasetStats] = useState(null);
  const [datasetSamples, setDatasetSamples] = useState([]); // eslint-disable-line no-unused-vars
  const [diagnostics, setDiagnostics]   = useState(null);
  const [datasetPage, setDatasetPage]   = useState(1); // eslint-disable-line no-unused-vars
  const [expandedSamples, setExpandedSamples] = useState(new Set()); // eslint-disable-line no-unused-vars
  const [models, setModels]             = useState([]);
  const [bestModel, setBestModel]       = useState(null);
  const [selectedModel, setSelectedModel] = useState(null);

  const [normsLoading, setNormsLoading]     = useState(true);
  const [statsLoading, setStatsLoading]     = useState(false);
  const [trainLoading, setTrainLoading]     = useState(false);
  const [compareLoading, setCompareLoading] = useState(false);
  const [testLoading, setTestLoading]       = useState(false);

  const [alert, setAlert]           = useState(null);
  const [file, setFile]             = useState(null);
  const [isDragActive, setIsDragActive] = useState(false);
  const [testResult, setTestResult] = useState(null);
  const [uploadError, setUploadError] = useState(null);

  useEffect(() => {
    if (!user || user.role !== "ADMIN") { navigate("/dashboard"); return; }
    fetchNorms();
  }, [user, navigate]); // eslint-disable-line

  const fetchNorms = async () => {
    setNormsLoading(true); setAlert(null);
    let normsData = [];
    try {
      for (const ep of ["/norms/", "/normes/"]) {
        try {
          const res = await api.get(ep);
          normsData = Array.isArray(res.data) ? res.data : res.data.results || [];
          if (normsData.length > 0) break;
        } catch (e) { if (e.response?.status !== 404) throw e; }
      }
      if (!normsData.length) throw new Error("No norms");
      setNorms(normsData);
      setSelectedNormId(String(normsData[0].id));
      setSelectedNorm(normsData[0]);
    } catch (err) {
      console.error(err);
      setAlert({ type: "error", message: "Impossible de charger les normes." });
    } finally { setNormsLoading(false); }
  };

  const handleNormChange = (normId) => {
    const norm = norms.find(n => String(n.id) === String(normId)) || norms[0] || null;
    setSelectedNormId(String(normId)); setSelectedNorm(norm);
    setModels([]); setBestModel(null); setSelectedModel(null); setTestResult(null);
  };

  const toggleSampleExpanded = (_id) => { // eslint-disable-line no-unused-vars
    setExpandedSamples(cur => { const n = new Set(cur); n.has(_id) ? n.delete(_id) : n.add(_id); return n; });
  };

  const fetchDatasetStats = useCallback(async (normId) => {
    setStatsLoading(true);
    try {
      const res = await api.get(`/dataset-stats/?norm_id=${normId}&dataset_type=${datasetType}`);
      setDatasetStats(res.data); setDatasetSamples(res.data.samples || []);
      setDatasetPage(1); setExpandedSamples(new Set());
    } catch { setDatasetStats(null); setDatasetSamples([]); }
    finally { setStatsLoading(false); }
  }, [datasetType]);

  // eslint-disable-next-line no-unused-vars
  const PAGE_SIZE = 10;
  // eslint-disable-next-line no-unused-vars
  const getPagedSamples = () => datasetSamples.slice((datasetPage-1)*PAGE_SIZE, datasetPage*PAGE_SIZE);
  const totalDatasetPages = Math.max(1, Math.ceil(datasetSamples.length / PAGE_SIZE));
  // eslint-disable-next-line no-unused-vars
  const goToPage = (p) => setDatasetPage(Math.max(1, Math.min(totalDatasetPages, p)));

  const fetchModels = useCallback(async (normId) => {
    setCompareLoading(true); setAlert(null);
    try {
      const res = await api.get(`/ml/models/?norm_id=${normId}&dataset_type=${datasetType}`);
      const normalized = normalizeModels(res.data);
      setModels(normalized);
      const best = getBestModel(normalized);
      setBestModel(best); setSelectedModel(best);
    } catch (err) {
      setAlert({ type: "error", message: err.response?.data?.error || "Impossible de récupérer les modèles." });
      setModels([]); setBestModel(null); setSelectedModel(null);
    } finally { setCompareLoading(false); }
  }, [datasetType]);

  const fetchDiagnostics = useCallback(async (normId) => {
    try { const res = await api.get(`/ml/diagnostics/?norm_id=${normId}`); setDiagnostics(res.data); }
    catch { setDiagnostics(null); }
  }, []);

  useEffect(() => {
    if (selectedNormId) {
      fetchDatasetStats(selectedNormId);
      fetchDiagnostics(selectedNormId);
      fetchModels(selectedNormId);
    }
  }, [selectedNormId, fetchDatasetStats, fetchDiagnostics, fetchModels]);

  const handleTrain = async () => {
    if (!selectedNormId) { setAlert({ type:"error", message:"Veuillez sélectionner une norme." }); return; }
    setTrainLoading(true); setAlert(null); setTestResult(null);
    try {
      const payload = { norm_id: selectedNormId, dataset_type: datasetType };
      if (selectedNorm?.name) payload.standard = selectedNorm.name;
      const res = await api.post(datasetType==="evidence" ? "/ml/train-evidence/" : "/ml/train/", payload);
      const normalized = normalizeModels(res.data);
      setModels(normalized);
      const best = getBestModel(normalized);
      setBestModel(best); setSelectedModel(best);
      setAlert({ type:"success", message:`Training complete — ${DATASET_LABELS[datasetType]}: ${selectedNorm?.name||""}` });
    } catch (err) {
      setAlert({ type:"error", message: err.response?.data?.error || "Training failed." });
    } finally { setTrainLoading(false); }
  };

  const handleCompare = async () => {
    if (!selectedNormId) return;
    setCompareLoading(true); setAlert(null);
    try { await fetchModels(selectedNormId); setAlert({ type:"success", message:"Models refreshed." }); }
    catch { } finally { setCompareLoading(false); }
  };

  const handleModelSelect = (model) => {
    setSelectedModel(model);
    setAlert({ type:"success", message:`${model.name} selected as active model.` });
  };

  const handleFileChange = (e) => {
    setUploadError(null);
    const f = e.target.files?.[0] || null;
    if (f) { setFile(f); setTestResult(null); }
  };

  const handleDrop = (e) => {
    e.preventDefault(); setIsDragActive(false);
    const f = e.dataTransfer.files?.[0] || null;
    if (f) { setFile(f); setUploadError(null); setTestResult(null); }
  };

  const handleAnalyze = async () => {
    if (!file)          { setUploadError("Please select a document."); return; }
    if (!activeModel?.id) { setUploadError("Please select a trained model."); return; }
    setTestLoading(true); setAlert(null);
    try {
      const fd = new FormData();
      fd.append("file", file); fd.append("model_id", activeModel.id);
      fd.append("norm_id", selectedNormId); fd.append("dataset_type", datasetType);
      if (selectedNorm?.name) fd.append("standard", selectedNorm.name);
      const res = await api.post(datasetType==="evidence" ? "/ml/test-evidence/" : "/ml/test-document/", fd, {
        headers: { "Content-Type":"multipart/form-data" }
      });
      setTestResult(res.data);
      setAlert({ type:"success", message:"Document analyzed successfully." });
    } catch (err) {
      setAlert({ type:"error", message: err.response?.data?.error || "Analysis failed." });
    } finally { setTestLoading(false); }
  };

  const activeModel = isModelTrained(selectedModel) ? selectedModel : bestModel;
  const recommendedSourceLabel = diagnostics?.recommended_source === 'document'
    ? 'Document-level pipeline' : 'Evidence retrieval pipeline';

  return (
    <Layout>
      <div className="page-container">

        {/* Header */}
        <div className="page-header">
          <div>
            <p className="section-label">AI / Machine Learning</p>
            <h1 className="page-title mt-1">ML Dashboard</h1>
            <p className="page-subtitle">{DATASET_DESCRIPTIONS[datasetType]}</p>
            {diagnostics && (
              <span className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-brand-200 bg-brand-50 px-2.5 py-1 text-xs font-medium text-brand-700">
                Recommended: {recommendedSourceLabel}
              </span>
            )}
          </div>
          <div className="flex flex-wrap items-end gap-3">
            <div>
              <label className="form-label">Dataset</label>
              <select value={datasetType} className="form-select"
                onChange={e => { setDatasetType(e.target.value); setModels([]); setBestModel(null); setSelectedModel(null); setTestResult(null); }}>
                <option value="classification">Classification</option>
                <option value="evidence">Evidence</option>
              </select>
            </div>
            <div>
              <label className="form-label">Standard</label>
              {normsLoading ? <div className="skeleton h-9 w-40 rounded-lg" /> : (
                <select value={selectedNormId ?? ''} disabled={!norms.length}
                  onChange={e => handleNormChange(e.target.value)} className="form-select">
                  {!norms.length ? <option value="">No standards</option>
                    : norms.map(n => <option key={n.id} value={String(n.id)}>{n.name}</option>)}
                </select>
              )}
            </div>
            <button onClick={handleTrain} disabled={trainLoading} className="btn-primary">
              <Zap size={15}/> {trainLoading ? "Training…" : "Train"}
            </button>
            <button onClick={handleCompare} disabled={compareLoading} className="btn-secondary">
              <TrendingUp size={15}/> {compareLoading ? "Loading…" : "Refresh"}
            </button>
          </div>
        </div>

        {/* Alert */}
        {alert && (
          <div className={`alert ${alert.type==='error' ? 'alert-danger' : 'alert-success'}`}>
            {alert.type==='error' ? <AlertCircle size={14} className="shrink-0"/> : <CheckCircle2 size={14} className="shrink-0"/>}
            <span>{alert.message}</span>
            <button onClick={() => setAlert(null)} className="ml-auto"><X size={13}/></button>
          </div>
        )}

        {/* KPI cards */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="kpi-card">
            <p className="kpi-label">Total Samples</p>
            <p className="kpi-value mt-2">{statsLoading ? "—" : (datasetStats?.total_samples ?? "—")}</p>
            <p className="text-xs text-slate-500 mt-1">Training dataset</p>
          </div>
          <div className="kpi-card bg-emerald-50 border-emerald-200">
            <p className="kpi-label text-emerald-700">{datasetType==="classification" ? "Approved" : "Indexed Vectors"}</p>
            <p className="text-3xl font-bold text-emerald-600 tabular-nums mt-2">
              {statsLoading ? "—" : datasetType==="classification"
                ? safeCount(datasetStats?.approved_samples ?? datasetStats?.valid_samples, "0")
                : safeCount(datasetStats?.indexed_vectors ?? datasetStats?.vector_count, "0")}
            </p>
            <p className="text-xs text-emerald-700 mt-1">
              {datasetType==="classification"
                ? (datasetStats ? formatPercent(safePercent(datasetStats.approved_samples ?? datasetStats.valid_samples, datasetStats.total_samples)) : "—")
                : "Semantic index"}
            </p>
          </div>
          <div className="kpi-card bg-red-50 border-red-200">
            <p className="kpi-label text-red-700">{datasetType==="classification" ? "Rejected" : "Docs Indexed"}</p>
            <p className="text-3xl font-bold text-red-600 tabular-nums mt-2">
              {statsLoading ? "—" : datasetType==="classification"
                ? safeCount(datasetStats?.invalid_samples, "0")
                : safeCount(datasetStats?.document_count ?? datasetStats?.indexed_documents ?? 0, "0")}
            </p>
            <p className="text-xs text-red-700 mt-1">
              {datasetType==="classification"
                ? (datasetStats ? formatPercent(safePercent(datasetStats.invalid_samples, datasetStats.total_samples)) : "—")
                : "Coverage"}
            </p>
          </div>
          <div className="kpi-card">
            <p className="kpi-label">{datasetType==="classification" ? "Rules" : "Embed Dim"}</p>
            <p className="kpi-value mt-2">{statsLoading ? "—" : datasetType==="classification" ? (datasetStats?.rules_count ?? "—") : (datasetStats?.embedding_dim ?? "—")}</p>
            <p className="text-xs text-slate-500 mt-1">{datasetType==="classification" ? "Validation rules" : "Vector size"}</p>
          </div>
          <div className="kpi-card bg-brand-50 border-brand-200">
            <p className="kpi-label text-brand-700">Active Standard</p>
            <p className="text-xl font-bold text-brand-700 mt-2 truncate">{selectedNorm?.name ?? "—"}</p>
            <p className="text-xs text-brand-600 mt-1">Current selection</p>
          </div>
        </div>

        {/* Models Comparison Table */}
        <div className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Models Comparison</h2>
              <p className="text-xs text-slate-500 mt-0.5">Accuracy · Precision · Recall · F1 Score per algorithm</p>
            </div>
            <span className="badge badge-slate">{models.length} models</span>
          </div>
          <div className="overflow-x-auto">
            <table className="table-enterprise">
              <thead>
                <tr>
                  <th>Algorithm</th>
                  {datasetType==="classification" ? (<>
                    <th className="text-center">Accuracy</th>
                    <th className="text-center">Precision</th>
                    <th className="text-center">Recall</th>
                    <th className="text-center">F1</th>
                    <th className="text-center">Overfit</th>
                    <th className="text-center">Split</th>
                    <th className="text-center">Train/Test</th>
                  </>) : (<>
                    <th className="text-center">Indexed</th>
                    <th className="text-center">Embed Dim</th>
                  </>)}
                  <th className="text-center">Status</th>
                  <th/>
                </tr>
              </thead>
              <tbody>
                {compareLoading ? (
                  [1,2,3].map(i => (
                    <tr key={i}>
                      {[1,2,3,4,5,6,7,8,9].map(j => (
                        <td key={j} className="px-4 py-3"><div className="skeleton h-4 rounded"/></td>
                      ))}
                    </tr>
                  ))
                ) : models.length === 0 ? (
                  <tr>
                    <td colSpan={datasetType==="classification" ? 10 : 5} className="px-4 py-10 text-center text-sm text-slate-400">
                      No models trained yet. Click "Train" to begin.
                    </td>
                  </tr>
                ) : (
                  models.map(model => {
                    const isBest     = model.name === bestModel?.name;
                    const mStatus    = getModelStatus(model);
                    const hasTrained = isModelTrained(model);
                    const ovfLevel   = model.overfitting_level || (model.overfitting_gap >= 0.15 ? 'HIGH' : model.overfitting_gap >= 0.08 ? 'MEDIUM' : 'LOW');
                    return (
                      <tr key={model.name} className={isBest ? "bg-brand-50/40" : ""}>
                        <td>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-slate-900">{model.name}</span>
                            {isBest && !bestModel?.is_tie && <span className="badge badge-green text-2xs">Best</span>}
                            {isBest && bestModel?.is_tie && <span className="badge badge-amber text-2xs">Tie</span>}
                          </div>
                        </td>
                        {datasetType==="classification" ? (<>
                          <td className="text-center tabular-nums">{hasTrained ? formatPercent(model.accuracy) : "—"}</td>
                          <td className="text-center tabular-nums">{hasTrained ? formatPercent(model.precision) : "—"}</td>
                          <td className="text-center tabular-nums">{hasTrained ? formatPercent(model.recall) : "—"}</td>
                          <td className="text-center font-semibold tabular-nums">{hasTrained ? formatPercent(model.f1_score) : "—"}</td>
                          <td className="text-center">
                            {hasTrained && model.overfitting_gap != null ? (
                              <span className={`badge ${ovfLevel==="HIGH" ? "badge-red" : ovfLevel==="MEDIUM" ? "badge-amber" : "badge-green"}`}>
                                {ovfLevel}
                              </span>
                            ) : "—"}
                          </td>
                          <td className="text-center">
                            {model.split_strategy
                              ? <span className={`badge ${model.split_strategy==="grouped" ? "badge-sky" : "badge-slate"}`}>{model.split_strategy}</span>
                              : <span className="text-xs text-slate-400">stratified</span>}
                          </td>
                          <td className="text-center text-xs tabular-nums">
                            {hasTrained && (model.train_size || model.test_size)
                              ? `${(model.train_size||0).toLocaleString()} / ${(model.test_size||0).toLocaleString()}` : "—"}
                          </td>
                        </>) : (<>
                          <td className="text-center">{safeCount(model.sample_count || model.index_size || 0,"0")}</td>
                          <td className="text-center">{model.embedding_dim ?? model.vector_dim ?? "—"}</td>
                        </>)}
                        <td className="text-center">
                          <span className={`badge ${mStatus.color}`}>{mStatus.label}</span>
                        </td>
                        <td className="text-right">
                          <button onClick={() => handleModelSelect(model)} disabled={!hasTrained} className="btn-secondary btn-sm">
                            Select
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Diagnostics */}
        {diagnostics && (
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Dataset Diagnostics</h2>
            </div>
            <div className="card-body">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label:"Dataset Completeness", val: formatPercent(diagnostics.dataset_completeness) },
                  { label:"Duplicate Rate",        val: formatPercent(diagnostics.duplicate_rate) },
                  { label:"Class Balance",         val: formatPercent(diagnostics.class_balance) },
                  { label:"Leakage Risk",          val: formatPercent(diagnostics.leakage_risk) },
                ].map(d => (
                  <div key={d.label} className="rounded-lg bg-slate-50 px-4 py-3">
                    <p className="text-xs text-slate-500">{d.label}</p>
                    <p className="text-2xl font-bold text-slate-900 tabular-nums mt-1">{d.val}</p>
                  </div>
                ))}
              </div>
              {isModelTrained(selectedModel) && selectedModel?.accuracy >= 0.99 && (
                <div className="mt-4 alert alert-warning">
                  <AlertCircle size={14} className="shrink-0"/>
                  <span><strong>Warning:</strong> Suspiciously perfect metrics — verify no data leakage in the training pipeline.</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Active model info */}
        {activeModel && isModelTrained(activeModel) && (
          <div className="card">
            <div className="card-header">
              <div className="flex items-center gap-2">
                <h2 className="card-title">Active Model</h2>
                <span className="badge badge-green">
                  <CheckCircle2 size={10}/> {activeModel.name}
                </span>
              </div>
              <span className="text-xs text-slate-500">Used for document analysis</span>
            </div>
            <div className="card-body">
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label:"F1 Score",  val: formatPercent(activeModel.f1_score),  color:"text-violet-600" },
                  { label:"Accuracy",  val: formatPercent(activeModel.accuracy),  color:"text-brand-600"  },
                  { label:"Precision", val: formatPercent(activeModel.precision), color:"text-emerald-600"},
                  { label:"Recall",    val: formatPercent(activeModel.recall),    color:"text-amber-600"  },
                ].map(m => (
                  <div key={m.label} className="rounded-lg bg-slate-50 px-4 py-3">
                    <p className="text-xs text-slate-500">{m.label}</p>
                    <p className={`text-2xl font-bold tabular-nums mt-1 ${m.color}`}>{m.val}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Document test panel */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Test Document</h2>
            <span className="text-xs text-slate-500">
              {activeModel ? `Using: ${activeModel.name}` : "No model selected"}
            </span>
          </div>
          <div className="card-body space-y-4">
            {uploadError && (
              <div className="alert alert-danger">
                <AlertCircle size={14} className="shrink-0"/>
                <span>{uploadError}</span>
                <button onClick={() => setUploadError(null)} className="ml-auto"><X size={13}/></button>
              </div>
            )}

            {/* Drop zone */}
            <div
              onDragOver={e => { e.preventDefault(); setIsDragActive(true); }}
              onDragLeave={() => setIsDragActive(false)}
              onDrop={handleDrop}
              className={`relative cursor-pointer rounded-xl border-2 border-dashed p-8 text-center transition-all ${
                isDragActive ? "border-brand-400 bg-brand-50" : file ? "border-emerald-300 bg-emerald-50/40" : "border-slate-200 hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              <input type="file" accept=".pdf,.docx,.txt" onChange={handleFileChange} className="absolute inset-0 h-full w-full cursor-pointer opacity-0"/>
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <CheckCircle2 size={20} className="text-emerald-500"/>
                  <div className="text-left">
                    <p className="text-sm font-semibold text-slate-900">{file.name}</p>
                    <p className="text-xs text-slate-500">{(file.size/1024).toFixed(1)} KB — ready to analyze</p>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center gap-2">
                  <UploadCloud size={28} className="text-slate-400"/>
                  <p className="text-sm font-medium text-slate-600">Drag & drop or click to upload</p>
                  <p className="text-xs text-slate-400">PDF, DOCX, TXT supported</p>
                </div>
              )}
            </div>

            <button
              onClick={handleAnalyze}
              disabled={testLoading || !file || !activeModel}
              className="btn-primary w-full justify-center"
            >
              {testLoading
                ? <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"/>Analyzing…</>
                : <><Sparkles size={15}/>Analyze Document</>}
            </button>

            {/* Test result */}
            {testResult && (
              <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-3 animate-fade-in">
                <p className="text-sm font-semibold text-slate-900">Analysis Result</p>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                  {[
                    { label:"Compliance",  val: testResult.compliance_score != null ? `${testResult.compliance_score}%` : "—",  color:"text-brand-600"  },
                    { label:"Prediction",  val: testResult.prediction || testResult.label || "—",                                 color:"text-slate-900" },
                    { label:"Confidence",  val: testResult.confidence   != null ? `${Math.round(testResult.confidence * 100)}%` : "—", color:"text-violet-600"},
                    { label:"Valid Rules", val: testResult.valid_count  != null ? testResult.valid_count : "—",                  color:"text-emerald-600"},
                  ].map(r => (
                    <div key={r.label} className="rounded-lg bg-white border border-slate-200 px-3 py-2.5 text-center">
                      <p className="text-2xs text-slate-500">{r.label}</p>
                      <p className={`text-lg font-bold tabular-nums mt-0.5 ${r.color}`}>{r.val}</p>
                    </div>
                  ))}
                </div>
                {testResult.recommendation && (
                  <div className="alert alert-info text-xs">{testResult.recommendation}</div>
                )}
              </div>
            )}
          </div>
        </div>

      </div>
    </Layout>
  );
}
