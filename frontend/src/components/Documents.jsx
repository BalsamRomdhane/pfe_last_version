import React, { useContext, useEffect, useMemo, useState } from 'react';
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
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    fetchDocuments();
    fetchNormes();
  }, []);

  const fetchDocuments = async () => {
    setLoading(true);
    try {
      const response = await api.get('/documents/');
      const documentsData = Array.isArray(response.data)
        ? response.data
        : Array.isArray(response.data?.results)
        ? response.data.results
        : [];
      setDocuments(documentsData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

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
    try {
      await api.patch(`/documents/${documentId}/status/`, { status });
      fetchDocuments();
      setMessage('Status updated.');
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || err?.response?.data || 'Unable to update status.');
    }
  };

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
              <h2 className="mt-2 text-xl font-semibold text-slate-900">Recent submissions</h2>
            </div>
          </div>

          <div className="mt-6 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50 text-slate-700">
                <tr>
                  <th className="px-4 py-3 text-left font-semibold">Norme</th>
                  <th className="px-4 py-3 text-left font-semibold">Employee</th>
                  <th className="px-4 py-3 text-left font-semibold">Status</th>
                  <th className="px-4 py-3 text-left font-semibold">Date</th>
                  <th className="px-4 py-3 text-left font-semibold">Team Lead</th>
                  <th className="px-4 py-3 text-left font-semibold">View file</th>
                  <th className="px-4 py-3 text-left font-semibold">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {loading ? (
                  <tr><td colSpan="7" className="px-4 py-6 text-center text-slate-500">Loading documents...</td></tr>
                ) : documents.length === 0 ? (
                  <tr><td colSpan="7" className="px-4 py-6 text-center text-slate-500">No documents submitted yet.</td></tr>
                ) : (
                  documents.map((document) => (
                    <tr key={document.id} className="hover:bg-slate-50">
                      <td className="px-4 py-4">{normeMap[document.norme] || `Norme #${document.norme}`}</td>
                      <td className="px-4 py-4">{document.employee_username}</td>
                      <td className="px-4 py-4">
                        {(user?.role === 'ADMIN' || user?.role === 'TEAMLEAD') ? (
                          <select
                            value={document.status}
                            onChange={(e) => updateStatus(document.id, e.target.value)}
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
                      <td className="px-4 py-4">{new Date(document.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-4">{document.teamlead_username || '—'}</td>
                      <td className="px-4 py-4">
                        {document.file_url ? (
                          <a href={document.file_url} target="_blank" rel="noreferrer" className="text-sky-600 hover:text-sky-700">
                            View file
                          </a>
                        ) : (
                          'Unavailable'
                        )}
                      </td>
                      <td className="px-4 py-4">
                        {document.status === 'rejected' && (
                          <Link to={`/validations?document=${document.id}`} className="text-slate-600 hover:text-slate-900 text-sm">
                            Review missing rules
                          </Link>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Documents;
