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
} from "lucide-react";
import Layout from "../components/Layout";
import { UserContext } from "../context/UserContext";
import api from "../services/api";

const standards = [
  { value: "ISO9001", label: "ISO 9001" },
  { value: "ISO27001", label: "ISO 27001" },
];

const getScore = (features) => {
  const values = Object.values(features || {});

  if (values.length === 0) {
    return 0;
  }

  return Math.round((values.reduce((sum, value) => sum + value, 0) / values.length) * 100);
};

const getFeatureSummary = (features) => {
  const values = Object.values(features || {});
  const valid = values.filter((value) => value === 1).length;

  return {
    total: values.length,
    valid,
    invalid: values.length - valid,
  };
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
  const [standard, setStandard] = useState("ISO9001");
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState(null);

  useEffect(() => {
    if (!user || user.role !== "ADMIN") {
      navigate("/dashboard");
      return;
    }

    setLoading(true);
    api
      .get(`/training-dataset/?standard=${standard}`)
      .then((res) => {
        setData(res.data.results || res.data || []);
        setExpandedId(null);
      })
      .catch(() => {
        setData([]);
        setExpandedId(null);
      })
      .finally(() => setLoading(false));
  }, [standard, user, navigate]);

  const toggleRow = (id) => {
    setExpandedId((currentId) => (currentId === id ? null : id));
  };

  const stats = {
    total: data.length,
    approved: data.filter((item) => item.label === "approved").length,
    rejected: data.filter((item) => item.label === "rejected").length,
    avgScore: data.length ? Math.round(data.reduce((sum, item) => sum + getScore(item.features), 0) / data.length) : 0,
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
                  <p className="mt-2 text-lg font-semibold">{standards.find((item) => item.value === standard)?.label}</p>
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
              <p className="mt-1 text-sm text-slate-500">Expand a row to inspect the exact feature vector stored for training.</p>
            </div>

            <label className="flex items-center gap-3">
              <span className="text-sm font-semibold text-slate-600">Standard</span>
              <select
                value={standard}
                onChange={(e) => setStandard(e.target.value)}
                className="rounded-xl border border-slate-300 bg-white px-4 py-2.5 text-sm font-medium text-slate-900 outline-none transition focus:border-blue-500 focus:ring-4 focus:ring-blue-100"
              >
                {standards.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {loading ? (
            <div className="flex items-center justify-center px-6 py-20">
              <div className="text-center">
                <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-b-blue-600" />
                <p className="mt-4 text-sm font-medium text-slate-500">Loading dataset...</p>
              </div>
            </div>
          ) : data.length === 0 ? (
            <div className="px-6 py-20 text-center">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-slate-100 text-slate-400">
                <Target size={28} />
              </div>
              <p className="mt-5 text-lg font-semibold text-slate-900">No training samples available</p>
              <p className="mt-2 text-sm text-slate-500">
                No dataset entries were found for {standards.find((item) => item.value === standard)?.label}.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/80">
                    <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">ID</th>
                    <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Label</th>
                    <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Score</th>
                    <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Rules</th>
                    <th className="px-8 py-4 text-left text-xs font-semibold uppercase tracking-[0.2em] text-slate-500">Created</th>
                    <th className="px-8 py-4 text-right text-xs font-semibold uppercase tracking-[0.2em] text-slate-500" />
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-200">
                  {data.map((item) => {
                    const score = getScore(item.features);
                    const summary = getFeatureSummary(item.features);
                    const labelTone = getLabelTone(item.label);
                    const isExpanded = expandedId === item.id;

                    return (
                      <React.Fragment key={item.id}>
                        <tr className="transition hover:bg-slate-50/80">
                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-slate-100 px-4 py-2 text-sm font-semibold text-blue-700">
                              #{item.id}
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className={`inline-flex items-center gap-3 rounded-full border px-4 py-2 text-sm font-semibold capitalize ${labelTone.badge} ${labelTone.text}`}>
                              <span className={`h-2.5 w-2.5 rounded-full ${labelTone.dot}`} />
                              {item.label}
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className={`inline-flex items-center rounded-2xl border px-4 py-2 text-sm font-semibold ${getScoreTone(score)}`}>
                              {score}%
                            </span>
                          </td>

                          <td className="px-8 py-5">
                            <span className="inline-flex items-center rounded-full bg-blue-50 px-4 py-2 text-sm font-medium text-blue-700">
                              {summary.total} rules
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
                            <button
                              type="button"
                              onClick={() => toggleRow(item.id)}
                              className="inline-flex h-10 w-10 items-center justify-center rounded-full text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
                              aria-label={isExpanded ? `Collapse sample ${item.id}` : `Expand sample ${item.id}`}
                            >
                              {isExpanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
                            </button>
                          </td>
                        </tr>

                        {isExpanded && (
                          <tr className="bg-slate-50/70">
                            <td colSpan={6} className="px-8 py-8">
                              <div className="space-y-6">
                                <div className="grid gap-4 md:grid-cols-3">
                                  <SummaryCard title="Valid rules" value={summary.valid} tone="green" />
                                  <SummaryCard title="Invalid rules" value={summary.invalid} tone="red" />
                                  <SummaryCard title="Compliance" value={`${score}%`} tone="blue" />
                                </div>

                                <div>
                                  <div className="mb-4 flex items-center justify-between gap-4">
                                    <div>
                                      <h3 className="text-2xl font-semibold tracking-tight text-slate-950">Feature Details</h3>
                                      <p className="mt-1 text-sm text-slate-500">
                                        Ordered rule features stored for {item.standard || standard}
                                      </p>
                                    </div>
                                  </div>

                                  <div className="grid gap-3 lg:grid-cols-2">
                                    {Object.entries(item.features || {}).map(([rule, value]) => (
                                      <div
                                        key={rule}
                                        className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-4 shadow-sm"
                                      >
                                        <div className="flex min-w-0 items-center gap-3">
                                          <Circle
                                            size={12}
                                            className={value ? "fill-emerald-500 text-emerald-500" : "fill-red-500 text-red-500"}
                                          />
                                          <span className="text-sm font-medium text-slate-800">{rule}</span>
                                        </div>

                                        <span
                                          className={`inline-flex items-center rounded-full px-4 py-1.5 text-sm font-medium ${
                                            value
                                              ? "bg-emerald-50 text-emerald-700"
                                              : "bg-red-50 text-red-700"
                                          }`}
                                        >
                                          {value ? "Valid" : "Invalid"}
                                        </span>
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
