import React, { useContext, useState, useEffect, useMemo } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import { Building2, Search, Plus, Edit3, Trash2, Eye, X, CheckCircle2 } from 'lucide-react';
import api from '../services/api';
import DepartmentModal from './DepartmentModal';
import EmptyState from './common/EmptyState';

/* ─── Department card ──────────────────────────────────────────────────── */
function DeptCard({ dept, onView, onEdit, onDelete }) {
  const initials = (dept.name || dept.code || '?')
    .split(' ')
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  const color = dept.theme_color || '#2563eb';

  return (
    <div className="card group hover:shadow-card-hover transition-all duration-200 hover:-translate-y-px">
      <div className="p-5">
        <div className="flex items-start justify-between gap-3">
          {/* Icon + info */}
          <div className="flex items-center gap-3 min-w-0">
            <div
              className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-sm font-bold text-white shadow-sm"
              style={{ backgroundColor: color }}
            >
              {initials}
            </div>
            <div className="min-w-0">
              <p className="text-base font-semibold text-slate-900 truncate">{dept.name}</p>
              <div className="flex items-center gap-2 mt-0.5">
                <span className="badge badge-slate text-2xs">{dept.code}</span>
                {dept.user_count != null && (
                  <span className="text-2xs text-slate-400">{dept.user_count} users</span>
                )}
              </div>
            </div>
          </div>

          {/* Color swatch */}
          <div
            className="h-5 w-5 shrink-0 rounded-md border border-black/10 shadow-sm"
            style={{ backgroundColor: color }}
            title={color}
          />
        </div>

        {dept.description && (
          <p className="mt-3 text-xs text-slate-500 leading-relaxed line-clamp-2">
            {dept.description}
          </p>
        )}

        {/* Actions */}
        <div className="mt-4 flex items-center gap-2 pt-3 border-t border-slate-100">
          <button
            type="button"
            onClick={() => onView(dept)}
            className="btn-ghost btn-sm flex-1 justify-center text-slate-600"
          >
            <Eye size={13} /> View
          </button>
          <button
            type="button"
            onClick={() => onEdit(dept)}
            className="btn-secondary btn-sm flex-1 justify-center"
          >
            <Edit3 size={13} /> Edit
          </button>
          <button
            type="button"
            onClick={() => onDelete(dept)}
            className="btn-icon-sm text-red-500 hover:bg-red-50 border border-slate-200"
            aria-label="Delete"
          >
            <Trash2 size={13} />
          </button>
        </div>
      </div>
    </div>
  );
}

/* ─── Departments page ─────────────────────────────────────────────────── */
const Departments = () => {
  const { user }       = useContext(UserContext);
  const [departments,  setDepartments]  = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [search,       setSearch]       = useState('');
  const [toast,        setToast]        = useState(null);
  const [modalState,   setModalState]   = useState({ open: false, mode: 'create', dept: null });
  const [viewDept,     setViewDept]     = useState(null);
  const [confirmDel,   setConfirmDel]   = useState(null);
  const [actionLoad,   setActionLoad]   = useState(false);
  const [modalError,   setModalError]   = useState('');

  useEffect(() => { fetchDepts(); }, []);

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 4000);
  };

  const fetchDepts = async () => {
    setLoading(true);
    try {
      const res  = await api.get('/rbac/departments/');
      const data = Array.isArray(res.data) ? res.data : (res.data?.data || []);
      setDepartments(data);
    } catch {}
    finally { setLoading(false); }
  };

  const openCreate = () => { setModalError(''); setModalState({ open: true, mode: 'create', dept: null }); };
  const openEdit   = (d) => { setModalError(''); setModalState({ open: true, mode: 'edit', dept: d }); };
  const closeModal = ()  => { setModalState({ open: false, mode: 'create', dept: null }); setModalError(''); };

  const handleModalSubmit = async (data) => {
    if (!data.name || !data.code) { setModalError('Name and code are required.'); return; }
    setActionLoad(true);
    try {
      if (modalState.mode === 'create') {
        await api.post('/rbac/departments/', data);
        showToast('Department created.');
      } else if (modalState.dept?.code) {
        await api.put(`/rbac/departments/${modalState.dept.code}/`, data);
        showToast('Department updated.');
      }
      closeModal();
      fetchDepts();
    } catch { setModalError('Unable to save department. Please try again.'); }
    finally { setActionLoad(false); }
  };

  const handleDelete = async () => {
    if (!confirmDel) return;
    setActionLoad(true);
    try {
      await api.delete(`/rbac/departments/${confirmDel.code}/`);
      showToast('Department deleted.');
      setConfirmDel(null);
      fetchDepts();
    } catch { showToast('Unable to delete department.', 'error'); setConfirmDel(null); }
    finally { setActionLoad(false); }
  };

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return departments.filter(d =>
      d.name?.toLowerCase().includes(q) ||
      d.code?.toLowerCase().includes(q) ||
      (d.description || '').toLowerCase().includes(q)
    );
  }, [departments, search]);

  if (user?.role !== 'ADMIN') {
    return <Layout><EmptyState title="Access Denied" description="You don't have permission to view this page." /></Layout>;
  }

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Administration</p>
            <h1 className="page-title mt-1">Departments</h1>
            <p className="page-subtitle">Manage corporate departments, themes and user assignments.</p>
          </div>
          <button type="button" onClick={openCreate} className="btn-primary">
            <Plus size={15} /> Add Department
          </button>
        </div>

        {/* ── Toast ── */}
        {toast && (
          <div className={`alert ${toast.type === 'error' ? 'alert-danger' : 'alert-success'}`}>
            <CheckCircle2 size={14} className="shrink-0" />
            {toast.msg}
            <button onClick={() => setToast(null)} className="ml-auto"><X size={13}/></button>
          </div>
        )}

        {/* ── Stats bar ── */}
        {!loading && departments.length > 0 && (
          <div className="flex items-center gap-4 text-xs text-slate-500">
            <span className="font-medium text-slate-700">{departments.length} departments</span>
            {departments.map(d => (
              <div key={d.code} className="flex items-center gap-1.5">
                <span
                  className="h-2.5 w-2.5 rounded-full"
                  style={{ backgroundColor: d.theme_color || '#94a3b8' }}
                />
                <span>{d.name}</span>
              </div>
            ))}
          </div>
        )}

        {/* ── Search ── */}
        <div className="relative max-w-sm">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            placeholder="Search departments…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="form-input pl-9"
          />
        </div>

        {/* ── Grid ── */}
        {loading ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="card p-5 animate-pulse space-y-3">
                <div className="flex gap-3">
                  <div className="skeleton h-11 w-11 rounded-xl" />
                  <div className="flex-1 space-y-2">
                    <div className="skeleton h-5 w-1/2" />
                    <div className="skeleton h-4 w-1/4" />
                  </div>
                </div>
                <div className="skeleton h-3 w-3/4" />
                <div className="skeleton h-8 rounded-lg" />
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Building2}
            title={search ? 'No departments match' : 'No departments yet'}
            description="Add your first department to get started."
          />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {filtered.map(dept => (
              <DeptCard
                key={dept.id || dept.code}
                dept={dept}
                onView={setViewDept}
                onEdit={openEdit}
                onDelete={setConfirmDel}
              />
            ))}
          </div>
        )}

        {/* ── Modals ── */}
        <DepartmentModal
          open={modalState.open}
          mode={modalState.mode}
          initialData={modalState.dept || {}}
          onClose={closeModal}
          onSubmit={handleModalSubmit}
          loading={actionLoad}
          error={modalError}
        />

        <DepartmentModal
          open={Boolean(viewDept)}
          mode="view"
          initialData={viewDept || {}}
          onClose={() => setViewDept(null)}
          onSubmit={() => {}}
          loading={false}
          error=""
        />

        {confirmDel && (
          <div className="modal-backdrop" role="presentation" onClick={() => setConfirmDel(null)}>
            <div className="modal-panel max-w-md" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="text-base font-semibold text-slate-900">Delete Department</h3>
                <button onClick={() => setConfirmDel(null)} className="btn-icon-sm"><X size={14}/></button>
              </div>
              <div className="modal-body">
                <p className="text-sm text-slate-600">
                  Delete <strong className="text-slate-900">{confirmDel.name}</strong>?
                  This action is irreversible.
                </p>
              </div>
              <div className="modal-footer">
                <button onClick={() => setConfirmDel(null)} className="btn-secondary" disabled={actionLoad}>Cancel</button>
                <button onClick={handleDelete} className="btn-danger" disabled={actionLoad}>
                  {actionLoad ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Departments;
