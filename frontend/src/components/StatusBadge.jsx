import React from 'react';

const statusConfig = {
  approved: {
    label: 'Approved',
    className: 'inline-flex rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-emerald-700',
  },
  rejected: {
    label: 'Rejected',
    className: 'inline-flex rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-rose-700',
  },
  reviewing: {
    label: 'Reviewing',
    className: 'inline-flex rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-sky-700',
  },
  pending: {
    label: 'Pending',
    className: 'inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-amber-700',
  },
};

const StatusBadge = ({ status }) => {
  const config = statusConfig[status] || {
    label: status?.toString() || 'Unknown',
    className: 'inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700',
  };

  return <span className={config.className}>{config.label}</span>;
};

export default StatusBadge;
