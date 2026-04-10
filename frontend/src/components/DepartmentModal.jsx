import React, { useEffect, useState } from 'react';
import { X, CheckCircle2 } from 'lucide-react';

const DepartmentModal = ({ open, mode, initialData = {}, onClose, onSubmit, loading, error }) => {
  const isView = mode === 'view';
  const title = mode === 'edit' ? 'Edit Department' : mode === 'create' ? 'Add Department' : 'Department details';

  const [form, setForm] = useState({
    name: '',
    code: '',
    description: '',
    theme_color: '#0ea5e9',
  });
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    if (initialData && (mode === 'edit' || mode === 'view')) {
      setForm({
        name: initialData.name || '',
        code: initialData.code || '',
        description: initialData.description || '',
        theme_color: initialData.theme_color || '#0ea5e9',
      });
      setValidationError('');
    } else if (mode === 'create') {
      setForm({
        name: '',
        code: '',
        description: '',
        theme_color: '#0ea5e9',
      });
      setValidationError('');
    }
  }, [initialData, mode, open]);

  const handleChange = (event) => {
    const { name, value } = event.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!form.name.trim() || !form.code.trim()) {
      setValidationError('Name and code are required.');
      return;
    }
    setValidationError('');
    await onSubmit({
      name: form.name.trim(),
      code: form.code.trim(),
      description: form.description.trim(),
      theme_color: form.theme_color,
    });
  };

  if (!open) {
    return null;
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 px-4 py-6">
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl bg-white shadow-2xl ring-1 ring-slate-200">
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div>
            <h2 className="text-xl font-semibold text-slate-900">{title}</h2>
            {mode !== 'view' && <p className="text-sm text-slate-500">Fill in the department details below.</p>}
          </div>
          <button type="button" onClick={onClose} className="rounded-full p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900">
            <X size={20} />
          </button>
        </div>

        <div className="px-6 py-6">
          {error && (
            <div className="mb-4 rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              {error}
            </div>
          )}
          {validationError && (
            <div className="mb-4 rounded-2xl border border-orange-200 bg-orange-50 p-4 text-sm text-orange-700">
              {validationError}
            </div>
          )}

          {isView ? (
            <div className="space-y-4">
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Name</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{form.name}</p>
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Code</p>
                <p className="mt-2 text-lg font-semibold text-slate-900">{form.code}</p>
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Description</p>
                <p className="mt-2 text-slate-700">{form.description || 'No description provided.'}</p>
              </div>
              <div>
                <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Theme color</p>
                <div className="mt-2 flex items-center gap-3">
                  <span className="text-lg font-semibold text-slate-900">{form.theme_color}</span>
                  <span className="h-8 w-8 rounded-full border" style={{ backgroundColor: form.theme_color }} />
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="mt-6 inline-flex items-center justify-center gap-2 rounded-2xl bg-slate-900 px-4 py-2 text-sm font-semibold text-white transition hover:bg-slate-800"
              >
                Close
              </button>
            </div>
          ) : (
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="grid gap-4 sm:grid-cols-2">
                <label className="block">
                  <span className="text-sm font-medium text-slate-700">Name</span>
                  <input
                    name="name"
                    value={form.name}
                    onChange={handleChange}
                    className="mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </label>
                <label className="block">
                  <span className="text-sm font-medium text-slate-700">Code</span>
                  <input
                    name="code"
                    value={form.code}
                    onChange={handleChange}
                    className="mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                  />
                </label>
              </div>

              <label className="block">
                <span className="text-sm font-medium text-slate-700">Description</span>
                <textarea
                  name="description"
                  value={form.description}
                  onChange={handleChange}
                  rows="4"
                  className="mt-2 w-full rounded-2xl border border-slate-300 bg-slate-50 px-4 py-3 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-slate-700">Theme color</span>
                <input
                  type="color"
                  name="theme_color"
                  value={form.theme_color}
                  onChange={handleChange}
                  className="mt-2 h-14 w-20 rounded-xl border border-slate-300 bg-white p-2"
                />
              </label>

              <div className="flex flex-col gap-3 pt-4 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100"
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center justify-center gap-2 rounded-2xl bg-blue-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-70"
                  disabled={loading}
                >
                  {loading ? 'Saving...' : mode === 'edit' ? 'Update Department' : 'Create Department'}
                  <CheckCircle2 size={16} />
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default DepartmentModal;
