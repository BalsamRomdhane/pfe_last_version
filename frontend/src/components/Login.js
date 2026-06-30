/**
 * Login.js — Enterprise ISO Compliance Platform
 * Minimal two-column enterprise layout — Microsoft / Linear style
 * Auth logic unchanged.
 */
import React, { useCallback, useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Eye, EyeOff, AlertCircle, ArrowRight,
  Mail, Lock, Loader2, AlertTriangle, ShieldCheck,
} from 'lucide-react';
import { UserContext } from '../context/UserContext';
import api from '../services/api';
import capgeminiLogo from '../Capgemini_Logo.png';

/* ── Caps Lock ───────────────────────────────────────────────────────── */
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

/* ── Input ───────────────────────────────────────────────────────────── */
function Field({ id, name, type, value, onChange, disabled, placeholder, autoComplete, autoFocus, Icon, right, label, capsWarn }) {
  const [focus, setFocus] = useState(false);
  return (
    <div>
      <label htmlFor={id} className="block text-xs font-medium text-slate-400 mb-1.5 tracking-wide">
        {label}
      </label>
      <div className={`relative rounded-lg overflow-hidden border transition-all duration-200
        ${focus ? 'border-blue-500/60 shadow-[0_0_0_3px_rgba(59,130,246,0.12)]' : 'border-white/[0.09]'}
        bg-white/[0.04]`}>
        <span className={`absolute left-3.5 top-1/2 -translate-y-1/2 transition-colors duration-150 pointer-events-none ${focus ? 'text-blue-400' : 'text-slate-600'}`}>
          <Icon size={15}/>
        </span>
        <input id={id} name={name} type={type} value={value} onChange={onChange}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          disabled={disabled} autoComplete={autoComplete} autoFocus={autoFocus}
          placeholder={placeholder} aria-label={label}
          className="w-full bg-transparent pl-9 pr-10 py-2.5 text-sm text-white placeholder:text-slate-700 outline-none disabled:opacity-40"/>
        {right && <span className="absolute right-3 top-1/2 -translate-y-1/2">{right}</span>}
        <motion.span className="absolute bottom-0 left-0 h-px bg-gradient-to-r from-blue-600 to-blue-400"
          initial={{ scaleX:0 }} animate={{ scaleX: focus ? 1 : 0 }}
          transition={{ duration:0.2 }} style={{ transformOrigin:'left' }}/>
      </div>
      <AnimatePresence>
        {capsWarn && (
          <motion.p initial={{ opacity:0, height:0 }} animate={{ opacity:1, height:'auto' }} exit={{ opacity:0, height:0 }}
            className="mt-1 flex items-center gap-1 text-xs text-amber-400/80">
            <AlertTriangle size={10}/> Caps Lock is on
          </motion.p>
        )}
      </AnimatePresence>
    </div>
  );
}

/* ═══════════════════════════════════════ */
const Login = () => {
  const navigate = useNavigate();
  const { login } = useContext(UserContext);
  const [form, setForm]     = useState({ login:'', password:'' });
  const [loading, setLoad]  = useState(false);
  const [error,   setError] = useState('');
  const [showPw,  setShowPw]= useState(false);
  const caps = useCapsLock();

  const onChange = useCallback((e) => {
    const { name, value } = e.target;
    setForm(p => ({ ...p, [name]:value }));
    if (error) setError('');
  }, [error]);

  const onSubmit = async (e) => {
    e.preventDefault();
    if (!form.login || !form.password) { setError('Please enter your credentials.'); return; }
    setLoad(true); setError('');
    try {
      const res = await api.post('/auth/login/', { login:form.login, password:form.password });
      login(res.data.access_token, res.data.user);
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

  return (
    <div className="min-h-screen flex"
         style={{ background:'#06091a' }}>

      {/* ══ LEFT ══ */}
      <div className="relative hidden lg:flex flex-col justify-between flex-1 overflow-hidden select-none"
           style={{ background:'linear-gradient(160deg,#07091e 0%,#0b1230 60%,#060916 100%)' }}>

        {/* Subtle grid */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.035]" xmlns="http://www.w3.org/2000/svg">
          <defs>
            <pattern id="grid" width="48" height="48" patternUnits="userSpaceOnUse">
              <path d="M48 0L0 0 0 48" fill="none" stroke="white" strokeWidth="0.6"/>
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)"/>
        </svg>

        {/* Blue glow — bottom-left */}
        <div className="absolute bottom-0 left-0 w-2/3 h-1/2 pointer-events-none"
             style={{ background:'radial-gradient(ellipse at 0% 100%, rgba(37,99,235,0.18) 0%, transparent 70%)' }}/>
        {/* Cyan glow — top-right */}
        <div className="absolute top-0 right-0 w-1/2 h-1/2 pointer-events-none"
             style={{ background:'radial-gradient(ellipse at 100% 0%, rgba(6,182,212,0.07) 0%, transparent 60%)' }}/>

        {/* Geometric lines */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none opacity-[0.06]" xmlns="http://www.w3.org/2000/svg" preserveAspectRatio="none">
          <line x1="0" y1="60%" x2="100%" y2="40%" stroke="url(#lineGrad)" strokeWidth="1"/>
          <line x1="0" y1="75%" x2="100%" y2="55%" stroke="url(#lineGrad)" strokeWidth="0.5"/>
          <defs>
            <linearGradient id="lineGrad" x1="0" y1="0" x2="1" y2="0" gradientUnits="objectBoundingBox">
              <stop offset="0%" stopColor="transparent"/>
              <stop offset="30%" stopColor="#3b82f6"/>
              <stop offset="70%" stopColor="#3b82f6"/>
              <stop offset="100%" stopColor="transparent"/>
            </linearGradient>
          </defs>
        </svg>

        {/* Fine particles */}
        {[...Array(10)].map((_,i) => (
          <motion.div key={i} className="absolute h-px w-px rounded-full bg-blue-300/50 pointer-events-none"
            style={{ left:`${12+(i*8.3)%78}%`, top:`${8+(i*9.1)%84}%` }}
            animate={{ opacity:[0,0.8,0] }}
            transition={{ duration:3+(i%3), repeat:Infinity, delay:i*0.5 }}/>
        ))}

        {/* Content */}
        <div className="relative z-10 flex flex-col justify-center flex-1 px-14 xl:px-20 py-16">
          {/* Platform mark */}
          <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:0.6 }}
            className="flex items-center gap-3 mb-14">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl shadow-lg"
                 style={{ background:'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
              <ShieldCheck size={17} className="text-white"/>
            </div>
            <span className="text-sm font-semibold text-slate-300 tracking-tight">ISO Compliance</span>
          </motion.div>

          <motion.div initial={{ opacity:0, y:16 }} animate={{ opacity:1, y:0 }}
            transition={{ duration:0.65, delay:0.05, ease:[0.22,1,0.36,1] }}>
            <h1 className="text-3xl xl:text-4xl font-bold text-white leading-snug tracking-tight mb-5"
                style={{ fontFeatureSettings:'"cv02","cv03","cv04","cv11"' }}>
              Enterprise ISO<br/>
              <span style={{ color:'#93c5fd' }}>Compliance Platform</span>
            </h1>
            <p className="text-sm text-slate-500 leading-relaxed max-w-xs">
              Secure AI-powered compliance platform for enterprise document governance.
            </p>
          </motion.div>
        </div>

        {/* Bottom Capgemini */}
        <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:0.5, delay:0.3 }}
          className="relative z-10 px-14 xl:px-20 pb-10 flex items-center gap-2.5">
          <span className="text-xs text-slate-700 tracking-wide">Innovation Project —</span>
          <img src={capgeminiLogo} alt="Capgemini" className="h-3.5 w-auto"
               style={{ filter:'brightness(0) invert(1)', opacity:0.22 }}/>
        </motion.div>
      </div>

      {/* Divider */}
      <div className="hidden lg:block w-px self-stretch"
           style={{ background:'linear-gradient(to bottom, transparent, rgba(255,255,255,0.06) 20%, rgba(255,255,255,0.06) 80%, transparent)' }}/>

      {/* ══ RIGHT ══ */}
      <div className="flex flex-col items-center justify-center w-full lg:w-[460px] xl:w-[500px] shrink-0 px-8 sm:px-14 lg:px-12 xl:px-16 py-12"
           style={{ background:'#070a1c' }}>

        {/* Mobile bg */}
        <div className="absolute inset-0 lg:hidden pointer-events-none"
             style={{ background:'radial-gradient(ellipse at 50% 0%, rgba(37,99,235,0.12) 0%, transparent 60%)' }}/>

        <div className="relative z-10 w-full max-w-[360px]">

          {/* Mobile header */}
          <motion.div initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:0.5 }}
            className="flex lg:hidden flex-col items-center mb-8">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl mb-3 shadow-lg"
                 style={{ background:'linear-gradient(135deg,#1d4ed8,#2563eb)' }}>
              <ShieldCheck size={20} className="text-white"/>
            </div>
            <p className="text-xs font-medium text-slate-500 tracking-wide">Enterprise ISO Compliance Platform</p>
          </motion.div>

          {/* Heading */}
          <motion.div initial={{ opacity:0, y:10 }} animate={{ opacity:1, y:0 }}
            transition={{ duration:0.5, ease:[0.22,1,0.36,1] }}
            className="mb-8">
            <h2 className="text-xl font-semibold text-white mb-1 tracking-tight">Sign in</h2>
            <p className="text-sm text-slate-600">Enter your credentials to continue</p>
          </motion.div>

          {/* Error */}
          <AnimatePresence mode="wait">
            {error && (
              <motion.div key="err"
                initial={{ opacity:0, y:-6 }} animate={{ opacity:1, y:0 }}
                exit={{ opacity:0 }} transition={{ duration:0.18 }}
                role="alert"
                className="flex items-start gap-2.5 rounded-lg border border-red-500/20 bg-red-500/[0.06] px-3.5 py-2.5 mb-5">
                <AlertCircle size={14} className="text-red-400 mt-0.5 shrink-0"/>
                <p className="text-xs text-red-300 leading-relaxed">{error}</p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Form */}
          <motion.form initial={{ opacity:0, y:8 }} animate={{ opacity:1, y:0 }}
            transition={{ duration:0.5, delay:0.08, ease:[0.22,1,0.36,1] }}
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
                  className="text-slate-600 hover:text-slate-400 transition-colors disabled:opacity-40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-blue-500 rounded p-0.5">
                  <AnimatePresence mode="wait">
                    <motion.span key={showPw?'h':'s'}
                      initial={{ opacity:0, scale:0.8 }} animate={{ opacity:1, scale:1 }} exit={{ opacity:0 }}
                      transition={{ duration:0.12 }}>
                      {showPw ? <EyeOff size={14}/> : <Eye size={14}/>}
                    </motion.span>
                  </AnimatePresence>
                </button>
              }/>

            <motion.button type="submit"
              disabled={loading || !form.login || !form.password}
              whileHover={{ scale:1.008 }} whileTap={{ scale:0.993 }}
              className="relative w-full flex items-center justify-center gap-2 rounded-lg py-2.5 text-sm font-semibold text-white overflow-hidden disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2 focus-visible:ring-offset-[#070a1c] mt-1"
              style={{ background:'linear-gradient(135deg,#1e40af,#2563eb 60%,#3b82f6)' }}>
              <motion.span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/[0.07] to-transparent pointer-events-none"
                initial={{ x:'-100%' }} whileHover={{ x:'100%' }} transition={{ duration:0.5 }}/>
              <AnimatePresence mode="wait">
                {loading
                  ? <motion.span key="l" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2"><Loader2 size={14} className="animate-spin"/> Signing in…</motion.span>
                  : <motion.span key="i" initial={{ opacity:0 }} animate={{ opacity:1 }} exit={{ opacity:0 }}
                      className="flex items-center gap-2">Sign in <ArrowRight size={14}/></motion.span>
                }
              </AnimatePresence>
            </motion.button>
          </motion.form>
        </div>

        {/* Footer */}
        <motion.footer initial={{ opacity:0 }} animate={{ opacity:1 }} transition={{ duration:0.5, delay:0.3 }}
          className="relative z-10 mt-auto pt-10 text-center space-y-1">
          <p className="text-xs text-slate-700">
            © {new Date().getFullYear()} Enterprise ISO Compliance Platform
          </p>
          <div className="flex items-center justify-center gap-2">
            <span className="text-xs text-slate-800">Developed during Capgemini Internship · PFE 2025–2026</span>
          </div>
          <div className="flex items-center justify-center gap-1.5 mt-1">
            <img src={capgeminiLogo} alt="Capgemini" className="h-3 w-auto"
                 style={{ filter:'brightness(0) invert(1)', opacity:0.18 }}/>
            <span className="text-2xs text-slate-800">v{ver}</span>
          </div>
        </motion.footer>
      </div>
    </div>
  );
};

export default Login;