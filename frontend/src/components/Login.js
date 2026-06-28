import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import api from '../services/api';
import {
  ShieldCheck, Eye, EyeOff, AlertCircle, ArrowRight,
} from 'lucide-react';

const Login = () => {
  const navigate        = useNavigate();
  const { login }       = useContext(UserContext);
  const [form,          setForm]         = useState({ login: '', password: '' });
  const [loading,       setLoading]      = useState(false);
  const [error,         setError]        = useState('');
  const [showPassword,  setShowPassword] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.login || !form.password) { setError('Please enter your credentials.'); return; }
    setLoading(true); setError('');
    try {
      const res = await api.post('/auth/login/', { login: form.login, password: form.password });
      const { access_token, user } = res.data;
      login(access_token, user);
      navigate('/dashboard');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.error  ||
        (typeof err.response?.data === 'string' ? err.response.data : null) ||
        'Invalid credentials. Please try again.'
      );
      setForm(prev => ({ ...prev, password: '' }));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 flex items-center justify-center p-4">

      {/* Background decorative elements */}
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -left-32 top-1/4 h-96 w-96 rounded-full bg-brand-600/10 blur-3xl" />
        <div className="absolute -right-32 bottom-1/4 h-96 w-96 rounded-full bg-violet-600/10 blur-3xl" />
      </div>

      <div className="relative w-full max-w-md animate-fade-in">

        {/* Card */}
        <div className="rounded-2xl border border-white/[0.08] bg-white/[0.04] p-8 shadow-2xl backdrop-blur-xl">

          {/* Brand */}
          <div className="flex flex-col items-center gap-4 mb-8">
            <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-600 shadow-lg shadow-brand-600/30">
              <ShieldCheck size={28} className="text-white" />
            </div>
            <div className="text-center">
              <h1 className="text-2xl font-bold text-white">Enterprise Platform</h1>
              <p className="text-sm text-slate-400 mt-1">Sign in to your account</p>
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="flex items-start gap-2.5 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3 mb-6">
              <AlertCircle size={15} className="text-red-400 mt-0.5 shrink-0" />
              <p className="text-sm text-red-300">{error}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Login field */}
            <div>
              <label htmlFor="login" className="block text-sm font-medium text-slate-300 mb-1.5">
                Email or username
              </label>
              <input
                id="login"
                name="login"
                type="text"
                value={form.login}
                onChange={handleChange}
                disabled={loading}
                autoComplete="username"
                autoFocus
                placeholder="Enter your email or username"
                className="w-full rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2.5 text-sm text-white placeholder:text-slate-500
                           transition-all focus:border-brand-500 focus:bg-white/[0.08] focus:ring-2 focus:ring-brand-500/20 outline-none
                           disabled:opacity-50 disabled:cursor-not-allowed"
              />
            </div>

            {/* Password field */}
            <div>
              <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-1.5">
                Password
              </label>
              <div className="relative">
                <input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  value={form.password}
                  onChange={handleChange}
                  disabled={loading}
                  autoComplete="current-password"
                  placeholder="Enter your password"
                  className="w-full rounded-xl border border-white/10 bg-white/[0.06] px-4 py-2.5 pr-11 text-sm text-white placeholder:text-slate-500
                             transition-all focus:border-brand-500 focus:bg-white/[0.08] focus:ring-2 focus:ring-brand-500/20 outline-none
                             disabled:opacity-50 disabled:cursor-not-allowed"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  disabled={loading}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading || !form.login || !form.password}
              className="
                w-full flex items-center justify-center gap-2 rounded-xl
                bg-brand-600 px-5 py-2.5 text-sm font-semibold text-white
                shadow-lg shadow-brand-600/25
                transition-all duration-150
                hover:bg-brand-500 hover:shadow-brand-600/40
                disabled:opacity-50 disabled:cursor-not-allowed disabled:shadow-none
                mt-2
              "
            >
              {loading ? (
                <>
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/30 border-t-white" />
                  Signing in…
                </>
              ) : (
                <>
                  Sign In
                  <ArrowRight size={15} />
                </>
              )}
            </button>
          </form>

          {/* Footer */}
          <p className="mt-8 text-center text-xs text-slate-600">
            © {new Date().getFullYear()} Enterprise Compliance Platform · Capgemini
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
