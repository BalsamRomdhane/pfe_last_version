import React, { useContext, useState, useEffect, useMemo } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import {
  Building,
  ArrowRight,
  Search,
  Plus,
  Edit3,
  Trash2,
  Eye,
  Loader2,
} from 'lucide-react';
import api from '../services/api';
import DepartmentModal from './DepartmentModal';

const Departments = () => {
  const { user } = useContext(UserContext);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [toast, setToast] = useState(null);
  const [modalState, setModalState] = useState({ open: false, mode: 'create', department: null });
  const [viewDepartment, setViewDepartment] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [modalError, setModalError] = useState('');

  useEffect(() => {
    fetchDepartments();
  }, []);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 3800);
  };

  const fetchDepartments = async () => {
    try {
      setLoading(true);
      const response = await api.get('/rbac/departments/');
      const payload = response.data;
      const departmentList = Array.isArray(payload) ? payload : payload?.data || [];
      setDepartments(departmentList);
      setError('');
    } catch (err) {
      setError('Unable to load departments.');
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setModalError('');
    setModalState({ open: true, mode: 'create', department: null });
  };

  const openEditModal = (department) => {
    setModalError('');
    setModalState({ open: true, mode: 'edit', department });
  };

  const openViewModal = (department) => {
    setViewDepartment(department);
  };

  const closeModal = () => {
    setModalState({ open: false, mode: 'create', department: null });
    setModalError('');
  };

  const closeViewModal = () => {
    setViewDepartment(null);
  };

  const handleModalSubmit = async (departmentData) => {
    if (!departmentData.name || !departmentData.code) {
      setModalError('Name and code are required.');
      return;
    }

    try {
      setActionLoading(true);
      if (modalState.mode === 'create') {
        await api.post('/rbac/departments/', departmentData);
        showToast('Department created successfully.');
      } else if (modalState.department?.code) {
        await api.put(`/rbac/departments/${modalState.department.code}/`, departmentData);
        showToast('Department updated successfully.');
      } else {
        throw new Error('Invalid department selected for update.');
      }
      closeModal();
      fetchDepartments();
    } catch (err) {
      setModalError('Unable to save department. Please try again.');
    } finally {
      setActionLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!confirmDelete) {
      return;
    }

    try {
      setActionLoading(true);
      await api.delete(`/rbac/departments/${confirmDelete.code}/`);
      showToast('Department deleted successfully.');
      setConfirmDelete(null);
      fetchDepartments();
    } catch (err) {
      setError('Unable to delete department.');
    } finally {
      setActionLoading(false);
    }
  };

  const filteredDepartments = useMemo(() => {
    return departments.filter((dept) =>
      dept.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      dept.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (dept.description || '').toLowerCase().includes(searchTerm.toLowerCase())
    );
  }, [departments, searchTerm]);

  if (user?.role !== 'ADMIN') {
    return (
      <Layout>
        <div className="rounded-xl bg-white p-10 shadow">
          <h2 className="text-2xl font-semibold">Access Denied</h2>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        {toast && (
          <div className={`rounded-3xl px-5 py-4 shadow ${toast.type === 'error' ? 'bg-red-50 text-red-700' : 'bg-emerald-50 text-emerald-700'}`}>
            {toast.message}
          </div>
        )}

        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <h1 className="text-3xl font-bold">Departments</h1>
            <p className="mt-1 text-sm text-slate-500">Manage the corporate department catalog and theme settings.</p>
          </div>
          <button
            type="button"
            onClick={openCreateModal}
            className="inline-flex items-center gap-2 rounded-2xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700"
          >
            <Plus size={16} /> Add Department
          </button>
        </div>

        <div className="flex items-center gap-2 rounded-3xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <Search size={18} className="text-slate-400" />
          <input
            type="text"
            placeholder="Search departments..."
            className="w-full bg-transparent text-sm text-slate-900 outline-none"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        {loading ? (
          <div className="rounded-3xl bg-white p-8 text-center text-slate-600 shadow-sm">Loading departments…</div>
        ) : error ? (
          <div className="rounded-3xl border border-red-200 bg-red-50 p-6 text-red-700">{error}</div>
        ) : filteredDepartments.length === 0 ? (
          <div className="rounded-3xl bg-white p-8 text-center text-slate-600 shadow-sm">No matching departments found.</div>
        ) : (
          <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
            {filteredDepartments.map((dept) => (
              <div
                key={dept.id || dept.code}
                className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-xl font-semibold text-slate-900">{dept.name}</h2>
                    <p className="mt-2 text-sm uppercase tracking-[0.2em] text-slate-500">{dept.code}</p>
                  </div>
                  <span className="flex h-10 w-10 items-center justify-center rounded-2xl bg-slate-100 text-slate-700" style={{ borderColor: dept.theme_color || '#0ea5e9', color: dept.theme_color || '#0ea5e9' }}>
                    <Building />
                  </span>
                </div>

                <p className="mt-5 text-slate-600">{dept.description || 'No description provided.'}</p>

                <div className="mt-6 flex flex-wrap gap-3">
                  <button
                    type="button"
                    onClick={() => openViewModal(dept)}
                    className="inline-flex items-center gap-2 rounded-2xl border border-slate-200 px-4 py-2 text-sm text-slate-700 transition hover:bg-slate-100"
                  >
                    <Eye size={16} /> View
                  </button>
                  <button
                    type="button"
                    onClick={() => openEditModal(dept)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
                  >
                    <Edit3 size={16} /> Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => setConfirmDelete(dept)}
                    className="inline-flex items-center gap-2 rounded-2xl bg-red-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-red-700"
                  >
                    <Trash2 size={16} /> Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        <DepartmentModal
          open={modalState.open}
          mode={modalState.mode}
          initialData={modalState.department || {}}
          onClose={closeModal}
          onSubmit={handleModalSubmit}
          loading={actionLoading}
          error={modalError}
        />

        <DepartmentModal
          open={Boolean(viewDepartment)}
          mode="view"
          initialData={viewDepartment || {}}
          onClose={closeViewModal}
          onSubmit={() => {}}
          loading={false}
          error=""
        />

        {confirmDelete && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/50 px-4 py-6">
            <div className="w-full max-w-lg rounded-3xl bg-white p-6 shadow-2xl ring-1 ring-slate-200">
              <h3 className="text-xl font-semibold text-slate-900">Delete department</h3>
              <p className="mt-3 text-slate-600">Are you sure you want to delete <span className="font-semibold">{confirmDelete.name}</span>? This action cannot be undone.</p>
              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={() => setConfirmDelete(null)}
                  className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
                  disabled={actionLoading}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleDelete}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-red-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-red-700 disabled:opacity-70"
                  disabled={actionLoading}
                >
                  {actionLoading ? 'Deleting...' : 'Delete'}
                  <Loader2 size={16} />
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
