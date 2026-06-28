import React, { useContext, useEffect, useState } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import api from '../services/api';
import CreateNormeModal from './CreateNormeModal';
import SeverityBadge from './SeverityBadge';
import EmptyState from './common/EmptyState';
import { Plus, Trash2, Edit3, BookOpen, ChevronDown, ChevronUp, X, CheckCircle2 } from 'lucide-react';

/* ─── Rule card ────────────────────────────────────────────────────────── */
function RuleItem({ rule }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="rounded-lg border border-slate-100 bg-slate-50/60">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
      >
        <div className="flex items-center gap-2 min-w-0">
          <SeverityBadge severity={rule.severity} />
          <span className="text-xs font-semibold text-slate-800 truncate">{rule.title}</span>
        </div>
        {open ? <ChevronUp size={13} className="text-slate-400 shrink-0" /> : <ChevronDown size={13} className="text-slate-400 shrink-0" />}
      </button>
      {open && (
        <div className="border-t border-slate-100 px-3 pb-3 pt-2 space-y-2 animate-fade-in">
          {rule.description && <p className="text-xs text-slate-600">{rule.description}</p>}
          {(rule.condition || rule.action) && (
            <div className="grid gap-2 sm:grid-cols-2">
              {rule.condition && (
                <div className="rounded-md bg-white border border-slate-100 px-2.5 py-2">
                  <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-1">Condition</p>
                  <p className="text-xs text-slate-600">{rule.condition}</p>
                </div>
              )}
              {rule.action && (
                <div className="rounded-md bg-white border border-slate-100 px-2.5 py-2">
                  <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-1">Action</p>
                  <p className="text-xs text-slate-600">{rule.action}</p>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Norme card ───────────────────────────────────────────────────────── */
function NormeCard({ norme, isAdmin, onEdit, onDelete }) {
  const severityCounts = (norme.rules || []).reduce((acc, r) => {
    acc[r.severity] = (acc[r.severity] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="card hover:shadow-card-hover transition-shadow duration-200">
      <div className="p-5">
        {/* Header */}
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3 min-w-0">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600">
              <BookOpen size={16} />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-slate-900 truncate">{norme.name}</h3>
              <div className="flex items-center gap-2 mt-1">
                <span className="badge badge-slate">{norme.rules?.length || 0} rules</span>
                {Object.entries(severityCounts).map(([sev, count]) => (
                  <span key={sev} className="text-2xs text-slate-400">{count} {sev.toLowerCase()}</span>
                ))}
              </div>
            </div>
          </div>

          {isAdmin && (
            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => onEdit(norme)}
                className="btn-icon-sm text-brand-500 hover:bg-brand-50 hover:text-brand-700 border border-slate-200"
                aria-label="Edit"
              >
                <Edit3 size={13} />
              </button>
              <button
                type="button"
                onClick={() => onDelete(norme.id)}
                className="btn-icon-sm text-red-500 hover:bg-red-50 border border-slate-200"
                aria-label="Delete"
              >
                <Trash2 size={13} />
              </button>
            </div>
          )}
        </div>

        {/* Description */}
        {norme.description && (
          <p className="mt-3 text-xs text-slate-500 leading-relaxed">{norme.description}</p>
        )}
      </div>

      {/* Rules list */}
      {norme.rules?.length > 0 && (
        <div className="border-t border-slate-100 px-5 pb-5 pt-4">
          <p className="text-2xs font-bold uppercase tracking-wider text-slate-400 mb-2">Rules</p>
          <div className="space-y-1.5">
            {norme.rules.map(rule => <RuleItem key={rule.id} rule={rule} />)}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Normes page ──────────────────────────────────────────────────────── */
const Normes = () => {
  const { user }     = useContext(UserContext);
  const isAdmin      = user?.role === 'ADMIN';
  const [normes,     setNormes]     = useState([]);
  const [loading,    setLoading]    = useState(true);
  const [saving,     setSaving]     = useState(false);
  const [pageError,  setPageError]  = useState('');
  const [modalError, setModalError] = useState('');
  const [modalOpen,  setModalOpen]  = useState(false);
  const [editing,    setEditing]    = useState(null);
  const [toast,      setToast]      = useState('');
  const [search,     setSearch]     = useState('');
  const [deleteId,   setDeleteId]   = useState(null);

  useEffect(() => { fetchNormes(); }, []);

  const fetchNormes = async () => {
    setLoading(true);
    try {
      const res  = await api.get('/normes/');
      const data = Array.isArray(res.data) ? res.data : (res.data?.results || []);
      setNormes(data);
    } catch {}
    finally { setLoading(false); }
  };

  const openCreate = () => { setEditing(null); setModalError(''); setModalOpen(true); };
  const openEdit   = (n)  => { setEditing(n);  setModalError(''); setModalOpen(true); };
  const closeModal = ()   => { setEditing(null); setModalError(''); setModalOpen(false); };

  const handleSubmit = async (payload) => {
    setSaving(true); setModalError('');
    const body = {
      name: payload.name,
      description: payload.description,
      rules: payload.rules.map(r => ({ id: r.id, title: r.title || '', description: r.description || '', severity: r.severity || '', condition: r.condition || '', action: r.action || '' })),
    };
    try {
      if (editing) await api.patch(`/normes/${editing.id}/`, body);
      else         await api.post('/normes/', body);
      closeModal();
      fetchNormes();
      showToast(editing ? 'Standard updated.' : 'Standard created.');
    } catch (err) {
      const raw = err?.response?.data?.detail || err?.response?.data || 'Unable to save standard.';
      setModalError(typeof raw === 'string' ? raw : JSON.stringify(raw));
    } finally { setSaving(false); }
  };

  const confirmDelete = (id) => setDeleteId(id);
  const handleDelete  = async () => {
    if (!deleteId) return;
    try {
      await api.delete(`/normes/${deleteId}/`);
      setDeleteId(null);
      fetchNormes();
      showToast('Standard deleted.');
    } catch (err) {
      setPageError(err?.response?.data?.detail || 'Unable to delete standard.');
      setDeleteId(null);
    }
  };

  const showToast = (msg) => {
    setToast(msg);
    setTimeout(() => setToast(''), 4000);
  };

  const filtered = normes.filter(n =>
    n.name.toLowerCase().includes(search.toLowerCase()) ||
    (n.description || '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Compliance Workflow</p>
            <h1 className="page-title mt-1">Standards</h1>
            <p className="page-subtitle">Define audit standards and rules for compliance validation.</p>
          </div>
          {isAdmin && (
            <button type="button" onClick={openCreate} className="btn-primary">
              <Plus size={15} />
              Create Standard
            </button>
          )}
        </div>

        {/* ── Toasts / Errors ── */}
        {toast     && <div className="alert alert-success"><CheckCircle2 size={14} className="shrink-0"/>{toast}<button onClick={() => setToast('')} className="ml-auto"><X size={13}/></button></div>}
        {pageError && <div className="alert alert-danger"><X size={14} className="shrink-0"/>{pageError}<button onClick={() => setPageError('')} className="ml-auto"><X size={13}/></button></div>}

        {/* ── Search ── */}
        {normes.length > 0 && (
          <div className="relative max-w-sm">
            <BookOpen size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search standards…"
              className="form-input pl-9"
            />
          </div>
        )}

        {/* ── Modal ── */}
        <CreateNormeModal
          open={modalOpen}
          onClose={closeModal}
          onSubmit={handleSubmit}
          saving={saving}
          initialData={editing}
          error={modalError}
        />

        {/* ── Content ── */}
        {loading ? (
          <div className="grid gap-5 xl:grid-cols-2">
            {[1,2,3,4].map(i => (
              <div key={i} className="card p-5 animate-pulse space-y-4">
                <div className="flex gap-3">
                  <div className="skeleton h-9 w-9 rounded-lg" />
                  <div className="flex-1 space-y-2">
                    <div className="skeleton h-5 w-1/2" />
                    <div className="skeleton h-4 w-1/4" />
                  </div>
                </div>
                <div className="skeleton h-3 w-3/4" />
                <div className="space-y-1.5">
                  {[1,2,3].map(j => <div key={j} className="skeleton h-9 rounded-lg" />)}
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title={search ? 'No standards match your search' : 'No standards defined yet'}
            description={isAdmin ? 'Create your first compliance standard to get started.' : 'No standards have been defined yet.'}
            action={isAdmin && !search ? (
              <button type="button" onClick={openCreate} className="btn-primary btn-sm">
                <Plus size={13} /> Create Standard
              </button>
            ) : null}
          />
        ) : (
          <>
            <p className="text-xs text-slate-500 font-medium">{filtered.length} standard{filtered.length !== 1 ? 's' : ''}</p>
            <div className="grid gap-5 xl:grid-cols-2">
              {filtered.map(n => (
                <NormeCard
                  key={n.id}
                  norme={n}
                  isAdmin={isAdmin}
                  onEdit={openEdit}
                  onDelete={confirmDelete}
                />
              ))}
            </div>
          </>
        )}

        {/* ── Delete confirm modal ── */}
        {deleteId && (
          <div className="modal-backdrop" onClick={() => setDeleteId(null)}>
            <div className="modal-panel max-w-md" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="text-base font-semibold text-slate-900">Delete Standard</h3>
                <button onClick={() => setDeleteId(null)} className="btn-icon-sm"><X size={14}/></button>
              </div>
              <div className="modal-body">
                <p className="text-sm text-slate-600">
                  Are you sure you want to delete this standard? This action is <strong>irreversible</strong> and will remove all associated rules.
                </p>
              </div>
              <div className="modal-footer">
                <button onClick={() => setDeleteId(null)} className="btn-secondary">Cancel</button>
                <button onClick={handleDelete} className="btn-danger">Delete Standard</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Normes;
