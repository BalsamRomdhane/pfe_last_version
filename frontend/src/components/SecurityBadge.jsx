/**
 * SecurityBadge — compact classification/security badge.
 *
 * Variants:
 *   classification : PUBLIC / INTERNAL / CONFIDENTIAL / RESTRICTED
 *   integrity      : VERIFIED / PENDING / TAMPERED / FILE_MISSING
 *   encrypted      : true / false
 */
import React from 'react';
import { Shield, ShieldCheck, ShieldAlert, ShieldOff, Lock, Unlock, CheckCircle2, Clock, AlertTriangle } from 'lucide-react';

// ── Classification config ─────────────────────────────────────────────────

const CLASSIFICATION_CFG = {
  PUBLIC:       { label: 'Public',        cls: 'bg-slate-100 text-slate-600 border-slate-200',    icon: Shield       },
  INTERNAL:     { label: 'Interne',       cls: 'bg-sky-50 text-sky-700 border-sky-200',            icon: ShieldCheck  },
  CONFIDENTIAL: { label: 'Confidentiel',  cls: 'bg-amber-50 text-amber-700 border-amber-200',      icon: ShieldAlert  },
  RESTRICTED:   { label: 'Restreint',     cls: 'bg-red-50 text-red-700 border-red-200',            icon: ShieldOff    },
  SECRET:       { label: 'Secret',        cls: 'bg-purple-50 text-purple-700 border-purple-200',   icon: ShieldOff    },
};

// ── Integrity config ──────────────────────────────────────────────────────

const INTEGRITY_CFG = {
  VERIFIED:     { label: 'Intégrité OK',  cls: 'bg-emerald-50 text-emerald-700 border-emerald-200', icon: CheckCircle2  },
  PENDING:      { label: 'En attente',    cls: 'bg-slate-50 text-slate-500 border-slate-200',        icon: Clock         },
  TAMPERED:     { label: 'Compromis',     cls: 'bg-red-50 text-red-700 border-red-200',              icon: AlertTriangle },
  FILE_MISSING: { label: 'Fichier absent',cls: 'bg-amber-50 text-amber-700 border-amber-200',        icon: AlertTriangle },
};

// ── Classification badge ──────────────────────────────────────────────────

export function ClassificationBadge({ level, size = 'sm' }) {
  const cfg = CLASSIFICATION_CFG[level] || CLASSIFICATION_CFG.PUBLIC;
  const Icon = cfg.icon;
  const px  = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-semibold ${px} ${cfg.cls}`}>
      <Icon size={size === 'xs' ? 9 : 11} />
      {cfg.label}
    </span>
  );
}

// ── Integrity badge ───────────────────────────────────────────────────────

export function IntegrityBadge({ status, size = 'sm' }) {
  const cfg = INTEGRITY_CFG[status] || INTEGRITY_CFG.PENDING;
  const Icon = cfg.icon;
  const px  = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-semibold ${px} ${cfg.cls}`}>
      <Icon size={size === 'xs' ? 9 : 11} />
      {cfg.label}
    </span>
  );
}

// ── Encryption badge ──────────────────────────────────────────────────────

export function EncryptionBadge({ encrypted, size = 'sm' }) {
  const px = size === 'xs' ? 'px-1.5 py-0.5 text-[10px]' : 'px-2 py-1 text-xs';

  if (encrypted) {
    return (
      <span className={`inline-flex items-center gap-1 rounded-full border font-semibold ${px} bg-violet-50 text-violet-700 border-violet-200`}>
        <Lock size={size === 'xs' ? 9 : 11} />
        Chiffré
      </span>
    );
  }

  return (
    <span className={`inline-flex items-center gap-1 rounded-full border font-semibold ${px} bg-slate-50 text-slate-500 border-slate-200`}>
      <Unlock size={size === 'xs' ? 9 : 11} />
      Non chiffré
    </span>
  );
}

// ── Default export: composite badge row ──────────────────────────────────

export default function SecurityBadge({ classification, integrityStatus, encrypted, size = 'sm' }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {classification && <ClassificationBadge level={classification} size={size} />}
      {encrypted !== undefined && <EncryptionBadge encrypted={encrypted} size={size} />}
      {integrityStatus && <IntegrityBadge status={integrityStatus} size={size} />}
    </div>
  );
}
