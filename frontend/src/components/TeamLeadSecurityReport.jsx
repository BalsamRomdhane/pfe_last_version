/**
 * TeamLeadSecurityReport — Full security report panel for TeamLead view.
 *
 * Displays all security fields from DocumentSecurityAnalysis.
 * READ-ONLY — TeamLead cannot modify any security data.
 *
 * Sections:
 *   1. Classification + Risk + Encryption + Integrity header
 *   2. Risk score (visual bar + breakdown)
 *   3. PII detected (types, count — no raw values)
 *   4. Secrets detected (types, count — no raw values)
 *   5. GDPR status
 *   6. Recommendations (full list, prioritised)
 *   7. Classification audit trail (which rules fired)
 *
 * Props:
 *   analysis       : DocumentSecurityAnalysis object (from /analysis/ endpoint)
 *   loading        : bool
 *   integrityStatus: string (VERIFIED | PENDING | TAMPERED | FILE_MISSING)
 *   encrypted      : bool
 *   hashCreatedAt  : string (ISO date)
 */
import React, { useState } from 'react';
import {
  Shield, ShieldCheck, ShieldAlert, ShieldOff,
  Lock, Unlock, CheckCircle2, XCircle, AlertTriangle,
  Eye, Key, Activity, FileText, ChevronDown, ChevronUp,
  Clock, Info,
} from 'lucide-react';
import { ClassificationBadge, IntegrityBadge, EncryptionBadge } from './SecurityBadge';

// ── Helpers ────────────────────────────────────────────────────────────────

const fmt = (iso) => {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('fr-FR', {
      day: '2-digit', month: 'short', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    });
  } catch { return iso; }
};

// ── Risk config ────────────────────────────────────────────────────────────

const RISK_CFG = {
  LOW:      { label: 'Faible',   cls: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200', bar: 'bg-emerald-500' },
  MEDIUM:   { label: 'Modéré',   cls: 'text-amber-700',   bg: 'bg-amber-50 border-amber-200',     bar: 'bg-amber-500'   },
  HIGH:     { label: 'Élevé',    cls: 'text-red-700',     bg: 'bg-red-50 border-red-200',         bar: 'bg-red-500'     },
  CRITICAL: { label: 'Critique', cls: 'text-purple-700',  bg: 'bg-purple-50 border-purple-200',   bar: 'bg-purple-500'  },
};

const GDPR_CFG = {
  OK:            { label: 'Conforme',       cls: 'text-emerald-700 bg-emerald-50 border-emerald-200', icon: CheckCircle2  },
  WARNING:       { label: 'Avertissement',  cls: 'text-amber-700 bg-amber-50 border-amber-200',       icon: AlertTriangle },
  NON_COMPLIANT: { label: 'Non conforme',   cls: 'text-red-700 bg-red-50 border-red-200',             icon: XCircle       },
  UNKNOWN:       { label: 'Inconnu',        cls: 'text-slate-600 bg-slate-50 border-slate-200',       icon: Info          },
};

const PRIO_CFG = {
  CRITICAL: 'text-purple-700 bg-purple-50 border-purple-200',
  HIGH:     'text-red-700 bg-red-50 border-red-200',
  MEDIUM:   'text-amber-700 bg-amber-50 border-amber-200',
  LOW:      'text-slate-600 bg-slate-50 border-slate-200',
};

// ── Sub-components ─────────────────────────────────────────────────────────

function Skel({ h = 'h-5', w = 'w-full' }) {
  return <div className={`${h} ${w} rounded animate-pulse bg-slate-100`} />;
}

function Section({ title, icon: Icon, children, defaultOpen = true, badge }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="border border-slate-100 rounded-xl overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center gap-2 px-4 py-3 bg-slate-50/60 hover:bg-slate-100/60 transition-colors text-left"
      >
        {Icon && <Icon size={14} className="text-slate-500 shrink-0" />}
        <span className="text-xs font-semibold text-slate-700 flex-1">{title}</span>
        {badge && <span className="text-[10px] font-semibold text-slate-500 bg-white border border-slate-200 rounded-full px-2 py-0.5">{badge}</span>}
        {open ? <ChevronUp size={12} className="text-slate-400" /> : <ChevronDown size={12} className="text-slate-400" />}
      </button>
      {open && <div className="px-4 py-3 space-y-2">{children}</div>}
    </div>
  );
}

function PiiTypeRow({ type, count }) {
  const TYPE_LABELS = {
    EMAIL: 'Adresse e-mail', PHONE: 'Numéro de téléphone', IBAN: 'IBAN',
    CREDIT_CARD: 'Carte bancaire', NATIONAL_ID: 'Numéro national', PASSPORT: 'Passeport',
    EMPLOYEE_ID: 'ID employé', DATE_OF_BIRTH: 'Date de naissance', FULL_NAME: 'Nom complet',
    ADDRESS: 'Adresse postale', DATE: 'Date',
  };
  return (
    <div className="flex items-center justify-between py-1 border-b border-slate-100 last:border-0">
      <span className="text-xs text-slate-600">{TYPE_LABELS[type] || type}</span>
      <span className="text-xs font-semibold text-slate-800">{count}</span>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export default function TeamLeadSecurityReport({
  analysis,
  loading,
  integrityStatus,
  encrypted,
  hashCreatedAt,
  className = '',
}) {
  // ── Loading state ────────────────────────────────────────────────────
  if (loading && !analysis) {
    return (
      <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm p-4 space-y-3 ${className}`}>
        <div className="flex items-center gap-2 mb-1">
          <Shield size={14} className="text-slate-400" />
          <span className="text-sm font-semibold text-slate-500">Rapport de sécurité</span>
        </div>
        {[1,2,3,4].map(i => <Skel key={i} w={i % 2 === 0 ? 'w-3/4' : 'w-full'} />)}
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className={`rounded-2xl border border-slate-100 bg-slate-50 p-4 ${className}`}>
        <div className="flex items-center gap-2 text-slate-400">
          <Shield size={14} />
          <p className="text-xs">Aucune analyse de sécurité disponible pour ce document.</p>
        </div>
      </div>
    );
  }

  const riskCfg  = RISK_CFG[analysis.risk_level] || RISK_CFG.LOW;
  const riskScore = analysis.risk_score || 0;
  const gdprCfg  = GDPR_CFG[analysis.gdpr_status] || GDPR_CFG.UNKNOWN;
  const GdprIcon = gdprCfg.icon;

  const piiTypes     = analysis.pii_types    || {};
  const secretTypes  = analysis.secret_types || {};
  const recs         = analysis.recommendations || [];
  const breakdown    = analysis.score_breakdown || {};
  const explanation  = analysis.score_explanation || [];
  const rulesMatched = analysis.classification_rules_matched || [];

  return (
    <div className={`rounded-2xl border border-slate-200 bg-white shadow-sm ${className}`}>

      {/* ── Header ──────────────────────────────────────────────────── */}
      <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
        <div className="flex h-7 w-7 items-center justify-center rounded-xl bg-violet-100">
          <Shield size={14} className="text-violet-600" />
        </div>
        <p className="text-sm font-semibold text-slate-900">Rapport de sécurité</p>
        <span className="ml-auto text-[10px] text-slate-400 font-medium bg-slate-100 rounded-full px-2 py-0.5">
          Lecture seule
        </span>
      </div>

      <div className="p-4 space-y-3">

        {/* ── Classification + status badges ──────────────────────── */}
        <div className="flex flex-wrap gap-1.5">
          <ClassificationBadge level={analysis.confidentiality_level} />
          <EncryptionBadge encrypted={!!encrypted} />
          {integrityStatus && <IntegrityBadge status={integrityStatus} />}
        </div>

        {/* ── Risk score bar ───────────────────────────────────────── */}
        <div className={`rounded-xl border p-3 ${riskCfg.bg}`}>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-1.5">
              <Activity size={12} className={riskCfg.cls} />
              <span className="text-xs font-semibold text-slate-700">Niveau de risque</span>
            </div>
            <span className={`text-xs font-bold ${riskCfg.cls}`}>{riskCfg.label} — {riskScore}/100</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-white/60">
            <div className={`h-full rounded-full transition-all duration-700 ${riskCfg.bar}`}
              style={{ width: `${riskScore}%` }} />
          </div>
          {explanation.length > 0 && (
            <ul className="mt-2 space-y-0.5">
              {explanation.map((e, i) => (
                <li key={i} className="text-[10px] text-slate-500">• {e}</li>
              ))}
            </ul>
          )}
        </div>

        {/* ── PII ──────────────────────────────────────────────────── */}
        <Section
          title="Données personnelles (PII)"
          icon={Eye}
          badge={analysis.pii_count > 0 ? `${analysis.pii_count} détecté(s)` : 'Aucune'}
          defaultOpen={analysis.pii_count > 0}
        >
          {analysis.pii_count === 0 ? (
            <p className="text-xs text-emerald-600 flex items-center gap-1.5">
              <CheckCircle2 size={12} /> Aucune donnée personnelle détectée.
            </p>
          ) : (
            <>
              <p className="text-xs text-slate-500 mb-1">Types détectés :</p>
              {Object.entries(piiTypes).map(([type, count]) => (
                <PiiTypeRow key={type} type={type} count={count} />
              ))}
              {analysis.gdpr_has_pii && (
                <p className="text-[10px] text-amber-600 mt-2 flex items-center gap-1">
                  <AlertTriangle size={10} /> Les valeurs exactes ne sont pas affichées pour des raisons de confidentialité.
                </p>
              )}
            </>
          )}
        </Section>

        {/* ── Secrets ──────────────────────────────────────────────── */}
        <Section
          title="Secrets & Credentials"
          icon={Key}
          badge={analysis.secret_count > 0 ? `${analysis.secret_count} trouvé(s)` : 'Aucun'}
          defaultOpen={analysis.secret_count > 0}
        >
          {analysis.secret_count === 0 ? (
            <p className="text-xs text-emerald-600 flex items-center gap-1.5">
              <CheckCircle2 size={12} /> Aucun secret ou identifiant détecté.
            </p>
          ) : (
            <>
              <p className="text-xs text-red-600 font-semibold flex items-center gap-1.5 mb-2">
                <AlertTriangle size={12} /> Action requise — des identifiants ont été détectés.
              </p>
              {Object.entries(secretTypes).map(([type, count]) => (
                <div key={type} className="flex justify-between py-1 border-b border-slate-100 last:border-0">
                  <span className="text-xs text-slate-600">{type.replace(/_/g, ' ')}</span>
                  <span className="text-xs font-semibold text-red-700">{count}</span>
                </div>
              ))}
            </>
          )}
        </Section>

        {/* ── GDPR ─────────────────────────────────────────────────── */}
        <Section title="Conformité GDPR" icon={FileText} defaultOpen={analysis.gdpr_status !== 'OK'}>
          <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 ${gdprCfg.cls}`}>
            <GdprIcon size={13} className="shrink-0" />
            <span className="text-xs font-semibold">{gdprCfg.label}</span>
          </div>
          {analysis.gdpr_compliance_summary && (
            <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
              {analysis.gdpr_compliance_summary}
            </p>
          )}
          {(analysis.gdpr_issues || []).length > 0 && (
            <div className="mt-2 space-y-1">
              {analysis.gdpr_issues.map((issue, i) => (
                <p key={i} className="text-[11px] text-amber-700 flex items-start gap-1.5">
                  <AlertTriangle size={10} className="mt-0.5 shrink-0" /> {issue}
                </p>
              ))}
            </div>
          )}
        </Section>

        {/* ── Recommendations ──────────────────────────────────────── */}
        {recs.length > 0 && (
          <Section title="Recommandations" icon={ShieldAlert} badge={`${recs.length}`} defaultOpen>
            <div className="space-y-2">
              {recs.map((rec, i) => (
                <div key={i} className={`rounded-lg border px-3 py-2 text-xs ${PRIO_CFG[rec.priority] || PRIO_CFG.LOW}`}>
                  <p className="font-semibold">{rec.title}</p>
                  {rec.description && (
                    <p className="mt-0.5 font-normal opacity-80 text-[10px]">{rec.description}</p>
                  )}
                </div>
              ))}
            </div>
          </Section>
        )}

        {/* ── Classification audit ─────────────────────────────────── */}
        {(rulesMatched.length > 0 || analysis.classification_source) && (
          <Section title="Audit de classification" icon={Shield} defaultOpen={false}>
            {analysis.classification_source && (
              <p className="text-xs text-slate-600">
                <span className="font-semibold">Règle déterminante :</span>{' '}
                {analysis.classification_source.replace(/_/g, ' ')}
              </p>
            )}
            {rulesMatched.length > 0 && (
              <div className="flex flex-wrap gap-1 mt-1">
                {rulesMatched.map((r, i) => (
                  <span key={i} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-600 font-medium">
                    {r.replace(/_/g, ' ')}
                  </span>
                ))}
              </div>
            )}
            {hashCreatedAt && (
              <p className="text-[10px] text-slate-400 mt-1 flex items-center gap-1">
                <Clock size={9} /> Hash calculé le {fmt(hashCreatedAt)}
              </p>
            )}
            <p className="text-[10px] text-slate-400 mt-1">
              v{analysis.analysis_version || '1.0.0'} — {fmt(analysis.analysis_date)}
            </p>
          </Section>
        )}

        {/* ── All clear ────────────────────────────────────────────── */}
        {recs.length === 0 && analysis.pii_count === 0 && analysis.secret_count === 0 && analysis.gdpr_status === 'OK' && (
          <div className="flex items-center gap-2 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2.5">
            <CheckCircle2 size={14} className="text-emerald-500 shrink-0" />
            <p className="text-xs font-medium text-emerald-700">
              Ce document ne présente aucun problème de sécurité.
            </p>
          </div>
        )}

      </div>
    </div>
  );
}
