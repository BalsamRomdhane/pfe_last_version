import React, { useContext, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Calendar,
  ChevronDown,
  ChevronUp,
  Circle,
  ShieldCheck,
  ShieldX,
  SlidersHorizontal,
  Target,
  Trash2,
} from "lucide-react";
import Layout from "../components/Layout";
import { UserContext } from "../context/UserContext";
import api from "../services/api";

const getScore = (features) => {
  const values = Object.values(features || {}).map((value) => Number(value));
  const binaryValues = values.filter((value) => value === 0 || value === 1);
  if (binaryValues.length === 0) return 0;
  return Math.round((binaryValues.reduce((sum, value) => sum + value, 0) / binaryValues.length) * 100);
};

const getLabelTone = (label) => {
  if (label === "approved") {
    return {
      dot: "bg-emerald-500",
      text: "text-emerald-700",
      badge: "bg-emerald-50 border-emerald-200",
    };
  }

  return {
    dot: "bg-red-500",
    text: "text-red-700",
    badge: "bg-red-50 border-red-200",
  };
};

const getRuleResults = (item) => {
  if (Array.isArray(item.rules_with_evidence) && item.rules_with_evidence.length > 0) {
    return item.rules_with_evidence;
  }

  const source =
    item.rule_results_json && typeof item.rule_results_json === 'object' && !Array.isArray(item.rule_results_json)
      ? item.rule_results_json
      : item.features && typeof item.features === 'object'
      ? item.features
      : {};

  return Object.entries(source)
    .map(([rule, feature_value]) => ({
      rule,
      feature_value: Number(feature_value) === 1 || feature_value === true,
      evidence: '',
    }));
};

const getComplianceScore = (item) => {
  const valid = Number(item.valid_rules_count || 0);
  const total = Number(item.total_rules ?? (item.rule_results_json ? Object.keys(item.rule_results_json).length : 0) ?? 0);

  if (total > 0) {
    return Math.round((valid / total) * 100);
  }

  if (item.compliance_score !== undefined && item.compliance_score !== null) {
    return Math.round(Number(item.compliance_score || 0));
  }

  const ruleResults = getRuleResults(item);
  if (ruleResults.length > 0) {
    const validCount = ruleResults.filter((rule) => rule.feature_value).length;
    return Math.round((validCount / ruleResults.length) * 100);
  }

  return 0;
};

const getScoreTone = (score) => {
  if (score >= 80) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (score >= 50) {
    return "border-amber-200 bg-amber-50 text-amber-700";
  }

  return "border-red-200 bg-red-50 text-red-700";
};

const SummaryCard = ({ title, value, tone }) => {
  const tones = {
    green: "border-emerald-200 bg-white text-emerald-600",
    red: "border-red-200 bg-white text-red-600",
    blue: "border-blue-200 bg-white text-blue-600",
  };

  return (
    <div className={`rounded-2xl border p-5 shadow-sm ${tones[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.22em] text-slate-500">{title}</p>
      <p className="mt-3 text-4xl font-semibold tracking-tight">{value}</p>
    </div>
  );
};

export default function TrainingDataset() {
  const { user } = useContext(UserContext);
  const navigate = useNavigate();
  const [standards, setStandards] = useState([]);
  const [standard, setStandard] = useState(null);
  const [selectedNorm, setSelectedNorm] = useState(null);
  const [activeTab, setActiveTab] = useState('classification');
  const [data, setData] = useState([]);
  const [evidenceData, setEvidenceData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [evidenceLoading, setEvidenceLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);
  const [trainingLoading, setTrainingLoading] = useState(false);
  const [trainingStatus, setTrainingStatus] = useState(null);
  const [trainingAccuracy, setTrainingAccuracy] = useState(null);
  const [trainingSamplesCount, setTrainingSamplesCount] = useState(null);
  const [trainingEmbeddingDim, setTrainingEmbeddingDim] = useState(null);
  const [trainingError, setTrainingError] = useState(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [evidencePage, setEvidencePage] = useState(1);
  const [totalSamples, setTotalSamples] = useState(0);
  const [totalEvidence, setTotalEvidence] = useState(0);
  const [approvedCount, setApprovedCount] = useState(0);
  const [rejectedCount, setRejectedCount] = useState(0);
  const PAGE_SIZE = 10;

  useEffect(() => {
    if (!user || user.role !== "ADMIN") {
      navigate("/dashboard");
      return;
    }

    const loadStandards = async () => {
      try {
        const endpoints = ["/norms/", "/normes/"];
        let normsResponse = null;

        for (const endpoint of endpoints) {
          try {
            const response = await api.get(endpoint);
            if (Array.isArray(response.data) && response.data.length > 0) {
              normsResponse = response.data;
              break;
            }
          } catch (err) {
            if (err.response?.status === 404) {
              continue;
            }
            throw err;
          }
        }

        if (!normsResponse) {
          normsResponse = [];
        }

        const normOptions = normsResponse.map((item) => ({
          value: item.name,
          label: item.name,
          id: item.id,
        }));
        setStandards(normOptions);

        // Only set the default once — do not include `standard` in deps to avoid re-render loop
        setStandard((prev) => {
          if (prev) return prev;
          return normOptions.length > 0 ? normOptions[0].value : null;
        });
        setSelectedNorm((prev) => {
          if (prev) return prev;
          return normOptions.length > 0 ? normOptions[0] : null;
        });
      } catch (err) {
        console.error("Erreur chargement des normes :", err);
        setStandards([]);
        setStandard(null);
        setSelectedNorm(null);
      }
    };

    loadStandards();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user, navigate]); // intentionally omit `standard` to prevent re-render loop

  useEffect(() => {
    if (!standard) {
      return;
    }

    const query = new URLSearchParams();
    query.set('page', activeTab === 'classification' ? currentPage : evidencePage);
    if (selectedNorm?.id) {
      query.set('norm', selectedNorm.id);
    }
    if (standard) {
      query.set('standard', standard);
    }

    const fetchEndpoint = activeTab === 'classification' ? '/training-dataset/' : '/rule-training-samples/';
    const setList = activeTab === 'classification' ? setData : setEvidenceData;
    const setTotal = activeTab === 'classification' ? setTotalSamples : setTotalEvidence;
    const setLoadingState = activeTab === 'classification' ? setLoading : setEvidenceLoading;

    setLoadingState(true);
    api
      .get(`${fetchEndpoint}?${query.toString()}`)
      .then((res) => {
        const results = res.data.results || res.data || [];
        setList(results);
        setExpandedId(null);
        setTotal(res.data.count ?? results.length);
      })
      .catch(() => {
        setList([]);
        setExpandedId(null);
        setTotal(0);
      })
      .finally(() => setLoadingState(false));

    // Fetch approved/rejected counts from dataset-stats for the classification tab
    if (activeTab === 'classification' && selectedNorm?.id) {
      api.get(`/dataset-stats/?norm_id=${selectedNorm.id}`).then((res) => {
        setApprovedCount(res.data.valid_samples ?? 0);
        setRejectedCount(res.data.invalid_samples ?? 0);
        if (!res.data.total_samples) return;
        setTotalSamples(res.data.total_samples);
      }).catch(() => {});
    }
  }, [standard, currentPage, evidencePage, activeTab, selectedNorm]);

  const toggleRow = (id) => {
    setExpandedId((currentId) => (currentId === id ? null : id));
  };

  const handleDelete = async (id) => {
    const confirmed = window.confirm("Confirmer la suppression ?");
    if (!confirmed) {
      return;
    }

    setDeletingId(id);
    try {
      await api.delete(`/training-dataset/${id}/`);
      setData((current) => current.filter((item) => item.id !== id));
    } catch (error) {
      console.error("Erreur suppression :", error);
      window.alert("Impossible de supprimer l'élément. Veuillez réessayer.");
    } finally {
      setDeletingId(null);
    }
  };

  const handleTrain = async () => {
    if (!standard) {
      window.alert('Veuillez sélectionner une norme avant de lancer le training.');
      return;
    }

    setTrainingLoading(true);
    setTrainingError(null);
    setTrainingStatus(null);

    try {
      const payload = {
        standard,
      };
      if (selectedNorm?.id) {
        payload.norm_id = selectedNorm.id;
      }

      // Choose endpoint depending on the active dataset tab
      const endpoint = activeTab === 'evidence' ? '/ml/train-evidence/' : '/train-model/';
      const res = await api.post(endpoint, payload);
      setTrainingStatus('success');

      // Parse response: classification -> accuracy/samples, evidence -> indexed counts / embedding dim
      setTrainingAccuracy(res.data.accuracy ?? null);
      setTrainingSamplesCount(res.data.samples ?? res.data.indexed_vectors ?? res.data.indexed_documents ?? res.data.indexed_count ?? null);
      setTrainingEmbeddingDim(res.data.embedding_dim ?? res.data.vector_dim ?? null);

      if (activeTab === 'evidence') {
        const indexed = res.data.indexed_vectors || res.data.indexed_documents || res.data.indexed_count || 'N/A';
        window.alert(`Evidence index built\nIndexed: ${indexed}`);
      } else {
        window.alert(`Training terminé\nAccuracy: ${res.data.accuracy}`);
      }
    } catch (error) {
      console.error('Erreur training :', error);
      setTrainingStatus('error');
      const errorMsg = error.response?.data?.error || 'Erreur lors du training';
      setTrainingError(errorMsg);
      window.alert(errorMsg);
    } finally {
      setTrainingLoading(false);
    }
  };

  const stats = activeTab === 'classification'
    ? {
        total: totalSamples || data.length,
        approved: approvedCount || data.filter((item) => item.label === 'approved').length,
        rejected: rejectedCount || data.filter((item) => item.label === 'rejected').length,
        // Average REAL compliance (from aggregated validations)
        avgScore: data.length ? Math.round(data.reduce((sum, item) => sum + getComplianceScore(item), 0) / data.length) : 0,
      }
    : {
        total: totalEvidence || evidenceData.length,
        approved: 0,
        rejected: 0,
        avgScore: 0,
      };

  const dataRows = activeTab === 'classification' ? data : evidenceData;
  const activePage = activeTab === 'classification' ? currentPage : evidencePage;
  const activeTotal = activeTab === 'classification' ? totalSamples : totalEvidence;
  const activeLoading = activeTab === 'classification' ? loading : evidenceLoading;

  const totalPages = Math.max(1, Math.ceil((activeTotal || dataRows.length) / PAGE_SIZE));
  const canPrev = activePage > 1;
  const canNext = activePage < totalPages;

  const goToPage = (page) => {
    if (activeTab === 'classification') {
      setCurrentPage(page);
    } else {
      setEvidencePage(page);
    }
  };

  const handleStandardChange = (value) => {
    setStandard(value);
    setSelectedNorm(standards.find((item) => item.value === value) || null);
    setCurrentPage(1);
    setEvidencePage(1);
    setApprovedCount(0);
    setRejectedCount(0);
    setTotalSamples(0);
    setTotalEvidence(0);
  };

  return (
    <Layout>
      <div className="space-y-6 px-4 pb-8 pt-6 sm:px-6 lg:px-8">
        <header className="overflow-hidden rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-100 bg-gradient-to-r from-slate-950 via-blue-950 to-sky-800 px-6 py-7 text-white sm:px-8">
            <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
              <div className="max-w-2xl">
                <p className="text-xs uppercase tracking-[0.35em] text-slate-300/75">ML Dataset</p>
                <h1 className="mt-3 text-3xl font-semibold tracking-tight sm:text-4xl">Structured validation samples</h1>
                <p className="mt-3 text-sm leading-7 text-slate-200">
                  Review the generated training dataset, inspect rule-level features, and confirm each sample stays consistent for machine learning.
                </p>
              </div>

              <div className="flex flex-wrap gap-3">
                <div className="rounded-[1.35rem] border border-white/15 bg-white/10 px-4 py-3 backdrop-blur-sm">
                  <p className="text-xs uppercase tracking-[0.25em] text-white/65">Standard</p>
                  <p className="mt-2 text-lg font-semibold">{selectedNorm?.label || "Aucune norme"}</p>
                </div>
                <div className="rounded-[1.35rem] border border-white/15 bg-white/10 px-4 py-3 backdrop-blur-sm">
                  <p className="text-xs uppercase tracking-[0.25em] text-white/65">Samples</p>
                  <p className="mt-2 text-lg font-semibold">{stats.total}</p>
                </div>
              </div>
            </div>
          </div>

          <div className="grid gap-4 px-6 py-6 md:grid-cols-4 md:px-8">
            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">Total samples</p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-900">{stats.total}</p>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-sky-100 text-sky-700">
                  <Target size={22} />
                </div>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">Approved</p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight text-emerald-600">{stats.approved}</p>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-emerald-100 text-emerald-700">
                  <ShieldCheck size={22} />
                </div>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">Rejected</p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight text-red-600">{stats.rejected}</p>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-red-100 text-red-700">
                  <ShieldX size={22} />
                </div>
              </div>
            </div>

            <div className="rounded-[1.5rem] border border-slate-200 bg-slate-50/70 p-5">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-500">Average compliance</p>
                  <p className="mt-3 text-3xl font-semibold tracking-tight text-blue-600">{stats.avgScore}%</p>
                </div>
                <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
                  <SlidersHorizontal size={22} />
                </div>
              </div>
            </div>
          </div>
        </header>

        <section className="rounded-[2rem] border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-4 border-b border-slate-100 px-6 py-5 sm:px-8 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="text-lg font-semibold text-slate-900">Dataset entries</p>
              <p className="mt-1 text-sm text-slate-500">
                Select between the document classification dataset and the rule-level evidence dataset. The evidence view shows rule-level evidence, reviewer comments and recommendations used to build the semantic memory index.
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={() => setActiveTab('classification')}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  activeTab === 'classification'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                Classification dataset
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('evidence')}
                className={`rounded-full px-4 py-2 text-sm font-semibold transition ${
                  activeTab === 'evidence'
                    ? 'bg-slate-900 text-white'
                    : 'border border-slate-300 bg-white text-slate-700 hover:bg-slate-50'
                }`}
              >
                Evidence dataset
              </button>
            </div>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label className="flex items-center gap-3">
                <span className="text-sm font-semibold text-slate-600">Standard</span>
                <select
                  value={standard || ""}
                  onChange={(e) => handleStandardChange(e.target.value)}
                  className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
                >
                  {standards.length > 0 ? (
                    standards.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))
                  ) : (
                    <option value="">Aucune norme disponible</option>
                  )}
                </select>
              </label>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={handleTrain}
                  disabled={trainingLoading}
                  className="inline-flex items-center justify-center rounded-full bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {trainingLoading ? 'Training...' : activeTab === 'evidence' ? '🚀 Build Evidence Index' : '🚀 Lancer Training'}
                </button>

                {trainingStatus && (
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-700">
                    <p className="font-semibold">Statut : {trainingStatus === 'success' ? 'Success' : 'Erreur'}</p>
                    {activeTab === 'classification' && trainingAccuracy !== null && <p>Accuracy : {trainingAccuracy}</p>}
                    {trainingSamplesCount !== null && <p>{activeTab === 'classification' ? 'Samples' : 'Indexed'} : {trainingSamplesCount}</p>}
                    {trainingEmbeddingDim !== null && <p>Embedding dim : {trainingEmbeddingDim}</p>}
                    {trainingError && <p className="text-rose-600">{trainingError}</p>}
                  </div>
                )}
              </div>
            </div>

          {activeLoading ? (
            <div className="flex items-center justify-center px-6 py-20">
              <div className="text-center">
                <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-b-blue-600" />
                <p className="mt-4 text-sm font-medium text-slate-500">Loading dataset...</p>
              </div>
            </div>
          ) : dataRows.length === 0 ? (
            <div className="px-6 py-20 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <Target size={28} />
              </div>
              <p className="mt-5 text-lg font-semibold text-slate-900">
                No {activeTab === 'classification' ? 'training samples' : 'evidence rows'} available
              </p>
              <p className="mt-2 text-sm text-slate-500">
                No dataset entries were found for {selectedNorm?.label || "the selected standard"}.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-slate-500">Showing {dataRows.length} of {activeTotal} samples</p>
                <div className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  <button
                    type="button"
                    onClick={() => canPrev && goToPage(activePage - 1)}
                    disabled={!canPrev}
                    className="rounded-full border border-slate-200 bg-white px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Prev
                  </button>
                  <span>Page {activePage} / {totalPages}</span>
                  <button
                    type="button"
                    onClick={() => canNext && goToPage(activePage + 1)}
                    disabled={!canNext}
                    className="rounded-full border border-slate-200 bg-white px-3 py-2 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80">
                    {activeTab === 'classification' ? (
                      <>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Document</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Label</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Compliance</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Valid rules</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Invalid rules</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Features</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Created</th>
                        <th className="px-8 py-4 text-right text-xs font-semibold uppercase tracking-[0.2em] text-slate-500" />
                      </>
                    ) : (
                      <>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Rule</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Evidence</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Comment</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Recommendation</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Label</th>
                        <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Updated</th>
                      </>
                    )}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-200">
                  {dataRows.map((item) => {
                    if (activeTab === 'classification') {
                      const score = getComplianceScore(item);
                      const ruleResults = getRuleResults(item);
                      const featureVector = Array.isArray(item.feature_vector)
                        ? item.feature_vector
                        : Array.isArray(item.features)
                        ? item.features
                        : Object.values(item.rule_results_json || item.features || {}).map((value) => Number(value || 0));
                      const featuresCount = Number(item.features_count ?? featureVector.length ?? Object.keys(item.rule_results_json || {}).length ?? Object.keys(item.features || {}).length ?? 0);
                      const totalRuleCount = Number(item.total_rules ?? Object.keys(item.rule_results_json || {}).length ?? featureVector.length ?? 0);
                      const validRuleCount = Number(item.valid_rules_count ?? ruleResults.filter((rule) => rule.feature_value).length ?? 0);
                      const invalidRuleCount = Number(item.invalid_rules_count ?? Math.max(totalRuleCount - validRuleCount, 0));
                      
                      const summary = {
                        total: totalRuleCount,
                        valid: validRuleCount,
                        invalid: invalidRuleCount,
                      };
                      const labelTone = getLabelTone(item.label);
                      const isExpanded = expandedId === item.id;
                      const mlConfidence = (item.confidence_score || item.confidence_score === 0)
                        ? (Math.abs(item.confidence_score) <= 1 ? Math.round(item.confidence_score * 100) : Math.round(item.confidence_score))
                        : null;
                      const semanticScore = (item.semantic_score || item.semantic_score === 0) ? Math.round(item.semantic_score) : null;

                    return (
                      <React.Fragment key={item.id}>
                        <tr className="transition hover:bg-slate-50/80">
                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-blue-700">
                              {item.document || item.document_id || `#${item.id}`}
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className={`inline-flex items-center gap-3 rounded-full border px-4 py-2 text-sm font-semibold capitalize ${labelTone.badge} ${labelTone.text}`}>
                              <span className={`h-2.5 w-2.5 rounded-full ${labelTone.dot}`} />
                              {item.label}
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <div>
                              <span className={`inline-flex items-center rounded-2xl border px-4 py-2 text-sm font-semibold ${getScoreTone(score)}`}>
                                {typeof score === 'number' ? `${score}%` : '—'}
                              </span>
                              <div className="mt-2 text-xs text-slate-500">
                                {mlConfidence !== null && <span className="mr-3">ML: {mlConfidence}%</span>}
                                {semanticScore !== null && <span>Semantic: {semanticScore}%</span>}
                              </div>
                            </div>
                          </td>

                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
                              {summary.valid} valid
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-rose-50 px-4 py-2 text-sm font-medium text-rose-700">
                              {summary.invalid} invalid
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-4 py-2 text-sm font-medium text-slate-800">
                              {featuresCount} features
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <div className="flex items-center gap-3 text-sm text-slate-600">
                              <Calendar className="h-4 w-4 text-slate-400" />
                              {new Date(item.created_at).toLocaleDateString("en-US", {
                                year: "numeric",
                                month: "short",
                                day: "numeric",
                                hour: "2-digit",
                                minute: "2-digit",
                              })}
                            </div>
                          </td>

                          <td className="px-8 py-5 text-right">
                            <div className="inline-flex items-center gap-2 justify-end">
                              <button
                                type="button"
                                onClick={() => handleDelete(item.id)}
                                disabled={deletingId === item.id}
                                className="inline-flex h-10 rounded-full border border-rose-200 bg-white px-3 text-rose-600 transition hover:bg-rose-50 disabled:cursor-not-allowed disabled:opacity-60"
                                aria-label={`Delete sample ${item.id}`}
                              >
                                <Trash2 size={16} />
                              </button>

                              <button
                                type="button"
                                onClick={() => toggleRow(item.id)}
                                className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                                aria-label={isExpanded ? `Collapse sample ${item.id}` : `Expand sample ${item.id}`}
                              >
                                {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                              </button>
                            </div>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-slate-50/70">
                            <td colSpan={8} className="px-8 py-8">
                              <div className="space-y-6">
                                <div className="grid gap-4 md:grid-cols-4">
                                  <SummaryCard title="Valid rules" value={summary.valid} tone="green" />
                                  <SummaryCard title="Invalid rules" value={summary.invalid} tone="red" />
                                  <SummaryCard title="Compliance" value={`${score}%`} tone="blue" />
                                  <SummaryCard title="Features" value={featuresCount} tone="blue" />
                                </div>

                                <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50 p-4">
                                  <p className="text-sm font-semibold text-slate-700">Feature vector</p>
                                  <p className="mt-2 text-sm text-slate-900 break-words">[{featureVector.join(', ')}]</p>
                                </div>

                                <div>
                                  <div className="mb-4 flex items-center justify-between gap-4">
                                    <div>
                                      <h3 className="text-2xl font-semibold tracking-tight text-slate-950">Rule Results</h3>
                                      <p className="mt-1 text-sm text-slate-500">
                                        Real ISO rule validation status for {item.standard || standard}
                                      </p>
                                    </div>
                                  </div>

                                  <div className="grid gap-3 lg:grid-cols-2">
                                    {ruleResults.map((rule_item, idx) => (
                                      <div key={idx} className="rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm">
                                        <div className="flex items-center justify-between mb-3">
                                          <div className="flex min-w-0 items-center gap-3">
                                            <Circle size={12} className={rule_item.feature_value ? "fill-emerald-500 text-emerald-500" : "fill-red-500 text-red-500"} />
                                            <span className="text-sm font-medium text-slate-800">{rule_item.rule}</span>
                                          </div>

                                          <span className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium ${rule_item.feature_value ? "bg-emerald-50 text-emerald-700" : "bg-red-50 text-red-700"}`}>
                                            {rule_item.feature_value ? "VALID" : "INVALID"}
                                          </span>
                                        </div>

                                        {rule_item.evidence && (
                                          <div className="mt-3 rounded-lg bg-slate-50 border border-slate-200 p-3">
                                            <p className="text-xs font-semibold text-slate-500 uppercase tracking-[0.1em] mb-1">Evidence</p>
                                            <p className="text-sm text-slate-700 leading-relaxed">{rule_item.evidence}</p>
                                          </div>
                                        )}
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
                  }

                    return (
                      <tr key={item.id} className="transition hover:bg-slate-50/80">
                        <td className="px-8 py-5">
                          <div className="text-sm font-semibold text-slate-900">{item.rule || item.rule_title || '—'}</div>
                        </td>
                        <td className="px-8 py-5">
                          <div className="text-sm text-slate-700 whitespace-pre-wrap">{item.evidence || item.evidence_text || '—'}</div>
                        </td>
                        <td className="px-8 py-5">
                          <div className="text-sm text-slate-700 whitespace-pre-wrap">{item.reviewer_comment || '—'}</div>
                        </td>
                        <td className="px-8 py-5">
                          <div className="text-sm text-slate-700 whitespace-pre-wrap">{item.recommendation || '—'}</div>
                        </td>
                        <td className="px-8 py-5">
                          <span className={`inline-flex items-center rounded-full border px-4 py-2 text-sm font-semibold capitalize ${getLabelTone(item.label).badge} ${getLabelTone(item.label).text}`}>
                            {item.label || 'pending'}
                          </span>
                        </td>
                        <td className="px-8 py-5 text-sm text-slate-600">
                          {item.updated_at ? new Date(item.updated_at).toLocaleDateString('en-US', {
                            year: 'numeric',
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          }) : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </Layout>
  );
}
