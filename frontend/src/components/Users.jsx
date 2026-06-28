import React, { useContext, useState, useEffect, useMemo } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import { Edit3, Trash2, Plus, Search, X, CheckCircle2, Filter } from 'lucide-react';
import api from '../services/api';
import UserModal from './UserModal';
import EmptyState from './common/EmptyState';

/* ─── Role badge ───────────────────────────────────────────────────────── */
const ROLE_CLS = {
  ADMIN:    'bg-amber-50 text-amber-700 ring-1 ring-amber-200',
  TEAMLEAD: 'bg-violet-50 text-violet-700 ring-1 ring-violet-200',
  EMPLOYEE: 'badge-slate',
};

/* ─── Skeleton row ─────────────────────────────────────────────────────── */
function SkeletonRow() {
  return (
    <tr>
      {[1,2,3,4,5,6].map(i => (
        <td key={i} className="px-4 py-3">
          <div className="skeleton h-4 rounded" style={{ width: `${50 + i * 8}%` }} />
        </td>
      ))}
    </tr>
  );
}

/* ─── Users page ───────────────────────────────────────────────────────── */
const Users = () => {
  const { user }          = useContext(UserContext);
  const [users,           setUsers]          = useState([]);
  const [departments,     setDepartments]    = useState([]);
  const [loading,         setLoading]        = useState(true);
  const [search,          setSearch]         = useState('');
  const [roleFilter,      setRoleFilter]     = useState('ALL');
  const [deptFilter,      setDeptFilter]     = useState('ALL');
  const [modalOpen,       setModalOpen]      = useState(false);
  const [selectedUser,    setSelectedUser]   = useState(null);
  const [confirmDelete,   setConfirmDelete]  = useState(null);
  const [modalError,      setModalError]     = useState('');
  const [modalLoading,    setModalLoading]   = useState(false);
  const [toast,           setToast]          = useState('');
  const [toastType,       setToastType]      = useState('success');

  useEffect(() => { fetchUsers(); fetchDepartments(); }, []);

  const fetchUsers = async () => {
    setLoading(true);
    try {
      const res  = await api.get('/rbac/users/');
      const data = res.data?.data || res.data || [];
      setUsers(Array.isArray(data) ? data.slice(0, 500) : []);
    } catch {}
    finally { setLoading(false); }
  };

  const fetchDepartments = async () => {
    try {
      const res  = await api.get('/rbac/departments/');
      const data = res.data?.data || res.data || [];
      setDepartments(Array.isArray(data) ? data : []);
    } catch {}
  };

  const showToast = (msg, type = 'success') => {
    setToast(msg); setToastType(type);
    setTimeout(() => setToast(''), 4000);
  };

  const filteredUsers = useMemo(() => {
    const q = search.toLowerCase();
    return users.filter(u => {
      const text = `${u.username} ${u.email} ${u.department} ${u.role}`.toLowerCase();
      return text.includes(q) &&
        (roleFilter === 'ALL' || u.role === roleFilter) &&
        (deptFilter === 'ALL' || u.department === deptFilter);
    });
  }, [users, search, roleFilter, deptFilter]);

  const handleDelete = async () => {
    if (!confirmDelete) return;
    try {
      await api.delete(`/rbac/users/${confirmDelete.id}/`);
      setConfirmDelete(null);
      fetchUsers();
      showToast('User deleted successfully.');
    } catch { showToast('Unable to delete user.', 'error'); setConfirmDelete(null); }
  };

  const handleModalSubmit = async (payload) => {
    setModalError(''); setModalLoading(true);
    try {
      if (selectedUser) await api.put(`/rbac/users/${selectedUser.id}/`, payload);
      else              await api.post('/rbac/users/', payload);
      setModalOpen(false); setSelectedUser(null);
      fetchUsers();
      showToast(selectedUser ? 'User updated.' : 'User created.');
    } catch (err) {
      setModalError(err?.response?.data || { error: err?.message || 'Save failed' });
    } finally { setModalLoading(false); }
  };

  /* Role stats — must be BEFORE any conditional return */
  const roleCounts = useMemo(() => {
    return users.reduce((acc, u) => { acc[u.role] = (acc[u.role]||0)+1; return acc; }, {});
  }, [users]);

  if (user?.role !== 'ADMIN') {
    return <Layout><EmptyState icon="default" title="Access Denied" description="You don't have permission to view this page." /></Layout>;
  }

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Administration</p>
            <h1 className="page-title mt-1">Users</h1>
            <p className="page-subtitle">Manage user accounts, roles and department assignments.</p>
          </div>
          <button
            type="button"
            onClick={() => { setSelectedUser(null); setModalError(''); setModalOpen(true); }}
            className="btn-primary"
          >
            <Plus size={15} />
            Create User
          </button>
        </div>

        {/* ── Toast ── */}
        {toast && (
          <div className={`alert ${toastType === 'error' ? 'alert-danger' : 'alert-success'}`}>
            <CheckCircle2 size={14} className="shrink-0" />
            {toast}
            <button onClick={() => setToast('')} className="ml-auto"><X size={13}/></button>
          </div>
        )}

        {/* ── KPI stats ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="kpi-card">
            <p className="kpi-label">Total Users</p>
            <p className="kpi-value mt-2">{loading ? '—' : users.length}</p>
          </div>
          <div className="kpi-card">
            <p className="kpi-label">Admins</p>
            <p className="kpi-value mt-2 text-amber-600">{loading ? '—' : (roleCounts.ADMIN || 0)}</p>
          </div>
          <div className="kpi-card">
            <p className="kpi-label">Team Leads</p>
            <p className="kpi-value mt-2 text-violet-600">{loading ? '—' : (roleCounts.TEAMLEAD || 0)}</p>
          </div>
          <div className="kpi-card">
            <p className="kpi-label">Employees</p>
            <p className="kpi-value mt-2 text-emerald-600">{loading ? '—' : (roleCounts.EMPLOYEE || 0)}</p>
          </div>
        </div>

        {/* ── Filters ── */}
        <div className="card">
          <div className="p-4 flex flex-col gap-3 sm:flex-row sm:items-center">
            <div className="relative flex-1">
              <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
              <input
                placeholder="Search users…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="form-input pl-9"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter size={13} className="text-slate-400" />
              <select
                value={roleFilter}
                onChange={e => setRoleFilter(e.target.value)}
                className="form-select w-auto text-xs py-1.5"
              >
                <option value="ALL">All roles</option>
                {['ADMIN','TEAMLEAD','EMPLOYEE'].map(r => <option key={r} value={r}>{r}</option>)}
              </select>
              <select
                value={deptFilter}
                onChange={e => setDeptFilter(e.target.value)}
                className="form-select w-auto text-xs py-1.5"
              >
                <option value="ALL">All departments</option>
                {departments.map(d => <option key={d.code} value={d.code}>{d.name || d.code}</option>)}
              </select>
              {(search || roleFilter !== 'ALL' || deptFilter !== 'ALL') && (
                <button
                  type="button"
                  onClick={() => { setSearch(''); setRoleFilter('ALL'); setDeptFilter('ALL'); }}
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
                  <th>Username</th>
                  <th>Email</th>
                  <th>Name</th>
                  <th>Role</th>
                  <th>Department</th>
                  <th className="text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  [1,2,3,4,5].map(i => <SkeletonRow key={i} />)
                ) : filteredUsers.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-4 py-10">
                      <EmptyState icon="search" title="No users found" description="Try adjusting the search or filters." />
                    </td>
                  </tr>
                ) : (
                  filteredUsers.map(u => (
                    <tr key={u.id}>
                      <td>
                        <div className="flex items-center gap-2">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-xs font-bold text-slate-600">
                            {u.username?.charAt(0)?.toUpperCase()}
                          </div>
                          <span className="font-medium text-slate-900">{u.username}</span>
                        </div>
                      </td>
                      <td className="text-sm text-slate-500">{u.email || '—'}</td>
                      <td className="text-sm">
                        {(u.first_name || u.last_name)
                          ? `${u.first_name || ''} ${u.last_name || ''}`.trim()
                          : '—'
                        }
                      </td>
                      <td>
                        <span className={`badge ${ROLE_CLS[u.role] || 'badge-slate'}`}>{u.role}</span>
                      </td>
                      <td className="text-sm text-slate-500">{u.department || 'Global'}</td>
                      <td className="text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => { setSelectedUser(u); setModalError(''); setModalOpen(true); }}
                            className="btn-icon-sm text-brand-500 hover:bg-brand-50 border border-slate-200"
                            aria-label={`Edit ${u.username}`}
                          >
                            <Edit3 size={13} />
                          </button>
                          <button
                            type="button"
                            onClick={() => setConfirmDelete(u)}
                            className="btn-icon-sm text-red-500 hover:bg-red-50 border border-slate-200"
                            aria-label={`Delete ${u.username}`}
                          >
                            <Trash2 size={13} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Footer count */}
          {!loading && (
            <div className="border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
              Showing {filteredUsers.length} of {users.length} users
            </div>
          )}
        </div>

        {/* ── Edit/Create modal ── */}
        {modalOpen && (
          <UserModal
            open={modalOpen}
            mode={selectedUser ? 'edit' : 'create'}
            initialData={selectedUser || {}}
            roles={['ADMIN','TEAMLEAD','EMPLOYEE']}
            departments={departments}
            onClose={() => { setModalOpen(false); setSelectedUser(null); setModalError(''); }}
            onSubmit={handleModalSubmit}
            loading={modalLoading}
            error={modalError}
          />
        )}

        {/* ── Delete confirm modal ── */}
        {confirmDelete && (
          <div className="modal-backdrop" onClick={() => setConfirmDelete(null)}>
            <div className="modal-panel max-w-md" onClick={e => e.stopPropagation()}>
              <div className="modal-header">
                <h3 className="text-base font-semibold text-slate-900">Delete User</h3>
                <button onClick={() => setConfirmDelete(null)} className="btn-icon-sm"><X size={14}/></button>
              </div>
              <div className="modal-body">
                <p className="text-sm text-slate-600">
                  Are you sure you want to delete <strong className="text-slate-900">{confirmDelete.username}</strong>?
                  This action cannot be undone.
                </p>
              </div>
              <div className="modal-footer">
                <button onClick={() => setConfirmDelete(null)} className="btn-secondary">Cancel</button>
                <button onClick={handleDelete} className="btn-danger">Delete User</button>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
};

export default Users;
