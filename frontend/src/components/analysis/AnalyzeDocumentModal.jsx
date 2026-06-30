import React, { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Brain, Sparkles, AlertCircle, ChevronRight, Settings2 } from 'lucide-react';
import UploadZone from './UploadZone';
import AnalysisLoading from './AnalysisLoading';
import AnalysisResults from './AnalysisResults';
import api from '../../services/api';

/* ── helpers ─────────────────────────────────────────────────────────────── */
const ANALYSIS_LEVELS = [
  { id: 'fast',     label: 'Fast',          desc: 'Quick keyword scan'         },
  { id: 'standard', label: 'Standard',      desc: 'Full rule evaluation'       },
  { id: 'deep',     label: 'Deep Semantic', desc: 'AI + evidence memory'       },
];

const TOGGLES = [
  { id: 'semantic',    label: 'Semantic search'     },
  { id: 'ai_recs',     label: 'AI recommendations'  },
  { id: 'scoring',     label: 'Compliance scoring'  },
  { id: 'risk',        label: 'Risk detection'      },
];

/* ── sub-components ──────────────────────────────────────────────────────── */
function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-xl border border-slate-100 bg-slate-50 px-3 py-2.5 transition hover:bg-slate-100">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 rounded-full transition-colors ${checked ? 'bg-sky-500' : 'bg-slate-300'}`}
      >
        <motion.span
          animate={{ x: checked ? 16 : 2 }}
          transition={{ type: 'spring', stiffness: 500, damping: 30 }}
          className="absolute top-0.5 h-4 w-4 rounded-full bg-white shadow"
        />
      </button>
    </label>
  );
}

function EmptyState() {
  return (
    <div className="flex flex-col items-center gap-5 py-10 text-center">
      <div className="relative">
        <motion.div
          animate={{ scale: [1, 1.1, 1], opacity: [0.3, 0.6, 0.3] }}
          transition={{ duration: 3, repeat: Infinity }}
          className="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400 to-violet-500 blur-2xl"
        />
        <div className="relative flex h-20 w-20 items-center justify-center rounded-3xl bg-gradient-to-br from-sky-500 to-violet-600 shadow-xl shadow-sky-500/25">
          <Brain size={36} className="text-white" />
        </div>
      </div>
      <div>
        <p className="text-base font-semibold text-slate-900">AI Compliance Analysis</p>
        <p className="mt-1.5 max-w-xs text-sm text-slate-500">
          Upload a compliance document to begin AI semantic analysis and evidence detection.
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-2">
        {['ISO 9001', 'Semantic AI', 'Evidence Memory', 'Risk Detection'].map((tag) => (
          <span key={tag} className="rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            {tag}
          </span>
        ))}
      </div>
    </div>
  );
}

function ErrorToast({ message, onDismiss }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -8, scale: 0.96 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, scale: 0.96 }}
      className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-4"
    >
      <AlertCircle size={18} className="mt-0.5 shrink-0 text-red-500" />
      <div className="flex-1">
        <p className="text-sm font-semibold text-red-800">Analysis failed</p>
        <p className="mt-0.5 text-xs text-red-600">{message}</p>
      </div>
      <button type="button" onClick={onDismiss} className="text-red-400 hover:text-red-600">
        <X size={14} />
      </button>
    </motion.div>
  );
}

/* ── main modal ──────────────────────────────────────────────────────────── */
export default function AnalyzeDocumentModal({ isOpen, onClose, norms = [], defaultNorm = '' }) {
  const [file, setFile]           = useState(null);
  const [normId, setNormId]       = useState(defaultNorm);
  const [level, setLevel]         = useState('standard');
  const [toggles, setToggles]     = useState({ semantic: true, ai_recs: true, scoring: true, risk: true });
  const [phase, setPhase]         = useState('idle'); // idle | loading | results | error
  const [result, setResult]       = useState(null);
  const [error, setError]         = useState('');
  const [showConfig, setShowConfig] = useState(false);
  const scrollRef = useRef();

  /* close on ESC + body scroll lock */
  useEffect(() => {
    if (!isOpen) return;
    document.body.classList.add('modal-open');
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => {
      window.removeEventListener('keydown', handler);
      document.body.classList.remove('modal-open');
    };
  }, [isOpen, onClose]);

  /* reset when closed */
  useEffect(() => {
    if (!isOpen) {
      setTimeout(() => {
        setFile(null); setPhase('idle'); setResult(null); setError('');
      }, 300);
    }
  }, [isOpen]);

  /* scroll to top when phase changes */
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: 0, behavior: 'smooth' });
  }, [phase]);

  const handleAnalyze = useCallback(async () => {
    if (!file) return;
    setPhase('loading');
    setError('');
    try {
      const formData = new FormData();
      formData.append('file', file);

      // Find the selected norm and send its name as 'standard'
      // normId can be a numeric id OR a name string — handle both
      const selectedNorm = norms.find((n) =>
        String(n.id) === String(normId) || n.name === normId
      ) || norms[0];
      const standardName = selectedNorm?.name || '';
      if (standardName) {
        formData.append('standard', standardName);
      }

      console.log('[Modal] Analyzing with standard:', standardName, 'normId:', normId);

      const res = await api.post('compliance/analyze/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      console.log('[Modal] Raw API response:', res.data);
      console.log('[Modal] compliance:', res.data?.compliance, 'valid_count:', res.data?.valid_count, 'total_rules:', res.data?.total_rules);

      setResult(res.data);
      setPhase('results');
    } catch (err) {
      setError(err?.response?.data?.error || err?.response?.data?.detail || 'Analysis failed. Please try again.');
      setPhase('error');
    }
  }, [file, normId, norms]);

  const reset = () => { setFile(null); setPhase('idle'); setResult(null); setError(''); };

  if (!isOpen) return null;

  return createPortal(
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={onClose}
            className="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm"
          />

          {/* Modal */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.94, y: 24 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.94, y: 24 }}
            transition={{ type: 'spring', stiffness: 380, damping: 32 }}
            className="fixed inset-x-4 bottom-4 top-4 z-50 mx-auto flex max-w-2xl flex-col overflow-hidden rounded-[2rem] bg-white shadow-2xl shadow-slate-900/20 ring-1 ring-slate-200 sm:inset-x-auto sm:left-1/2 sm:w-full sm:-translate-x-1/2"
            role="dialog"
            aria-modal="true"
            aria-label="AI Document Analysis"
          >
            {/* ── HEADER ── */}
            <div className="relative shrink-0 overflow-hidden rounded-t-[2rem] bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 px-6 py-5">
              {/* Subtle animated gradient */}
              <motion.div
                animate={{ backgroundPosition: ['0% 50%', '100% 50%', '0% 50%'] }}
                transition={{ duration: 8, repeat: Infinity, ease: 'linear' }}
                className="pointer-events-none absolute inset-0 opacity-20"
                style={{
                  background: 'linear-gradient(135deg, #38bdf8, #818cf8, #c084fc, #38bdf8)',
                  backgroundSize: '300% 300%',
                }}
              />

              <div className="relative flex items-start gap-4">
                {/* AI icon with pulse */}
                <div className="relative shrink-0">
                  <motion.div
                    animate={{ scale: [1, 1.3, 1], opacity: [0.5, 0.8, 0.5] }}
                    transition={{ duration: 2.5, repeat: Infinity }}
                    className="absolute inset-0 rounded-2xl bg-sky-400 blur-md"
                  />
                  <div className="relative flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-sky-400 to-violet-500 shadow-lg">
                    <Brain size={22} className="text-white" />
                  </div>
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-bold text-white">AI Document Analysis</h2>
                    <span className="flex items-center gap-1 rounded-full bg-white/10 px-2 py-0.5 text-xs font-medium text-sky-300">
                      <Sparkles size={10} /> AI
                    </span>
                  </div>
                  <p className="mt-0.5 text-sm text-slate-400">
                    Semantic compliance verification and evidence detection
                  </p>
                </div>

                <button
                  type="button"
                  onClick={onClose}
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl text-slate-400 transition hover:bg-white/10 hover:text-white"
                  aria-label="Close"
                >
                  <X size={18} />
                </button>
              </div>

              {/* Phase indicator */}
              {phase !== 'idle' && (
                <div className="relative mt-4 flex items-center gap-2 text-xs text-slate-400">
                  {['upload', 'analyze', 'results'].map((s, i) => {
                    const active = (phase === 'loading' && i === 1) || (phase === 'results' && i === 2) || (phase === 'idle' && i === 0);
                    const done   = (phase === 'loading' && i === 0) || (phase === 'results' && i <= 1);
                    return (
                      <React.Fragment key={s}>
                        <span className={`font-medium capitalize ${done ? 'text-emerald-400' : active ? 'text-sky-300' : 'text-slate-600'}`}>
                          {s}
                        </span>
                        {i < 2 && <ChevronRight size={12} className="text-slate-600" />}
                      </React.Fragment>
                    );
                  })}
                </div>
              )}
            </div>

            {/* ── BODY ── */}
            <div ref={scrollRef} className="modal-scroll flex-1 overflow-y-auto">
              <div className="space-y-5 p-6">
                <AnimatePresence mode="wait">
                  {/* IDLE — upload + config */}
                  {(phase === 'idle' || phase === 'error') && (
                    <motion.div
                      key="idle"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="space-y-5"
                    >
                      {!file && <EmptyState />}

                      <UploadZone file={file} onFile={setFile} onRemove={() => setFile(null)} />

                      <AnimatePresence>
                        {phase === 'error' && error && (
                          <ErrorToast message={error} onDismiss={() => setPhase('idle')} />
                        )}
                      </AnimatePresence>

                      {/* Config toggle */}
                      <button
                        type="button"
                        onClick={() => setShowConfig((v) => !v)}
                        className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
                      >
                        <span className="flex items-center gap-2"><Settings2 size={15} /> Analysis configuration</span>
                        <motion.span animate={{ rotate: showConfig ? 180 : 0 }} transition={{ duration: 0.2 }}>
                          <ChevronRight size={15} className="rotate-90" />
                        </motion.span>
                      </button>

                      <AnimatePresence>
                        {showConfig && (
                          <motion.div
                            initial={{ height: 0, opacity: 0 }}
                            animate={{ height: 'auto', opacity: 1 }}
                            exit={{ height: 0, opacity: 0 }}
                            className="overflow-hidden"
                          >
                            <div className="space-y-4 rounded-2xl border border-slate-200 bg-white p-4">
                              {/* Norm select */}
                              {norms.length > 0 && (
                                <div>
                                  <label htmlFor="modal-norm-select" className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">ISO Standard</label>
                                  <select
                                    id="modal-norm-select"
                                    value={normId}
                                    onChange={(e) => setNormId(e.target.value)}
                                    className="w-full rounded-xl border border-slate-200 bg-slate-50 px-3 py-2.5 text-sm text-slate-900 outline-none transition focus:border-sky-400 focus:ring-2 focus:ring-sky-100"
                                  >
                                    {norms.map((n) => (
                                      <option key={n.id} value={n.id}>{n.name}</option>
                                    ))}
                                  </select>
                                </div>
                              )}

                              {/* Analysis level */}
                              <fieldset>
                                <legend className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Analysis depth</legend>
                                <div className="grid grid-cols-3 gap-2">
                                  {ANALYSIS_LEVELS.map((l) => (
                                    <button
                                      key={l.id}
                                      type="button"
                                      onClick={() => setLevel(l.id)}
                                      className={`rounded-xl border p-3 text-left transition ${
                                        level === l.id
                                          ? 'border-sky-300 bg-sky-50 ring-2 ring-sky-200'
                                          : 'border-slate-200 bg-slate-50 hover:border-slate-300'
                                      }`}
                                    >
                                      <p className="text-xs font-bold text-slate-900">{l.label}</p>
                                      <p className="mt-0.5 text-xs text-slate-500">{l.desc}</p>
                                    </button>
                                  ))}
                                </div>
                              </fieldset>

                              {/* Toggles */}
                              <fieldset>
                                <legend className="mb-1.5 block text-xs font-semibold uppercase tracking-wider text-slate-500">Features</legend>
                                <div className="grid grid-cols-2 gap-2">
                                  {TOGGLES.map((t) => (
                                    <Toggle
                                      key={t.id}
                                      label={t.label}
                                      checked={toggles[t.id]}
                                      onChange={(v) => setToggles((prev) => ({ ...prev, [t.id]: v }))}
                                    />
                                  ))}
                                </div>
                              </fieldset>
                            </div>
                          </motion.div>
                        )}
                      </AnimatePresence>
                    </motion.div>
                  )}

                  {/* LOADING */}
                  {phase === 'loading' && (
                    <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                      <AnalysisLoading />
                    </motion.div>
                  )}

                  {/* RESULTS */}
                  {phase === 'results' && result && (
                    <motion.div key="results" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}>
                      <AnalysisResults result={result} onClose={onClose} />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>

            {/* ── FOOTER ── */}
            {(phase === 'idle' || phase === 'error') && (
              <div className="shrink-0 border-t border-slate-100 bg-white/80 px-6 py-4 backdrop-blur-sm">
                <div className="flex items-center gap-3">
                  {phase === 'results' || phase === 'loading' ? null : (
                    <>
                      <button
                        type="button"
                        onClick={onClose}
                        className="rounded-full border border-slate-200 px-5 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={handleAnalyze}
                        disabled={!file}
                        className="flex flex-1 items-center justify-center gap-2 rounded-full bg-gradient-to-r from-sky-500 to-violet-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-sky-500/25 transition hover:from-sky-400 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Brain size={16} />
                        Analyze with AI
                        <Sparkles size={14} className="opacity-70" />
                      </button>
                    </>
                  )}
                </div>
              </div>
            )}

            {phase === 'results' && (
              <div className="shrink-0 border-t border-slate-100 bg-white/80 px-6 py-4 backdrop-blur-sm">
                <button
                  type="button"
                  onClick={reset}
                  className="w-full rounded-full border border-slate-200 py-2.5 text-sm font-semibold text-slate-600 transition hover:bg-slate-50"
                >
                  Analyze another document
                </button>
              </div>
            )}
          </motion.div>
        </>
      )}
    </AnimatePresence>,
    document.body
  );
}
