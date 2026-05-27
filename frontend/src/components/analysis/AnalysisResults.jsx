/**
 * AnalysisResults — reads ONLY from backend response fields.
 * BUNDLE_ID: AR_2026_V4
 */
import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  ShieldCheck, Lightbulb, Search, Download, BookOpen,
  CheckCircle2, XCircle, Sparkles, Database,
} from 'lucide-react';
import ComplianceScore from './ComplianceScore';
import DetectedRuleCard from './DetectedRuleCard';

// ── Tab button ────────────────────────────────────────────────────────────
const TAB_ICON_MAP = { rules: ShieldCheck, suggestions: Lightbulb, evidence: Search };

function TabBtn({ id, label, active, onClick, count }) {
  const Icon = TAB_ICON_MAP[id];
  return (
    <button
      type="button"
      onClick={() => onClick(id)}
      className={`flex items-center gap-2 rounded-xl px-4 py-2 text-sm font-semibold transition-all ${
        active ? 'bg-slate-900 text-white shadow-sm' : 'text-slate-500 hover:bg-slate-100 hover:text-slate-800'
      }`}
    >
      {Icon && <Icon size={14} />}
      {label}
      {count !== undefined && (
        <span className={`rounded-full px-1.5 py-0.5 text-xs ${active ? 'bg-white/20 text-white' : 'bg-slate-200 text-slate-600'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

// ── Suggestion card ───────────────────────────────────────────────────────
function SuggestionCard({ text, idx }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -8 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: idx * 0.06 }}
      className="flex gap-3 rounded-2xl border border-violet-100 bg-violet-50/40 p-4"
    >
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-600">
        <Sparkles size={14} />
      </div>
      <p className="text-sm text-slate-700">{text}</p>
    </motion.div>
  );
}

// ── Build AI suggestions from backend data ────────────────────────────────
function buildAISuggestions(result) {
  const list = [];
  const score    = Number(result?.compliance ?? result?.compliance_score ?? 0);
  const decision = String(result?.decision ?? '');

  // Invalid rules from backend
  const invalidArr = Array.isArray(result?.invalid_rules)
    ? result.invalid_rules
    : (Array.isArray(result?.detected_rules) ? result.detected_rules : []).filter(
        (r) => r.is_valid === false || r.is_valid === 0
      );

  if (invalidArr.length > 0) {
    const names = invalidArr.slice(0, 2).map((r) => r.title || '?').join(', ');
    list.push(`Address ${invalidArr.length} non-compliant rule${invalidArr.length > 1 ? 's' : ''}: ${names}${invalidArr.length > 2 ? '…' : ''}.`);
  }
  if (Number(result?.clarity_score ?? 100) < 70) {
    list.push('Improve document clarity — reduce ambiguous language and passive voice.');
  }
  if (Number(result?.structure_score ?? 100) < 70) {
    list.push('Add missing mandatory sections: objective, scope, responsibilities, review.');
  }
  if (decision === 'TEAMLEAD_REVIEW') {
    list.push('Document is compliant. Submit for Team Lead final validation.');
  }
  if (score > 0 && score < 80) {
    list.push('Consider a full document review with the Quality Manager before submission.');
  }
  if (list.length === 0) {
    list.push('Document is fully compliant. Maintain current quality standards.');
    list.push('Schedule periodic review within 12 months to ensure continued compliance.');
  }
  return list;
}

// ── Main export ───────────────────────────────────────────────────────────
export default function AnalysisResults({ result, onClose }) {
  const [activeTab, setActiveTab] = useState('rules');

  // ── Read ONLY from backend fields ──────────────────────────────────────
  const COMPLIANCE   = Number(result?.compliance      ?? result?.compliance_score ?? 0);
  const VALID_COUNT  = Number(result?.valid_count      ?? 0);
  const INVALID_COUNT= Number(result?.invalid_count    ?? 0);
  const TOTAL_RULES  = Number(result?.total_rules      ?? 0);

  // detected_rules[] is the authoritative rule list
  const DETECTED_RULES = Array.isArray(result?.detected_rules) ? result.detected_rules : [];

  // Derive counts from detected_rules as fallback
  const DERIVED_VALID   = DETECTED_RULES.filter((r) => r.is_valid === true  || r.is_valid === 1).length;
  const DERIVED_INVALID = DETECTED_RULES.filter((r) => r.is_valid === false || r.is_valid === 0).length;

  // Use backend counts when available, fall back to derived
  const SHOW_VALID   = VALID_COUNT   > 0 ? VALID_COUNT   : DERIVED_VALID;
  const SHOW_INVALID = INVALID_COUNT > 0 ? INVALID_COUNT : DERIVED_INVALID;
  const SHOW_TOTAL   = TOTAL_RULES   > 0 ? TOTAL_RULES   : DETECTED_RULES.length;

  // AI suggestions
  const AI_SUGGESTIONS = buildAISuggestions(result);

  // Evidence: only real semantic search results (have similarity/evidence_text but no is_valid)
  const EVIDENCE_ITEMS = (Array.isArray(result?.matches) ? result.matches : []).filter(
    (m) => m.is_valid === undefined && (m.similarity !== undefined || m.evidence_text !== undefined)
  );

  // Debug — open DevTools console
  console.log('[AR v4] compliance=%d valid=%d/%d invalid=%d rules=%d suggestions=%d',
    COMPLIANCE, SHOW_VALID, SHOW_TOTAL, SHOW_INVALID, DETECTED_RULES.length, AI_SUGGESTIONS.length);

  // Export
  const handleExport = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement('a');
    a.href     = url;
    a.download = `compliance-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5">

      {/* ── Global score card ── */}
      <ComplianceScore result={result} />

      {/* ── Quick stats ── */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Valid Rules',   value: SHOW_VALID,            color: 'text-emerald-600', bg: 'bg-emerald-50', Icon: CheckCircle2 },
          { label: 'Invalid Rules', value: SHOW_INVALID,          color: 'text-red-600',     bg: 'bg-red-50',     Icon: XCircle      },
          { label: 'AI Insights',   value: AI_SUGGESTIONS.length, color: 'text-violet-600',  bg: 'bg-violet-50',  Icon: Lightbulb    },
          { label: 'Total Rules',   value: SHOW_TOTAL,            color: 'text-sky-600',     bg: 'bg-sky-50',     Icon: Database     },
        ].map((s, i) => (
          <motion.div
            key={s.label}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: i * 0.05 }}
            className={`rounded-2xl p-3 ${s.bg}`}
          >
            <s.Icon size={16} className={s.color} />
            <p className={`mt-1 text-2xl font-bold ${s.color}`}>{s.value}</p>
            <p className="text-xs text-slate-500">{s.label}</p>
          </motion.div>
        ))}
      </div>

      {/* ── Tabs ── */}
      <div className="flex flex-wrap gap-2 rounded-2xl bg-slate-50 p-1.5">
        <TabBtn id="rules"       label="Rules"       active={activeTab === 'rules'}       onClick={setActiveTab} count={DETECTED_RULES.length} />
        <TabBtn id="suggestions" label="AI Insights" active={activeTab === 'suggestions'} onClick={setActiveTab} count={AI_SUGGESTIONS.length} />
        {EVIDENCE_ITEMS.length > 0 && (
          <TabBtn id="evidence" label="Evidence" active={activeTab === 'evidence'} onClick={setActiveTab} count={EVIDENCE_ITEMS.length} />
        )}
      </div>

      {/* ── Tab content ── */}
      <div className="space-y-3">

        {/* Rules */}
        {activeTab === 'rules' && (
          DETECTED_RULES.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-slate-200 py-10 text-center text-sm text-slate-400">
              No compliance rules detected in this document.
            </div>
          ) : (
            DETECTED_RULES.map((rule, i) => (
              <DetectedRuleCard key={rule.id ?? i} rule={rule} index={i} />
            ))
          )
        )}

        {/* AI Insights */}
        {activeTab === 'suggestions' && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 rounded-2xl bg-gradient-to-r from-violet-50 to-sky-50 px-4 py-3">
              <Sparkles size={16} className="text-violet-500" />
              <p className="text-sm font-semibold text-slate-700">AI-generated improvement suggestions</p>
            </div>
            {AI_SUGGESTIONS.map((text, i) => (
              <SuggestionCard key={i} text={text} idx={i} />
            ))}
          </div>
        )}

        {/* Evidence */}
        {activeTab === 'evidence' && (
          <div className="space-y-3">
            {EVIDENCE_ITEMS.map((item, i) => (
              <div key={item.id ?? i} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <p className="text-sm font-semibold text-slate-900">{item.rule || item.rule_title || '—'}</p>
                <p className="mt-1 text-xs text-slate-500">{item.evidence || item.evidence_text || '—'}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* ── Footer ── */}
      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 pt-4">
        <p className="mr-auto text-xs text-slate-400">
          {COMPLIANCE}% compliant · {SHOW_VALID}/{SHOW_TOTAL} rules valid
        </p>
        <button
          type="button"
          onClick={handleExport}
          className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-xs font-semibold text-slate-700 shadow-sm transition hover:bg-slate-50"
        >
          <Download size={13} /> Export JSON
        </button>
        <button
          type="button"
          onClick={onClose}
          className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-xs font-semibold text-white transition hover:bg-slate-800"
        >
          <BookOpen size={13} /> Done
        </button>
      </div>
    </div>
  );
}
