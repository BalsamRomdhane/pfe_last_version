import React, { useEffect, useState, useContext } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { UserContext } from '../../context/UserContext';
import Layout from '../../components/Layout';
import StatusBadge from '../../components/StatusBadge';
import DocumentSecurityPanel from '../../components/DocumentSecurityPanel';
import api from '../../services/api';
import { useSecureDocumentView } from '../../hooks/useSecureDocumentView';
import { useDocumentSecurity } from '../../hooks/useDocumentSecurity';
import {
  ArrowLeft, FileText, Download, CheckCircle2, XCircle,
  Clock, AlertTriangle, ExternalLink, RefreshCw,
  ShieldCheck, ShieldAlert, User, Calendar, BookOpen,
  ChevronDown, ChevronUp, MessageSquare, Shield,
} from 'lucide-react';

/* ─── helpers ─────────────────────────────────────────────────────────── */
const fmt = (d) =>
  d ? new Date(d).toLocaleDateString('fr-FR', {
    day: '2-digit', month: 'long', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  }) : '—';

const fmtShort = (d) =>
  d ? new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';

/* ─── Status pipeline ─────────────────────────────────────────────────── */
const STEPS = [
  { key: 'pending',   label: 'Soumis',      icon: Clock },
  { key: 'reviewing', label: 'En révision', icon: RefreshCw },
  { key: 'approved',  label: 'Approuvé',   icon: CheckCircle2 },
];

function StatusPipeline({ status }) {
  const currentIdx = status === 'rejected'
    ? 3
    : STEPS.findIndex(s => s.key === status);

  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => {
        const Icon = step.icon;
        const done    = status === 'approved' ? i <= 2 : i < currentIdx;
        const current = i === currentIdx && status !== 'rejected';
        const rejected = status === 'rejected';
        return (
          <React.Fragment key={step.key}>
            <div className={`flex flex-col items-center gap-1.5 ${i > 0 ? '' : ''}`}>
              <div className={`flex h-8 w-8 items-center justify-center rounded-full border-2 transition-all
                ${done    ? 'border-emerald-500 bg-emerald-500 text-white' :
                  current ? 'border-brand-500 bg-brand-50 text-brand-600' :
                  rejected && i === 2 ? 'border-red-300 bg-red-50 text-red-400' :
                  'border-slate-200 bg-white text-slate-300'}`}>
                {rejected && i === 2
                  ? <XCircle size={14} className="text-red-500" />
                  : <Icon size={14} />
                }
              </div>
              <span className={`text-2xs font-medium whitespace-nowrap
                ${done ? 'text-emerald-600' : current ? 'text-brand-600' : 'text-slate-400'}`}>
                {rejected && i === 2 ? 'Rejeté' : step.label}
              </span>
            </div>
            {i < STEPS.length - 1 && (
              <div className={`flex-1 h-0.5 mb-4 mx-1 min-w-[24px]
                ${done ? 'bg-emerald-400' : 'bg-slate-200'}`} />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ─── Score ring ───────────────────────────────────────────────────────── */
function ScoreRing({ score }) {
  if (typeof score !== 'number') return null;
  const R = 28;
  const C = 2 * Math.PI * R;
  const offset = C * (1 - score / 100);
  const color = score >= 80 ? '#10b981' : score >= 60 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-3">
      <div className="relative flex h-16 w-16 shrink-0 items-center justify-center">
        <svg viewBox="0 0 72 72" className="-rotate-90 h-16 w-16">
          <circle cx="36" cy="36" r={R} fill="none" stroke="#e2e8f0" strokeWidth="6" />
          <circle cx="36" cy="36" r={R} fill="none" stroke={color} strokeWidth="6"
            strokeLinecap="round" strokeDasharray={C} strokeDashoffset={offset}
            style={{ transition: 'stroke-dashoffset 0.8s ease' }} />
        </svg>
        <span className="absolute text-sm font-bold text-slate-900">{score}%</span>
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-900">Score de conformité</p>
        <p className={`text-xs mt-0.5 ${score >= 80 ? 'text-emerald-600' : score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
          {score >= 80 ? 'Conforme' : score >= 60 ? 'Partiellement conforme' : 'Non conforme'}
        </p>
      </div>
    </div>
  );
}

/* ─── Validation rule row ─────────────────────────────────────────────── */
function ValidationRow({ v }) {
  const [open, setOpen] = useState(false);
  const valid = v.is_valid;
  return (
    <div className={`rounded-xl border overflow-hidden
      ${valid ? 'border-emerald-100 bg-emerald-50/20' : 'border-red-100 bg-red-50/20'}`}>
      <button type="button" onClick={() => setOpen(o => !o)}
        className="flex w-full items-center gap-3 px-4 py-3 text-left">
        <div className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full
          ${valid ? 'bg-emerald-100' : 'bg-red-100'}`}>
          {valid
            ? <CheckCircle2 size={13} className="text-emerald-600" />
            : <XCircle     size={13} className="text-red-600" />
          }
        </div>
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-slate-900 truncate">
            {v.rule?.title || `Règle #${v.rule}`}
          </p>
          {v.evidence_text && (
            <p className="text-xs text-slate-500 truncate mt-0.5">{v.evidence_text}</p>
          )}
        </div>
        <span className={`badge shrink-0 ${valid ? 'badge-green' : 'badge-red'}`}>
          {valid ? 'Conforme' : 'Non conforme'}
        </span>
        {(v.evidence_text || v.reviewer_comment) &&
          (open ? <ChevronUp size={14} className="text-slate-400 shrink-0" />
                : <ChevronDown size={14} className="text-slate-400 shrink-0" />)
        }
      </button>
      {open && (v.evidence_text || v.reviewer_comment || v.rule?.description) && (
        <div className="border-t border-slate-100 px-4 pb-3 pt-2 space-y-2">
          {v.rule?.description && (
            <div>
              <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-0.5">Description</p>
              <p className="text-xs text-slate-600">{v.rule.description}</p>
            </div>
          )}
          {v.evidence_text && (
            <div>
              <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-0.5">Commentaire</p>
              <p className="text-xs text-slate-700">{v.evidence_text}</p>
            </div>
          )}
          {v.reviewer_comment && (
            <div className="rounded-md bg-amber-50 border border-amber-100 px-2.5 py-1.5">
              <p className="text-2xs font-bold uppercase tracking-wider text-amber-600 mb-0.5">Note du reviewer</p>
              <p className="text-xs text-amber-800">{v.reviewer_comment}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── PDF download ────────────────────────────────────────────────────── */
function usePdfDownload(docId) {
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');

  const download = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get(`/documents/${docId}/report/`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a   = document.createElement('a');
      a.href     = url;
      a.download = `conformite-rapport-${docId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError('Rapport PDF non disponible pour ce document.');
      setTimeout(() => setError(''), 4000);
    } finally {
      setLoading(false);
    }
  };

  return { loading, error, download };
}

/* ═══════════════════════════════════════════════════════════════════════════
   DOCUMENT DETAIL PAGE
═══════════════════════════════════════════════════════════════════════════ */
export default function DocumentDetail() {
  const { id }          = useParams();
  const navigate        = useNavigate();
  const { user }        = useContext(UserContext);

  const [doc,         setDoc]         = useState(null);
  const [validations, setValidations] = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState('');

  const { loading: pdfLoading, error: pdfError, download: downloadPdf } = usePdfDownload(id);
  const { openDocument: openSecureDoc, downloadDocument, loading: viewLoading, error: viewError, setError: setViewError } = useSecureDocumentView();

  // Phase 9 — security analysis panel
  const docIdNum = id ? parseInt(id, 10) : null;
  const { analysis: securityAnalysis, loading: securityLoading } = useDocumentSecurity({
    docId: docIdNum,
    autoFetch: !!docIdNum,
    maxAttempts: 8,
    interval: 3000,
  });

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [docRes, valRes] = await Promise.allSettled([
        api.get(`/documents/${id}/`),
        api.get(`/documents/${id}/validations/`),
      ]);

      if (docRes.status === 'fulfilled') {
        setDoc(docRes.value.data);
      } else {
        setError('Document introuvable ou accès refusé.');
        return;
      }

      if (valRes.status === 'fulfilled') {
        const list = Array.isArray(valRes.value.data) ? valRes.value.data : [];
        setValidations(list);
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]); // eslint-disable-line

  /* ── Derived ── */
  const validCount   = validations.filter(v => v.is_valid === true).length;
  const invalidCount = validations.filter(v => v.is_valid === false).length;
  const fileName     = doc?.file ? doc.file.split('/').pop() : `Document #${id}`;
  const normeName    = doc?.norme?.name || (doc?.norme ? `Norme #${doc.norme}` : '—');

  /* ── Loading skeleton ── */
  if (loading) {
    return (
      <Layout>
        <div className="page-container">
          <div className="animate-pulse space-y-5">
            <div className="skeleton h-8 w-48 rounded" />
            <div className="card p-6 space-y-4">
              <div className="skeleton h-6 w-64 rounded" />
              <div className="skeleton h-4 w-40 rounded" />
              <div className="skeleton h-20 w-full rounded-xl" />
            </div>
          </div>
        </div>
      </Layout>
    );
  }

  /* ── Error state ── */
  if (error) {
    return (
      <Layout>
        <div className="page-container">
          <div className="flex flex-col items-center gap-4 py-20">
            <AlertTriangle size={40} className="text-red-300" />
            <p className="text-base font-semibold text-slate-700">{error}</p>
            <button type="button" onClick={() => navigate(-1)} className="btn-secondary">
              <ArrowLeft size={14} /> Retour
            </button>
          </div>
        </div>
      </Layout>
    );
  }

  const isRejected = doc?.status === 'rejected';
  const isApproved = doc?.status === 'approved' || doc?.status === 'auto_approved';

  return (
    <Layout>
      <div className="page-container">

        {/* ── Back + Header ── */}
        <div className="flex items-center gap-3">
          <button type="button" onClick={() => navigate('/documents')}
            className="btn-icon-md border border-slate-200 hover:bg-slate-50" aria-label="Retour">
            <ArrowLeft size={16} />
          </button>
          <div className="flex-1 min-w-0">
            <p className="section-label">Mes documents</p>
            <h1 className="page-title mt-0.5 truncate">{fileName}</h1>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button type="button" onClick={load}
              className="btn-icon-sm text-slate-400 hover:text-slate-700 border border-slate-200" title="Rafraîchir">
              <RefreshCw size={13} />
            </button>
            <button type="button" onClick={downloadPdf} disabled={pdfLoading}
              className="btn-secondary">
              {pdfLoading
                ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                : <Download size={14} />
              }
              Rapport PDF
            </button>
            {doc?.secure_download_url && (
              <button
                type="button"
                onClick={() => downloadDocument(doc.id)}
                disabled={viewLoading}
                className="btn-secondary"
              >
                {viewLoading
                  ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                  : <Download size={14} />
                }
                Télécharger
              </button>
            )}
            {doc?.secure_view_url && (
              <button
                type="button"
                onClick={() => openSecureDoc(doc.id)}
                disabled={viewLoading}
                className="btn-secondary"
              >
                {viewLoading
                  ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                  : <ExternalLink size={14} />
                }
                Ouvrir le fichier
              </button>
            )}
            {viewError && (
              <span className="text-xs text-red-600">{viewError}</span>
            )}
          </div>
        </div>

        {/* PDF error */}
        {pdfError && (
          <div className="alert alert-warning">
            <AlertTriangle size={13} className="shrink-0" />
            <span>{pdfError}</span>
          </div>
        )}

        {/* ── Rejection banner ── */}
        {isRejected && (
          <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-4">
            <ShieldAlert size={16} className="text-red-500 shrink-0 mt-0.5" />
            <div className="flex-1">
              <p className="text-sm font-semibold text-red-900">Document rejeté</p>
              <p className="text-xs text-red-700 mt-0.5">
                {doc?.reviewer_comment || doc?.decision_reason
                  || 'Consultez les règles non conformes ci-dessous pour corriger votre document.'}
              </p>
            </div>
            <button type="button" onClick={() => navigate('/documents')}
              className="shrink-0 flex items-center gap-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors">
              Re-soumettre
            </button>
          </div>
        )}

        {/* ── Approval banner ── */}
        {isApproved && (
          <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3">
            <ShieldCheck size={16} className="text-emerald-600 shrink-0" />
            <p className="text-sm font-semibold text-emerald-800">
              Document approuvé
              {doc?.approved_at ? ` le ${fmtShort(doc.approved_at)}` : ''}
              {doc?.approved_by ? ` par ${doc.approved_by}` : ''}
            </p>
          </div>
        )}

        {/* ── Main grid ── */}
        <div className="grid gap-5 lg:grid-cols-[1fr_320px]">

          {/* ── LEFT ── */}
          <div className="space-y-5">

            {/* Document info card */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Informations</h2>
                <StatusBadge status={doc?.status} />
              </div>
              <div className="card-body">
                {/* Pipeline */}
                <div className="mb-5">
                  <StatusPipeline status={doc?.status} />
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  {[
                    { icon: FileText,  label: 'Fichier',    value: fileName },
                    { icon: BookOpen,  label: 'Norme',      value: normeName },
                    { icon: User,      label: 'Soumis par', value: doc?.employee_username },
                    { icon: Calendar,  label: 'Date',       value: fmtShort(doc?.created_at) },
                    doc?.teamlead_username && { icon: User, label: 'Reviewer', value: doc.teamlead_username },
                    doc?.review_completed_at && { icon: Calendar, label: 'Révisé le', value: fmtShort(doc.review_completed_at) },
                  ].filter(Boolean).map(item => (
                    <div key={item.label} className="flex items-center gap-3">
                      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                        <item.icon size={13} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-2xs text-slate-400 uppercase tracking-wider">{item.label}</p>
                        <p className="text-sm font-medium text-slate-900 truncate">{item.value || '—'}</p>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Reviewer decision */}
                {(doc?.decision_reason || doc?.reviewer_comment) && (
                  <div className="mt-4 rounded-xl border border-slate-200 bg-slate-50 p-4 space-y-2">
                    <div className="flex items-center gap-2">
                      <MessageSquare size={13} className="text-slate-400" />
                      <p className="text-xs font-bold uppercase tracking-wider text-slate-400">Commentaire du reviewer</p>
                    </div>
                    {doc?.decision_reason && (
                      <p className="text-sm text-slate-700">{doc.decision_reason}</p>
                    )}
                    {doc?.reviewer_comment && doc.reviewer_comment !== doc?.decision_reason && (
                      <p className="text-xs text-slate-500 italic">{doc.reviewer_comment}</p>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Validations */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Résultats par règle</h2>
                <div className="flex items-center gap-2">
                  {validCount > 0   && <span className="badge badge-green"><CheckCircle2 size={10}/>{validCount} conforme{validCount > 1 ? 's' : ''}</span>}
                  {invalidCount > 0 && <span className="badge badge-red"><XCircle size={10}/>{invalidCount} non conforme{invalidCount > 1 ? 's' : ''}</span>}
                </div>
              </div>
              <div className="card-body space-y-2">
                {validations.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-8 text-center">
                    <Clock size={24} className="text-slate-300" />
                    <p className="text-sm text-slate-500">
                      {doc?.status === 'pending'
                        ? 'Votre document est en attente de révision. Les résultats apparaîtront ici après validation.'
                        : 'Aucun résultat de validation disponible.'}
                    </p>
                  </div>
                ) : (
                  <>
                    {/* Show invalid first */}
                    {[...validations].sort((a, b) => (a.is_valid === false ? -1 : 1)).map((v, i) => (
                      <ValidationRow key={v.id || i} v={v} />
                    ))}
                  </>
                )}
              </div>
            </div>
          </div>

          {/* ── RIGHT ── */}
          <div className="space-y-5">
            {/* Score */}
            {typeof doc?.compliance_score === 'number' && (
              <div className="card card-body">
                <ScoreRing score={doc.compliance_score} />
              </div>
            )}

            {/* Quick stats */}
            {validations.length > 0 && (
              <div className="card card-body space-y-3">
                <p className="text-sm font-semibold text-slate-900">Résumé</p>
                <div className="grid grid-cols-2 gap-2">
                  <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-3 text-center">
                    <p className="text-2xl font-bold text-emerald-600">{validCount}</p>
                    <p className="text-2xs text-slate-500 mt-0.5">Conformes</p>
                  </div>
                  <div className="rounded-xl bg-red-50 border border-red-100 p-3 text-center">
                    <p className="text-2xl font-bold text-red-600">{invalidCount}</p>
                    <p className="text-2xs text-slate-500 mt-0.5">Non conformes</p>
                  </div>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-emerald-500 transition-all duration-700"
                    style={{ width: `${validations.length > 0 ? (validCount / validations.length) * 100 : 0}%` }}
                  />
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="card card-body space-y-2">
              <p className="text-sm font-semibold text-slate-900">Actions</p>
              <button type="button" onClick={downloadPdf} disabled={pdfLoading}
                className="btn-secondary w-full justify-center">
                <Download size={14} /> Télécharger le rapport PDF
              </button>
              {doc?.secure_download_url && (
                <button
                  type="button"
                  onClick={() => downloadDocument(doc.id, doc.secure_download_url?.split('/').pop()?.replace('download', '') || 'document.pdf')}
                  disabled={viewLoading}
                  className="btn-secondary w-full justify-center"
                >
                  {viewLoading
                    ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                    : <Download size={14} />
                  }
                  Télécharger le document
                </button>
              )}
              {doc?.secure_view_url && (
                <button
                  type="button"
                  onClick={() => openSecureDoc(doc.id)}
                  disabled={viewLoading}
                  className="btn-secondary w-full justify-center"
                >
                  {viewLoading
                    ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
                    : <ExternalLink size={14} />
                  }
                  Ouvrir le document
                </button>
              )}
              {isRejected && (
                <button type="button" onClick={() => navigate('/documents')}
                  className="btn-primary w-full justify-center">
                  Re-soumettre un document corrigé
                </button>
              )}
            </div>

            {/* Phase 9 — Security Analysis Panel */}
            <DocumentSecurityPanel
              analysis={securityAnalysis}
              loading={securityLoading && !securityAnalysis}
              encrypted={doc?.encrypted}
              integrityStatus={doc?.integrity_status}
            />

          </div>
        </div>
      </div>
    </Layout>
  );
}
