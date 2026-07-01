import React, { useContext, useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import Layout from './Layout';
import StatusBadge from './StatusBadge';
import api from '../services/api';
import {
  FileText, Clock, CheckCircle2, AlertCircle, ArrowRight,
  Bell, TrendingUp, Upload, RefreshCw, ChevronRight,
  Users, Building2, Activity, ShieldCheck,
  ClipboardCheck, BookOpen, TrendingDown, Info,
  X, AlertTriangle, History, User,
} from 'lucide-react';

/* ═══════════════════════════════════════════════════════════════════════════
   SHARED MICRO-COMPONENTS
═══════════════════════════════════════════════════════════════════════════ */
function SkeletonCard() {
  return (
    <div className="kpi-card animate-pulse">
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-2 flex-1">
          <div className="skeleton h-3 w-20" />
          <div className="skeleton h-8 w-16" />
          <div className="skeleton h-3 w-28" />
        </div>
        <div className="skeleton h-10 w-10 rounded-lg" />
      </div>
    </div>
  );
}

function KpiCard({ icon: Icon, label, value, sub, color, bg, loading, onClick, urgent }) {
  return (
    <div
      onClick={onClick}
      className={`kpi-card group transition-all duration-200 hover:shadow-card-hover hover:-translate-y-px
        ${onClick ? 'cursor-pointer' : ''}
        ${urgent ? 'ring-2 ring-red-300 ring-offset-1' : ''}
      `}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="kpi-label">{label}</p>
          <p className="kpi-value mt-2">
            {loading ? <span className="skeleton h-8 w-16 inline-block rounded" /> : value}
          </p>
          {sub && <p className="mt-1.5 text-xs text-slate-500">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${bg} relative`}>
          <Icon size={18} className={color} />
          {urgent && (
            <span className="absolute -top-1 -right-1 h-3 w-3 rounded-full bg-red-500 border-2 border-white animate-pulse" />
          )}
        </div>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   EMPLOYEE DASHBOARD SUB-COMPONENTS
═══════════════════════════════════════════════════════════════════════════ */

/* ── Approval ring (SVG inline) ── */
function ApprovalRing({ rate, loading }) {
  const pct = Math.min(100, Math.max(0, Number(rate) || 0));
  const R = 32;
  const C = 2 * Math.PI * R;
  const offset = C * (1 - pct / 100);
  const color = pct >= 80 ? '#10b981' : pct >= 60 ? '#f59e0b' : '#ef4444';
  return (
    <div className="flex items-center gap-4">
      <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
        <svg viewBox="0 0 80 80" className="-rotate-90 h-20 w-20">
          <circle cx="40" cy="40" r={R} fill="none" stroke="#e2e8f0" strokeWidth="7" strokeLinecap="round" />
          {!loading && (
            <circle cx="40" cy="40" r={R} fill="none" stroke={color} strokeWidth="7" strokeLinecap="round"
              strokeDasharray={C} strokeDashoffset={offset}
              style={{ transition: 'stroke-dashoffset 0.8s ease-out' }}
            />
          )}
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          {loading
            ? <div className="skeleton h-5 w-8 rounded" />
            : <><span className="text-lg font-bold text-slate-900 leading-none">{pct}%</span></>
          }
        </div>
      </div>
      <div>
        <p className="text-sm font-semibold text-slate-900">Taux d'approbation</p>
        <p className="text-xs text-slate-500 mt-0.5">
          {loading ? '…' : `${pct >= 80 ? 'Excellent' : pct >= 60 ? 'Satisfaisant' : 'À améliorer'}`}
        </p>
      </div>
    </div>
  );
}

/* ── Trend sparkline (7 days) ── */
function TrendSparkline({ trend, loading }) {
  if (loading) return <div className="skeleton h-10 w-full rounded mt-2" />;
  if (!trend || trend.length === 0) return null;
  const max = Math.max(...trend.map(d => d.total), 1);
  const w = 100 / trend.length;
  return (
    <div className="mt-3">
      <p className="text-2xs text-slate-400 font-medium uppercase tracking-wider mb-1.5">Activité 7 derniers jours</p>
      <div className="flex items-end gap-0.5 h-10">
        {trend.map((d, i) => {
          const h = Math.max(4, Math.round((d.total / max) * 40));
          return (
            <div key={i} className="flex-1 flex flex-col items-center gap-0.5 group relative">
              <div
                className="w-full rounded-sm bg-brand-200 group-hover:bg-brand-400 transition-colors"
                style={{ height: `${h}px` }}
                title={`${d.date}: ${d.total} doc(s)`}
              />
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Needs Attention Banner ── */
function NeedsAttentionBanner({ count, onNavigate }) {
  if (!count || count === 0) return null;
  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3.5 animate-slide-up">
      <AlertTriangle size={16} className="text-red-500 shrink-0 mt-0.5" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-red-900">
          {count} document{count > 1 ? 's' : ''} nécessite{count > 1 ? 'nt' : ''} votre attention
        </p>
        <p className="text-xs text-red-700 mt-0.5">
          {count > 1 ? 'Ces documents ont été rejetés.' : 'Ce document a été rejeté.'} Consultez le feedback et re-soumettez une version corrigée.
        </p>
      </div>
      <button
        type="button"
        onClick={onNavigate}
        className="shrink-0 flex items-center gap-1 text-xs font-semibold text-red-700 hover:text-red-900 transition-colors"
      >
        Voir <ChevronRight size={13} />
      </button>
    </div>
  );
}

/* ── Recent document row ── */
function RecentDocRow({ doc, normeMap, onClick }) {
  const fmt = (d) => d ? new Date(d).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' }) : '—';
  const name = doc.file ? doc.file.split('/').pop() : `Document #${doc.id}`;
  return (
    <button
      type="button"
      onClick={() => onClick(doc)}
      className="flex items-center gap-3 w-full rounded-lg px-3 py-2.5 text-left hover:bg-slate-50 transition-colors group"
    >
      <div className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg
        ${doc.status === 'approved' || doc.status === 'auto_approved' ? 'bg-emerald-50' :
          doc.status === 'rejected' ? 'bg-red-50' :
          doc.status === 'reviewing' ? 'bg-sky-50' : 'bg-amber-50'}`}
      >
        <FileText size={13} className={
          doc.status === 'approved' || doc.status === 'auto_approved' ? 'text-emerald-600' :
          doc.status === 'rejected' ? 'text-red-600' :
          doc.status === 'reviewing' ? 'text-sky-600' : 'text-amber-600'
        } />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-semibold text-slate-800 truncate group-hover:text-brand-700 transition-colors">
          {name}
        </p>
        <p className="text-2xs text-slate-400 truncate mt-0.5">
          {normeMap[doc.norme] || (doc.norme ? `Norme #${doc.norme}` : '—')}
        </p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <StatusBadge status={doc.status} size="xs" />
        <span className="text-2xs text-slate-400">{fmt(doc.created_at)}</span>
      </div>
    </button>
  );
}

/* ── Notification item ── */
function NotifItem({ n, onMark }) {
  const timeAgo = (iso) => {
    if (!iso) return '';
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return `${diff}s`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
    return `${Math.floor(diff / 86400)}j`;
  };
  const isUnread = !n.is_read;
  return (
    <button
      type="button"
      onClick={() => isUnread && onMark(n.id)}
      className={`flex items-start gap-3 w-full rounded-lg px-3 py-2.5 text-left transition-colors
        ${isUnread ? 'bg-brand-50/50 hover:bg-brand-50' : 'hover:bg-slate-50'}`}
    >
      <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${isUnread ? 'bg-brand-500' : 'bg-slate-200'}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium truncate ${isUnread ? 'text-slate-900' : 'text-slate-500'}`}>
          {n.title}
        </p>
        {n.message && <p className="text-2xs text-slate-400 truncate-2 mt-0.5">{n.message}</p>}
      </div>
      <span className="text-2xs text-slate-400 shrink-0">{timeAgo(n.created_at)}</span>
    </button>
  );
}

/* ── Quick action card ── */
function QuickAction({ icon: Icon, title, desc, color, bg, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="card group flex items-center gap-3 p-4 text-left w-full hover:shadow-card-hover hover:-translate-y-px transition-all duration-200"
    >
      <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${bg} group-hover:scale-110 transition-transform`}>
        <Icon size={16} className={color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 group-hover:text-brand-700 transition-colors">{title}</p>
        <p className="text-xs text-slate-400 mt-0.5 truncate">{desc}</p>
      </div>
      <ArrowRight size={13} className="text-slate-300 group-hover:text-brand-500 group-hover:translate-x-0.5 transition-all shrink-0" />
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   EMPLOYEE DASHBOARD
═══════════════════════════════════════════════════════════════════════════ */
function EmployeeDashboard({ user }) {
  const { notifications, unreadCount, markRead, markAllRead } = useNotifications();
  const navigate = useNavigate();

  const [stats, setStats]       = useState(null);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(false);
  const [normes, setNormes]     = useState([]);
  const [recentDocs, setRecentDocs] = useState([]);
  const [docsLoading, setDocsLoading] = useState(true);

  const normeMap = Object.fromEntries(normes.map(n => [n.id, n.name]));

  const displayName = user?.username || 'Employé';
  const displayDept = user?.department || '—';

  const greet = () => {
    const h = new Date().getHours();
    if (h < 12) return 'Bonjour';
    if (h < 18) return 'Bon après-midi';
    return 'Bonsoir';
  };

  const load = useCallback(async () => {
    setLoading(true);
    setError(false);
    try {
      const [statsRes, normesRes] = await Promise.allSettled([
        api.get('/dashboard/stats/'),
        api.get('/normes/'),
      ]);
      if (statsRes.status === 'fulfilled') setStats(statsRes.value.data);
      else setError(true);
      if (normesRes.status === 'fulfilled') {
        const data = Array.isArray(normesRes.value.data)
          ? normesRes.value.data
          : (normesRes.value.data?.results || []);
        setNormes(data);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const loadRecentDocs = useCallback(async () => {
    setDocsLoading(true);
    try {
      const res = await api.get('/documents/', { params: { page_size: 5, ordering: '-created_at' } });
      const list = Array.isArray(res.data?.results) ? res.data.results : (Array.isArray(res.data) ? res.data : []);
      setRecentDocs(list);
    } catch { setRecentDocs([]); }
    finally { setDocsLoading(false); }
  }, []);

  useEffect(() => { load(); loadRecentDocs(); }, [load, loadRecentDocs]);

  const docs = stats?.documents || {};
  const rejectedCount = docs.rejected || 0;
  const complianceRate = stats?.compliance_rate ?? 0;
  const trend = stats?.compliance_trend || [];

  return (
    <Layout>
      <div className="page-container">

        {/* ── HERO ── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-brand-950 to-slate-900 px-6 py-7 text-white shadow-lg sm:px-8">
          <div className="pointer-events-none absolute -right-16 -top-12 h-64 w-64 rounded-full bg-brand-600/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-8 left-8 h-48 w-48 rounded-full bg-violet-500/10 blur-3xl" />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="section-label text-slate-400">Espace conformité</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
                {greet()}, <span className="text-brand-300">{displayName}</span> 👋
              </h1>
              <p className="mt-1.5 text-sm text-slate-400">
                {new Date().toLocaleDateString('fr-FR', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Rôle</p>
                <p className="mt-1 text-sm font-bold text-white">Employee</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Département</p>
                <p className="mt-1 text-sm font-bold text-white">{displayDept}</p>
              </div>
              {unreadCount > 0 && (
                <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 backdrop-blur-sm flex items-center gap-2">
                  <Bell size={14} className="text-red-300" />
                  <div>
                    <p className="text-2xs font-bold uppercase tracking-wider text-red-400">Notifications</p>
                    <p className="mt-1 text-sm font-bold text-white">{unreadCount} non lue{unreadCount > 1 ? 's' : ''}</p>
                  </div>
                </div>
              )}
              <button
                type="button"
                onClick={() => navigate('/documents')}
                className="rounded-lg border border-brand-400/40 bg-brand-600/20 px-4 py-3 backdrop-blur-sm flex items-center gap-2 hover:bg-brand-600/30 transition-colors"
              >
                <Upload size={14} className="text-brand-300" />
                <span className="text-sm font-semibold text-white">Soumettre un document</span>
              </button>
            </div>
          </div>
        </div>

        {/* ── ALERTE DOCS À CORRIGER ── */}
        {!loading && (
          <NeedsAttentionBanner
            count={rejectedCount}
            onNavigate={() => navigate('/documents?status=rejected')}
          />
        )}
        {error && (
          <div className="alert alert-warning">
            <AlertCircle size={14} className="shrink-0" />
            <span>Impossible de charger les statistiques. Vérifiez votre connexion.</span>
            <button type="button" onClick={load} className="ml-auto flex items-center gap-1 text-xs font-medium hover:underline">
              <RefreshCw size={12} /> Réessayer
            </button>
          </div>
        )}

        {/* ── KPI GRID ── */}
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {loading ? (
            [1,2,3,4].map(i => <SkeletonCard key={i} />)
          ) : (
            <>
              <KpiCard icon={FileText} label="Mes documents" value={docs.total ?? 0}
                sub="Total soumis" color="text-brand-600" bg="bg-brand-50" loading={false}
                onClick={() => navigate('/documents')} />
              <KpiCard icon={Clock} label="En attente" value={(docs.pending ?? 0) + (docs.reviewing ?? 0)}
                sub={`${docs.pending ?? 0} pendants · ${docs.reviewing ?? 0} en révision`}
                color="text-amber-600" bg="bg-amber-50" loading={false}
                onClick={() => navigate('/documents?status=pending')} />
              <KpiCard icon={CheckCircle2} label="Approuvés" value={docs.approved ?? 0}
                sub="Documents validés" color="text-emerald-600" bg="bg-emerald-50" loading={false}
                onClick={() => navigate('/documents?status=approved')} />
              <KpiCard icon={AlertCircle} label="À corriger" value={rejectedCount}
                sub={rejectedCount > 0 ? 'Action requise' : 'Aucun rejet'}
                color="text-red-600" bg="bg-red-50" loading={false}
                urgent={rejectedCount > 0}
                onClick={() => navigate('/documents?status=rejected')} />
            </>
          )}
        </div>

        {/* ── MAIN GRID ── */}
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">

          {/* ── COLONNE GAUCHE ── */}
          <div className="space-y-5">

            {/* Taux d'approbation + tendance */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Conformité personnelle</h2>
                <span className="badge badge-slate">
                  <TrendingUp size={10} /> Taux d'approbation
                </span>
              </div>
              <div className="card-body space-y-1">
                <ApprovalRing rate={complianceRate} loading={loading} />
                <TrendSparkline trend={trend} loading={loading} />
              </div>
            </div>

            {/* Documents récents */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Mes derniers documents</h2>
                <button
                  type="button"
                  onClick={() => navigate('/documents')}
                  className="text-xs font-medium text-brand-600 hover:text-brand-700 flex items-center gap-1 transition-colors"
                >
                  Tout voir <ChevronRight size={12} />
                </button>
              </div>
              <div className="p-2">
                {docsLoading ? (
                  <div className="space-y-2 p-3">
                    {[1,2,3].map(i => <div key={i} className="skeleton h-10 rounded-lg" />)}
                  </div>
                ) : recentDocs.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-8">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
                      <FileText size={20} className="text-slate-300" />
                    </div>
                    <p className="text-sm text-slate-500">Aucun document soumis</p>
                    <button type="button" onClick={() => navigate('/documents')}
                      className="btn-primary btn-sm mt-1">
                      <Upload size={13} /> Soumettre mon premier document
                    </button>
                  </div>
                ) : (
                  <div className="space-y-0.5">
                    {recentDocs.map(doc => (
                      <RecentDocRow key={doc.id} doc={doc} normeMap={normeMap}
                        onClick={() => navigate(`/documents/${doc.id}`)} />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* Actions rapides */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Actions rapides</h2>
              </div>
              <div className="p-4 grid gap-2 sm:grid-cols-2">
                <QuickAction icon={Upload} title="Soumettre un document"
                  desc="Envoyer un fichier de conformité" color="text-brand-600" bg="bg-brand-50"
                  onClick={() => navigate('/documents')} />
                <QuickAction icon={History} title="Mes soumissions"
                  desc="Suivre le statut de mes documents" color="text-slate-600" bg="bg-slate-100"
                  onClick={() => navigate('/documents')} />
                <QuickAction icon={Bell} title="Notifications"
                  desc={unreadCount > 0 ? `${unreadCount} non lue${unreadCount > 1 ? 's' : ''}` : 'Toutes lues'}
                  color="text-violet-600" bg="bg-violet-50"
                  onClick={() => navigate('/notifications')} />
                <QuickAction icon={User} title="Mon profil"
                  desc="Informations personnelles" color="text-teal-600" bg="bg-teal-50"
                  onClick={() => navigate('/profile')} />
              </div>
            </div>
          </div>

          {/* ── COLONNE DROITE ── */}
          <div className="space-y-5">

            {/* Notifications récentes */}
            <div className="card flex flex-col" style={{ maxHeight: '420px' }}>
              <div className="card-header shrink-0">
                <h2 className="card-title">Notifications</h2>
                <div className="flex items-center gap-2">
                  {unreadCount > 0 && (
                    <><span className="badge badge-red">{unreadCount}</span>
                    <button type="button" onClick={markAllRead}
                      className="text-2xs font-medium text-brand-600 hover:text-brand-700 transition-colors">
                      Tout lire
                    </button></>
                  )}
                </div>
              </div>
              <div className="flex-1 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-300">
                      <Bell size={20} />
                    </div>
                    <p className="text-sm text-slate-500">Aucune notification</p>
                  </div>
                ) : (
                  <div className="p-2 space-y-0.5">
                    {notifications.slice(0, 8).map(n => (
                      <NotifItem key={n.id} n={n} onMark={markRead} />
                    ))}
                  </div>
                )}
              </div>
              {notifications.length > 0 && (
                <div className="shrink-0 border-t border-slate-100 p-3">
                  <button type="button" onClick={() => navigate('/notifications')}
                    className="w-full text-xs font-medium text-brand-600 hover:text-brand-700 text-center py-1 transition-colors">
                    Voir toutes les notifications →
                  </button>
                </div>
              )}
            </div>

            {/* Stats personnelles résumées */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Récapitulatif</h2>
              </div>
              <div className="card-body space-y-3">
                {loading ? (
                  <div className="space-y-2">{[1,2,3,4].map(i => <div key={i} className="skeleton h-6 rounded" />)}</div>
                ) : (
                  [
                    { label: 'Documents approuvés', value: docs.approved ?? 0, color: 'text-emerald-600', dot: 'bg-emerald-400' },
                    { label: 'En cours de révision', value: docs.reviewing ?? 0, color: 'text-sky-600', dot: 'bg-sky-400' },
                    { label: 'En attente',           value: docs.pending ?? 0, color: 'text-amber-600', dot: 'bg-amber-400' },
                    { label: 'Rejetés',              value: docs.rejected ?? 0, color: 'text-red-600', dot: 'bg-red-400' },
                  ].map(s => (
                    <div key={s.label} className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={`h-2 w-2 rounded-full ${s.dot}`} />
                        <span className="text-sm text-slate-600">{s.label}</span>
                      </div>
                      <span className={`text-sm font-bold tabular-nums ${s.color}`}>{s.value}</span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   ADMIN / TEAMLEAD DASHBOARD (conservé intact)
═══════════════════════════════════════════════════════════════════════════ */
function ActionCard({ title, description, icon: Icon, link, onClick }) {
  return (
    <button type="button" onClick={onClick}
      className="card group flex items-center gap-4 p-4 text-left transition-all duration-200 hover:shadow-card-hover hover:-translate-y-px w-full">
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-100 transition-colors">
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 group-hover:text-brand-700 transition-colors">{title}</p>
        <p className="text-xs text-slate-500 truncate mt-0.5">{description}</p>
      </div>
      <ArrowRight size={14} className="text-slate-400 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
    </button>
  );
}

function AdminActivityItem({ notification }) {
  const timeAgo = (iso) => {
    if (!iso) return '';
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60) return `${diff}s ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };
  const isUnread = !notification.is_read;
  return (
    <div className={`flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors ${isUnread ? 'bg-brand-50/40' : 'hover:bg-slate-50'}`}>
      <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${isUnread ? 'bg-brand-500' : 'bg-slate-300'}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium truncate ${isUnread ? 'text-slate-900' : 'text-slate-600'}`}>{notification.title}</p>
        {notification.message && <p className="text-2xs text-slate-400 truncate mt-0.5">{notification.message}</p>}
      </div>
      <span className="text-2xs text-slate-400 shrink-0">{timeAgo(notification.created_at)}</span>
    </div>
  );
}

function ComplianceBar({ label, value, color }) {
  const pct = Math.min(100, Math.max(0, value || 0));
  const barColor = pct >= 80 ? 'bg-emerald-500' : pct >= 60 ? 'bg-amber-500' : 'bg-red-500';
  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-slate-600">{label}</span>
        <span className={`text-xs font-bold ${color || 'text-slate-700'}`}>{pct}%</span>
      </div>
      <div className="progress-track">
        <div className={`progress-bar ${barColor}`} style={{ width: `${pct}%`, transition: 'width 0.8s ease-out' }} />
      </div>
    </div>
  );
}

function AdminTeamLeadDashboard({ user }) {
  const { notifications, unreadCount } = useNotifications();
  const navigate = useNavigate();
  const [stats, setStats]       = useState(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [docCounts, setDocCounts] = useState(null);

  const displayDepartment = user?.department || (user?.role === 'ADMIN' ? 'Global' : '—');

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      try {
        const [usersRes, deptRes, docsRes] = await Promise.allSettled([
          user?.role === 'ADMIN' ? api.get('/rbac/users/') : Promise.resolve(null),
          user?.role === 'ADMIN' ? api.get('/rbac/departments/') : Promise.resolve(null),
          api.get('/documents/', { params: { page_size: 1 } }),
        ]);
        if (!mounted) return;
        const usersData = usersRes.status === 'fulfilled' && usersRes.value?.data;
        const deptData  = deptRes.status  === 'fulfilled' && deptRes.value?.data;
        const docsData  = docsRes.status  === 'fulfilled' && docsRes.value?.data;
        const userCount = Array.isArray(usersData?.data) ? usersData.data.length : (Array.isArray(usersData) ? usersData.length : null);
        const deptCount = Array.isArray(deptData?.data)  ? deptData.data.length  : (Array.isArray(deptData)  ? deptData.length  : null);
        const docCount  = docsData?.count ?? (Array.isArray(docsData) ? docsData.length : null);
        setStats({ userCount, deptCount, docCount });
      } catch {}
      finally { if (mounted) setLoadingStats(false); }
    };
    load();
    const loadDocCounts = async () => {
      try {
        const statuses = ['approved','rejected','pending','reviewing'];
        const results = await Promise.allSettled(statuses.map(s => api.get('/documents/', { params: { page_size: 1, status: s } })));
        if (!mounted) return;
        const map = {};
        statuses.forEach((s, i) => { map[s] = results[i].status === 'fulfilled' ? (results[i].value?.data?.count ?? 0) : 0; });
        setDocCounts(map);
      } catch {}
    };
    loadDocCounts();
    return () => { mounted = false; };
  }, [user?.role]);

  const ACTIONS = {
    TEAMLEAD: [
      { title: 'Valider des documents', description: 'Approuver ou rejeter les soumissions', icon: ClipboardCheck, link: '/validations' },
      { title: 'Gérer les normes',      description: 'Définir et mettre à jour les règles',  icon: BookOpen,      link: '/normes' },
    ],
    ADMIN: [
      { title: 'Valider des documents', description: 'Approuver ou rejeter les soumissions', icon: ClipboardCheck, link: '/validations' },
      { title: 'Gérer les utilisateurs',description: 'Créer et gérer les comptes',           icon: Users,         link: '/users' },
      { title: 'ML Dashboard',          description: 'Entraîner et comparer les modèles',    icon: Activity,      link: '/ml-dashboard' },
      { title: 'Compliance Dashboard',  description: "Vue exécutive de la conformité",       icon: TrendingUp,    link: '/compliance-dashboard' },
    ],
  };
  const actions = ACTIONS[user?.role] || [];
  const totalDocs   = stats?.docCount || 0;
  const approvedPct = totalDocs > 0 && docCounts ? Math.round((docCounts.approved || 0) / totalDocs * 100) : 0;
  const rejectedPct = totalDocs > 0 && docCounts ? Math.round((docCounts.rejected || 0) / totalDocs * 100) : 0;
  const pendingPct  = totalDocs > 0 && docCounts ? Math.round(((docCounts.pending || 0) + (docCounts.reviewing || 0)) / totalDocs * 100) : 0;

  return (
    <Layout>
      <div className="page-container">
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-brand-950 to-slate-900 px-6 py-7 text-white shadow-lg sm:px-8">
          <div className="pointer-events-none absolute -right-16 -top-12 h-64 w-64 rounded-full bg-brand-600/10 blur-3xl" />
          <div className="pointer-events-none absolute -bottom-8 left-8 h-48 w-48 rounded-full bg-violet-500/10 blur-3xl" />
          <div className="relative flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <p className="section-label text-slate-400">Enterprise Overview</p>
              <h1 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">
                Welcome back, <span className="text-brand-300">{user?.username}</span>
              </h1>
              <p className="mt-1.5 text-sm text-slate-400">
                {new Date().toLocaleDateString('en-GB', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
              </p>
            </div>
            <div className="flex flex-wrap gap-3">
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Role</p>
                <p className="mt-1 text-sm font-bold text-white">{user?.role}</p>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Department</p>
                <p className="mt-1 text-sm font-bold text-white">{displayDepartment}</p>
              </div>
              {unreadCount > 0 && (
                <div className="rounded-lg border border-red-400/30 bg-red-500/10 px-4 py-3 backdrop-blur-sm flex items-center gap-2">
                  <Bell size={15} className="text-red-300" />
                  <div>
                    <p className="text-2xs font-bold uppercase tracking-wider text-red-400">Alerts</p>
                    <p className="mt-1 text-sm font-bold text-white">{unreadCount} unread</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loadingStats ? [1,2,3,4].map(i => <SkeletonCard key={i} />) : (
            <>
              <KpiCard icon={Users} label="Total Users" value={stats?.userCount ?? '—'} sub={user?.role === 'ADMIN' ? 'Registered accounts' : undefined} color="text-brand-600" bg="bg-brand-50" loading={false} />
              <KpiCard icon={Building2} label="Departments" value={stats?.deptCount ?? '4'} sub="Active divisions" color="text-violet-600" bg="bg-violet-50" loading={false} />
              <KpiCard icon={FileText} label="Documents" value={stats?.docCount ?? '—'} sub={docCounts ? `${docCounts.approved ?? 0} approved` : 'Total submissions'} color="text-emerald-600" bg="bg-emerald-50" loading={false} />
              <KpiCard icon={Activity} label="System Status" value="Online" sub="All services operational" color="text-teal-600" bg="bg-teal-50" loading={false} />
            </>
          )}
        </div>
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
          <div className="space-y-5">
            <div className="card">
              <div className="card-header"><h2 className="card-title">Quick Actions</h2><span className="badge badge-slate">{actions.length} actions</span></div>
              <div className="p-4 grid gap-2 sm:grid-cols-2">
                {actions.map(a => <ActionCard key={a.title} {...a} onClick={() => navigate(a.link)} />)}
              </div>
            </div>
            {(docCounts || loadingStats) && (
              <div className="card">
                <div className="card-header"><h2 className="card-title">Document Compliance</h2>{totalDocs > 0 && <span className="text-xs text-slate-500 font-medium">{totalDocs} total</span>}</div>
                <div className="card-body space-y-4">
                  {loadingStats ? <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="skeleton h-8 rounded-lg" />)}</div>
                    : totalDocs === 0 ? <p className="text-sm text-slate-400 py-4 text-center">No documents submitted yet.</p>
                    : (<>
                      <ComplianceBar label="Approved" value={approvedPct} color="text-emerald-600" />
                      <ComplianceBar label="Pending / Reviewing" value={pendingPct} color="text-amber-600" />
                      <ComplianceBar label="Rejected" value={rejectedPct} color="text-red-600" />
                      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                        {[{label:'Approved',val:docCounts?.approved??0,cls:'text-emerald-600'},{label:'Reviewing',val:docCounts?.reviewing??0,cls:'text-sky-600'},{label:'Pending',val:docCounts?.pending??0,cls:'text-amber-600'},{label:'Rejected',val:docCounts?.rejected??0,cls:'text-red-600'}].map(s => (
                          <div key={s.label} className="rounded-lg bg-slate-50 py-2.5">
                            <p className={`text-xl font-bold tabular-nums ${s.cls}`}>{s.val}</p>
                            <p className="text-2xs text-slate-500 mt-0.5">{s.label}</p>
                          </div>
                        ))}
                      </div>
                    </>)}
                </div>
              </div>
            )}
          </div>
          <div className="space-y-5">
            <div className="card flex flex-col" style={{ maxHeight: '480px' }}>
              <div className="card-header shrink-0"><h2 className="card-title">Recent Activity</h2>{unreadCount > 0 && <span className="badge badge-red">{unreadCount} new</span>}</div>
              <div className="flex-1 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10"><div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-300"><Bell size={20} /></div><p className="text-sm text-slate-500">No recent activity</p></div>
                ) : (
                  <div className="p-2 space-y-0.5">{notifications.slice(0,12).map(n => <AdminActivityItem key={n.id} notification={n} />)}</div>
                )}
              </div>
              {notifications.length > 0 && <div className="shrink-0 border-t border-slate-100 p-3"><button type="button" onClick={() => navigate('/dashboard')} className="w-full text-xs font-medium text-brand-600 hover:text-brand-700 text-center py-1 transition-colors">View all notifications →</button></div>}
            </div>
            <div className="card">
              <div className="card-header"><h2 className="card-title">System Health</h2><span className="badge badge-green"><span className="status-dot-green animate-pulse" />Operational</span></div>
              <div className="card-body space-y-3">
                {[{label:'Backend API',status:'online'},{label:'Database',status:'online'},{label:'Auth Service',status:'online'},{label:'ML Pipeline',status:'online'}].map(svc => (
                  <div key={svc.label} className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">{svc.label}</span>
                    <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600"><CheckCircle2 size={12} />Healthy</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   ROOT — routage par rôle
═══════════════════════════════════════════════════════════════════════════ */
const Dashboard = () => {
  const { user } = useContext(UserContext);
  if (user?.role === 'EMPLOYEE') return <EmployeeDashboard user={user} />;
  return <AdminTeamLeadDashboard user={user} />;
};

export default Dashboard;
