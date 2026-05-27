import React, { useContext, useEffect, useState } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import api from '../services/api';
import CreateNormeModal from './CreateNormeModal';
import SeverityBadge from './SeverityBadge';
import { Plus, Trash2, Edit3 } from 'lucide-react';

const Normes = () => {
  const { user } = useContext(UserContext);
  const isAdmin = user?.role === 'ADMIN';
  const [normes, setNormes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [pageError, setPageError] = useState('');
  const [modalError, setModalError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editingNorme, setEditingNorme] = useState(null);
  const [toast, setToast] = useState('');

  useEffect(() => {
    fetchNormes();
  }, []);

  const fetchNormes = async () => {
    setLoading(true);
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
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingNorme(null);
    setModalError('');
    setModalOpen(true);
  };

  const openEditModal = (norme) => {
    setEditingNorme(norme);
    setModalError('');
    setModalOpen(true);
  };

  const closeModal = () => {
    setEditingNorme(null);
    setModalError('');
    setModalOpen(false);
  };

  const handleNormeSubmit = async (payload, action) => {
    setSaving(true);
    setModalError('');

    const payloadBody = {
      name: payload.name,
      description: payload.description,
      rules: payload.rules.map((rule) => ({
        id: rule.id,
        title: rule.title || '',
        description: rule.description || '',
        severity: rule.severity || '',
        condition: rule.condition || '',
        action: rule.action || '',
      })),
    };

    try {
      if (editingNorme) {
        await api.patch(`/normes/${editingNorme.id}/`, payloadBody);
      } else {
        await api.post('/normes/', payloadBody);
      }
      setModalOpen(false);
      setEditingNorme(null);
      fetchNormes();
      setToast(action === 'draft' ? 'Norm saved as draft successfully.' : 'Norm published successfully.');
      window.setTimeout(() => setToast(''), 4000);
    } catch (err) {
      setModalError(
        formatError(
          err?.response?.data?.detail || err?.response?.data || 'Unable to save norme.'
        )
      );
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteNorme = async (normeId) => {
    if (!window.confirm('Voulez-vous vraiment supprimer cette norme ? Cette action est irréversible.')) {
      return;
    }

    try {
      await api.delete(`/normes/${normeId}/`);
      fetchNormes();
    } catch (err) {
      console.error(err);
      setPageError(
        formatError(err?.response?.data?.detail || err?.response?.data || 'Unable to delete norme.')
      );
    }
  };

  const formatError = (errorValue) => {
    if (!errorValue) return '';
    if (typeof errorValue === 'string') return errorValue;
    if (Array.isArray(errorValue)) return errorValue.join(' ');
    if (typeof errorValue === 'object') {
      return Object.values(errorValue)
        .flat()
        .filter(Boolean)
        .join(' ');
    }
    return String(errorValue);
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.3em] text-sky-600">Compliance workflow</p>
            <h1 className="mt-2 text-3xl font-bold text-slate-900">Normes</h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-600">
              Define audit norms and rules so employees can submit documents and team leads can validate them.
            </p>
          </div>

          {isAdmin ? (
            <button
              type="button"
              onClick={openCreateModal}
              className="inline-flex items-center gap-2 rounded-3xl bg-sky-600 px-5 py-3 text-white shadow-lg shadow-sky-600/15 transition hover:bg-sky-700"
            >
              <Plus size={18} />
              Create norme
            </button>
          ) : (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-600">
              Seuls les administrateurs peuvent créer de nouvelles normes.
            </div>
          )}
        </div>

        <CreateNormeModal
          open={modalOpen}
          onClose={closeModal}
          onSubmit={handleNormeSubmit}
          saving={saving}
          initialData={editingNorme}
          error={modalError}
        />

        {toast && (
          <div className="rounded-3xl border border-emerald-200 bg-emerald-50 p-4 text-sm text-emerald-800">
            {toast}
          </div>
        )}

        {pageError && (
          <div className="rounded-3xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            {pageError}
          </div>
        )}

        <section className="space-y-4">
          <div className="flex items-center justify-between gap-4">
            <div>
              <p className="text-sm uppercase tracking-[0.25em] text-slate-500">Norme catalog</p>
              <h2 className="text-2xl font-semibold text-slate-900">Active norms</h2>
            </div>
          </div>

          {loading ? (
            <div className="rounded-3xl border border-slate-200 bg-white p-8 text-center text-slate-500">Loading...</div>
          ) : normes.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center text-slate-500">No normes found. Create one to get started.</div>
          ) : (
            <div className="grid gap-6 xl:grid-cols-2">
              {normes.map((norme) => (
                <div key={norme.id} className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <h3 className="text-xl font-semibold text-slate-900">{norme.name}</h3>
                    </div>
                    <div className="flex items-center gap-2">
                      {isAdmin && (
                        <>
                          <button
                            type="button"
                            onClick={() => openEditModal(norme)}
                            className="inline-flex items-center gap-2 rounded-3xl border border-slate-200 bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700 transition hover:bg-slate-200"
                          >
                            <Edit3 size={14} />
                            Edit
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteNorme(norme.id)}
                            className="inline-flex items-center gap-2 rounded-3xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs font-semibold text-rose-700 transition hover:bg-rose-100"
                          >
                            <Trash2 size={14} />
                            Delete
                          </button>
                        </>
                      )}
                      <div className="inline-flex items-center gap-2 rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">
                        {norme.rules?.length || 0} rules
                      </div>
                    </div>
                  </div>
                  {norme.description && <p className="mt-4 text-sm leading-6 text-slate-600">{norme.description}</p>}

                  {norme.rules?.length > 0 && (
                    <div className="mt-6 space-y-3">
                      {norme.rules.map((rule) => (
                        <div key={rule.id} className="rounded-3xl border border-slate-100 bg-slate-50 p-4">
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-slate-900">{rule.title}</p>
                              {rule.description && <p className="mt-2 text-sm text-slate-600">{rule.description}</p>}
                            </div>
                            <SeverityBadge severity={rule.severity} className="shrink-0" />
                          </div>
                          {(rule.condition || rule.action) && (
                            <div className="mt-4 grid gap-3 sm:grid-cols-2">
                              {rule.condition && (
                                <div>
                                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Condition</p>
                                  <p className="mt-1 text-sm text-slate-600">{rule.condition}</p>
                                </div>
                              )}
                              {rule.action && (
                                <div>
                                  <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Action</p>
                                  <p className="mt-1 text-sm text-slate-600">{rule.action}</p>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </Layout>
  );
};

export default Normes;
