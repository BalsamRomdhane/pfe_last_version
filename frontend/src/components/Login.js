/**
 * Login.js — Enterprise ISO Compliance Platform
 * Premium redesign — Capgemini x SaaS Enterprise UI
 *
 * Auth logic is unchanged. Only the interface is redesigned.
 */
import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldCheck, Eye, EyeOff, AlertCircle, ArrowRight,
  Mail, Lock, Loader2, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { UserContext } from '../context/UserContext';
import api from '../services/api';

/* ── Animation variants ─────────────────────────────────────────── */
const fadeUp = {
  hidden:  { opacity: 0, y: 20 },
  visible: (d = 0) => ({ opacity: 1, y: 0, transition: { duration: 0.5, delay: d, ease: [0.22, 1, 0.36, 1] } }),
};
const fadeIn = {
  hidden:  { opacity: 0 },
  visible: (d = 0) => ({ opacity: 1, transition: { duration: 0.4, delay: d } }),
};

/* ── Floating orb ───────────────────────────────────────────────── */
function Orb({ className }) {
  return (
    <motion.div
      className={`absolute rounded-full blur-3xl pointer-events-none ${className}`}
      animate={{ scale: [1, 1.15, 1], opacity: [0.4, 0.65, 0.4] }}
      transition={{ duration: 8, repeat: Infinity, ease: 'easeInOut' }}
    />
  );
}

/* ── Mesh grid overlay ──────────────────────────────────────────── */
function MeshGrid() {
  return (
    <svg
      className="absolute inset-0 w-full h-full opacity-[0.04] pointer-events-none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse">
          <path d="M 40 0 L 0 0 0 40" fill="none" stroke="white" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#grid)" />
    </svg>
  );
}

/* ── Security badge ─────────────────────────────────────────────── */
function SecurityBadge({ icon: Icon, label }) {
  return (
    <div className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1">
      <Icon size={10} className="text-brand-400 shrink-0" />
      <span className="text-2xs text-slate-500 font-medium">{label}</span>
    </div>
  );
}

/* ── Caps Lock indicator ────────────────────────────────────────── */
function useCapsLock() {
  const [caps, setCaps] = useState(false);
  useEffect(() => {
    const h = (e) => setCaps(e.getModifierState?.('CapsLock') ?? false);
    window.addEventListener('keydown', h);
    window.addEventListener('keyup', h);
    return () => { window.removeEventListener('keydown', h); window.removeEventListener('keyup', h); };
  }, []);
  return caps;
}

/* ── Input field ────────────────────────────────────────────────── */
function InputField({ id, name, type, value, onChange, disabled, placeholder, autoComplete, autoFocus, icon: Icon, rightSlot, label, capsWarning }) {
  const [focused, setFocused] = useState(false);
  const hasValue = value.length > 0;

  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-slate-300 mb-2">
        {label}
      </label>
      <div className={`
        relative rounded-xl border transition-all duration-200
        ${focused
          ? 'border-brand-500 shadow-[0_0_0_3px_rgba(37,99,235,0.18)]'
          : hasValue
            ? 'border-white/20 shadow-none'
            : 'border-white/10 shadow-none'
        }
        bg-white/[0.06] overflow-hidden
      `}>
        {/* Left icon */}
        <div className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 ${focused ? 'text-brand-400' : 'text-slate-500'}`}>
          <Icon size={16} />
        </div>

        <input
          id={id}
          name={name}
          type={type}
          value={value}
          onChange={onChange}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          disabled={disabled}
          autoComplete={autoComplete}
          autoFocus={autoFocus}
          placeholder={placeholder}
          aria-label={label}
          className="
            w-full bg-transparent pl-10 pr-11 py-3 text-sm text-white
            placeholder:text-slate-600 outline-none
            disabled:opacity-50 disabled:cursor-not-allowed
          "
        />

        {/* Right slot */}
        {rightSlot && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            {rightSlot}
          </div>
        )}

        {/* Focus glow line */}
        <motion.div
          className="absolute bottom-0 left-0 h-px bg-gradient-to-r from-brand-600 via-brand-400 to-violet-500"
          initial={{ scaleX: 0 }}
          animate={{ scaleX: focused ? 1 : 0 }}
          transition={{ duration: 0.25 }}
          style={{ transformOrigin: 'left' }}
        />
      </div>

      {/* Caps Lock warning */}
      <AnimatePresence>
        {capsWarning && (
          <motion.p
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-1.5 flex items-center gap-1.5 text-xs text-amber-400"
          >
            <AlertTriangle size={11} /> Caps Lock is on
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Main Login component ───────────────────────────────────────── */
const Login = () => {
  const navigate       = useNavigate();
  const { login }      = useContext(UserContext);
  const [form,          setForm]         = useState({ login: '', password: '' });
  const [loading,       setLoading]      = useState(false);
  const [error,         setError]        = useState('');
  const [showPassword,  setShowPassword] = useState(false);
  const capsLock = useCapsLock();
  const btnRef = useRef(null);

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm(prev => ({ ...prev, [name]: value }));
    if (error) setError('');
  }, [error]);

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

  const version = process.env.REACT_APP_VERSION || '1.0.0';
  const env     = process.env.NODE_ENV === 'production' ? 'Production' : 'Development';

  return (
    <div className="relative min-h-screen overflow-hidden flex flex-col items-center justify-center p-4"
         style={{ background: 'linear-gradient(135deg, #020617 0%, #0a0f2e 40%, #0c1a3d 70%, #060b1f 100%)' }}>

      {/* ── Background ── */}
      <MeshGrid />

      {/* Orbs */}
      <Orb className="h-[600px] w-[600px] -top-48 -left-48 bg-brand-900/60" />
      <Orb className="h-[500px] w-[500px] -bottom-32 -right-32 bg-violet-900/40" />
      <Orb className="h-[300px] w-[300px] top-1/3 left-1/2 -translate-x-1/2 bg-cyan-900/20" />

      {/* Particle dots */}
      {[...Array(12)].map((_, i) => (
        <motion.div
          key={i}
          className="absolute h-1 w-1 rounded-full bg-brand-400/30"
          style={{
            left:  `${10 + (i * 7.5) % 85}%`,
            top:   `${5  + (i * 11)  % 90}%`,
          }}
          animate={{ opacity: [0, 0.6, 0], scale: [0.5, 1.2, 0.5] }}
          transition={{ duration: 3 + (i % 3), repeat: Infinity, delay: i * 0.4, ease: 'easeInOut' }}
        />
      ))}

      {/* ── Top Capgemini banner ── */}
      <motion.div
        variants={fadeIn} initial="hidden" animate="visible" custom={0}
        className="relative z-10 mb-8 flex items-center gap-2"
      >
        <div className="h-px w-12 bg-gradient-to-r from-transparent to-white/20" />
        <span className="text-xs font-semibold tracking-[0.2em] uppercase text-slate-500">
          Capgemini Innovation Lab
        </span>
        <div className="h-px w-12 bg-gradient-to-l from-transparent to-white/20" />
      </motion.div>

      {/* ── Main card ── */}
      <motion.div
        variants={fadeUp} initial="hidden" animate="visible" custom={0.05}
        className="relative z-10 w-full max-w-md"
      >
        {/* Glow ring behind card */}
        <div className="absolute -inset-px rounded-2xl bg-gradient-to-br from-brand-600/30 via-violet-600/10 to-transparent blur-sm pointer-events-none" />

        <div
          className="relative rounded-2xl border border-white/[0.08] p-8 shadow-2xl overflow-hidden"
          style={{ background: 'rgba(10,14,40,0.85)', backdropFilter: 'blur(24px) saturate(1.4)' }}
        >
          {/* Card inner glow */}
          <div className="absolute inset-0 bg-gradient-to-br from-brand-900/20 via-transparent to-violet-900/10 pointer-events-none rounded-2xl" />

          {/* ── Header ── */}
          <motion.div variants={fadeUp} custom={0.1} className="relative flex flex-col items-center gap-4 mb-8">
            {/* Logo ring */}
            <div className="relative">
              <motion.div
                className="absolute inset-0 rounded-2xl bg-brand-500/30 blur-lg"
                animate={{ opacity: [0.3, 0.7, 0.3], scale: [0.9, 1.1, 0.9] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              />
              <div className="relative flex h-16 w-16 items-center justify-center rounded-2xl shadow-xl"
                   style={{ background: 'linear-gradient(135deg, #1d4ed8, #2563eb, #3b82f6)' }}>
                <ShieldCheck size={32} className="text-white" />
              </div>
              {/* Verified badge */}
              <div className="absolute -bottom-1 -right-1 flex h-5 w-5 items-center justify-center rounded-full bg-emerald-500 shadow-lg">
                <CheckCircle2 size={11} className="text-white" />
              </div>
            </div>

            <div className="text-center space-y-1">
              <h1 className="text-2xl font-bold text-white tracking-tight">
                Enterprise ISO Compliance
              </h1>
              <p className="text-sm text-slate-400 font-medium">
                AI-Powered Governance &amp; Document Intelligence
              </p>
              <div className="flex items-center justify-center gap-1.5 mt-2">
                <div className="h-px w-8 bg-gradient-to-r from-transparent to-brand-500/50" />
                <span className="text-xs font-semibold tracking-wider text-brand-400/80 uppercase">
                  Powered by Capgemini
                </span>
                <div className="h-px w-8 bg-gradient-to-l from-transparent to-brand-500/50" />
              </div>
            </div>
          </motion.div>

          {/* ── Error message ── */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div
                key="error"
                initial={{ opacity: 0, y: -8, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, scale: 0.97 }}
                transition={{ duration: 0.2 }}
                role="alert"
                className="flex items-start gap-3 rounded-xl border border-red-500/25 bg-red-500/[0.08] px-4 py-3 mb-5"
              >
                <AlertCircle size={16} className="text-red-400 mt-0.5 shrink-0" />
                <p className="text-sm text-red-300 leading-relaxed">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Form ── */}
          <motion.form
            variants={fadeUp} custom={0.15}
            onSubmit={handleSubmit}
            className="relative space-y-4"
            noValidate
          >
            {/* Email / username */}
            <InputField
              id="login"
              name="login"
              type="text"
              value={form.login}
              onChange={handleChange}
              disabled={loading}
              autoComplete="username"
              autoFocus
              placeholder="email@capgemini.com"
              icon={Mail}
              label="Email or username"
            />

            {/* Password */}
            <InputField
              id="password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={form.password}
              onChange={handleChange}
              disabled={loading}
              autoComplete="current-password"
              placeholder="••••••••••••"
              icon={Lock}
              label="Password"
              capsWarning={capsLock && form.password.length > 0}
              rightSlot={
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  disabled={loading}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500 rounded"
                >
                  <motion.span
                    key={showPassword ? 'off' : 'on'}
                    initial={{ opacity: 0, scale: 0.7, rotate: -15 }}
                    animate={{ opacity: 1, scale: 1, rotate: 0 }}
                    transition={{ duration: 0.18 }}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </motion.span>
                </button>
              }
            />

            {/* Submit */}
            <motion.button
              ref={btnRef}
              type="submit"
              disabled={loading || !form.login || !form.password}
              whileHover={{ scale: 1.015 }}
              whileTap={{ scale: 0.985 }}
              className="
                relative w-full mt-2 flex items-center justify-center gap-2.5
                rounded-xl px-5 py-3 text-sm font-semibold text-white
                overflow-hidden
                disabled:opacity-50 disabled:cursor-not-allowed
                transition-all duration-200
                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent
              "
              style={{ background: loading ? 'linear-gradient(135deg,#1e40af,#1d4ed8)' : 'linear-gradient(135deg,#1d4ed8 0%,#2563eb 50%,#3b82f6 100%)' }}
            >
              {/* Shimmer effect on hover */}
              <motion.span
                className="absolute inset-0 bg-gradient-to-r from-transparent via-white/10 to-transparent"
                initial={{ x: '-100%' }}
                whileHover={{ x: '100%' }}
                transition={{ duration: 0.5 }}
              />

              {/* Shadow glow */}
              <span className="absolute inset-0 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ boxShadow: '0 8px 30px rgba(37,99,235,0.5)' }} />

              <AnimatePresence mode="wait">
                {loading ? (
                  <motion.span key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="flex items-center gap-2.5">
                    <Loader2 size={16} className="animate-spin" />
                    Authenticating…
                  </motion.span>
                ) : (
                  <motion.span key="idle" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                    className="relative flex items-center gap-2.5">
                    Sign In to Platform
                    <ArrowRight size={16} />
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.button>
          </motion.form>

          {/* ── Security badges ── */}
          <motion.div
            variants={fadeIn} custom={0.3}
            className="relative mt-6 pt-5 border-t border-white/[0.06]"
          >
            <p className="text-center text-2xs text-slate-600 uppercase tracking-widest mb-3 font-semibold">
              Secured connection
            </p>
            <div className="flex flex-wrap items-center justify-center gap-2">
              <SecurityBadge icon={ShieldCheck} label="JWT Authentication" />
              <SecurityBadge icon={ShieldCheck} label="Keycloak Protected" />
              <SecurityBadge icon={ShieldCheck} label="ISO Compliance" />
            </div>
          </motion.div>

          {/* ── System info ── */}
          <motion.div variants={fadeIn} custom={0.35}
            className="relative mt-4 flex items-center justify-center gap-3 flex-wrap">
            <span className="text-2xs text-slate-700">v{version}</span>
            <span className="text-slate-800">·</span>
            <span className="text-2xs text-slate-700">{env}</span>
            <span className="text-slate-800">·</span>
            <span className="text-2xs text-slate-700">AI-Powered</span>
          </motion.div>
        </div>
      </motion.div>

      {/* ── Footer ── */}
      <motion.footer
        variants={fadeIn} initial="hidden" animate="visible" custom={0.4}
        className="relative z-10 mt-8 text-center space-y-1"
      >
        <p className="text-xs text-slate-600 font-medium">
          © {new Date().getFullYear()} Enterprise ISO Compliance Platform
        </p>
        <p className="text-xs text-slate-700">
          Developed during Capgemini Internship · PFE 2025–2026
        </p>
        <p className="text-2xs text-slate-800 mt-1">
          Version {version} · All rights reserved
        </p>
      </motion.footer>
    </div>
  );
};

export default Login;
