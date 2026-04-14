import React, { useEffect, useState, useMemo } from 'react';
import { X, CheckCircle2 } from 'lucide-react';

const UserModal = ({
  open,
  mode,
  initialData = {},
  roles = [],
  departments = [],
  onClose,
  onSubmit,
  loading,
  error
}) => {

  const title = mode === 'edit' ? 'Edit User' : 'Create User';

  // ✅ MEMO ROLES (évite re-render inutile)
  const availableRoles = useMemo(() => {
    return roles.length > 0 ? roles : ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'];
  }, [roles]);

  // ✅ STATE
  const [form, setForm] = useState({
    username: '',
    nom: '',
    email: '',
    date_naissance: '',
    password: '',
    role: 'EMPLOYEE',
    department: ''
  });

  const [validationError, setValidationError] = useState('');

  // ✅ FIX CRITIQUE (ANTI LOOP)
  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && initialData) {
      setForm({
        username: initialData.username || '',
        nom: initialData.last_name || initialData.username || '',
        email: initialData.email || '',
        date_naissance: initialData.date_naissance || '',
        password: '',
        role: initialData.role || 'EMPLOYEE',
        department: initialData.department || ''
      });
    } else {
      setForm({
        username: '',
        nom: '',
        email: '',
        date_naissance: '',
        password: '',
        role: 'EMPLOYEE',
        department: ''
      });
    }

    setValidationError('');

  }, [open, mode, initialData]); // ✅ dépendances stables uniquement

  const showDepartmentField = form.role !== 'ADMIN';

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.username.trim() || !form.nom.trim() || !form.email.trim() || !form.date_naissance.trim()) {
      setValidationError('Username, nom, email, and date de naissance are required.');
      return;
    }

    if (mode === 'create' && !form.password.trim()) {
      // password may be generated automatically by backend, but allow initial input if provided
      // no error here
    }

    if (showDepartmentField && !form.department) {
      setValidationError('Department required for non-admin.');
      return;
    }

    setValidationError('');

    const payload = mode === 'edit'
      ? {
          first_name: form.nom.trim(),
          last_name: form.nom.trim(),
          role: form.role,
          ...(showDepartmentField ? { department: form.department } : { department: null }),
        }
      : {
          username: form.username.trim(),
          nom: form.nom.trim(),
          email: form.email.trim(),
          date_naissance: form.date_naissance.trim(),
          ...(form.password.trim() ? { password: form.password.trim() } : {}),
          role: form.role,
          ...(showDepartmentField ? { department: form.department } : {}),
        };

    await onSubmit(payload);
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">

      <div className="bg-white w-full max-w-lg rounded-2xl shadow-xl p-6">

        {/* HEADER */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-bold">{title}</h2>
          <button onClick={onClose}>
            <X />
          </button>
        </div>

        {/* ERRORS */}
        {error && <div className="text-red-500 mb-2">{error}</div>}
        {validationError && <div className="text-orange-500 mb-2">{validationError}</div>}

        {/* FORM */}
        <form onSubmit={handleSubmit} className="space-y-4">

          <input
            name="username"
            placeholder="Username"
            value={form.username}
            onChange={handleChange}
            className="w-full border p-2 rounded"
            disabled={mode === 'edit'}
          />

          <input
            name="nom"
            placeholder="Nom"
            value={form.nom}
            onChange={handleChange}
            className="w-full border p-2 rounded"
          />

          <input
            name="email"
            placeholder="Email"
            value={form.email}
            onChange={handleChange}
            className="w-full border p-2 rounded"
            disabled={mode === 'edit'}
          />

          <input
            name="date_naissance"
            placeholder="Date de naissance (DD/MM/YYYY)"
            value={form.date_naissance}
            onChange={handleChange}
            className="w-full border p-2 rounded"
          />

          {mode === 'create' && (
            <>
              <input
                name="password"
                type="password"
                placeholder="Password (laisser vide pour génération automatique)"
                value={form.password}
                onChange={handleChange}
                className="w-full border p-2 rounded"
              />
              <p className="text-xs text-gray-500 mt-1">
                Laissez vide pour générer automatiquement le mot de passe à partir du username et de la date de naissance.
              </p>
            </>
          )}

          <select
            name="role"
            value={form.role}
            onChange={handleChange}
            className="w-full border p-2 rounded"
          >
            {availableRoles.map(r => (
              <option key={r}>{r}</option>
            ))}
          </select>

          {showDepartmentField && (
            <select
              name="department"
              value={form.department}
              onChange={handleChange}
              className="w-full border p-2 rounded"
            >
              <option value="">Select Department</option>
              {departments.map((d) => (
                <option key={d.code} value={d.code}>
                  {d.name}
                </option>
              ))}
            </select>
          )}

          {/* ACTIONS */}
          <div className="flex justify-end gap-3">
            <button type="button" onClick={onClose}>
              Cancel
            </button>

            <button
              type="submit"
              className="bg-blue-600 text-white px-4 py-2 rounded flex items-center gap-2"
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Save'}
              <CheckCircle2 size={16} />
            </button>
          </div>

        </form>
      </div>
    </div>
  );
};

export default UserModal;