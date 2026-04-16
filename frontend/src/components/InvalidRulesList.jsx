import React from 'react';

const InvalidRulesList = ({ invalidRules }) => {
  if (!invalidRules?.length) {
    return (
      <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
        <p className="font-medium text-slate-900">No invalid rules to display.</p>
        <p className="mt-2">This document has not been rejected or no rule feedback has been recorded yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {invalidRules.map((validation) => (
        <div key={validation.id} className="rounded-3xl border border-rose-200 bg-rose-50 p-5 shadow-sm">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-base font-semibold text-rose-800">❌ {validation.rule.title}</p>
              {validation.rule.description && (
                <p className="mt-2 text-sm text-slate-600">{validation.rule.description}</p>
              )}
            </div>
            <span className="inline-flex rounded-full bg-rose-200 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-rose-700">
              Invalid
            </span>
          </div>

          <div className="mt-4 space-y-3 rounded-3xl bg-white p-4 shadow-sm">
            {validation.evidence_text ? (
              <div>
                <p className="text-sm font-semibold text-slate-900">Comment</p>
                <p className="mt-1 text-sm leading-6 text-slate-700">{validation.evidence_text}</p>
              </div>
            ) : (
              <p className="text-sm text-slate-600">No reviewer comment was provided for this rule.</p>
            )}
            {validation.evidence_file_url && (
              <a
                href={validation.evidence_file_url}
                target="_blank"
                rel="noreferrer"
                className="text-sky-600 hover:text-sky-700 text-sm font-medium"
              >
                View submitted evidence
              </a>
            )}
          </div>
        </div>
      ))}
    </div>
  );
};

export default InvalidRulesList;
