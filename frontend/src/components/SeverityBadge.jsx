import React from 'react';

const SEVERITY_CFG = {
  CRITICAL: { label: 'Critical',      cls: 'bg-purple-50 text-purple-700 ring-1 ring-purple-200' },
  HIGH:     { label: 'High',          cls: 'bg-red-50    text-red-700    ring-1 ring-red-200'    },
  MEDIUM:   { label: 'Medium',        cls: 'bg-amber-50  text-amber-700  ring-1 ring-amber-200'  },
  LOW:      { label: 'Low',           cls: 'bg-sky-50    text-sky-700    ring-1 ring-sky-200'    },
  INFO:     { label: 'Info',          cls: 'badge-slate'                                         },
};

const SeverityBadge = ({ severity, className = '' }) => {
  const cfg = SEVERITY_CFG[(severity || '').toUpperCase()];

  if (!cfg) {
    return (
      <span className={`badge badge-slate ${className}`}>Unrated</span>
    );
  }

  return (
    <span className={`badge ${cfg.cls} ${className}`}>
      {cfg.label}
    </span>
  );
};

export default SeverityBadge;
