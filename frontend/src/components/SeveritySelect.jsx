import React from 'react';
import SeverityBadge from './SeverityBadge';

const options = [
  { value: 'CRITICAL', label: 'Critical' },
  { value: 'HIGH', label: 'High' },
  { value: 'MEDIUM', label: 'Medium' },
  { value: 'LOW', label: 'Low' },
  { value: 'INFO', label: 'Informational' },
];

const SeveritySelect = ({ value, onChange, error }) => {
  return (
    <label className="space-y-2 text-sm text-slate-700">
      <span className="flex items-center gap-2 font-medium">
        Severity <span className="text-rose-600">*</span>
      </span>
      <div className="flex items-center gap-3 rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3">
        <SeverityBadge severity={value} />
        <select
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="w-full bg-transparent text-sm text-slate-900 outline-none focus:outline-none"
          required
        >
          <option value="" disabled>
            Select severity
          </option>
          {options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
      {error && <p className="text-xs text-rose-600">{error}</p>}
    </label>
  );
};

export default SeveritySelect;
