import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X, Plus } from 'lucide-react';
import RuleCard from './RuleCard';

const defaultRule = () => ({
  title: '',
  description: '',
  severity: '',
  condition: '',
  action: '',
  expanded: true,
});

const initialFormState = {
  name: '',
  description: '',
  rules: [defaultRule()],
};

const CreateNormeModal = ({ open, onClose, onSubmit, saving, initialData, error }) => {
  const [form, setForm] = useState(initialFormState);
  const [validationError, setValidationError] = useState('');

  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
      if (initialData) {
        setForm({
          name: initialData.name || '',
          description: initialData.description || '',
          rules: initialData.rules?.length > 0
            ? initialData.rules.map((rule) => ({
                ...defaultRule(),
                id: rule.id,
                title: rule.title,
                description: rule.description,
                severity: rule.severity || '',
                condition: rule.condition || '',
                action: rule.action || '',
              }))
            : [defaultRule()],
        });
      } else {
        setForm(initialFormState);
      }
      setValidationError('');
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [open, initialData]);

  const dirty = useMemo(() => {
    return JSON.stringify(form) !== JSON.stringify(initialFormState);
  }, [form]);

  const handleClose = useCallback(() => {
    if (dirty && !saving) {
      const confirmed = window.confirm('Vous avez des modifications non sauvegardées. Voulez-vous vraiment fermer ?');
      if (!confirmed) return;
    }
    onClose();
  }, [dirty, onClose, saving]);

  useEffect(() => {
    const handleEsc = (event) => {
      if (event.key === 'Escape' && open) {
        handleClose();
      }
    };
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }, [open, handleClose]);

  const handleFieldChange = (field, value) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleRuleChange = (index, field, value) => {
    setForm((current) => ({
      ...current,
      rules: current.rules.map((rule, idx) => (idx === index ? { ...rule, [field]: value } : rule)),
    }));
  };

  const validateForm = () => {
    if (!form.name.trim()) {
      setValidationError('Norm name is required.');
      return false;
    }

    for (let i = 0; i < form.rules.length; i += 1) {
      const rule = form.rules[i];
      if (!rule.title.trim()) {
        setValidationError(`Rule #${i + 1} needs a title.`);
        return false;
      }
      if (!rule.severity) {
        setValidationError(`Rule #${i + 1} needs a severity level.`);
        return false;
      }
    }
    setValidationError('');
    return true;
  };

  const addRule = () => {
    setForm((current) => ({ ...current, rules: [...current.rules, defaultRule()] }));
  };

  const removeRule = (index) => {
    setForm((current) => ({
      ...current,
      rules: current.rules.filter((_, idx) => idx !== index),
    }));
  };

  const handleSaveDraft = () => {
    if (!validateForm()) return;
    onSubmit(form, 'draft');
  };

  const handlePublish = () => {
    if (!validateForm()) return;
    onSubmit(form, 'publish');
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 px-4 py-8"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={handleClose}
        >
          <motion.div
            className="relative mx-auto w-full max-w-[950px] overflow-hidden rounded-[24px] bg-white shadow-2xl shadow-slate-400/30"
            initial={{ opacity: 0, scale: 0.96, y: 30 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 30 }}
            transition={{ duration: 0.2 }}
            onClick={(event) => event.stopPropagation()}
            style={{ maxHeight: '90vh' }}
          >
            <div className="flex items-start justify-between gap-4 border-b border-slate-200 bg-slate-50 px-6 py-5">
              <div className="max-w-3xl">
                <p className="text-xs uppercase tracking-[0.35em] text-sky-600">Create Compliance Norm</p>
                <h2 className="mt-3 text-2xl font-semibold text-slate-900">Create Compliance Norm</h2>
                <p className="mt-2 text-sm leading-6 text-slate-600">Define audit norms and rules with the same fields as before.</p>
              </div>
              <button
                type="button"
                onClick={handleClose}
                className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-slate-800 bg-slate-900 text-slate-300 transition hover:bg-slate-800"
                aria-label="Close modal"
              >
                <X size={20} />
              </button>
            </div>

            <div className="flex max-h-[calc(90vh-124px)] overflow-hidden">
              <div className="flex-1 overflow-y-auto p-6 bg-white">
                {error && (
                  <div className="mb-4 rounded-3xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
                    {error}
                  </div>
                )}
                {validationError && (
                  <div className="mb-4 rounded-3xl bg-rose-50 px-4 py-3 text-sm text-rose-700 ring-1 ring-rose-200">
                    {validationError}
                  </div>
                )}

                <div className="space-y-6">
                  <div className="grid gap-5 lg:grid-cols-1">
                    <label className="space-y-2 text-sm text-slate-700">
                      Norm name
                      <input
                        value={form.name}
                        onChange={(e) => handleFieldChange('name', e.target.value)}
                        placeholder="e.g. ISO 9001 Quality Standard"
                        className="w-full rounded-[24px] border border-slate-200 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition focus:border-sky-500"
                        required
                      />
                    </label>
                  </div>

                  <label className="space-y-2 text-sm text-slate-300">
                    Description
                    <textarea
                      value={form.description}
                      onChange={(e) => handleFieldChange('description', e.target.value)}
                      placeholder="Describe the compliance norm, audit scope and critical success criteria."
                      rows={5}
                      className="w-full rounded-[24px] border border-slate-200 bg-white px-4 py-4 text-sm text-slate-900 outline-none transition focus:border-sky-500"
                    />
                  </label>
                </div>

                <div className="space-y-6">
                  <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-5">
                    <p className="text-sm uppercase tracking-[0.3em] text-slate-500">Rules</p>
                    <p className="mt-2 text-sm leading-6 text-slate-600">Add compliance rules with a title and summary.</p>
                  </div>
                  <div className="space-y-4">
                    {form.rules.map((rule, index) => (
                      <RuleCard
                        key={`rule-${index}`}
                        rule={rule}
                        index={index}
                        onChange={handleRuleChange}
                        onRemove={removeRule}
                        canRemove={form.rules.length > 1}
                      />
                    ))}
                  </div>
                  <button
                    type="button"
                    onClick={addRule}
                    className="inline-flex items-center gap-2 rounded-[24px] border border-slate-700 bg-slate-900 px-5 py-3 text-sm font-semibold text-white transition hover:border-slate-500 hover:bg-slate-800"
                  >
                    <Plus size={16} />
                    Add rule
                  </button>
                </div>
              </div>
            </div>

            <div className="flex flex-col gap-4 border-t border-slate-200 bg-white px-6 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex items-center gap-3 text-sm text-slate-700">
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-3xl border border-slate-200 bg-white px-4 py-3 text-slate-900 transition hover:border-slate-300"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveDraft}
                  disabled={saving}
                  className="rounded-3xl border border-sky-500 bg-white px-4 py-3 text-sky-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Save Draft
                </button>
              </div>

              <div className="flex flex-wrap items-center gap-3 justify-end">
                <button
                  type="button"
                  onClick={handlePublish}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-3xl bg-blue-600 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {saving ? 'Saving...' : 'Create norme'}
                </button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default CreateNormeModal;
