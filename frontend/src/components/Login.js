/**
 * Login.js — Enterprise ISO Compliance Platform
 * Two-column SaaS Enterprise layout — Capgemini PFE 2025-2026
 * Auth logic unchanged. Interface only.
 */
import React, { useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye, EyeOff, AlertCircle, ArrowRight, Mail, Lock, Loader2,
  ShieldCheck, AlertTriangle, Brain, FileCheck2, Activity,
  GitBranch, ScanSearch, Shield,
} from 'lucide-react';
import { UserContext } from '../context/UserContext';
import api from '../services/api';
import capgeminiLogo from '../Capgemini_Logo.png';

/* ── Variants ─────────────────────────────────────────────────────────────── */
const easeOut = [0.22, 1, 0.36, 1];
const fadeUp  = (d = 0) => ({ hidden:{ opacity:0, y:24 }, visible:{ opacity:1, y:0, transition:{ duration:0.55, delay:d, ease:easeOut } } });
const fadeIn  = (d = 0) => ({ hidden:{ opacity:0 },       visible:{ opacity:1,     transition:{ duration:0.4,  delay:d } } });

/* ── Caps Lock ────────────────────────────────────────────────────────────── */
function useCapsLock() {
  const [caps, setCaps] = useState(false);
  useEffect(() => {
    const h = e => setCaps(e.getModifierState?.('CapsLock') ?? false);
    window.addEventListener('keydown', h);
    window.addEventListener('keyup',   h);
    return () => { window.removeEventListener('keydown', h); window.removeEventListener('keyup', h); };
  }, []);
  return caps;
}

/* ── Input ────────────────────────────────────────────────────────────────── */
function InputField({ id, name, type, value, onChange, disabled, placeholder, autoComplete, autoFocus, IconLeft, rightSlot, label, capsWarn }) {
  const [focused, setFocused] = useState(false);
  const filled = value.length > 0;
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-semibold uppercase tracking-wider text-slate-400 mb-1.5">{label}</label>
      <div className={`relative rounded-lg border transition-all duration-200 overflow-hidden
        ${focused ? 'border-brand-500/70 shadow-[0_0_0_3px_rgba(59,130,246,0.15)]' : filled ? 'border-white/20' : 'border-white/10'}
        bg-white/[0.05]`}>
        <div className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-200 ${focused ? 'text-brand-400' : 'text-slate-500'}`}>
          <IconLeft size={15}/>
        </div>
        <input id={id} name={name} type={type} value={value} onChange={onChange}
          onFocus={() => setFocused(true)} onBlur={() => setFocused(false)}
          disabled={disabled} autoComplete={autoComplete} autoFocus={autoFocus}
          placeholder={placeholder} aria-label={label}
          className="w-full bg-transparent pl-9 pr-10 py-2.5 text-sm text-white placeholder:text-slate-600 outline-none disabled:opacity-50 disabled:cursor-not-allowed"/>
        {rightSlot && <div className="absolute right-3 top-1/2 -translate-y-1/2">{rightSlot}</div>}
        <motion.div className="absolute bottom-0 left-0 h-[1.5px] bg-gradient-to-r from-brand-600 via-brand-400 to-violet-500"
          initial={{ scaleX:0 }} animate={{ scaleX: focused ? 1 : 0 }}
          transition={{ duration:0.22 }} style={{ transformOrigin:'left' }}/>
      </div>
      <AnimatePresence>
        {capsWarn && (
          <motion.p initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:'auto' }} exit={{ opacity:0, height:0 }}
            className="mt-1 flex items-center gap-1 text-xs text-amber-400">
            <AlertTriangle size={11}/> Caps Lock is on
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ── Feature item ─────────────────────────────────────────────────────────── */
function Feature({ icon: Icon, label, delay }) {
  return (
    <motion.div variants={fadeUp(delay)} className="flex items-center gap-3">
      <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-brand-500/15 border border-brand-500/20">
        <Icon size={14} className="text-brand-300"/>
      </div>
      <span className="text-sm text-slate-300/90 font-medium">{label}</span>
    </motion.div>
  );
}

/* ── Orb ──────────────────────────────────────────────────────────────────── */
function Orb({ cls }) {
  return (
    <motion.div className={`absolute rounded-full blur-3xl pointer-events-none ${cls}`}
      animate={{ scale:[1,1.2,1], opacity:[0.35,0.6,0.35] }}
      transition={{ duration:9, repeat:Infinity, ease:'easeInOut' }}/>
  );
}

/* ── Grid overlay ─────────────────────────────────────────────────────────── */
function Grid() {
  return (
    <svg className="absolute inset-0 w-full h-full pointer-events-none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id="g" width="44" height="44" patternUnits="userSpaceOnUse">
          <path d="M44 0L0 0 0 44" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5"/>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#g)"/>
    </svg>
  );
}

/* ── Particle ─────────────────────────────────────────────────────────────── */
function Particles() {
  return (
    <>
      {[...Array(14)].map((_,i) => (
        <motion.div key={i} className="absolute h-0.5 w-0.5 rounded-full bg-brand-300/40 pointer-events-none"
          style={{ left:`${8+(i*6.3)%86}%`, top:`${4+(i*9.7)%92}%` }}
          animate={{ opacity:[0,0.7,0], scale:[0.5,1.3,0.5] }}
          transition={{ duration:2.5+(i%4)*0.8, repeat:Infinity, delay:i*0.35, ease:'easeInOut' }}/>
      ))}
    </>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════ */
/*  Main Login                                                                 */
/* ═══════════════════════════════════════════════════════════════════════════ */
const Login = () => {
  const navigate = useNavigate();
  const { login } = useContext(UserContext);
  const [form, setForm]     = useState({ login:'', password:'' });
  const [loading, setLoad]  = useState(false);
  const [error, setError]   = useState('');
  const [showPw, setShowPw] = useState(false);
  const capsLock = useCapsLock();

  const handleChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm(p => ({ ...p, [name]:value }));
    if (error) setError('');
  }, [error]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.login || !form.password) { setError('Please enter your credentials.'); return; }
    setLoad(true); setError('');
    try {
      const res = await api.post('/auth/login/', { login:form.login, password:form.password });
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
      setForm(p => ({ ...p, password:'' }));
    } finally { setLoad(false); }
  };

  const ver = process.env.REACT_APP_VERSION || '1.0.0';
  const features = [
    { icon: ScanSearch,  label:'AI Document Analysis'    },
    { icon: FileCheck2,  label:'ISO 9001 / ISO 27001'    },
    { icon: Shield,      label:'Secure Authentication'   },
    { icon: Brain,       label:'Document Intelligence'   },
    { icon: GitBranch,   label:'MLOps Pipeline'          },
    { icon: Activity,    label:'Real-Time Monitoring'    },
  ];

  return (
    <div className="min-h-screen flex overflow-hidden"
         style={{ background:'linear-gradient(135deg,#020817 0%,#080d2e 50%,#050b20 100%)' }}>

      {/* ═══ LEFT — Hero (hidden on mobile) ════════════════════════════════ */}
      <div className="relative hidden lg:flex flex-col justify-between flex-1 p-12 xl:p-16 overflow-hidden">
        <Grid/>
        <Particles/>
        <Orb cls="h-[700px] w-[700px] -top-64 -left-64 bg-brand-800/50"/>
        <Orb cls="h-[500px] w-[500px] bottom-0 left-1/3 bg-violet-900/35"/>
        <Orb cls="h-[300px] w-[300px] top-1/2 right-0 bg-cyan-900/25"/>

        {/* Top brand */}
        <motion.div variants={fadeUp(0)} initial="hidden" animate="visible" className="relative z-10 flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-brand-600 shadow-lg shadow-brand-600/30">
            <ShieldCheck size={18} className="text-white"/>
          </div>
          <div>
            <p className="text-sm font-bold text-white leading-none">Enterprise ISO</p>
            <p className="text-xs text-slate-500 mt-0.5 leading-none">Compliance Platform</p>
          </div>
        </motion.div>

        {/* Center hero */}
        <div className="relative z-10 flex-1 flex flex-col justify-center py-12">
          <motion.div variants={fadeUp(0.05)} initial="hidden" animate="visible">
            <span className="inline-flex items-center gap-1.5 rounded-full border border-brand-500/30 bg-brand-500/10 px-3 py-1 text-xs font-semibold text-brand-300 mb-6">
              <span className="h-1.5 w-1.5 rounded-full bg-brand-400 animate-pulse"/>
              v{ver} — AI-Powered
            </span>
          </motion.div>

          <motion.h1 variants={fadeUp(0.1)} initial="hidden" animate="visible"
            className="text-4xl xl:text-5xl font-extrabold text-white leading-[1.15] tracking-tight mb-4">
            Enterprise ISO<br/>
            <span className="bg-gradient-to-r from-brand-300 via-blue-300 to-violet-300 bg-clip-text text-transparent">
              Compliance Platform
            </span>
          </motion.h1>

          <motion.p variants={fadeUp(0.15)} initial="hidden" animate="visible"
            className="text-base text-slate-400 leading-relaxed max-w-md mb-3 font-medium">
            AI-Powered Governance &amp; Document Intelligence
          </motion.p>

          <motion.p variants={fadeUp(0.2)} initial="hidden" animate="visible"
            className="text-sm text-slate-500 leading-relaxed max-w-sm mb-10">
            Enterprise platform designed to automate ISO compliance, intelligent document analysis and AI-assisted governance.
          </motion.p>

          {/* Feature grid */}
          <motion.div initial="hidden" animate="visible" className="grid grid-cols-2 gap-3 max-w-md">
            {features.map((f, i) => (
              <Feature key={f.label} icon={f.icon} label={f.label} delay={0.25 + i * 0.05}/>
            ))}
          </motion.div>
        </div>

        {/* Bottom capgemini */}
        <motion.div variants={fadeIn(0.5)} initial="hidden" animate="visible"
          className="relative z-10 flex items-center gap-3">
          <div className="flex-1 h-px bg-white/[0.06]"/>
          <div className="flex items-center gap-2.5">
            <span className="text-xs text-slate-600">Innovation Project —</span>
            <img src={capgeminiLogo} alt="Capgemini" className="h-4 w-auto object-contain opacity-30"
                 style={{ filter:'brightness(0) invert(1)' }}/>
          </div>
          <div className="flex-1 h-px bg-white/[0.06]"/>
        </motion.div>
      </div>

      {/* ═══ RIGHT — Login card ══════════════════════════════════════════════ */}
      <div className="relative flex flex-col items-center justify-center w-full lg:w-[480px] xl:w-[520px] shrink-0 p-6 sm:p-10 lg:border-l lg:border-white/[0.06]"
           style={{ background:'rgba(4,8,26,0.92)', backdropFilter:'blur(20px)' }}>

        {/* Mobile-only background effects */}
        <div className="absolute inset-0 lg:hidden pointer-events-none overflow-hidden">
          <Orb cls="h-96 w-96 -top-32 -right-32 bg-brand-900/50"/>
          <Orb cls="h-64 w-64 -bottom-16 -left-16 bg-violet-900/30"/>
          <Grid/>
          <Particles/>
        </div>

        <div className="relative z-10 w-full max-w-[400px]">

          {/* Card header */}
          <motion.div variants={fadeUp(0)} initial="hidden" animate="visible" className="mb-8 text-center lg:text-left">
            {/* Mobile: platform icon */}
            <div className="flex lg:hidden justify-center mb-5">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl shadow-xl"
                   style={{ background:'linear-gradient(135deg,#1d4ed8,#3b82f6)' }}>
                <ShieldCheck size={24} className="text-white"/>
              </div>
            </div>
            <h2 className="text-2xl font-bold text-white mb-1 tracking-tight">Sign in</h2>
            <p className="text-sm text-slate-500">
              Enterprise ISO Compliance Platform
            </p>
          </motion.div>

          {/* Error */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div key="err"
                initial={{ opacity:0, y:-6, scale:0.97 }} animate={{ opacity:1, y:0, scale:1 }}
                exit={{ opacity:0 }} transition={{ duration:0.18 }}
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-red-500/25 bg-red-500/[0.07] px-3.5 py-3 mb-5">
                <AlertCircle size={15} className="text-red-400 mt-0.5 shrink-0"/>
                <p className="text-sm text-red-300">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <motion.form variants={fadeUp(0.05)} initial="hidden" animate="visible"
            onSubmit={handleSubmit} className="space-y-4" noValidate>

            <InputField id="login" name="login" type="text" value={form.login}
              onChange={handleChange} disabled={loading}
              autoComplete="username" autoFocus placeholder="you@company.com"
              IconLeft={Mail} label="Email or username"/>

            <InputField id="password" name="password" type={showPw ? 'text' : 'password'}
              value={form.password} onChange={handleChange} disabled={loading}
              autoComplete="current-password" placeholder="••••••••••••"
              IconLeft={Lock} label="Password"
              capsWarn={capsLock && form.password.length > 0}
              rightSlot={
                <button type="button" onClick={() => setShowPw(v => !v)} disabled={loading}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                  className="text-slate-600 hover:text-slate-300 transition-colors disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-brand-500 rounded">
                  <AnimatePresence mode="wait">
                    <motion.span key={showPw ? 'off':'on'}
                      initial={{ opacity:0, scale:0.75 }} animate={{ opacity:1, scale:1 }} exit={{ opacity:0 }}
                      transition={{ duration:0.15 }}>
                      {showPw ? <EyeOff size={15}/> : <Eye size={15}/>}
                    </motion.span>
                  </AnimatePresence>
                </button>
              }/>

            {/* Submit */}
            <motion.button type="submit"
              disabled={loading || !form.login || !form.password}
              whileHover={{ scale:1.012, boxShadow:'0 8px 32px rgba(37,99,235,0.45)' }}
              whileTap={{ scale:0.988 }}
              transition={{ duration:0.15 }}
              className="relative w-full flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-semibold text-white overflow-hidden disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 focus-visible:ring-offset-2 focus-visible:ring-offset-transparent"
              style={{ background:'linear-gradient(135deg,#1e40af 0%,#2563eb 55%,#3b82f6 100%)', marginTop:'8px' }}>
              {/* Shimmer */}
              <motion.span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.08] to-transparent pointer-events-none"
                initial={{ x:'-100%' }} whileHover={{ x:'100%' }} transition={{ duration:0.55 }}/>
              <AnimatePresence mode="wait">
                {loading
                  ? <motion.span key="l" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2"><Loader2 size={15} className="animate-spin"/> Authenticating…</motion.span>
                  : <motion.span key="i" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2">Sign In <ArrowRight size={15}/></motion.span>
                }
              </AnimatePresence>
            </motion.button>
          </motion.form>

          {/* Divider */}
          <motion.div variants={fadeIn(0.2)} initial="hidden" animate="visible"
            className="mt-7 pt-5 border-t border-white/[0.07]">
            <div className="grid grid-cols-3 gap-2 text-center">
              {[['Secure','JWT + Keycloak'],['ISO Ready','9001 · 27001'],['AI-Powered','Document AI']].map(([h,s]) => (
                <div key={h} className="rounded-lg bg-white/[0.03] border border-white/[0.05] px-2 py-2.5">
                  <p className="text-xs font-semibold text-slate-300">{h}</p>
                  <p className="text-2xs text-slate-600 mt-0.5">{s}</p>
                </div>
              ))}
            </div>
          </motion.div>

          {/* Mobile Capgemini */}
          <motion.div variants={fadeIn(0.25)} initial="hidden" animate="visible"
            className="mt-6 flex items-center justify-center gap-2 lg:hidden">
            <span className="text-xs text-slate-700">Innovation Project —</span>
            <img src={capgeminiLogo} alt="Capgemini" className="h-3.5 w-auto opacity-25"
                 style={{ filter:'brightness(0) invert(1)' }}/>
          </motion.div>
        </div>

        {/* Footer */}
        <motion.footer variants={fadeIn(0.3)} initial="hidden" animate="visible"
          className="relative z-10 mt-auto pt-8 text-center">
          <p className="text-xs text-slate-700">© {new Date().getFullYear()} Enterprise ISO Compliance Platform</p>
          <p className="text-xs text-slate-800 mt-0.5">Developed during Capgemini Internship · PFE 2025–2026 · v{ver}</p>
        </motion.footer>
      </div>
    </div>
  );
};

export default Login;