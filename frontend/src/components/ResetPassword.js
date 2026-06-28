import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { ShieldCheck, Eye, EyeOff, AlertCircle, CheckCircle2, ArrowRight } from 'lucide-react';
import api from '../services/api';

const ResetPassword = () => {
  const navigate  = useNavigate();
  const location  = useLocation();
  const token     = new URLSearchParams(location.search).get('token') || '';

  const [form,    setForm]    = useState({ new_password: '', confirm_password: '' });
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState('');
  const [success, setSuccess] = useState('');
  const [showPw,  setShowPw]  = useState({ new: false, confirm: false });

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(''); setSuccess('');
    if (!token)                                          return setError('Reset token is missing or invalid.');
    if (!form.new_password || !form.confirm_password)   return setError('Please fill in both password fields.');
    if (form.new_password !== form.confirm_password)    return setError('Passwords do not match.');
    setLoading(true);
    try {
      const res = await api.post('/auth/reset-password/', {
        token,
        new_password: form.new_password,
        confirm_password: form.confirm_password,
      });
      setSuccess(res.data?.message || 'Password updated successfully.');
      setTimeout(() => navigate('/login'), 1800);
    } catch (err) {
      setError(err.response?.data?.detail || err.response?.data?.error || 'Unable to reset password.');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-brand-600/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md animate-fade-in">
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.04] p-8 shadow-2xl backdrop-blur-xl">

          {/* Brand */}
          <div className="flex flex-col items-center gap-4 mb-8">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg shadow-brand-600/30">
              <ShieldCheck size={28} className="text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold text-white">Reset Password</h1>
              <p className="text-sm text-slate-400 mt-1">Enter your new password below.</p>
            </div>
          </div>

          {error   && <div className="flex gap-2 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 mb-5"><AlertCircle size={15} className="text-red-400 shrink-0 mt-0.5"/><p className="text-sm text-red-300">{error}</p></div>}
          {success && <div className="flex gap-2 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 mb-5"><CheckCircle2 size={15} className="text-emerald-400 shrink-0 mt-0.5"/><p className="text-sm text-emerald-300">{success}</p></div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            {[
              { id: 'new_password',     label: 'New password',     key: 'new'     },
              { id: 'confirm_password', label: 'Confirm password', key: 'confirm' },
            ].map(f => (
              <div key={f.id}>
                <label htmlFor={f.id} className="block text-sm font-medium text-slate-300 mb-1.5">{f.label}</label>
                <div className="relative">
                  <input
                    id={f.id}
                    name={f.id}
                    type={showPw[f.key] ? 'text' : 'password'}
                    value={form[f.id]}
                    onChange={handleChange}
                    disabled={loading}
                    autoComplete={f.id === 'new_password' ? 'new-password' : 'new-password'}
                    className="w-full rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2.5 pr-11 text-sm text-white
                               focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 outline-none transition-all
                               disabled:opacity-50"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPw(prev => ({ ...prev, [f.key]: !prev[f.key] }))}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"
                  >
                    {showPw[f.key] ? <EyeOff size={16}/> : <Eye size={16}/>}
                  </button>
                </div>
              </div>
            ))}

            <button
              type="submit"
              disabled={loading || !form.new_password || !form.confirm_password}
              className="w-full flex items-center justify-center gap-2 rounded-xl bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white shadow-lg transition-all hover:bg-brand-500 disabled:opacity-50 mt-2"
            >
              {loading ? (
                <><span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white"/>Updating…</>
              ) : (
                <>Update Password <ArrowRight size={15}/></>
              )}
            </button>
          </form>

          <p className="mt-8 text-center text-xs text-slate-600">© {new Date().getFullYear()} Enterprise Compliance Platform</p>
        </div>
      </div>
    </div>
  );
};

export default ResetPassword;
