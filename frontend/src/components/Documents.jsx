import React, { useContext, useEffect, useMemo, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import UploadBox from './UploadBox';
import api from '../services/api';
import { FileText } from 'lucide-react';

const statusLabels = {
  pending: 'Pending',
  reviewing: 'Under Review',
  approved: 'Approved',
  rejected: 'Rejected',
};

const Documents = () => {
  const { user } = useContext(UserContext);
  const [documents, setDocuments] = useState([]);
  const [normes, setNormes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [selectedNorme, setSelectedNorme] = useState('');
  const [search, setSearch] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [page, setPage] = useState(1);
  const [pageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [file, setFile] = useState(null);
  const [counts, setCounts] = useState({ total: 0, approved: 0, rejected: 0, pending: 0, reviewing: 0 });
  const [statusFilter, setStatusFilter] = useState('');
  const [sortBy, setSortBy] = useState('newest');
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [updatingStatusId, setUpdatingStatusId] = useState(null);

  useEffect(() => {
    fetchDocuments();
    fetchNormes();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Debounce search input
  useEffect(() => {
    const t = setTimeout(() => setDebouncedSearch(search.trim()), 350);
    return () => clearTimeout(t);
  }, [search]);

  // Fetch counts for stats cards
  const fetchCounts = useCallback(async () => {
    try {
      // Use paginated endpoint to rely on DRF count field
      const base = await api.get('/documents/', { params: { page_size: 1 } });
      const totalCount = base.data?.count ?? (Array.isArray(base.data) ? base.data.length : 0);

      const statuses = ['approved', 'rejected', 'pending', 'reviewing'];
      const promises = statuses.map((s) => api.get('/documents/', { params: { page_size: 1, status: s } }).catch(() => null));
      const results = await Promise.all(promises);
      const map = { total: totalCount };
      statuses.forEach((s, i) => {
        const res = results[i];
        map[s] = res?.data?.count ?? 0;
      });
      setCounts(map);
    } catch (err) {
      console.error('Counts fetch error', err);
    }
  }, []);

  useEffect(() => { fetchCounts(); }, [fetchCounts]);

  const fetchDocuments = useCallback(async (opts = {}) => {
    setLoading(true);
    try {
      const params = {
        page: opts.page || page,
        page_size: opts.pageSize || pageSize,
      };
      if (debouncedSearch) params.search = debouncedSearch;
      if (selectedNorme) params.norme = selectedNorme;
      if (statusFilter) params.status = statusFilter;
      if (sortBy === 'oldest') params.ordering = 'created_at';
      if (sortBy === 'newest') params.ordering = '-created_at';
      if (sortBy === 'highest') params.ordering = '-compliance_score';
      if (sortBy === 'lowest') params.ordering = 'compliance_score';

      const response = await api.get('/documents/', { params });

      // DRF pagination: { count, next, previous, results }
      if (response.data && Array.isArray(response.data.results)) {
        setDocuments(response.data.results);
        setTotal(response.data.count || response.data.results.length);
      } else if (Array.isArray(response.data)) {
        setDocuments(response.data);
        setTotal(response.data.length);
      } else {
        setDocuments([]);
        setTotal(0);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, debouncedSearch, selectedNorme, statusFilter, sortBy]);

  const fetchNormes = async () => {
    try {
      const response = await api.get('/normes/');
      const normesData = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.results)
        ? response.data.results
        : [];
      setNormes(normesData);
    } catch (err) {
      console.error(err);
    }
  };

  const normeMap = useMemo(
    () => Object.fromEntries(normes.map((norme) => [norme.id, norme.name])),
    [normes]
  );

  const handleUpload = async (event) => {
    event.preventDefault();
    setError('');
    setMessage('');
    setUploading(true);

    if (!selectedNorme || !file) {
      setError('Please select a norme and a document file.');
      setUploading(false);
      return;
    }

    const payload = new FormData();
    payload.append('norme', selectedNorme);
    payload.append('file', file);

    try {
      await api.post('/documents/', payload, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessage('Document uploaded successfully.');
      setSelectedNorme('');
      setFile(null);
      fetchDocuments();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || err?.response?.data || 'Unable to upload document.');
    } finally {
      setUploading(false);
    }
  };

  const updateStatus = async (documentId, status) => {
    setError('');
    setMessage('');
    setUpdatingStatusId(documentId);
    try {
      const response = await api.patch(`/documents/${documentId}/status/`, { status });
      const updatedDocument = response.data?.document;
      const savedStatus = updatedDocument?.status || response.data?.status || status;

      setDocuments((currentDocuments) =>
        currentDocuments.map((document) =>
          document.id === documentId
            ? {
                ...document,
                status: savedStatus,
                teamlead_username:
                  updatedDocument?.teamlead_username ?? document.teamlead_username,
              }
            : document
        )
      );
      await fetchDocuments();
      setMessage(`Status updated to ${statusLabels[savedStatus] || savedStatus}.`);
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || err?.response?.data || 'Unable to update status.');
    } finally {
      setUpdatingStatusId(null);
    }
  };

  // Fetch when pagination/search/filter changes
  useEffect(() => {
    setPage(1); // reset to first page when search/filter change
  }, [debouncedSearch, selectedNorme, pageSize, statusFilter, sortBy]);

  useEffect(() => {
    fetchCounts();
  }, [debouncedSearch, selectedNorme, statusFilter, fetchCounts]);

  useEffect(() => {
    fetchDocuments({ page, pageSize });
  }, [fetchDocuments, page, pageSize]);

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-sky-600">Compliance workflow</p>
            <h1 className="mt-2 text-3xl font-bold text-slate-900">Documents</h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-600">
              Submit evidence against a norme, then review submission status from the workflow board.
            </p>
          </div>
          <div className="rounded-3xl bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <FileText size={18} />
              Document workflow access for employees and reviewers.
            </div>
          </div>
        </div>

        <div className="space-y-6 w-full">
          <section className="w-full space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Submit evidence</p>
                <h2 className="mt-2 text-2xl font-semibold text-slate-900">Upload a document</h2>
              </div>
              <div className="inline-flex items-center gap-2 rounded-3xl bg-slate-50 px-4 py-2 text-sm text-slate-700">
                <FileText size={16} /> File upload
              </div>
            </div>

            {message && <div className="rounded-3xl bg-emerald-50 p-4 text-sm text-emerald-700">{message}</div>}
            {error && <div className="rounded-3xl bg-red-50 p-4 text-sm text-red-700">{typeof error === 'string' ? error : JSON.stringify(error)}</div>}

            {user?.role === 'EMPLOYEE' ? (
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
            ) : (
              <div className="rounded-3xl border border-slate-200 bg-slate-50 p-6 text-sm text-slate-600">
                Only employees may submit documents. Admins and team leads may review and update statuses in the table below.
              </div>
            )}
          </section>

        </div>

        <section className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Submitted documents</p>
                <h2 className="mt-2 text-xl font-semibold text-slate-900">Compliance dashboard</h2>
              </div>
            </div>

            {/* Stats cards */}
            <div className="mt-6 grid gap-4 sm:grid-cols-5">
              <div className="rounded-2xl bg-white p-4 shadow-sm text-sm">
                <p className="text-xs text-slate-500">Total documents</p>
                <div className="mt-2 text-2xl font-semibold">{counts.total}</div>
              </div>
              <div className="rounded-2xl bg-white p-4 shadow-sm text-sm">
                <p className="text-xs text-slate-500">Approved</p>
                <div className="mt-2 text-2xl font-semibold text-emerald-600">{counts.approved}</div>
              </div>
              <div className="rounded-2xl bg-white p-4 shadow-sm text-sm">
                <p className="text-xs text-slate-500">Rejected</p>
                <div className="mt-2 text-2xl font-semibold text-rose-600">{counts.rejected}</div>
              </div>
              <div className="rounded-2xl bg-white p-4 shadow-sm text-sm">
                <p className="text-xs text-slate-500">Pending</p>
                <div className="mt-2 text-2xl font-semibold text-amber-500">{counts.pending}</div>
              </div>
              <div className="rounded-2xl bg-white p-4 shadow-sm text-sm">
                <p className="text-xs text-slate-500">Reviewing</p>
                <div className="mt-2 text-2xl font-semibold text-sky-600">{counts.reviewing}</div>
              </div>
            </div>

            {/* Search + filters + sort */}
            <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-2 w-full">
                <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search filename, employee, norme, teamlead, id, status" className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm outline-none" />
              </div>
              <div className="flex items-center gap-2">
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm">
                  <option value="">All status</option>
                  <option value="pending">Pending</option>
                  <option value="reviewing">Reviewing</option>
                  <option value="approved">Approved</option>
                  <option value="rejected">Rejected</option>
                </select>
                <select value={selectedNorme} onChange={(e) => setSelectedNorme(e.target.value)} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm">
                  <option value="">All normes</option>
                  {normes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
                </select>
                <select value={sortBy} onChange={(e) => setSortBy(e.target.value)} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-sm">
                  <option value="newest">Newest</option>
                  <option value="oldest">Oldest</option>
                  <option value="highest">Highest compliance</option>
                  <option value="lowest">Lowest compliance</option>
                </select>
              </div>
            </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">ID</th>
                  <th className="px-4 py-3 text-left font-semibold">Filename</th>
                  <th className="px-4 py-3 text-left font-semibold">Norme</th>
                  <th className="px-4 py-3 text-left font-semibold">Employee</th>
                  <th className="px-4 py-3 text-left font-semibold">Compliance</th>
                  <th className="px-4 py-3 text-left font-semibold">Status</th>
                  <th className="px-4 py-3 text-left font-semibold">TeamLead</th>
                  <th className="px-4 py-3 text-left font-semibold">Created</th>
                  <th className="px-4 py-3 text-left font-semibold">Updated</th>
                  <th className="px-4 py-3 text-left font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {loading ? (
                  <tr><td colSpan="10" className="px-4 py-6 text-center text-slate-500">Loading documents...</td></tr>
                ) : documents.length === 0 ? (
                  <tr><td colSpan="10" className="px-4 py-6 text-center text-slate-500">No documents found.</td></tr>
                ) : (
                  documents.map((document) => (
                    <tr key={document.id} className="hover:bg-slate-50">
                      <td className="px-4 py-4 font-mono text-xs">#{document.id}</td>
                      <td className="px-4 py-4">{document.file ? document.file.split('/').pop() : (document.file_url || '—')}</td>
                      <td className="px-4 py-4">{normeMap[document.norme] || `Norme #${document.norme}`}</td>
                      <td className="px-4 py-4">{document.employee_username}</td>
                      <td className="px-4 py-4">{typeof document.compliance_score === 'number' ? `${document.compliance_score}%` : '—'}</td>
                      <td className="px-4 py-4">
                        {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') ? (
                          <select
                            value={document.status}
                            onChange={(e) => updateStatus(document.id, e.target.value)}
                            disabled={updatingStatusId === document.id}
                            className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-3 py-2 text-sm outline-none"
                          >
                            {Object.entries(statusLabels).map(([key, label]) => (
                              <option key={key} value={key}>{label}</option>
                            ))}
                          </select>
                        ) : (
                          <span className="inline-flex rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.18em] text-slate-700">
                            {statusLabels[document.status] || document.status}
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-4">{document.teamlead_username || '—'}</td>
                      <td className="px-4 py-4">{new Date(document.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-4">{document.updated_at ? new Date(document.updated_at).toLocaleDateString() : '—'}</td>
                      <td className="px-4 py-4">
                        <Link to={`/validations?document=${document.id}`} className="text-slate-600 hover:text-slate-900 text-sm mr-3">
                          Review
                        </Link>
                        {document.file_url && (
                          <a href={document.file_url} target="_blank" rel="noreferrer" className="text-sky-600 hover:text-sky-700 text-sm">Open</a>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          <div className="mt-4 flex items-center justify-between">
            <div className="text-sm text-slate-600">{total} documents</div>
            <div className="flex items-center gap-2">
              <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page === 1} className="px-3 py-1 rounded border">Prev</button>
              <div className="px-3 py-1">Page {page}</div>
              <button onClick={() => setPage((p) => p + 1)} disabled={documents.length < pageSize} className="px-3 py-1 rounded border">Next</button>
            </div>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Documents;
