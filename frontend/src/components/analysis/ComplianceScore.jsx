/**
 * ComplianceScore — reads ONLY from backend response fields.
 * Backend fields used: compliance, valid_count, invalid_count,
 * total_rules, confidence_score, similarity_score, decision
 * BUNDLE_ID: CS_2026_V4
 */
import React from 'react';
import { motion } from 'framer-motion';
import { ShieldCheck, ShieldAlert, ShieldX, Brain, TrendingUp } from 'lucide-react';

// ── Risk level from compliance score ─────────────────────────────────────
function computeRisk(complianceScore, decisionStr) {
  const pct = Number(complianceScore) || 0;
  const dec = String(decisionStr || '');

  if (pct >= 90 || (pct >= 80 && dec === 'TEAMLEAD_REVIEW')) {
    return {
      label : dec === 'TEAMLEAD_REVIEW' ? 'Compliant — Team Lead Review' : 'Low Risk',
      color : 'text-emerald-600',
      bg    : 'bg-emerald-50',
      ring  : 'ring-emerald-200',
      stroke: '#10b981',
      Icon  : ShieldCheck,
      desc  : dec === 'TEAMLEAD_REVIEW'
        ? 'Document is fully compliant. Awaiting Team Lead validation.'
        : 'Document meets ISO compliance requirements.',
    };
  }
  if (pct >= 70) {
    return {
      label : 'Medium Risk',
      color : 'text-amber-600',
      bg    : 'bg-amber-50',
      ring  : 'ring-amber-200',
      stroke: '#f59e0b',
      Icon  : ShieldAlert,
      desc  : 'Document partially compliant — review required.',
    };
  }
  return {
    label : 'High Risk',
    color : 'text-red-600',
    bg    : 'bg-red-50',
    ring  : 'ring-red-200',
    stroke: '#ef4444',
    Icon  : ShieldX,
    desc  : 'Document does not meet compliance requirements.',
  };
}

// ── Circular progress using stroke-dashoffset (no degenerate path) ───────
function CircularArc({ pct, strokeColor }) {
  const RADIUS = 44;
  const CIRC   = 2 * Math.PI * RADIUS;
  // clamp so arc is always visible at 0% and 100%
  const clamped = Math.min(99.5, Math.max(0.5, Number(pct) || 0));
  const offset  = CIRC * (1 - clamped / 100);

  return (
    <div className="relative flex h-32 w-32 items-center justify-center">
      {/* SVG rotated so arc starts at top */}
      <svg width="128" height="128" viewBox="0 0 128 128" className="-rotate-90">
        {/* Track */}
        <circle cx="64" cy="64" r={RADIUS} fill="none" stroke="#e2e8f0" strokeWidth="10" strokeLinecap="round" />
        {/* Animated fill */}
        <motion.circle
          cx="64" cy="64" r={RADIUS}
          fill="none"
          stroke={strokeColor}
          strokeWidth="10"
          strokeLinecap="round"
          strokeDasharray={CIRC}
          initial={{ strokeDashoffset: CIRC }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </svg>
      {/* Center label — counter-rotated */}
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <motion.span
          className="text-3xl font-bold text-slate-900"
          initial={{ opacity: 0, scale: 0.5 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.35, type: 'spring', stiffness: 280 }}
        >
          {Number(pct) || 0}%
        </motion.span>
      </div>
    </div>
  );
}

// ── Main export ───────────────────────────────────────────────────────────
export default function ComplianceScore({ result }) {
  // ── Read ONLY from backend fields ──────────────────────────────────────
  const COMPLIANCE  = Number(result?.compliance       ?? result?.compliance_score ?? 0);
  const VALID_COUNT = Number(result?.valid_count       ?? 0);
  const TOTAL_RULES = Number(result?.total_rules       ?? 0);
  const CONFIDENCE  = Number(result?.confidence_score  ?? 0);
  const SIMILARITY  = Number(result?.similarity_score  ?? 0);
  const DECISION    = String(result?.decision          ?? '');

  // Debug — open DevTools to confirm values
  console.log('[CS v4] compliance=%d valid=%d/%d confidence=%d decision=%s',
    COMPLIANCE, VALID_COUNT, TOTAL_RULES, CONFIDENCE, DECISION);

  const risk = computeRisk(COMPLIANCE, DECISION);
  const { Icon: RiskIcon } = risk;

  const METRICS = [
    {
      label: 'Valid Rules',
      value: TOTAL_RULES > 0 ? `${VALID_COUNT}/${TOTAL_RULES}` : String(VALID_COUNT),
      Icon : ShieldCheck,
      color: 'text-emerald-600',
      bg   : 'bg-emerald-50',
    },
    {
      label: 'AI Confidence',
      value: `${CONFIDENCE}%`,
      Icon : Brain,
      color: 'text-violet-600',
      bg   : 'bg-violet-50',
    },
    {
      label: 'Similarity',
      value: `${SIMILARITY}%`,
      Icon : TrendingUp,
      color: 'text-sky-600',
      bg   : 'bg-sky-50',
    },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      className="overflow-hidden rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white shadow-sm"
    >
      <div className="flex flex-col items-center gap-6 p-6 sm:flex-row">

        {/* Circular progress */}
        <div className="shrink-0">
          <CircularArc pct={COMPLIANCE} strokeColor={risk.stroke} />
        </div>

        <div className="flex-1 space-y-4">
          {/* Risk badge */}
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold ring-1 ${risk.bg} ${risk.color} ${risk.ring}`}>
                <RiskIcon size={12} />
                {risk.label}
              </span>
              {DECISION && DECISION !== 'TEAMLEAD_REVIEW' && (
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-600">
                  {DECISION.replace(/_/g, ' ')}
                </span>
              )}
            </div>
            <p className="mt-2 text-sm text-slate-500">{risk.desc}</p>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-3">
            {METRICS.map((m, i) => (
              <motion.div
                key={m.label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.15 + i * 0.07 }}
                className={`rounded-xl p-3 ${m.bg}`}
              >
                <m.Icon size={14} className={m.color} />
                <p className="mt-1.5 text-lg font-bold text-slate-900">{m.value}</p>
                <p className="text-xs text-slate-500">{m.label}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
