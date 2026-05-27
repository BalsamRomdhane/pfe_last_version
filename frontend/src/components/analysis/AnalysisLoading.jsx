import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { CheckCircle2, Loader2 } from 'lucide-react';

const STEPS = [
  { id: 1, label: 'Extracting document text',        duration: 900  },
  { id: 2, label: 'Detecting semantic patterns',     duration: 1200 },
  { id: 3, label: 'Comparing with evidence memory',  duration: 1100 },
  { id: 4, label: 'Running compliance AI',           duration: 1000 },
  { id: 5, label: 'Generating recommendations',      duration: 800  },
];

export default function AnalysisLoading() {
  const [currentStep, setCurrentStep] = useState(0);
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let elapsed = 0;
    const total = STEPS.reduce((s, st) => s + st.duration, 0);
    let stepIdx = 0;

    const tick = setInterval(() => {
      elapsed += 60;
      setProgress(Math.min(98, Math.round((elapsed / total) * 100)));

      let acc = 0;
      for (let i = 0; i < STEPS.length; i++) {
        acc += STEPS[i].duration;
        if (elapsed >= acc && stepIdx <= i) {
          stepIdx = i + 1;
          setCurrentStep(stepIdx);
        }
      }
      if (elapsed >= total) clearInterval(tick);
    }, 60);

    return () => clearInterval(tick);
  }, []);

  return (
    <div className="flex flex-col items-center gap-8 py-6">
      {/* Animated AI orb */}
      <div className="relative flex h-24 w-24 items-center justify-center">
        <motion.div
          animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          className="absolute inset-0 rounded-full bg-gradient-to-br from-sky-400 to-violet-500 blur-xl"
        />
        <motion.div
          animate={{ rotate: 360 }}
          transition={{ duration: 3, repeat: Infinity, ease: 'linear' }}
          className="absolute inset-2 rounded-full border-2 border-dashed border-sky-300/60"
        />
        <div className="relative flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-sky-500 to-violet-600 shadow-lg shadow-sky-500/30">
          <Loader2 size={24} className="animate-spin text-white" />
        </div>
      </div>

      {/* Title */}
      <div className="text-center">
        <p className="text-base font-semibold text-slate-900">AI Analysis in Progress</p>
        <p className="mt-1 text-sm text-slate-500">Processing your compliance document…</p>
      </div>

      {/* Progress bar */}
      <div className="w-full max-w-sm">
        <div className="mb-2 flex items-center justify-between text-xs text-slate-500">
          <span>Progress</span>
          <span className="font-semibold text-sky-600">{progress}%</span>
        </div>
        <div className="h-2 overflow-hidden rounded-full bg-slate-100">
          <motion.div
            className="h-full rounded-full bg-gradient-to-r from-sky-500 to-violet-500"
            animate={{ width: `${progress}%` }}
            transition={{ duration: 0.3, ease: 'easeOut' }}
          />
        </div>
      </div>

      {/* Steps */}
      <div className="w-full max-w-sm space-y-2.5">
        {STEPS.map((step, i) => {
          const done = currentStep > i;
          const active = currentStep === i;
          return (
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: done || active ? 1 : 0.35, x: 0 }}
              transition={{ delay: i * 0.08 }}
              className="flex items-center gap-3"
            >
              <div className="flex h-6 w-6 shrink-0 items-center justify-center">
                {done ? (
                  <motion.div
                    initial={{ scale: 0 }}
                    animate={{ scale: 1 }}
                    transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                  >
                    <CheckCircle2 size={18} className="text-emerald-500" />
                  </motion.div>
                ) : active ? (
                  <motion.div
                    animate={{ rotate: 360 }}
                    transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  >
                    <Loader2 size={16} className="text-sky-500" />
                  </motion.div>
                ) : (
                  <div className="h-4 w-4 rounded-full border-2 border-slate-200" />
                )}
              </div>
              <span className={`text-sm ${done ? 'font-medium text-slate-700' : active ? 'font-semibold text-sky-700' : 'text-slate-400'}`}>
                {step.label}
              </span>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
}
