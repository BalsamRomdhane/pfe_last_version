import React from 'react';

const stepData = [
  { key: 'pending', label: 'Pending' },
  { key: 'reviewing', label: 'Reviewing' },
  { key: 'approved', label: 'Approved' },
  { key: 'rejected', label: 'Rejected' },
];

const PipelineStepper = ({ currentStatus }) => {
  const currentIndex = stepData.findIndex((step) => step.key === currentStatus);

  return (
    <div className="rounded-3xl border border-slate-200 bg-slate-50 p-4 shadow-sm">
      <div className="flex items-center gap-4 overflow-x-auto text-sm text-slate-600">
        {stepData.map((step, index) => {
          const isActive = index === currentIndex;
          const isCompleted = index < currentIndex;
          const isFuture = index > currentIndex;

          const circleClassName = isCompleted
            ? 'bg-emerald-600 text-white'
            : isActive
            ? 'bg-sky-600 text-white'
            : 'bg-slate-100 text-slate-500';

          const labelClassName = isActive
            ? 'font-semibold text-slate-900'
            : isCompleted
            ? 'text-slate-700'
            : 'text-slate-500';

          return (
            <div key={step.key} className="flex min-w-[120px] flex-1 items-center gap-3">
              <div className="flex items-center gap-3">
                <div className={`flex h-10 w-10 items-center justify-center rounded-full ${circleClassName} shadow-sm`}>
                  {isCompleted ? '✓' : index + 1}
                </div>
                <div className="min-w-0">
                  <div className={labelClassName}>{step.label}</div>
                </div>
              </div>
              {index < stepData.length - 1 && (
                <div className="h-px flex-1 bg-slate-200" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default PipelineStepper;
