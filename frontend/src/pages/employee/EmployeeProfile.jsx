import React, { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../../context/UserContext';
import Layout from '../../components/Layout';
import api from '../../services/api';
import {
  User, Building2, Shield, Mail, Calendar, Lock,
  ChevronRight, RefreshCw, AlertCircle, CheckCircle2,
  Edit3, LogOut,
} from 'lucide-react';

/* ─── Info row ─────────────────────────────────────────────────────────── */
function InfoRow({ icon: Icon, label, value, loading }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
      <div className="flex items-center gap-3">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
          <Icon size={14} />
        </div>
        <span className="text-sm text-slate-500">{label}</span>
      </div>
      {loading
        ? <div className="skeleton h-4 w-28 rounded" />
        : <span className="text-sm font-medium text-slate-900 text-right max-w-[200px] truncate">{value || '—'}</span>
      }
    </div>
  );
}

/* ─── Role badge ───────────────────────────────────────────────────────── */
function RoleBadge({ role }) {
  const cfg = {
    ADMIN:    { cls: 'bg-amber-100 text-amber-800 ring-1 ring-amber-200',   label: 'Administrateur' },
    TEAMLEAD: { cls: 'bg-violet-100 text-violet-800 ring-1 ring-violet-200', label: 'Team Lead' },
    EMPLOYEE: { cls: 'bg-emerald-100 text-emerald-800 ring-1 ring-emerald-200', label: 'Employé' },
  };
  const c = cfg[role] || { cls: 'badge-slate', label: role };
  return (
    <span className={`inline-flex items-center rounded-full px-3 py-1 text-xs font-semibold ${c.cls}`}>
      {c.label}
    </span>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   EMPLOYEE PROFILE PAGE
═══════════════════════════════════════════════════════════════════════════ */
export default function EmployeeProfile() {
  const { user, logout } = useContext(UserContext);
  const navigate         = useNavigate();

  const [profile,  setProfile]  = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await api.get('/auth/me/');
      setProfile(res.data);
    } catch {
      setError('Impossible de charger le profil. Les informations locales sont affichées.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const displayName  = profile?.username  || profile?.preferred_username || user?.username || '—';
  const displayEmail = profile?.email     || '—';
  const displayDept  = profile?.department || user?.department || '—';
  const displayRole  = profile?.role      || user?.role || '—';

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Mon compte</p>
            <h1 className="page-title mt-1">Profil</h1>
            <p className="page-subtitle">Vos informations personnelles et paramètres du compte.</p>
          </div>
          <button type="button" onClick={load} disabled={loading}
            className="btn-secondary">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Actualiser
          </button>
        </div>

        {error && (
          <div className="alert alert-warning">
            <AlertCircle size={14} className="shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-[300px_1fr]">

          {/* ── LEFT — Avatar + identity card ── */}
          <div className="space-y-4">
            <div className="card p-6 flex flex-col items-center text-center gap-4">
              {/* Avatar */}
              <div className="relative">
                <div className="flex h-20 w-20 items-center justify-center rounded-2xl bg-brand-600 shadow-lg shadow-brand-600/20 text-3xl font-bold text-white select-none">
                  {displayName?.charAt(0)?.toUpperCase() || 'U'}
                </div>
                <div className="absolute -bottom-1 -right-1 h-5 w-5 rounded-full bg-emerald-500 border-2 border-white" title="En ligne" />
              </div>

              <div>
                <p className="text-lg font-bold text-slate-900">{loading ? <span className="skeleton h-5 w-28 inline-block rounded" /> : displayName}</p>
                <p className="text-sm text-slate-500 mt-0.5">{loading ? <span className="skeleton h-4 w-36 inline-block rounded mt-1" /> : displayEmail}</p>
                <div className="mt-2">
                  <RoleBadge role={displayRole} />
                </div>
              </div>

              <div className="w-full border-t border-slate-100 pt-4 space-y-2">
                <button
                  type="button"
                  onClick={() => navigate('/reset-password')}
                  className="btn-secondary w-full justify-center"
                >
                  <Lock size={14} />
                  Changer de mot de passe
                </button>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="btn-ghost w-full justify-center text-red-600 hover:bg-red-50"
                >
                  <LogOut size={14} />
                  Se déconnecter
                </button>
              </div>
            </div>
          </div>

          {/* ── RIGHT — Details ── */}
          <div className="space-y-5">

            {/* Personal info */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Informations personnelles</h2>
                <span className="badge badge-slate"><CheckCircle2 size={10} /> Vérifié</span>
              </div>
              <div className="card-body">
                <InfoRow icon={User}     label="Nom d'utilisateur"  value={displayName}  loading={loading} />
                <InfoRow icon={Mail}     label="Adresse e-mail"     value={displayEmail} loading={loading} />
                <InfoRow icon={Building2}label="Département"        value={displayDept}  loading={loading} />
                <InfoRow icon={Shield}   label="Rôle"               value={displayRole}  loading={loading} />
              </div>
            </div>

            {/* Security section */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Sécurité</h2>
              </div>
              <div className="card-body space-y-3">
                <button
                  type="button"
                  onClick={() => navigate('/reset-password')}
                  className="flex items-center justify-between w-full rounded-lg border border-slate-200 px-4 py-3 hover:bg-slate-50 transition-colors group"
                >
                  <div className="flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
                      <Lock size={14} />
                    </div>
                    <div className="text-left">
                      <p className="text-sm font-medium text-slate-900">Mot de passe</p>
                      <p className="text-xs text-slate-500">Modifier votre mot de passe actuel</p>
                    </div>
                  </div>
                  <ChevronRight size={14} className="text-slate-400 group-hover:text-slate-600 transition-colors" />
                </button>
              </div>
            </div>

            {/* Platform info */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Plateforme</h2>
              </div>
              <div className="card-body">
                <InfoRow icon={Calendar} label="Environnement" value="Enterprise ISO Compliance Platform" loading={false} />
                <InfoRow icon={Shield}   label="Version"       value={process.env.REACT_APP_VERSION || '1.0.0'}          loading={false} />
                <InfoRow icon={CheckCircle2} label="Statut"    value="Actif"                                             loading={false} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}
