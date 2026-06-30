import React, { useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import UploadBox from './UploadBox';
import StatusBadge from './StatusBadge';
import EmptyState from './common/EmptyState';
import api from '../services/api';
import {
  FileText, Search, ChevronLeft, ChevronRight,
  ExternalLink, ClipboardCheck, SlidersHorizontal, X, ShieldAlert,
} from 'lucide-react';

/* ─── helpers ──────────────────────────────────────────────────────────── */
const fmt = (d) => d ? new Date(d).toLocaleDateString('en-GB', { day:'2-digit', month:'short', year:'numeric' }) : '—';
const statusLabels = { pending: 'Pending', reviewing: 'Reviewing', approved: 'Approved', rejected: 'Rejected' };

/* ─── Skeleton row ─────────────────────────────────────────────────────── */
function SkeletonRow() {
  return (
    <tr>
      {[1,2,3,4,5,6,7].map(i => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton h-4 rounded" style={{ width: `${60 + Math.random()*30}%` }} />
        </td>
      ))}
    </tr>
  );
}

/* ─── Stat card ────────────────────────────────────────────────────────── */
function StatCard({ label, value, color, loading }) {
  return (
    <div className="kpi-card">
      <p className="kpi-label">{label}</p>
      {loading
        ? <div className="skeleton h-8 w-12 mt-2 rounded" />
        : <p className={`text-3xl font-bold tabular-nums mt-2 ${color}`}>{value}</p>
      }
    </div>
  );
}

/* ─── Documents page ───────────────────────────────────────────────────── */
const Documents = () => {
  const { user } = useContext(UserContext);
  const [documents,    setDocuments]    = useState([]);
  const [normes,       setNormes]       = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [uploading,    setUploading]    = useState(false);
  const [selectedNorme,setSelectedNorme]= useState('');
  const [search,       setSearch]       = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page,         setPage]         = useState(1);
  const [pageSize]                      = useState(20);
  const [total,        setTotal]        = useState(0);
  const [file,         setFile]         = useState(null);
  const [counts,       setCounts]       = useState({ total:0, approved:0, rejected:0, pending:0, reviewing:0 });
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy,       setSortBy]       = useState('newest');
  const [message,      setMessage]      = useState('');
  const [error,        setError]        = useState('');
  const [updatingId,   setUpdatingId]   = useState(null);
  const [showUpload,   setShowUpload]   = useState(false);

  /* Debounce search */
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(t);
  }, [search]);

  /* Reset page on filter change */
  useEffect(() => { setPage(1); }, [debouncedSearch, selectedNorme, statusFilter, sortBy]);

  /* Fetch counts */
  const fetchCounts = useCallback(async () => {
    try {
      const base = await api.get('/documents/', { params: { page_size: 1 } });
      const total = base.data?.count ?? 0;
      const statuses = ['approved','rejected','pending','reviewing'];
      const results = await Promise.allSettled(
        statuses.map(s => api.get('/documents/', { params: { page_size: 1, status: s } }))
      );
      const map = { total };
      statuses.forEach((s, i) => {
        map[s] = results[i].status === 'fulfilled' ? (results[i].value?.data?.count ?? 0) : 0;
      });
      setCounts(map);
    } catch {}
  }, []);

  useEffect(() => { fetchCounts(); }, [fetchCounts, debouncedSearch, selectedNorme, statusFilter]);

  /* Fetch documents */
  const fetchDocuments = useCallback(async (opts = {}) => {
    setLoading(true);
    try {
      const params = { page: opts.page || page, page_size: opts.pageSize || pageSize };
      if (debouncedSearch)  params.search   = debouncedSearch;
      if (selectedNorme)    params.norme    = selectedNorme;
      if (statusFilter)     params.status   = statusFilter;
      if (sortBy === 'oldest')  params.ordering = 'created_at';
      if (sortBy === 'newest')  params.ordering = '-created_at';
      if (sortBy === 'highest') params.ordering = '-compliance_score';
      if (sortBy === 'lowest')  params.ordering = 'compliance_score';

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

  /* Upload */
  const handleUpload = async (e) => {
    e.preventDefault();
    setError(''); setMessage('');
    if (!selectedNorme || !file) { setError('Please select a standard and a document file.'); return; }
    setUploading(true);
    const payload = new FormData();
    payload.append('norme', selectedNorme);
    payload.append('file', file);
    try {
      await api.post('/documents/', payload, { headers: { 'Content-Type': 'multipart/form-data' } });
      setMessage('Document uploaded successfully.');
      setSelectedNorme(''); setFile(null);
      setShowUpload(false);
      fetchDocuments(); fetchCounts();
    } catch (err) {
      setError(err?.response?.data?.detail || err?.response?.data || 'Unable to upload document.');
    } finally { setUploading(false); }
  };

  /* Update status */
  const updateStatus = async (docId, status) => {
    setError(''); setMessage(''); setUpdatingId(docId);
    try {
      const res = await api.patch(`/documents/${docId}/status/`, { status });
      const saved = res.data?.document?.status || res.data?.status || status;
      setDocuments(prev => prev.map(d => d.id === docId ? { ...d, status: saved, teamlead_username: res.data?.document?.teamlead_username ?? d.teamlead_username } : d));
      setMessage(`Status updated to "${statusLabels[saved] || saved}".`);
      fetchCounts();
    } catch (err) {
      setError(err?.response?.data?.detail || 'Unable to update status.');
    } finally { setUpdatingId(null); }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <Layout>
      <div className="page-container">

        {/* ── Page header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Compliance Workflow</p>
            <h1 className="page-title mt-1">Documents</h1>
            <p className="page-subtitle">Submit evidence against a standard and track review status.</p>
          </div>
          {user?.role === 'EMPLOYEE' && (
            <button
              type="button"
              onClick={() => setShowUpload(v => !v)}
              className={showUpload ? 'btn-secondary' : 'btn-primary'}
            >
              <FileText size={15} />
              {showUpload ? 'Cancel Upload' : 'Upload Document'}
            </button>
          )}
        </div>

        {/* ── Alerts ── */}
        {message && (
          <div className="alert alert-success">
            <span>{message}</span>
            <button type="button" onClick={() => setMessage('')} className="ml-auto"><X size={14} /></button>
          </div>
        )}
        {error && (
          <div className="alert alert-danger">
            <span>{typeof error === 'string' ? error : JSON.stringify(error)}</span>
            <button type="button" onClick={() => setError('')} className="ml-auto"><X size={14} /></button>
          </div>
        )}

        {/* ── Upload panel ── */}
        {user?.role === 'EMPLOYEE' && showUpload && (
          <div className="card animate-slide-up">
            <div className="card-header">
              <h2 className="card-title">Upload Document</h2>
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
                error={error}
                onError={setError}
                onSubmit={handleUpload}
              />
            </div>
          </div>
        )}

        {user?.role !== 'EMPLOYEE' && (
          <div className="alert alert-info">
            <FileText size={14} className="shrink-0" />
            <span>Only employees may submit documents. Admins and team leads can review and update statuses below.</span>
          </div>
        )}

        {/* ── KPI stats ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard label="Total"     value={counts.total}     color="text-slate-900"   loading={loading} />
          <StatCard label="Approved"  value={counts.approved}  color="text-emerald-600" loading={loading} />
          <StatCard label="Reviewing" value={counts.reviewing} color="text-sky-600"     loading={loading} />
          <StatCard label="Pending"   value={counts.pending}   color="text-amber-600"   loading={loading} />
          <StatCard label="Rejected"  value={counts.rejected}  color="text-red-600"     loading={loading} />
        </div>

        {/* ── Filters ── */}
        <div className="card">
          <div className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            {/* Search */}
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                type="search"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search filename, employee, norme, ID…"
                className="form-input pl-9"
              />
            </div>

            {/* Filters row */}
            <div className="flex items-center gap-2 flex-wrap">
              <div className="flex items-center gap-1 text-xs text-slate-500 font-medium">
                <SlidersHorizontal size={13} />
                <span>Filter:</span>
              </div>
              <select
                value={statusFilter}
                onChange={e => setStatusFilter(e.target.value)}
                className="form-select w-auto text-xs py-1.5"
              >
                <option value="">All statuses</option>
                {Object.entries(statusLabels).map(([k,v]) => <option key={k} value={k}>{v}</option>)}
              </select>
              <select
                value={selectedNorme}
                onChange={e => setSelectedNorme(e.target.value)}
                className="form-select w-auto text-xs py-1.5"
              >
                <option value="">All standards</option>
                {normes.map(n => <option key={n.id} value={n.id}>{n.name}</option>)}
              </select>
              <select
                value={sortBy}
                onChange={e => setSortBy(e.target.value)}
                className="form-select w-auto text-xs py-1.5"
              >
                <option value="newest">Newest first</option>
                <option value="oldest">Oldest first</option>
                <option value="highest">Highest compliance</option>
                <option value="lowest">Lowest compliance</option>
              </select>
              {(search || statusFilter || selectedNorme) && (
                <button
                  type="button"
                  onClick={() => { setSearch(''); setStatusFilter(''); setSelectedNorme(''); }}
                  className="btn-ghost btn-sm text-slate-500"
                >
                  <X size={12} /> Clear
                </button>
              )}
            </div>
          </div>

          {/* ── Table ── */}
          <div className="overflow-x-auto border-t border-slate-100">
            <table className="table-enterprise">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Filename</th>
                  <th>Standard</th>
                  <th>Employee</th>
                  <th>Score</th>
                  <th>Status</th>
                  <th>Team Lead</th>
                  <th>Created</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [1,2,3,4,5].map(i => <SkeletonRow key={i} />)
                ) : documents.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-10">
                      <EmptyState
                        icon="search"
                        title="No documents found"
                        description="Try adjusting the filters or upload a new document."
                      />
                    </td>
                  </tr>
                ) : (
                  documents.map(doc => (
                    <tr key={doc.id}>
                      <td>
                        <span className="font-mono text-xs text-slate-500">#{doc.id}</span>
                      </td>
                      <td>
                        <div className="flex items-center gap-2">
                          <FileText size={13} className="text-slate-400 shrink-0" />
                          <span className="text-sm font-medium text-slate-800 max-w-[180px] truncate">
                            {doc.file ? doc.file.split('/').pop() : (doc.file_url || '—')}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="text-xs font-medium text-slate-600">
                          {normeMap[doc.norme] || `#${doc.norme}`}
                        </span>
                      </td>
                      <td className="text-sm">{doc.employee_username || '—'}</td>
                      <td>
                        {typeof doc.compliance_score === 'number' ? (
                          <div className="flex items-center gap-2">
                            <div className="w-16 h-1.5 bg-slate-100 rounded-full overflow-hidden">
                              <div
                                className={`h-full rounded-full ${doc.compliance_score >= 80 ? 'bg-emerald-500' : doc.compliance_score >= 60 ? 'bg-amber-500' : 'bg-red-500'}`}
                                style={{ width: `${doc.compliance_score}%` }}
                              />
                            </div>
                            <span className={`text-xs font-bold tabular-nums ${doc.compliance_score >= 80 ? 'text-emerald-600' : doc.compliance_score >= 60 ? 'text-amber-600' : 'text-red-600'}`}>
                              {doc.compliance_score}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">—</span>
                        )}
                      </td>
                      <td>
                        {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') ? (
                          <select
                            value={doc.status}
                            onChange={e => updateStatus(doc.id, e.target.value)}
                            disabled={updatingId === doc.id}
                            className="form-select text-xs py-1 w-32"
                          >
                            {Object.entries(statusLabels).map(([k,v]) => (
                              <option key={k} value={k}>{v}</option>
                            ))}
                          </select>
                        ) : (
                          <StatusBadge status={doc.status} />
                        )}
                      </td>
                      <td className="text-sm text-slate-500">{doc.teamlead_username || '—'}</td>
                      <td className="text-xs text-slate-500">{fmt(doc.created_at)}</td>
                      <td>
                        <div className="flex items-center gap-1">
                          {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') && (
                            <Link
                              to={`/validations?document=${doc.id}`}
                              className="btn-icon-sm text-brand-500 hover:bg-brand-50 hover:text-brand-700"
                              title="Review validations"
                            >
                              <ClipboardCheck size={13} />
                            </Link>
                          )}
                          {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') && (
                            <Link
                              to={`/document-security`}
                              className="btn-icon-sm text-amber-500 hover:bg-amber-50 hover:text-amber-700"
                              title="View security analysis"
                            >
                              <ShieldAlert size={13} />
                            </Link>
                          )}
                          {doc.file_url && (
                            <a
                              href={doc.file_url}
                              target="_blank"
                              rel="noreferrer"
                              className="btn-icon-sm text-slate-500 hover:bg-slate-100"
                              title="Open file"
                            >
                              <ExternalLink size={13} />
                            </a>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* ── Pagination ── */}
          {total > pageSize && (
            <div className="flex items-center justify-between border-t border-slate-100 px-4 py-3">
              <span className="text-xs text-slate-500">
                Showing {(page-1)*pageSize+1}–{Math.min(page*pageSize, total)} of <strong>{total}</strong>
              </span>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage(p => Math.max(1, p-1))}
                  disabled={page === 1}
                  className="btn-icon-sm border border-slate-200 disabled:opacity-40"
                >
                  <ChevronLeft size={13} />
                </button>
                <span className="px-3 text-xs font-medium text-slate-600">
                  Page {page} / {totalPages}
                </span>
                <button
                  onClick={() => setPage(p => Math.min(totalPages, p+1))}
                  disabled={page >= totalPages}
                  className="btn-icon-sm border border-slate-200 disabled:opacity-40"
                >
                  <ChevronRight size={13} />
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
};

export default Documents;
