import React, { useContext, useEffect, useMemo, useState, useCallback, useRef } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import UploadBox from './UploadBox';
import StatusBadge from './StatusBadge';
import EmptyState from './common/EmptyState';
import AnalyzeDocumentModal from './analysis/AnalyzeDocumentModal';
import DocumentSecurityPanel from './DocumentSecurityPanel';
import { ClassificationBadge } from './SecurityBadge';
import api from '../services/api';
import { useSecureDocumentView } from '../hooks/useSecureDocumentView';
import { useDocumentSecurity } from '../hooks/useDocumentSecurity';
import {
  FileText, Search, ChevronLeft, ChevronRight,
  ExternalLink, ClipboardCheck, SlidersHorizontal, X, ShieldAlert,
  Download, Brain, AlertTriangle, ChevronDown, ChevronUp,
  CheckCircle2, XCircle, Eye, Upload, RefreshCw,
} from 'lucide-react';

/* ─── helpers ──────────────────────────────────────────────────────────── */
const fmt = (d) => d ? new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short', year: 'numeric' }) : '—';
const statusLabels = { pending: 'En attente', reviewing: 'En révision', approved: 'Approuvé', rejected: 'Rejeté' };
const statusLabelsEN = { pending: 'Pending', reviewing: 'Reviewing', approved: 'Approved', rejected: 'Rejected' };

const parseError = (err) => {
  const data = err?.response?.data;
  if (!data) return 'Une erreur inattendue est survenue.';
  if (typeof data === 'string') return data;
  if (data.detail) return data.detail;
  if (data.file) return `Fichier : ${Array.isArray(data.file) ? data.file[0] : data.file}`;
  if (data.norme) return `Norme : ${Array.isArray(data.norme) ? data.norme[0] : data.norme}`;
  return 'Impossible de traiter la requête.';
};

/* ─── Skeleton row ─────────────────────────────────────────────────────── */
function SkeletonRow({ cols }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton h-4 rounded" style={{ width: `${55 + (i * 17) % 40}%` }} />
        </td>
      ))}
    </tr>
  );
}

/* ─── Stat card ────────────────────────────────────────────────────────── */
function StatCard({ label, value, color, loading, onClick, urgent }) {
  return (
    <div
      onClick={onClick}
      className={`kpi-card transition-all duration-150
        ${onClick ? 'cursor-pointer hover:shadow-card-hover hover:-translate-y-px' : ''}
        ${urgent ? 'ring-2 ring-red-300 ring-offset-1' : ''}
      `}
    >
      <p className="kpi-label">{label}</p>
      {loading
        ? <div className="skeleton h-8 w-12 mt-2 rounded" />
        : <p className={`text-3xl font-bold tabular-nums mt-2 ${color}`}>{value}</p>
      }
      {urgent && value > 0 && (
        <p className="text-2xs text-red-600 font-medium mt-1">Action requise →</p>
      )}
    </div>
  );
}

/* ─── Rejection feedback panel (Employee only) ─────────────────────────── */
function RejectionFeedback({ docId, onResubmit }) {
  const [validations, setValidations] = useState(null);
  const [loading, setLoading]         = useState(true);
  const [open, setOpen]               = useState(true);

  useEffect(() => {
    if (!docId) return;
    setLoading(true);
    api.get(`/documents/${docId}/validations/`)
      .then(res => {
        const list = Array.isArray(res.data) ? res.data : [];
        setValidations(list);
      })
      .catch(() => setValidations([]))
      .finally(() => setLoading(false));
  }, [docId]);

  const invalid = useMemo(
    () => (validations || []).filter(v => v.is_valid === false),
    [validations]
  );

  if (!loading && invalid.length === 0) return null;

  return (
    <div className="rounded-xl border border-red-200 bg-red-50 overflow-hidden animate-slide-up">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-red-100/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <AlertTriangle size={15} className="text-red-500 shrink-0" />
          <span className="text-sm font-semibold text-red-900">
            {loading ? 'Chargement du feedback…' : `${invalid.length} règle${invalid.length > 1 ? 's' : ''} non conforme${invalid.length > 1 ? 's' : ''} détectée${invalid.length > 1 ? 's' : ''}`}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); onResubmit(); }}
            className="flex items-center gap-1 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-red-700 transition-colors"
          >
            <Upload size={11} /> Re-soumettre
          </button>
          {open ? <ChevronUp size={14} className="text-red-400" /> : <ChevronDown size={14} className="text-red-400" />}
        </div>
      </button>

      {open && (
        <div className="border-t border-red-200 px-4 pb-4 pt-3 space-y-2">
          {loading ? (
            <div className="space-y-2">{[1,2].map(i => <div key={i} className="skeleton h-12 rounded-lg" />)}</div>
          ) : (
            invalid.map((v, i) => (
              <div key={v.id || i} className="rounded-lg border border-red-200 bg-white p-3 space-y-1.5">
                <div className="flex items-start gap-2">
                  <XCircle size={13} className="text-red-500 shrink-0 mt-0.5" />
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-semibold text-slate-900">
                      {v.rule?.title || `Règle #${v.rule}`}
                    </p>
                    {v.rule?.description && (
                      <p className="text-xs text-slate-500 mt-0.5">{v.rule.description}</p>
                    )}
                  </div>
                </div>
                {(v.evidence_text || v.reviewer_comment || v.decision_reason) && (
                  <div className="pl-5">
                    {v.evidence_text && (
                      <div className="rounded-md bg-slate-50 px-2.5 py-1.5 mt-1">
                        <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-0.5">Commentaire du reviewer</p>
                        <p className="text-xs text-slate-700">{v.evidence_text}</p>
                      </div>
                    )}
                    {(v.reviewer_comment || v.decision_reason) && (
                      <div className="rounded-md bg-amber-50 border border-amber-100 px-2.5 py-1.5 mt-1">
                        <p className="text-2xs font-bold uppercase tracking-wider text-amber-600 mb-0.5">Action recommandée</p>
                        <p className="text-xs text-amber-800">{v.reviewer_comment || v.decision_reason}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Score bar inline ─────────────────────────────────────────────────── */
function ScoreBar({ score }) {
  if (typeof score !== 'number') return <span className="text-xs text-slate-400">—</span>;
  const color = score >= 80 ? 'bg-emerald-500' : score >= 60 ? 'bg-amber-500' : 'bg-red-500';
  const textColor = score >= 80 ? 'text-emerald-600' : score >= 60 ? 'text-amber-600' : 'text-red-600';
  return (
    <div className="flex items-center gap-2">
      <div className="w-14 h-1.5 bg-slate-100 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
      <span className={`text-xs font-bold tabular-nums ${textColor}`}>{score}%</span>
    </div>
  );
}

/* ─── PDF download button ──────────────────────────────────────────────── */
function PdfDownloadBtn({ docId }) {
  const [loading, setLoading] = useState(false);

  const handleDownload = async () => {
    setLoading(true);
    try {
      const res = await api.get(`/documents/${docId}/report/`, { responseType: 'blob' });
      const url = URL.createObjectURL(res.data);
      const a = document.createElement('a');
      a.href = url;
      a.download = `compliance-report-${docId}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* silently ignore — the endpoint may return 404 if no report yet */
    } finally {
      setLoading(false);
    }
  };

  return (
    <button
      type="button"
      onClick={handleDownload}
      disabled={loading}
      className="btn-icon-sm text-slate-500 hover:bg-slate-100 hover:text-slate-700 disabled:opacity-40"
      title="Télécharger le rapport PDF"
    >
      {loading
        ? <span className="h-3 w-3 animate-spin rounded-full border-2 border-slate-300 border-t-slate-600" />
        : <Download size={13} />
      }
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   DOCUMENTS PAGE
═══════════════════════════════════════════════════════════════════════════ */
const Documents = () => {
  const { user }                        = useContext(UserContext);
  const navigate                        = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  const isEmployee = user?.role === 'EMPLOYEE';

  const [documents,     setDocuments]     = useState([]);
  const [normes,        setNormes]        = useState([]);
  const [loading,       setLoading]       = useState(true);
  const [uploading,     setUploading]     = useState(false);
  const [uploadProgress,setUploadProgress]= useState(0);
  const [selectedNorme, setSelectedNorme] = useState('');
  const [search,        setSearch]        = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page,          setPage]          = useState(1);
  const [pageSize]                        = useState(20);
  const [total,         setTotal]         = useState(0);
  const [file,          setFile]          = useState(null);
  const [counts,        setCounts]        = useState({ total:0, approved:0, rejected:0, pending:0, reviewing:0 });
  const [statusFilter,  setStatusFilter]  = useState('');
  const [sortBy,        setSortBy]        = useState('newest');
  const [message,       setMessage]       = useState('');
  const [error,         setError]         = useState('');
  const [updatingId,    setUpdatingId]    = useState(null);
  const [showUpload,    setShowUpload]    = useState(false);
  const [analyzeOpen,   setAnalyzeOpen]   = useState(false);
  const [expandedReject,setExpandedReject]= useState(null); // docId whose feedback is open

  const { openDocument: openSecureDoc, downloadDocument, loading: viewLoading, error: viewError } = useSecureDocumentView();

  // Phase 9 — track the last uploaded document to show security analysis
  const [lastUploadedId, setLastUploadedId] = useState(null);
  const [showSecurityPanel, setShowSecurityPanel] = useState(false);
  const { analysis: uploadedDocSecurity, loading: securityLoading } = useDocumentSecurity({
    docId: lastUploadedId,
    autoFetch: !!lastUploadedId,
    maxAttempts: 12,
    interval: 3000,
  });

  /* Read ?status= and ?search= from URL (from Dashboard KPI clicks / Topbar search) */
  useEffect(() => {
    const s = searchParams.get('status');
    const q = searchParams.get('search');
    if (s && Object.keys(statusLabelsEN).includes(s)) setStatusFilter(s);
    if (q) setSearch(q);
    if (s || q) setSearchParams({}, { replace: true });
  }, []); // eslint-disable-line

  /* Debounce search */
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(t);
  }, [search]);

  /* Reset page on filter change */
  useEffect(() => { setPage(1); }, [debouncedSearch, selectedNorme, statusFilter, sortBy]);

  /* Fetch counts via optimised endpoint */
  const fetchCounts = useCallback(async () => {
    try {
      const res = await api.get('/documents/stats/');
      if (res.data) setCounts(res.data);
    } catch {
      // fallback: 5 separate calls (legacy)
      try {
        const base = await api.get('/documents/', { params: { page_size: 1 } });
        const tot = base.data?.count ?? 0;
        const statuses = ['approved','rejected','pending','reviewing'];
        const results = await Promise.allSettled(
          statuses.map(s => api.get('/documents/', { params: { page_size: 1, status: s } }))
        );
        const map = { total: tot };
        statuses.forEach((s, i) => {
          map[s] = results[i].status === 'fulfilled' ? (results[i].value?.data?.count ?? 0) : 0;
        });
        setCounts(map);
      } catch {}
    }
  }, []);

  useEffect(() => { fetchCounts(); }, [fetchCounts]);

  /* Fetch documents */
  const fetchDocuments = useCallback(async (opts = {}) => {
    setLoading(true);
    try {
      const params = { page: opts.page || page, page_size: opts.pageSize || pageSize };
      if (debouncedSearch) params.search   = debouncedSearch;
      if (selectedNorme)   params.norme    = selectedNorme;
      if (statusFilter)    params.status   = statusFilter;
      const orderMap = { newest: '-created_at', oldest: 'created_at', highest: '-compliance_score', lowest: 'compliance_score' };
      if (orderMap[sortBy]) params.ordering = orderMap[sortBy];

      const res = await api.get('/documents/', { params });
      if (Array.isArray(res.data?.results)) {
        setDocuments(res.data.results);
        setTotal(res.data.count || 0);
      } else if (Array.isArray(res.data)) {
        setDocuments(res.data);
        setTotal(res.data.length);
      } else {
        setDocuments([]); setTotal(0);
      }
    } catch { setDocuments([]); setTotal(0); }
    finally { setLoading(false); }
  }, [page, pageSize, debouncedSearch, selectedNorme, statusFilter, sortBy]);

  useEffect(() => { fetchDocuments({ page, pageSize }); }, [fetchDocuments, page, pageSize]);

  /* Fetch normes */
  useEffect(() => {
    api.get('/normes/').then(res => {
      const data = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setNormes(data);
    }).catch(() => {});
  }, []);

  const normeMap = useMemo(
    () => Object.fromEntries(normes.map(n => [n.id, n.name])),
    [normes]
  );

  /* Upload with real progress */
  const handleUpload = async (e) => {
    e.preventDefault();
    setError(''); setMessage('');
    if (!selectedNorme || !file) {
      setError('Veuillez sélectionner une norme et un fichier.');
      return;
    }
    setUploading(true);
    setUploadProgress(0);
    const payload = new FormData();
    payload.append('norme', selectedNorme);
    payload.append('file', file);
    try {
      const res = await api.post('/documents/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (e.total) setUploadProgress(Math.round((e.loaded * 100) / e.total));
        },
      });
      // Phase 9 — capture uploaded doc ID to poll security analysis
      const newDocId = res.data?.id;
      if (newDocId) {
        setLastUploadedId(newDocId);
        setShowSecurityPanel(true);
      }
      setMessage('Document soumis avec succès. Il est maintenant en attente de validation.');
      setSelectedNorme(''); setFile(null);
      setShowUpload(false); setUploadProgress(0);
      fetchDocuments(); fetchCounts();
    } catch (err) {
      setError(parseError(err));
      setUploadProgress(0);
    } finally { setUploading(false); }
  };

  /* Update status (Admin/TeamLead only) */
  const updateStatus = async (docId, status) => {
    setError(''); setMessage(''); setUpdatingId(docId);
    try {
      const res = await api.patch(`/documents/${docId}/status/`, { status });
      const saved = res.data?.document?.status || res.data?.status || status;
      setDocuments(prev => prev.map(d =>
        d.id === docId ? { ...d, status: saved, teamlead_username: res.data?.document?.teamlead_username ?? d.teamlead_username } : d
      ));
      setMessage(`Statut mis à jour : "${statusLabelsEN[saved] || saved}".`);
      fetchCounts();
    } catch (err) {
      setError(parseError(err));
    } finally { setUpdatingId(null); }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const hasFilters = !!(search || statusFilter || selectedNorme);

  /* ── EMPLOYEE TABLE COLUMNS (simplified) ── */
  const employeeCols = ['#', 'Fichier', 'Norme', 'Score', 'Statut', 'Date', 'Actions'];
  /* ── ADMIN/TL TABLE COLUMNS ── */
  const adminCols    = ['#', 'Fichier', 'Norme', 'Employé', 'Score', 'Statut', 'Team Lead', 'Date', 'Actions'];

  return (
    <Layout>
      <div className="page-container">

        {/* ── PAGE HEADER ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Workflow de conformité</p>
            <h1 className="page-title mt-1">
              {isEmployee ? 'Mes documents' : 'Documents'}
            </h1>
            <p className="page-subtitle">
              {isEmployee
                ? 'Soumettez vos preuves de conformité et suivez leur état de validation.'
                : 'Submit evidence against a standard and track review status.'}
            </p>
          </div>
          {isEmployee && (
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setAnalyzeOpen(true)}
                className="btn-secondary"
                title="Analyser un document avec l'IA avant soumission"
              >
                <Brain size={15} />
                Analyser avec l'IA
              </button>
              <button
                type="button"
                onClick={() => setShowUpload(v => !v)}
                className={showUpload ? 'btn-secondary' : 'btn-primary'}
              >
                <Upload size={15} />
                {showUpload ? 'Annuler' : 'Soumettre un document'}
              </button>
            </div>
          )}
        </div>

        {/* ── ALERTS ── */}
        {message && (
          <div className="alert alert-success">
            <CheckCircle2 size={14} className="shrink-0" />
            <span>{message}</span>
            <button type="button" onClick={() => setMessage('')} className="ml-auto"><X size={14} /></button>
          </div>
        )}

        {/* ── Phase 9: Security Analysis post-upload ── */}
        {isEmployee && showSecurityPanel && lastUploadedId && (
          <div className="animate-slide-up">
            <div className="flex items-center justify-between mb-2">
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                Analyse de sécurité du document soumis
              </p>
              <button
                type="button"
                onClick={() => { setShowSecurityPanel(false); setLastUploadedId(null); }}
                className="text-slate-400 hover:text-slate-600"
              >
                <X size={13} />
              </button>
            </div>
            <DocumentSecurityPanel
              analysis={uploadedDocSecurity}
              loading={securityLoading && !uploadedDocSecurity}
              encrypted={uploadedDocSecurity?.document
                ? undefined  // fetched from doc directly in detail view
                : false}
              integrityStatus={null}
            />
          </div>
        )}
        {error && (
          <div className="alert alert-danger">
            <AlertTriangle size={14} className="shrink-0" />
            <span>{error}</span>
            <button type="button" onClick={() => setError('')} className="ml-auto"><X size={14} /></button>
          </div>
        )}

        {/* ── UPLOAD PANEL (Employee) ── */}
        {isEmployee && showUpload && (
          <div className="card animate-slide-up">
            <div className="card-header">
              <h2 className="card-title">Soumettre un document</h2>
              <button type="button" onClick={() => setShowUpload(false)}
                className="btn-icon-sm text-slate-400 hover:text-slate-600">
                <X size={14} />
              </button>
            </div>
            <div className="card-body">
              <UploadBox
                normes={normes}
                selectedNorme={selectedNorme}
                onNormeChange={setSelectedNorme}
                file={file}
                onFileChange={setFile}
                onFileRemove={() => setFile(null)}
                uploading={uploading}
                uploadProgress={uploadProgress}
                error={error}
                onError={setError}
                onSubmit={handleUpload}
              />
            </div>
          </div>
        )}

        {/* ── INFO BANNER (Admin/TL) ── */}
        {!isEmployee && (
          <div className="alert alert-info">
            <FileText size={14} className="shrink-0" />
            <span>Seuls les employés peuvent soumettre des documents. Les Admins et Team Leads peuvent réviser et mettre à jour les statuts.</span>
          </div>
        )}

        {/* ── KPI STATS ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label={isEmployee ? 'Total' : 'Total'}        value={counts.total}     color="text-slate-900"   loading={loading} onClick={() => { setStatusFilter(''); }} />
          <StatCard label="Approuvés"  value={counts.approved}  color="text-emerald-600" loading={loading} onClick={() => setStatusFilter('approved')} />
          <StatCard label="En révision"value={counts.reviewing} color="text-sky-600"     loading={loading} onClick={() => setStatusFilter('reviewing')} />
          <StatCard label="En attente" value={counts.pending}   color="text-amber-600"   loading={loading} onClick={() => setStatusFilter('pending')} />
          <StatCard label="Rejetés"    value={counts.rejected}  color="text-red-600"     loading={loading}
            urgent={isEmployee && counts.rejected > 0}
            onClick={() => setStatusFilter('rejected')} />
        </div>

        {/* ── FILTERS ── */}
        <div className="card">
          <div className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder={isEmployee ? 'Rechercher par nom de fichier, norme, ID…' : 'Rechercher par nom, employé, norme, ID…'}
                className="form-input pl-9"
              />
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                <SlidersHorizontal size={13} />
                <span>Filtres :</span>
              </div>
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className="form-select w-auto text-xs py-1.5">
                <option value="">Tous les statuts</option>
                {Object.entries(statusLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <select value={selectedNorme} onChange={e => setSelectedNorme(e.target.value)} className="form-select w-auto text-xs py-1.5">
                <option value="">Toutes les normes</option>
                {normes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
              <select value={sortBy} onChange={e => setSortBy(e.target.value)} className="form-select w-auto text-xs py-1.5">
                <option value="newest">Plus récents</option>
                <option value="oldest">Plus anciens</option>
                <option value="highest">Score le plus élevé</option>
                <option value="lowest">Score le plus bas</option>
              </select>
              {hasFilters && (
                <button type="button" onClick={() => { setSearch(''); setStatusFilter(''); setSelectedNorme(''); }}
                  className="btn-ghost btn-sm text-slate-500">
                  <X size={12} /> Effacer
                </button>
              )}
              <button type="button" onClick={() => { fetchDocuments(); fetchCounts(); }}
                className="btn-icon-sm text-slate-400 hover:text-slate-700 border border-slate-200" title="Rafraîchir">
                <RefreshCw size={12} />
              </button>
            </div>
          </div>

          {/* ── TABLE ── */}
          <div className="overflow-x-auto border-t border-slate-100">
            <table className="table-enterprise">
              <thead>
                <tr>
                  {(isEmployee ? employeeCols : adminCols).map(h => <th key={h}>{h}</th>)}
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [1,2,3,4,5].map(i => <SkeletonRow key={i} cols={isEmployee ? 7 : 9} />)
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={isEmployee ? 7 : 9} className="px-4 py-10">
                      {isEmployee && !hasFilters ? (
                        <div className="flex flex-col items-center gap-3 py-6">
                          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100">
                            <FileText size={24} className="text-slate-300" />
                          </div>
                          <p className="text-base font-semibold text-slate-700">Aucun document soumis</p>
                          <p className="text-sm text-slate-500 max-w-xs text-center">
                            Commencez par soumettre votre premier document de conformité.
                          </p>
                          <button type="button" onClick={() => setShowUpload(true)}
                            className="btn-primary mt-1">
                            <Upload size={14} /> Soumettre un document
                          </button>
                        </div>
                      ) : (
                        <EmptyState icon="search" title="Aucun document trouvé"
                          description="Modifiez les filtres ou soumettez un nouveau document." />
                      )}
                    </td>
                  </tr>
                ) : (
                  documents.map(doc => (
                    <React.Fragment key={doc.id}>
                      <tr className={doc.status === 'rejected' && isEmployee ? 'bg-red-50/30' : ''}>
                        <td>
                          <span className="font-mono text-xs text-slate-500">#{doc.id}</span>
                        </td>
                        <td>
                          <div className="flex items-center gap-2">
                            <FileText size={13} className={`shrink-0
                              ${doc.status === 'approved' ? 'text-emerald-500' :
                                doc.status === 'rejected' ? 'text-red-500' :
                                doc.status === 'reviewing' ? 'text-sky-500' : 'text-amber-500'}`}
                            />
                            <button
                              type="button"
                              onClick={() => navigate(`/documents/${doc.id}`)}
                              className="text-sm font-medium text-slate-800 max-w-[160px] truncate hover:text-brand-600 transition-colors text-left"
                              title="Voir les détails"
                            >
                              {doc.file ? doc.file.split('/').pop() : `Document #${doc.id}`}
                            </button>
                          </div>
                        </td>
                        <td>
                          <span className="text-xs font-medium text-slate-600">
                            {normeMap[doc.norme] || `#${doc.norme}`}
                          </span>
                          {/* Phase 9 — integrity + encryption badges (inline, compact) */}
                          {(doc.integrity_status || doc.encrypted) && (
                            <div className="flex flex-wrap gap-1 mt-1">
                              {doc.encrypted && (
                                <span className="inline-flex items-center gap-0.5 rounded-full border border-violet-200 bg-violet-50 px-1.5 py-0.5 text-[9px] font-semibold text-violet-700">
                                  🔒 Chiffré
                                </span>
                              )}
                              {doc.integrity_status === 'VERIFIED' && (
                                <span className="inline-flex items-center gap-0.5 rounded-full border border-emerald-200 bg-emerald-50 px-1.5 py-0.5 text-[9px] font-semibold text-emerald-700">
                                  ✓ Intégrité
                                </span>
                              )}
                            </div>
                          )}
                        </td>
                        {/* Employee col — hidden for employee */}
                        {!isEmployee && (
                          <td className="text-sm">{doc.employee_username || '—'}</td>
                        )}
                        <td><ScoreBar score={doc.compliance_score} /></td>
                        <td>
                          {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') ? (
                            <select
                              value={doc.status}
                              onChange={e => updateStatus(doc.id, e.target.value)}
                              disabled={updatingId === doc.id}
                              className="form-select text-xs py-1 w-32"
                            >
                              {Object.entries(statusLabelsEN).map(([k,v]) => (
                                <option key={k} value={k}>{v}</option>
                              ))}
                            </select>
                          ) : (
                            <div className="flex items-center gap-2">
                              <StatusBadge status={doc.status} />
                              {doc.status === 'rejected' && (
                                <button
                                  type="button"
                                  onClick={() => setExpandedReject(expandedReject === doc.id ? null : doc.id)}
                                  className="text-2xs font-medium text-red-600 hover:text-red-800 transition-colors"
                                >
                                  {expandedReject === doc.id ? 'Masquer' : 'Voir pourquoi'}
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                        {/* TeamLead col — hidden for employee */}
                        {!isEmployee && (
                          <td className="text-sm text-slate-500">{doc.teamlead_username || '—'}</td>
                        )}
                        <td className="text-xs text-slate-500">{fmt(doc.created_at)}</td>
                        <td>
                          <div className="flex items-center gap-1">
                            {isEmployee && <PdfDownloadBtn docId={doc.id} />}
                            {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') && (
                              <>
                                <Link to={`/validations?document=${doc.id}`}
                                  className="btn-icon-sm text-brand-500 hover:bg-brand-50 hover:text-brand-700"
                                  title="Valider le document">
                                  <ClipboardCheck size={13} />
                                </Link>
                                <Link to="/document-security"
                                  className="btn-icon-sm text-amber-500 hover:bg-amber-50 hover:text-amber-700"
                                  title="Analyse sécurité">
                                  <ShieldAlert size={13} />
                                </Link>
                              </>
                            )}
                            <button
                              type="button"
                              onClick={() => navigate(`/documents/${doc.id}`)}
                              className="btn-icon-sm text-slate-500 hover:bg-slate-100"
                              title="Voir les détails"
                            >
                              <Eye size={13} />
                            </button>
                            {doc.secure_view_url && (
                              <button
                                type="button"
                                onClick={() => openSecureDoc(doc.id)}
                                disabled={viewLoading}
                                className="btn-icon-sm text-slate-500 hover:bg-slate-100"
                                title="Ouvrir le fichier"
                              >
                                <ExternalLink size={13} />
                              </button>
                            )}
                            {doc.secure_download_url && (
                              <button
                                type="button"
                                onClick={() => downloadDocument(doc.id)}
                                disabled={viewLoading}
                                className="btn-icon-sm text-slate-500 hover:bg-slate-100"
                                title="Télécharger le document"
                              >
                                <Download size={13} />
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>

                      {/* Inline rejection feedback for Employee */}
                      {isEmployee && expandedReject === doc.id && (
                        <tr>
                          <td colSpan={7} className="px-4 py-3 bg-red-50/20">
                            <RejectionFeedback
                              docId={doc.id}
                              onResubmit={() => {
                                setExpandedReject(null);
                                setShowUpload(true);
                                window.scrollTo({ top: 0, behavior: 'smooth' });
                              }}
                            />
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* ── PAGINATION ── */}
          {total > pageSize && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <span className="text-xs text-slate-500">
                {(page-1)*pageSize+1}–{Math.min(page*pageSize, total)} sur <strong>{total}</strong>
              </span>
              <div className="flex items-center gap-1">
                <button onClick={() => setPage(p => Math.max(1, p-1))} disabled={page === 1}
                  className="btn-icon-sm border border-slate-200 disabled:opacity-40">
                  <ChevronLeft size={13} />
                </button>
                <span className="px-3 text-xs font-medium text-slate-600">Page {page} / {totalPages}</span>
                <button onClick={() => setPage(p => Math.min(totalPages, p+1))} disabled={page >= totalPages}
                  className="btn-icon-sm border border-slate-200 disabled:opacity-40">
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>

        {/* ── AI ANALYSIS MODAL (Employee) ── */}
        {isEmployee && (
          <AnalyzeDocumentModal
            isOpen={analyzeOpen}
            onClose={() => setAnalyzeOpen(false)}
            norms={normes}
            defaultNorm={normes[0]?.id ? String(normes[0].id) : ''}
          />
        )}
      </div>
    </Layout>
  );
};

export default Documents;
