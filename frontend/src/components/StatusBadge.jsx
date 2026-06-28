import React from 'react';
import { CheckCircle, XCircle, Clock, RotateCcw } from 'lucide-react';

const CONFIG = {
  approved:  { label: 'Approved',  cls: 'badge-green',  dot: 'bg-emerald-500', Icon: CheckCircle },
  rejected:  { label: 'Rejected',  cls: 'badge-red',    dot: 'bg-red-500',     Icon: XCircle    },
  reviewing: { label: 'Reviewing', cls: 'badge-sky',    dot: 'bg-sky-500',     Icon: RotateCcw  },
  pending:   { label: 'Pending',   cls: 'badge-amber',  dot: 'bg-amber-500',   Icon: Clock      },
};

const StatusBadge = ({ status, showIcon = true, size = 'sm' }) => {
  const cfg = CONFIG[status] || {
    label: status || 'Unknown',
    cls: 'badge-slate',
    dot: 'bg-slate-400',
    Icon: null,
  };

  const Icon = cfg.Icon;

  return (
    <span className={`badge ${cfg.cls} ${size === 'xs' ? 'text-2xs px-1.5 py-0.5' : ''}`}>
      {showIcon && Icon ? (
        <Icon size={10} />
      ) : (
        <span className={`status-dot ${cfg.dot}`} />
      )}
      {cfg.label}
    </span>
  );
};

export default StatusBadge;
