/**
 * DocumentSecurityPanel — security report panel for Employee view.
 *
 * Shows:
 *   - Classification (PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED)
 *   - Risk score + level
 *   - Encryption status
 *   - Integrity status
 *   - PII count (no details — just the count)
 *   - Secrets count (no details)
 *   - Top recommendations (max 3, no technical jargon)
 *
 * Rules:
 *   - Never shows raw PII values, file paths, or internal IDs.
 *   - Loading state: skeleton placeholders.
 *   - If analysis is not yet available: informational pending state.
 *   - Read-only. Employee cannot modify anything here.
 */
import React from 'react';
import {
  Shield, ShieldCheck, ShieldAlert, Lock, Unlock,
  CheckCircle2, Clock, AlertTriangle, Info,
  Eye, Key, RefreshCw,
} from 'lucide-react';
import { ClassificationBadge, IntegrityBadge, EncryptionBadge } from './SecurityBadge';

// ── Risk level config ─────────────────────────────────────────────────────

const RISK_CFG = {
  LOW:      { label: 'Faible',    cls: 'text-emerald-700', bg: 'bg-emerald-50', bar: 'bg-emerald-500' },
  MEDIUM:   { label: 'Modéré',    cls: 'text-amber-700',   bg: 'bg-amber-50',   bar: 'bg-amber-500'   },
  HIGH:     { label: 'Élevé',     cls: 'text-red-700',     bg: 'bg-red-50',     bar: 'bg-red-500'     },
  CRITICAL: { label: 'Critique',  cls: 'text-purple-700',  bg: 'bg-purple-50',  bar: 'bg-purple-500'  },
};

// ── Friendly recommendation labels (strip technical actions) ─────────────

const friendlyRec = (rec) => {
  if (!rec) return null;
  const title = rec.title || '';
  const desc  = rec.description || '';
  // Only show the title — trim overly technical descriptions
  return title.length > 0 ? title : desc.slice(0, 80);
};

const PRIO_COLOR = {
  CRITICAL: 'text-purple-700 bg-purple-50 border-purple-200',
  HIGH:     'text-red-700 bg-red-50 border-red-200',
  MEDIUM:   'text-amber-700 bg-amber-50 border-amber-200',
  LOW:      'text-slate-600 bg-slate-50 border-slate-200',
};

// ── Skeleton placeholder ──────────────────────────────────────────────────

function Skel({ w = 'w-full', h = 'h-4' }) {
  return <div className={`${w} ${h} rounded animate-pulse bg-slate-100`} />;
}

// ── Main component ────────────────────────────────────────────────────────

export default function DocumentSecurityPanel({
  analysis,       // DocumentSecurityAnalysis object from API (may be null)
  loading,        // bool — pipeline still running
  integrityStatus,// string — from /integrity/ endpoint or doc.integrity_status
  encrypted,      // bool — from Document.encrypted
  className = '',
}) {
  // ── Pending state (analysis not yet computed) ─────────────────────────
  if (loading || !analysis) {
    return (
      <div className={`rounded-2xl border border-slate-100 bg-slate-50 p-4 ${className}`}>
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-slate-200">
            <Shield size={14} className="text-slate-400" />
          </div>
          <p className="text-sm font-semibold text-slate-600">Analyse de sécurité</p>
          {loading && (
            <span className="ml-auto flex items-center gap-1 text-[10px] text-slate-400 font-medium">
              <RefreshCw size={10} className="animate-spin" /> En cours…
            </span>
          )}
        </div>
        {loading ? (
          <div className="space-y-2">
            <Skel w="w-1/2" />
            <Skel w="w-3/4" />
            <Skel w="w-2/3" />
          </div>
        ) : (
          <p className="text-xs text-slate-400">
            L'analyse de sécurité sera disponible dans quelques instants.
          </p>
        )}
      </div>
    );
  }

  // ── Risk bar ──────────────────────────────────────────────────────────
  const riskCfg   = RISK_CFG[analysis.risk_level] || RISK_CFG.LOW;
  const riskScore = analysis.risk_score || 0;

  // ── Top recommendations (max 3, CRITICAL or HIGH priority first) ──────
  const recs = (analysis.recommendations || [])
    .filter(r => ['CRITICAL', 'HIGH', 'MEDIUM'].includes(r.priority))
    .slice(0, 3);

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-100">
          <Shield size={14} className="text-violet-600" />
        </div>
        <p className="text-sm font-semibold text-slate-900">Analyse de sécurité</p>
        <span className="ml-auto text-[10px] text-slate-400 font-medium">
          v{analysis.analysis_version || '1.0.0'}
        </span>
      </div>

      <div className="p-4 space-y-4">

        {/* ── Classification + Encryption + Integrity row ───────────── */}
        <div className="flex flex-wrap gap-1.5">
          <ClassificationBadge level={analysis.confidentiality_level} />
          <EncryptionBadge encrypted={!!encrypted} />
          {integrityStatus && <IntegrityBadge status={integrityStatus} />}
        </div>

        {/* ── Risk score ────────────────────────────────────────────── */}
        <div className={`rounded-xl p-3 ${riskCfg.bg}`}>
          <div className="flex items-center justify-between mb-1.5">
            <p className="text-xs font-semibold text-slate-700">Niveau de risque</p>
            <span className={`text-xs font-bold ${riskCfg.cls}`}>{riskCfg.label}</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-white/60">
            <div
              className={`h-full rounded-full transition-all duration-700 ${riskCfg.bar}`}
              style={{ width: `${riskScore}%` }}
            />
          </div>
          <p className="mt-1 text-[10px] text-slate-500">{riskScore}/100</p>
        </div>

        {/* ── PII + Secrets summary ─────────────────────────────────── */}
        <div className="grid grid-cols-2 gap-2">
          <div className="rounded-xl border border-slate-100 bg-slate-50 p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <Eye size={12} className="text-slate-400" />
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Données perso.</p>
            </div>
            <p className={`text-xl font-bold ${analysis.pii_count > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
              {analysis.pii_count}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {analysis.pii_count === 0 ? 'Aucune détectée' : 'élément(s) identifié(s)'}
            </p>
          </div>

          <div className="rounded-xl border border-slate-100 bg-slate-50 p-2.5">
            <div className="flex items-center gap-1.5 mb-1">
              <Key size={12} className="text-slate-400" />
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide">Secrets</p>
            </div>
            <p className={`text-xl font-bold ${analysis.secret_count > 0 ? 'text-red-600' : 'text-emerald-600'}`}>
              {analysis.secret_count}
            </p>
            <p className="text-[10px] text-slate-400 mt-0.5">
              {analysis.secret_count === 0 ? 'Aucun détecté' : 'credential(s) trouvé(s)'}
            </p>
          </div>
        </div>

        {/* ── Recommendations (simplified) ─────────────────────────── */}
        {recs.length > 0 && (
          <div>
            <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">
              Recommandations
            </p>
            <div className="space-y-1.5">
              {recs.map((rec, i) => {
                const label = friendlyRec(rec);
                if (!label) return null;
                return (
                  <div
                    key={i}
                    className={`flex items-start gap-2 rounded-lg border px-2.5 py-2 text-xs ${PRIO_COLOR[rec.priority] || PRIO_COLOR.LOW}`}
                  >
                    <AlertTriangle size={11} className="mt-0.5 shrink-0" />
                    <span className="font-medium">{label}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* ── All clear ────────────────────────────────────────────── */}
        {recs.length === 0 && analysis.pii_count === 0 && analysis.secret_count === 0 && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5">
            <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
            <p className="text-xs font-medium text-emerald-700">
              Aucun problème de sécurité détecté.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}
