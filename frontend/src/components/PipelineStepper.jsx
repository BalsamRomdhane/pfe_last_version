import React from 'react';
import { Check } from 'lucide-react';

const STEPS = [
  { key: 'pending',   label: 'Pending'   },
  { key: 'reviewing', label: 'Reviewing' },
  { key: 'approved',  label: 'Approved'  },
  { key: 'rejected',  label: 'Rejected'  },
];

const PipelineStepper = ({ currentStatus }) => {
  const currentIdx = STEPS.findIndex(s => s.key === currentStatus);
  const isRejected = currentStatus === 'rejected';

  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const isActive    = i === currentIdx;
        const isCompleted = i < currentIdx && !isRejected;
        const isLast      = i === STEPS.length - 1;
        const isReject    = step.key === 'rejected' && isRejected;

        const circleClass =
          isReject    ? 'bg-red-500 border-red-500 text-white' :
          isActive    ? 'bg-brand-600 border-brand-600 text-white' :
          isCompleted ? 'bg-emerald-500 border-emerald-500 text-white' :
                        'bg-white border-slate-300 text-slate-400';

        const labelClass  =
          isReject    ? 'text-red-600 font-semibold' :
          isActive    ? 'text-brand-700 font-semibold' :
          isCompleted ? 'text-emerald-700' :
                        'text-slate-400';

        const lineClass   =
          isCompleted ? 'bg-emerald-400' : 'bg-slate-200';

        return (
          <div key={step.key} className="flex flex-1 items-center">
            <div className="flex flex-col items-center">
              <div className={`flex h-7 w-7 items-center justify-center rounded-full border-2 transition-all ${circleClass}`}>
                {isCompleted ? (
                  <Check size={12} />
                ) : (
                  <span className="text-2xs font-bold">{i + 1}</span>
                )}
              </div>
              <span className={`mt-1 text-2xs whitespace-nowrap ${labelClass}`}>{step.label}</span>
            </div>
            {!isLast && (
              <div className={`flex-1 h-0.5 mx-1 rounded-full transition-colors ${lineClass}`} />
            )}
          </div>
        );
      })}
    </div>
  );
};

export default PipelineStepper;
