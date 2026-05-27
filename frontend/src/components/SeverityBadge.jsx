import React from 'react';

const styles = {
  CRITICAL: {
    label: 'Critical',
    badge: 'bg-rose-100 text-rose-700 border-rose-200',
  },
  HIGH: {
    label: 'High',
    badge: 'bg-orange-100 text-orange-700 border-orange-200',
  },
  MEDIUM: {
    label: 'Medium',
    badge: 'bg-amber-100 text-amber-800 border-amber-200',
  },
  LOW: {
    label: 'Low',
    badge: 'bg-sky-100 text-sky-700 border-sky-200',
  },
  INFO: {
    label: 'Informational',
    badge: 'bg-slate-100 text-slate-700 border-slate-200',
  },
};

const SeverityBadge = ({ severity, className = '' }) => {
  if (!severity || !styles[severity]) {
    return (
      <span className={`rounded-full border border-slate-200 bg-slate-50 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-600 ${className}`}>
        Unrated
      </span>
    );
  }

  const { label, badge } = styles[severity];
  return (
    <span className={`inline-flex items-center rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] ${badge} ${className}`}>
      {label}
    </span>
  );
};

export default SeverityBadge;
