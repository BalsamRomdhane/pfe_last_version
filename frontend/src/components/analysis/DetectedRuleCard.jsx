/**
 * DetectedRuleCard — displays one rule from detected_rules[].
 * BUNDLE_ID: DRC_2026_V4
 */
import React, { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';

// ── Severity → color mapping ──────────────────────────────────────────────
const SEV = {
  CRITICAL: { label: 'Critical', bg: 'bg-purple-100', text: 'text-purple-700', ring: 'ring-purple-200' },
  HIGH:     { label: 'High',     bg: 'bg-red-100',    text: 'text-red-700',    ring: 'ring-red-200'    },
  MEDIUM:   { label: 'Medium',   bg: 'bg-amber-100',  text: 'text-amber-700',  ring: 'ring-amber-200'  },
  LOW:      { label: 'Low',      bg: 'bg-emerald-100',text: 'text-emerald-700',ring: 'ring-emerald-200' },
  INFO:     { label: 'Info',     bg: 'bg-slate-100',  text: 'text-slate-600',  ring: 'ring-slate-200'  },
};

// ── Coerce is_valid to true / false / null ────────────────────────────────
function toValid(v) {
  if (v === true  || v === 1 || v === '1' || v === 'true')  return true;
  if (v === false || v === 0 || v === '0' || v === 'false') return false;
  return null;
}

export default function DetectedRuleCard({ rule, index }) {
  const [open, setOpen] = useState(false);

  const valid = toValid(rule.is_valid);
  const sev   = SEV[(String(rule.severity || '')).toUpperCase()] || SEV.INFO;

  // Status config
  const ST = valid === true
    ? { Icon: CheckCircle2,  iconCls: 'text-emerald-500', iconBg: 'bg-emerald-50',  badge: 'bg-emerald-100 text-emerald-700', label: 'Valid'   }
    : valid === false
    ? { Icon: XCircle,       iconCls: 'text-red-500',     iconBg: 'bg-red-50',      badge: 'bg-red-100 text-red-700',         label: 'Invalid' }
    : { Icon: AlertTriangle, iconCls: 'text-amber-500',   iconBg: 'bg-amber-50',    badge: 'bg-amber-100 text-amber-700',     label: 'Warning' };

  const cardBorder = valid === true
    ? 'border-emerald-100 bg-emerald-50/20'
    : valid === false
    ? 'border-red-100 bg-red-50/20'
    : 'border-amber-100 bg-amber-50/20';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: index * 0.04 }}
      className={`overflow-hidden rounded-2xl border transition-shadow hover:shadow-md ${cardBorder}`}
    >
      {/* Header */}
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center gap-3 p-4 text-left"
      >
        <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl ${ST.iconBg}`}>
          <ST.Icon size={16} className={ST.iconCls} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-semibold text-slate-900">{rule.title || '—'}</span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ${sev.bg} ${sev.text} ${sev.ring}`}>
              {sev.label}
            </span>
            <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${ST.badge}`}>
              {ST.label}
            </span>
          </div>
          {rule.evidence && (
            <p className="mt-0.5 truncate text-xs text-slate-500">
              Evidence: <span className="font-medium text-slate-700">{rule.evidence}</span>
            </p>
          )}
        </div>

        <motion.div animate={{ rotate: open ? 180 : 0 }} transition={{ duration: 0.2 }}>
          <ChevronDown size={16} className="text-slate-400" />
        </motion.div>
      </button>

      {/* Expanded */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="space-y-3 border-t border-slate-100 px-4 pb-4 pt-3">
              {rule.description && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Description</p>
                  <p className="mt-1 text-sm text-slate-700">{rule.description}</p>
                </div>
              )}
              {rule.evidence && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Evidence detected</p>
                  <div className="mt-1 rounded-xl bg-white px-3 py-2 text-sm font-medium text-slate-800 ring-1 ring-slate-200">
                    {rule.evidence}
                  </div>
                </div>
              )}
              {rule.action && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Recommended action</p>
                  <p className="mt-1 text-sm font-medium text-slate-700">{rule.action}</p>
                </div>
              )}
              {rule.condition && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-slate-400">Condition</p>
                  <code className="mt-1 block rounded-lg bg-slate-100 px-3 py-1.5 text-xs text-slate-600">
                    {rule.condition}
                  </code>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
