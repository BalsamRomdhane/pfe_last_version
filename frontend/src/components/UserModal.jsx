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
    first_name: '',
    last_name: '',
    email: '',
    date_naissance: '',
    password: '',
    role: 'EMPLOYEE',
    department: '',
    is_first_login: true,
  });

  const [validationError, setValidationError] = useState('');
  const [fieldErrors, setFieldErrors] = useState({});

  // ✅ FIX CRITIQUE (ANTI LOOP)
  useEffect(() => {
    if (!open) return;

    if (mode === 'edit' && initialData) {
      // ensure date is in YYYY-MM-DD for <input type="date">
      let dateVal = initialData.date_naissance || '';
      if (dateVal && dateVal.includes('T')) dateVal = dateVal.split('T')[0];
      setForm({
        first_name: initialData.first_name || '',
        last_name: initialData.last_name || '',
        email: initialData.email || '',
        date_naissance: dateVal,
        password: '',
        role: initialData.role || 'EMPLOYEE',
        department: initialData.department || '',
        is_first_login: typeof initialData.is_first_login === 'boolean' ? initialData.is_first_login : true,
      });
    } else {
      setForm({
        first_name: '',
        last_name: '',
        email: '',
        date_naissance: '',
        password: '',
        role: 'EMPLOYEE',
        department: ''
      });
    }

    setValidationError('');
    setFieldErrors({});

  }, [open, mode, initialData]); // ✅ dépendances stables uniquement

  const showDepartmentField = form.role !== 'ADMIN';

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setForm(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value,
    }));
  };

  // update fieldErrors when parent passes an error object
  useEffect(() => {
    if (!error) return;
    // error may be { detail: { field: [msg] } } or { error: 'Invalid input', detail: {...} }
    const errObj = typeof error === 'object' ? (error.detail || error) : null;
    if (errObj && typeof errObj === 'object') {
      const mapped = {};
      Object.keys(errObj).forEach((k) => {
        try {
          const v = errObj[k];
          mapped[k] = Array.isArray(v) ? v.join(' ') : String(v);
        } catch (e) {
          mapped[k] = String(errObj[k]);
        }
      });
      setFieldErrors(mapped);
    } else {
      setFieldErrors({});
    }
  }, [error]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (!form.first_name.trim() || !form.last_name.trim() || !form.email.trim() || !form.date_naissance.trim()) {
      setValidationError('Prénom, nom, email et date de naissance sont requis.');
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
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
          role: form.role,
          ...(showDepartmentField ? { department: form.department } : { department: null }),
          is_first_login: form.is_first_login,
        }
      : {
          first_name: form.first_name.trim(),
          last_name: form.last_name.trim(),
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
        {error && (
          <div className="text-red-500 mb-2">
            {typeof error === 'string' ? error : (error.error || JSON.stringify(error))}
          </div>
        )}
        {validationError && <div className="text-orange-500 mb-2">{validationError}</div>}

        {/* FORM */}
        <form onSubmit={handleSubmit} className="space-y-4">

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div>
              <input
                name="first_name"
                placeholder="Prénom"
                value={form.first_name}
                onChange={handleChange}
                className="w-full border p-2 rounded"
              />
              {fieldErrors.first_name && (
                <div className="text-red-500 text-sm">{fieldErrors.first_name}</div>
              )}
            </div>
            <div>
              <input
                name="last_name"
                placeholder="Nom"
                value={form.last_name}
                onChange={handleChange}
                className="w-full border p-2 rounded"
              />
              {fieldErrors.last_name && (
                <div className="text-red-500 text-sm">{fieldErrors.last_name}</div>
              )}
            </div>
          </div>

          <input
            name="email"
            placeholder="Email"
            value={form.email}
            onChange={handleChange}
            className="w-full border p-2 rounded"
            disabled={mode === 'edit'}
          />
          {fieldErrors.email && (
            <div className="text-red-500 text-sm">{fieldErrors.email}</div>
          )}

          <div>
            <label className="text-sm text-gray-600">Date de naissance</label>
            <input
              name="date_naissance"
              type="date"
              value={form.date_naissance}
              onChange={handleChange}
              className="w-full border p-2 rounded"
            />
            {fieldErrors.date_naissance && (
              <div className="text-red-500 text-sm mt-1">{fieldErrors.date_naissance}</div>
            )}
          </div>

          {mode === 'edit' && (
            <div className="flex items-center gap-2">
              <input
                id="is_first_login"
                name="is_first_login"
                type="checkbox"
                checked={form.is_first_login}
                onChange={handleChange}
                className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
              />
              <label htmlFor="is_first_login" className="text-sm text-gray-700">
                Première connexion
              </label>
            </div>
          )}

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
              {fieldErrors.password && (
                <div className="text-red-500 text-sm">{fieldErrors.password}</div>
              )}
              <p className="text-xs text-gray-500 mt-1">
                Laissez vide pour générer automatiquement le mot de passe à partir du prénom et de la date de naissance.
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