import React, { useContext, useState, useEffect, useMemo } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import { Edit3, Trash2, Plus } from 'lucide-react';
import api from '../services/api';
import UserModal from './UserModal';

const roleClasses = {
  ADMIN: 'bg-orange-100 text-orange-800',
  TEAMLEAD: 'bg-blue-100 text-blue-800',
  EMPLOYEE: 'bg-slate-100 text-slate-800',
};

const Users = () => {
  const { user } = useContext(UserContext);

  const [users, setUsers] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('ALL');
  const [deptFilter, setDeptFilter] = useState('ALL');

  const [modalOpen, setModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState(null);
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [modalError, setModalError] = useState('');
  const [modalLoading, setModalLoading] = useState(false);
  const [toast, setToast] = useState(null);

  // ✅ SAFE FETCH
  useEffect(() => {
    fetchUsers();
    fetchDepartments();
  }, []);

  const fetchUsers = async () => {
    try {
      const res = await api.get('/rbac/users/');
      let data = res.data?.data || res.data || [];

      if (!Array.isArray(data)) data = [];

      // 🔥 LIMIT DATA TO PREVENT CRASH
      setUsers(data.slice(0, 200));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const fetchDepartments = async () => {
    try {
      const res = await api.get('/rbac/departments/');
      let data = res.data?.data || res.data || [];
      if (!Array.isArray(data)) data = [];
      setDepartments(data);
    } catch (err) {}
  };

  // ✅ SAFE FILTER
  const filteredUsers = useMemo(() => {
    return users.filter((u) => {
      const text = `${u.username} ${u.email} ${u.department} ${u.role}`.toLowerCase();

      return (
        text.includes(searchTerm.toLowerCase()) &&
        (roleFilter === 'ALL' || u.role === roleFilter) &&
        (deptFilter === 'ALL' || u.department === deptFilter)
      );
    });
  }, [users, searchTerm, roleFilter, deptFilter]);

  const roles = ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'];
  const departmentsList = departments.map((d) => d.name);

  const handleDelete = async () => {
    if (!confirmDelete) return;

    try {
      await api.delete(`/rbac/users/${confirmDelete.id}/`);
      setConfirmDelete(null);
      fetchUsers();
    } catch (err) {
      console.error(err);
    }
  };

  const getSubmitError = (err) => {
    const detail = err?.response?.data?.detail;
    const error = err?.response?.data?.error;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (typeof error === 'string' && error.trim()) return error;
    if (detail && typeof detail === 'object') return JSON.stringify(detail);
    return err?.message || 'Unable to save user. Please try again.';
  };

  const handleModalSubmit = async (payload) => {
    setModalError('');
    setModalLoading(true);

    try {
      if (selectedUser) {
        await api.put(`/rbac/users/${selectedUser.id}/`, payload);
        showToast('User updated successfully.');
      } else {
        const response = await api.post('/rbac/users/', payload);
        const generatedPassword = response.data?.generated_password;
        const keycloakWarning = response.data?.keycloak_created === false
          ? ' (Keycloak creation may have failed.)'
          : '';

        if (generatedPassword) {
          showToast(`User created. Password: ${generatedPassword}${keycloakWarning}`);
        } else {
          showToast(`User created successfully.${keycloakWarning}`);
        }
      }
      setModalOpen(false);
      setSelectedUser(null);
      fetchUsers();
    } catch (err) {
      console.error('User save error', err?.response?.data || err);
      setModalError(getSubmitError(err));
    } finally {
      setModalLoading(false);
    }
  };

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    window.setTimeout(() => setToast(null), 3800);
  };

  if (user?.role !== 'ADMIN') {
    return (
      <Layout>
        <div className="p-10">Access Denied</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">

        {/* HEADER */}
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">Users</h1>

          <button
            onClick={() => {
              setSelectedUser(null);
              setModalOpen(true);
            }}
            className="bg-blue-600 text-white px-4 py-2 rounded-lg flex gap-2"
          >
            <Plus size={16} /> Create
          </button>
        </div>

        {/* FILTERS */}
        <div className="flex gap-3">
          <input
            placeholder="Search..."
            className="border p-2 rounded w-full"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />

          <select onChange={(e) => setRoleFilter(e.target.value)} className="border p-2">
            <option value="ALL">Role</option>
            {roles.map((r) => <option key={r}>{r}</option>)}
          </select>

          <select onChange={(e) => setDeptFilter(e.target.value)} className="border p-2">
            <option value="ALL">Department</option>
            {departmentsList.map((d) => <option key={d}>{d}</option>)}
          </select>
        </div>

        {/* TABLE */}
        <div className="bg-white shadow rounded-xl overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-100">
              <tr>
                <th className="p-3">Username</th>
                <th>Email</th>
                <th>Role</th>
                <th>Department</th>
                <th>Actions</th>
              </tr>
            </thead>

            <tbody>
              {loading ? (
                <tr><td colSpan="5" className="text-center p-6">Loading...</td></tr>
              ) : filteredUsers.map((u) => (
                <tr key={u.id} className="border-t">
                  <td className="p-3">{u.username}</td>
                  <td>{u.email}</td>

                  <td>
                    <span className={`px-2 py-1 rounded text-xs ${roleClasses[u.role]}`}>
                      {u.role}
                    </span>
                  </td>

                  <td>{u.department || 'Global'}</td>

                  <td className="flex gap-2 p-3">
                    <button
                      onClick={() => {
                        setSelectedUser(u);
                        setModalOpen(true);
                      }}
                      className="bg-blue-500 text-white px-2 py-1 rounded"
                    >
                      <Edit3 size={14} />
                    </button>

                    <button
                      onClick={() => setConfirmDelete(u)}
                      className="bg-red-500 text-white px-2 py-1 rounded"
                    >
                      <Trash2 size={14} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* MODAL */}
        {modalOpen && (
          <UserModal
            open={modalOpen}
            mode={selectedUser ? 'edit' : 'create'}
            initialData={selectedUser || {}}
            roles={roles}
            departments={departments}
            onClose={() => {
              setModalOpen(false);
              setSelectedUser(null);
              setModalError('');
            }}
            onSubmit={handleModalSubmit}
            loading={modalLoading}
            error={modalError}
          />
        )}

        {/* DELETE */}
        {confirmDelete && (
          <div className="fixed inset-0 flex items-center justify-center bg-black/40">
            <div className="bg-white p-6 rounded-xl">
              <p>Delete {confirmDelete.username}?</p>
              <div className="flex gap-3 mt-4">
                <button onClick={() => setConfirmDelete(null)}>Cancel</button>
                <button onClick={handleDelete} className="text-red-600">
                  Confirm
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </Layout>
  );
};

export default Users;