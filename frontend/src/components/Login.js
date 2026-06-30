/**
 * Login.js — Enterprise ISO Compliance Platform
 * Glassmorphism centered card — Capgemini Enterprise SaaS
 * Auth logic unchanged.
 */
import React, { useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye, EyeOff, AlertCircle, ArrowRight, Mail, Lock,
  Loader2, AlertTriangle,
} from 'lucide-react';
import { UserContext } from '../context/UserContext';
import api from '../services/api';
import capgeminiLogo from '../Capgemini_Logo.png';

function useCapsLock() {
  const [caps, setCaps] = useState(false);
  useEffect(() => {
    const h = e => setCaps(e.getModifierState?.('CapsLock') ?? false);
    window.addEventListener('keydown', h);
    window.addEventListener('keyup', h);
    return () => { window.removeEventListener('keydown', h); window.removeEventListener('keyup', h); };
  }, []);
  return caps;
}

function Field({ id, name, type, value, onChange, disabled, placeholder, autoComplete, autoFocus, Icon, right, label, capsWarn }) {
  const [focus, setFocus] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-400 mb-1.5 tracking-wide">{label}</label>
      <div className={`relative rounded-xl overflow-hidden border transition-all duration-200
        ${focus ? 'border-blue-400/50 shadow-[0_0_0_3px_rgba(59,130,246,0.14)]' : 'border-white/[0.1]'}
        bg-white/[0.06]`}>
        <span className={`absolute left-3.5 top-1/2 -translate-y-1/2 pointer-events-none transition-colors duration-150 ${focus ? 'text-blue-400' : 'text-slate-500'}`}>
          <Icon size={15}/>
        </span>
        <input id={id} name={name} type={type} value={value} onChange={onChange}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          disabled={disabled} autoComplete={autoComplete} autoFocus={autoFocus}
          placeholder={placeholder} aria-label={label}
          className="w-full bg-transparent pl-9 pr-10 py-3 text-sm text-white placeholder:text-slate-600 outline-none disabled:opacity-40"/>
        {right && <span className="absolute right-3 top-1/2 -translate-y-1/2">{right}</span>}
        <motion.span className="absolute bottom-0 left-0 h-px bg-gradient-to-r from-blue-600 via-blue-400 to-cyan-400"
          initial={{ scaleX: 0 }} animate={{ scaleX: focus ? 1 : 0 }}
          transition={{ duration: 0.22 }} style={{ transformOrigin: 'left' }}/>
      </div>
      <AnimatePresence>
        {capsWarn && (
          <motion.p initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }}
            className="mt-1 flex items-center gap-1 text-xs text-amber-400/80">
            <AlertTriangle size={10}/> Caps Lock is on
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ─── Premium background — 6 depth layers ──────────────────────── */
function Bg() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none" aria-hidden="true">

      {/* ── Layer 1: Mesh gradient base ── */}
      <div className="absolute inset-0" style={{
        background: [
          'radial-gradient(ellipse 90% 60% at 15% 10%, rgba(6,182,212,0.07) 0%, transparent 55%)',
          'radial-gradient(ellipse 70% 70% at 85% 85%, rgba(37,99,235,0.18) 0%, transparent 60%)',
          'radial-gradient(ellipse 60% 50% at 50% 50%, rgba(99,102,241,0.06) 0%, transparent 65%)',
          'radial-gradient(ellipse 80% 40% at 0% 100%, rgba(37,99,235,0.12) 0%, transparent 55%)',
          '#04061a',
        ].join(', '),
      }}/>
      {/* Animated mesh shift */}
      <motion.div className="absolute inset-0" style={{
        background: 'radial-gradient(ellipse 50% 40% at 70% 20%, rgba(6,182,212,0.06) 0%, transparent 60%)',
      }}
        animate={{ opacity: [0.4, 0.9, 0.4], scale: [1, 1.06, 1] }}
        transition={{ duration: 14, repeat: Infinity, ease: 'easeInOut' }}/>

      {/* ── Layer 2: Glow halos ── */}
      {/* Cyan top-left */}
      <motion.div className="absolute pointer-events-none"
        style={{ top: '-10%', left: '-8%', width: '42vw', height: '42vw', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(6,182,212,0.11) 0%, transparent 68%)', filter: 'blur(1px)' }}
        animate={{ opacity: [0.5, 0.85, 0.5], scale: [1, 1.07, 1] }}
        transition={{ duration: 11, repeat: Infinity, ease: 'easeInOut' }}/>
      {/* Blue bottom-right */}
      <motion.div className="absolute pointer-events-none"
        style={{ bottom: '-12%', right: '-10%', width: '50vw', height: '50vw', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(37,99,235,0.15) 0%, transparent 65%)', filter: 'blur(1px)' }}
        animate={{ opacity: [0.4, 0.8, 0.4], scale: [1, 1.09, 1] }}
        transition={{ duration: 13, repeat: Infinity, ease: 'easeInOut', delay: 2 }}/>
      {/* Diffuse center glow behind card */}
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
        style={{ width: '36vw', height: '36vw', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59,130,246,0.06) 0%, transparent 70%)', filter: 'blur(20px)' }}/>
      {/* Violet top-right accent */}
      <motion.div className="absolute pointer-events-none"
        style={{ top: '5%', right: '5%', width: '22vw', height: '22vw', borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(139,92,246,0.07) 0%, transparent 65%)' }}
        animate={{ opacity: [0.3, 0.65, 0.3] }}
        transition={{ duration: 9, repeat: Infinity, ease: 'easeInOut', delay: 3 }}/>

      {/* ── Layer 3: Orbital rings ── */}
      {/* Ring A — large, off-center bottom-right, slow CW */}
      <motion.div className="absolute pointer-events-none" style={{
        bottom: '-18%', right: '-12%',
        width: '68vw', height: '68vw', borderRadius: '50%',
        border: '1px solid rgba(59,130,246,0.1)',
        boxShadow: '0 0 24px rgba(59,130,246,0.06)',
      }} animate={{ rotate: 360 }} transition={{ duration: 55, repeat: Infinity, ease: 'linear' }}/>
      {/* Ring B — medium, partial top-left, CCW */}
      <motion.div className="absolute pointer-events-none" style={{
        top: '-22%', left: '-14%',
        width: '56vw', height: '56vw', borderRadius: '50%',
        border: '1px solid rgba(6,182,212,0.09)',
        boxShadow: '0 0 18px rgba(6,182,212,0.04)',
      }} animate={{ rotate: -360 }} transition={{ duration: 70, repeat: Infinity, ease: 'linear' }}/>
      {/* Ring C — inner, near card, very faint */}
      <motion.div className="absolute pointer-events-none" style={{
        top: '30%', left: '22%',
        width: '32vw', height: '32vw', borderRadius: '50%',
        border: '0.5px solid rgba(148,163,184,0.07)',
      }} animate={{ rotate: 360 }} transition={{ duration: 90, repeat: Infinity, ease: 'linear', delay: 5 }}/>
      {/* Ring D — off-screen bottom-left */}
      <motion.div className="absolute pointer-events-none" style={{
        bottom: '-25%', left: '-18%',
        width: '44vw', height: '44vw', borderRadius: '50%',
        border: '0.5px solid rgba(99,102,241,0.08)',
      }} animate={{ rotate: -360 }} transition={{ duration: 80, repeat: Infinity, ease: 'linear', delay: 10 }}/>
      {/* Ring E — thin, top-center, partial */}
      <motion.div className="absolute pointer-events-none" style={{
        top: '-35%', left: '30%',
        width: '38vw', height: '38vw', borderRadius: '50%',
        border: '0.5px solid rgba(37,99,235,0.08)',
      }} animate={{ rotate: 360 }} transition={{ duration: 100, repeat: Infinity, ease: 'linear', delay: 7 }}/>

      {/* ── Layer 4: Particles ── */}
      {[...Array(22)].map((_, i) => {
        const size   = i % 5 === 0 ? 2 : 1;
        const colors = ['rgba(147,197,253,0.5)', 'rgba(6,182,212,0.4)', 'rgba(167,139,250,0.35)', 'rgba(148,163,184,0.3)'];
        const color  = colors[i % colors.length];
        const dur    = 4 + (i % 5) * 1.5;
        const twinkle = i % 3 === 0;
        return (
          <motion.div key={i}
            className="absolute rounded-full pointer-events-none"
            style={{ width: size, height: size, background: color, left: `${4+(i*4.3)%92}%`, top: `${3+(i*7.9)%94}%` }}
            animate={twinkle
              ? { opacity: [0, 1, 0.3, 1, 0], y: [0, -6, 0] }
              : { opacity: [0, 0.7, 0], y: [0, -4, 0] }
            }
            transition={{ duration: dur, repeat: Infinity, delay: i * 0.3, ease: 'easeInOut' }}/>
        );
      })}

      {/* ── Layer 5: Curved abstract lines ── */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg"
           style={{ opacity: 0.055 }}>
        <defs>
          <linearGradient id="lg1" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="transparent"/>
            <stop offset="40%" stopColor="#3b82f6"/>
            <stop offset="60%" stopColor="#06b6d4"/>
            <stop offset="100%" stopColor="transparent"/>
          </linearGradient>
          <linearGradient id="lg2" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0%" stopColor="transparent"/>
            <stop offset="50%" stopColor="#6366f1"/>
            <stop offset="100%" stopColor="transparent"/>
          </linearGradient>
        </defs>
        {/* Orbit arc — bottom sweep */}
        <path d="M -80 620 Q 300 400 760 580 T 1500 520" fill="none" stroke="url(#lg1)" strokeWidth="0.8"/>
        {/* Secondary arc */}
        <path d="M -50 720 Q 400 520 900 680 T 1600 640" fill="none" stroke="url(#lg1)" strokeWidth="0.4"/>
        {/* Top diagonal */}
        <path d="M 100 -20 Q 500 180 900 80 T 1500 200" fill="none" stroke="url(#lg2)" strokeWidth="0.6"/>
        {/* Circuit-like right side */}
        <path d="M 1200 100 Q 1350 300 1280 500 T 1400 750" fill="none" stroke="url(#lg1)" strokeWidth="0.5"/>
      </svg>

      {/* ── Grid texture ── */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg"
           style={{ opacity: 0.022 }}>
        <defs>
          <pattern id="grd" width="48" height="48" patternUnits="userSpaceOnUse">
            <path d="M48 0L0 0 0 48" fill="none" stroke="white" strokeWidth="0.5"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#grd)"/>
      </svg>

    </div>
  );
}

/* ═══════════════════════════════════════════════════════════ */
const Login = () => {
  const navigate = useNavigate();
  const { login } = useContext(UserContext);
  const [form, setForm]     = useState({ login: '', password: '' });
  const [loading, setLoad]  = useState(false);
  const [error, setError]   = useState('');
  const [showPw, setShowPw] = useState(false);
  const caps = useCapsLock();

  const onChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm(p => ({ ...p, [name]: value }));
    if (error) setError('');
  }, [error]);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.login || !form.password) { setError('Please enter your credentials.'); return; }
    setLoad(true); setError('');
    try {
      const res = await api.post('/auth/login/', { login: form.login, password: form.password });
      login(res.data.access_token, res.data.user);
      navigate('/dashboard');
    } catch (err) {
      setError(
        err.response?.data?.detail ||
        err.response?.data?.error  ||
        (typeof err.response?.data === 'string' ? err.response.data : null) ||
        'Invalid credentials. Please try again.'
      );
      setForm(p => ({ ...p, password: '' }));
    } finally { setLoad(false); }
  };

  const ver = process.env.REACT_APP_VERSION || '1.0.0';

  return (
    <div className="relative min-h-screen flex flex-col items-center justify-center p-4 sm:p-6 overflow-hidden">
      <Bg/>

      {/* ── Floating card ── */}
      <motion.div
        initial={{ opacity: 0, y: 24, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.65, ease: [0.22, 1, 0.36, 1] }}
        className="relative z-10 w-full max-w-[420px]"
      >
        {/* Outer glow */}
        <div className="absolute -inset-px rounded-2xl pointer-events-none"
             style={{ background: 'linear-gradient(135deg, rgba(59,130,246,0.2), rgba(6,182,212,0.08), transparent)', borderRadius: '1rem' }}/>

        {/* Card */}
        <div className="relative rounded-2xl px-8 py-9 sm:px-10"
             style={{
               background: 'rgba(10, 14, 38, 0.72)',
               backdropFilter: 'blur(28px) saturate(1.6)',
               WebkitBackdropFilter: 'blur(28px) saturate(1.6)',
               border: '1px solid rgba(255,255,255,0.09)',
               boxShadow: '0 32px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(59,130,246,0.07), inset 0 1px 0 rgba(255,255,255,0.06)',
             }}>

          {/* Inner top glow */}
          <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-px pointer-events-none"
               style={{ background: 'linear-gradient(90deg, transparent, rgba(99,179,237,0.35), transparent)' }}/>

          {/* ── Header ── */}
          <motion.div
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.12, duration: 0.5, ease: [0.22,1,0.36,1] }}
            className="flex flex-col items-center mb-8 text-center"
          >
            {/* Capgemini logo */}
            <div className="relative mb-4">
              <motion.div className="absolute inset-0 rounded-xl blur-xl opacity-30 pointer-events-none"
                style={{ background: 'radial-gradient(circle, rgba(59,130,246,0.5), transparent)' }}
                animate={{ opacity: [0.2, 0.45, 0.2] }}
                transition={{ duration: 4, repeat: Infinity }}/>
              <div className="relative rounded-xl px-5 py-3 border border-white/[0.08]"
                   style={{ background: 'rgba(255,255,255,0.05)', backdropFilter: 'blur(8px)' }}>
                <img src={capgeminiLogo} alt="Capgemini"
                     className="h-10 w-auto object-contain"
                     style={{ filter: 'brightness(0) invert(1)' }}/>
              </div>
            </div>

            <h1 className="text-xl font-bold text-white leading-snug mb-1 tracking-tight">
              Enterprise ISO Compliance
            </h1>
            <p className="text-xs text-slate-400 font-medium">
              AI-Powered Governance &amp; Document Intelligence
            </p>
          </motion.div>

          {/* ── Divider ── */}
          <div className="mb-6 h-px w-full"
               style={{ background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.07), transparent)' }}/>

          {/* ── Error ── */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div key="e"
                initial={{ opacity: 0, y: -6, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0 }} transition={{ duration: 0.18 }}
                role="alert"
                className="flex items-start gap-2.5 rounded-xl border border-red-500/20 bg-red-500/[0.07] px-3.5 py-2.5 mb-5">
                <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0"/>
                <p className="text-xs text-red-300 leading-relaxed">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ── Form ── */}
          <motion.form
            initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.18, duration: 0.5, ease: [0.22,1,0.36,1] }}
            onSubmit={onSubmit} className="space-y-4" noValidate>

            <Field id="login" name="login" type="text" value={form.login} onChange={onChange}
              disabled={loading} autoComplete="username" autoFocus
              placeholder="name@company.com" Icon={Mail} label="Email or username"/>

            <Field id="password" name="password" type={showPw ? 'text' : 'password'}
              value={form.password} onChange={onChange} disabled={loading}
              autoComplete="current-password" placeholder="Password"
              Icon={Lock} label="Password" capsWarn={caps && form.password.length > 0}
              right={
                <button type="button" onClick={() => setShowPw(v => !v)} disabled={loading}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  className="text-slate-500 hover:text-slate-300 transition-colors disabled:opacity-40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded p-0.5">
                  <AnimatePresence mode="wait">
                    <motion.span key={showPw ? 'h' : 's'}
                      initial={{ opacity: 0, scale: 0.8 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }}
                      transition={{ duration: 0.12 }}>
                      {showPw ? <EyeOff size={14}/> : <Eye size={14}/>}
                    </motion.span>
                  </AnimatePresence>
                </button>
              }/>

            {/* Submit */}
            <motion.button type="submit"
              disabled={loading || !form.login || !form.password}
              whileHover={{ scale: 1.01, boxShadow: '0 8px 30px rgba(37,99,235,0.5)' }}
              whileTap={{ scale: 0.99 }}
              className="relative w-full flex items-center justify-center gap-2 rounded-xl py-3 text-sm font-semibold text-white overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent mt-1"
              style={{ background: 'linear-gradient(135deg,#1e40af 0%,#2563eb 55%,#3b82f6 100%)', boxShadow: '0 4px 20px rgba(37,99,235,0.35)' }}>
              <motion.span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.07] to-transparent pointer-events-none"
                initial={{ x: '-100%' }} whileHover={{ x: '100%' }} transition={{ duration: 0.55 }}/>
              <AnimatePresence mode="wait">
                {loading
                  ? <motion.span key="l" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2"><Loader2 size={14} className="animate-spin"/>Signing in…</motion.span>
                  : <motion.span key="i" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2">Sign In<ArrowRight size={14}/></motion.span>
                }
              </AnimatePresence>
            </motion.button>
          </motion.form>
        </div>
      </motion.div>

      {/* ── Footer ── */}
      <motion.footer
        initial={{ opacity: 0 }} animate={{ opacity: 1 }}
        transition={{ delay: 0.45, duration: 0.5 }}
        className="relative z-10 mt-7 text-center space-y-0.5">
        <p className="text-xs text-white/20">© {new Date().getFullYear()} Enterprise ISO Compliance Platform</p>
        <p className="text-xs text-white/15">Developed during Capgemini Internship · PFE 2025–2026 · v{ver}</p>
      </motion.footer>
    </div>
  );
};

export default Login;