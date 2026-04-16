import React, { useContext, useEffect, useState } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import api from '../services/api';
import { Plus, Trash2, CheckCircle2 } from 'lucide-react';

const emptyRule = () => ({ title: '', description: '' });

const Normes = () => {
  const { user } = useContext(UserContext);
  const isAdmin = user?.role === 'ADMIN';
  const [normes, setNormes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [formOpen, setFormOpen] = useState(false);
  const [form, setForm] = useState({
    name: '',
    description: '',
    rules: [emptyRule()],
  });

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

  const handleFormChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleRuleChange = (index, field, value) => {
    setForm((current) => ({
      ...current,
      rules: current.rules.map((rule, idx) => (idx === index ? { ...rule, [field]: value } : rule)),
    }));
  };

  const addRule = () => {
    setForm((current) => ({ ...current, rules: [...current.rules, emptyRule()] }));
  };

  const removeRule = (index) => {
    setForm((current) => ({
      ...current,
      rules: current.rules.filter((_, idx) => idx !== index),
    }));
  };

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError('');
    setSaving(true);

    try {
      await api.post('/normes/', form);
      setForm({ name: '', description: '', rules: [emptyRule()] });
      setFormOpen(false);
      fetchNormes();
    } catch (err) {
      console.error(err);
      setError(err?.response?.data?.detail || err?.response?.data || 'Unable to save norme.');
    } finally {
      setSaving(false);
    }
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
              onClick={() => setFormOpen((open) => !open)}
              className="inline-flex items-center gap-2 rounded-3xl bg-sky-600 px-5 py-3 text-white shadow-lg shadow-sky-600/15 transition hover:bg-sky-700"
            >
              <Plus size={18} />
              {formOpen ? 'Hide form' : 'Create norme'}
            </button>
          ) : (
            <div className="rounded-3xl border border-slate-200 bg-slate-50 px-5 py-4 text-sm text-slate-600">
              Seuls les administrateurs peuvent créer de nouvelles normes.
            </div>
          )}
        </div>

        {formOpen && isAdmin && (
          <form onSubmit={handleSubmit} className="space-y-6 rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            {error && <div className="rounded-2xl bg-rose-50 p-4 text-sm text-rose-700">{error}</div>}

            <div className="space-y-4">
              <label className="space-y-2 text-sm text-slate-700">
                Norme name
                <input
                  value={form.name}
                  onChange={(e) => handleFormChange('name', e.target.value)}
                  className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                  required
                />
              </label>
            </div>

            <label className="space-y-2 text-sm text-slate-700">
              Description
              <textarea
                value={form.description}
                onChange={(e) => handleFormChange('description', e.target.value)}
                className="w-full rounded-3xl border border-slate-300 bg-slate-50 px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                rows={4}
              />
            </label>

            <div className="space-y-4">
              <div className="flex items-center justify-between gap-3">
                <h2 className="text-lg font-semibold text-slate-900">Rules</h2>
                <button
                  type="button"
                  onClick={addRule}
                  className="inline-flex items-center gap-2 rounded-3xl border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 transition hover:border-slate-300"
                >
                  <Plus size={16} /> Add rule
                </button>
              </div>

              {form.rules.map((rule, index) => (
                <div key={index} className="rounded-3xl border border-slate-200 bg-slate-50 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-semibold text-slate-900">Rule {index + 1}</p>
                    {form.rules.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeRule(index)}
                        className="inline-flex items-center gap-2 rounded-3xl bg-rose-100 px-3 py-2 text-sm text-rose-700 transition hover:bg-rose-200"
                      >
                        <Trash2 size={14} /> Remove
                      </button>
                    )}
                  </div>

                  <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <label className="space-y-2 text-sm text-slate-700">
                      Rule title
                      <input
                        value={rule.title}
                        onChange={(event) => handleRuleChange(index, 'title', event.target.value)}
                        className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                        required
                      />
                    </label>

                    <label className="space-y-2 text-sm text-slate-700">
                      Summary
                      <input
                        value={rule.description}
                        onChange={(event) => handleRuleChange(index, 'description', event.target.value)}
                        className="w-full rounded-3xl border border-slate-300 bg-white px-4 py-3 text-sm outline-none transition focus:border-sky-500"
                      />
                    </label>
                  </div>
                </div>
              ))}
            </div>

            <button
              type="submit"
              disabled={saving}
              className="inline-flex items-center gap-2 rounded-3xl bg-sky-600 px-6 py-3 text-white transition hover:bg-sky-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <CheckCircle2 size={18} />
              {saving ? 'Saving...' : 'Create norme'}
            </button>
          </form>
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
                    <div className="inline-flex items-center gap-2 rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold text-sky-700">
                      {norme.rules?.length || 0} rules
                    </div>
                  </div>
                  {norme.description && <p className="mt-4 text-sm leading-6 text-slate-600">{norme.description}</p>}

                  {norme.rules?.length > 0 && (
                    <div className="mt-6 space-y-3">
                      {norme.rules.map((rule) => (
                        <div key={rule.id} className="rounded-3xl border border-slate-100 bg-slate-50 p-4">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-sm font-semibold text-slate-900">{rule.title}</p>
                            <CheckCircle2 size={18} className="text-sky-500" />
                          </div>
                          {rule.description && <p className="mt-2 text-sm text-slate-600">{rule.description}</p>}
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
