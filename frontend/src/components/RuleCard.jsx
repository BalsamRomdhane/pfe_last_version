import React from 'react';
import { ChevronDown, ChevronUp, Trash2 } from 'lucide-react';
import SeverityBadge from './SeverityBadge';
import SeveritySelect from './SeveritySelect';

const RuleCard = ({
  rule,
  index,
  onChange,
  onRemove,
  canRemove,
}) => {
  const toggleExpanded = () => {
    onChange(index, 'expanded', !rule.expanded);
  };

  return (
    <div className="rounded-[24px] border border-slate-200 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md">
      <div className="flex flex-col gap-4 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <p className="text-sm font-semibold text-slate-900">Rule #{index + 1}</p>
            <SeverityBadge severity={rule.severity} className="shrink-0" />
          </div>
          <p className="mt-3 text-base font-semibold text-slate-900">{rule.title || 'Untitled rule'}</p>
          <p className="mt-2 text-sm text-slate-500">{rule.description || 'Use the rule summary to describe the validation requirement.'}</p>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={toggleExpanded}
            className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-slate-600 transition hover:bg-slate-100"
            aria-label={rule.expanded ? 'Collapse rule' : 'Expand rule'}
          >
            {rule.expanded ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
          </button>
          {canRemove && (
            <button
              type="button"
              onClick={() => onRemove(index)}
              className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-rose-200 bg-rose-50 text-rose-700 transition hover:bg-rose-100"
              aria-label="Remove rule"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {rule.expanded && (
        <div className="space-y-5 border-t border-slate-200 px-5 py-5">
          <div className="grid gap-4 lg:grid-cols-2">
            <label className="space-y-2 text-sm text-slate-700">
              Rule title <span className="text-rose-600">*</span>
              <input
                value={rule.title}
                onChange={(e) => onChange(index, 'title', e.target.value)}
                placeholder="Enter rule title"
                className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500"
                required
              />
            </label>

            <SeveritySelect
              value={rule.severity}
              onChange={(value) => onChange(index, 'severity', value)}
            />
          </div>

          <label className="space-y-2 text-sm text-slate-700">
            Summary
            <textarea
              value={rule.description}
              onChange={(e) => onChange(index, 'description', e.target.value)}
              placeholder="Enter a short summary"
              rows={3}
              className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500"
            />
          </label>

          <div className="grid gap-4 lg:grid-cols-2">
            <label className="space-y-2 text-sm text-slate-700">
              Condition
              <textarea
                value={rule.condition}
                onChange={(e) => onChange(index, 'condition', e.target.value)}
                placeholder="Describe the condition that triggers this rule"
                rows={4}
                className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500"
              />
            </label>
            <label className="space-y-2 text-sm text-slate-700">
              Action
              <textarea
                value={rule.action}
                onChange={(e) => onChange(index, 'action', e.target.value)}
                placeholder="Describe the action taken when the rule applies"
                rows={4}
                className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500"
              />
            </label>
          </div>
        </div>
      )}
    </div>
  );
};

export default RuleCard;
