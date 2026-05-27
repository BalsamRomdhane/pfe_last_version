import React from 'react';

const stepLabels = [
  'General Information',
  'Rules',
  'Validation',
  'Review',
];

const NormeStepper = ({ activeStep }) => (
  <div className="rounded-[24px] border border-slate-800/10 bg-slate-950/95 p-5 text-white shadow-[0_24px_80px_-40px_rgba(15,23,42,0.65)]">
    <div className="grid gap-4 md:grid-cols-4">
      {stepLabels.map((label, index) => {
        const step = index;
        const isActive = step === activeStep;
        const isCompleted = step < activeStep;
        return (
          <div key={label} className="flex items-start gap-3">
            <div className={`flex h-10 w-10 items-center justify-center rounded-2xl border ${isActive ? 'border-sky-300 bg-sky-600 text-white shadow-lg' : isCompleted ? 'border-emerald-300 bg-emerald-100 text-emerald-800' : 'border-slate-700 bg-slate-900 text-slate-300'}`}>
              {isCompleted ? '✓' : index + 1}
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.3em] text-slate-400">Step {index + 1}</p>
              <p className={`text-sm font-semibold ${isActive ? 'text-white' : 'text-slate-300'}`}>{label}</p>
            </div>
          </div>
        );
      })}
    </div>
  </div>
);

export default NormeStepper;
