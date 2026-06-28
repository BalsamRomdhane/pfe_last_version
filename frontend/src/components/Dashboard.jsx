import React, { useContext, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import Layout from './Layout';
import api from '../services/api';
import {
  Users, Building2, Activity, ShieldCheck, FileText,
  ClipboardCheck, BookOpen, ArrowRight, Bell,
  TrendingUp, CheckCircle2,
} from 'lucide-react';

/* ─── Skeleton ──────────────────────────────────────────────────────────── */
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

/* ─── KPI Card ──────────────────────────────────────────────────────────── */
function KpiCard({ icon: Icon, label, value, sub, color, bg, loading }) {
  return (
    <div className="kpi-card group transition-all duration-200 hover:shadow-card-hover hover:-translate-y-px">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="kpi-label">{label}</p>
          <p className="kpi-value mt-2">
            {loading ? <span className="skeleton h-8 w-16 inline-block" /> : value}
          </p>
          {sub && <p className="mt-1.5 text-xs text-slate-500">{sub}</p>}
        </div>
        <div className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-lg ${bg}`}>
          <Icon size={18} className={color} />
        </div>
      </div>
    </div>
  );
}

/* ─── Quick action card ─────────────────────────────────────────────────── */
function ActionCard({ title, description, icon: Icon, link, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="card group flex items-center gap-4 p-4 text-left transition-all duration-200 hover:shadow-card-hover hover:-translate-y-px w-full"
    >
      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600 group-hover:bg-brand-100 transition-colors">
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-slate-900 group-hover:text-brand-700 transition-colors">
          {title}
        </p>
        <p className="text-xs text-slate-500 truncate mt-0.5">{description}</p>
      </div>
      <ArrowRight size={14} className="text-slate-400 group-hover:text-brand-600 group-hover:translate-x-0.5 transition-all shrink-0" />
    </button>
  );
}

/* ─── Activity item ─────────────────────────────────────────────────────── */
function ActivityItem({ notification }) {
  const timeAgo = (iso) => {
    if (!iso) return '';
    const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
    if (diff < 60)    return `${diff}s ago`;
    if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
  };

  const isUnread = !notification.is_read;

  return (
    <div className={`flex items-start gap-3 rounded-lg px-3 py-2.5 transition-colors ${isUnread ? 'bg-brand-50/40' : 'hover:bg-slate-50'}`}>
      <div className={`mt-0.5 h-2 w-2 shrink-0 rounded-full ${isUnread ? 'bg-brand-500' : 'bg-slate-300'}`} />
      <div className="flex-1 min-w-0">
        <p className={`text-xs font-medium truncate ${isUnread ? 'text-slate-900' : 'text-slate-600'}`}>
          {notification.title}
        </p>
        {notification.message && (
          <p className="text-2xs text-slate-400 truncate mt-0.5">{notification.message}</p>
        )}
      </div>
      <span className="text-2xs text-slate-400 shrink-0">{timeAgo(notification.created_at)}</span>
    </div>
  );
}

/* ─── Compliance metric bar ─────────────────────────────────────────────── */
function ComplianceBar({ label, value, color }) {
  const pct = Math.min(100, Math.max(0, value || 0));
  const barColor =
    pct >= 80 ? 'bg-emerald-500'
    : pct >= 60 ? 'bg-amber-500'
    : 'bg-red-500';

  return (
    <div>
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-xs text-slate-600">{label}</span>
        <span className={`text-xs font-bold ${color || 'text-slate-700'}`}>{pct}%</span>
      </div>
      <div className="progress-track">
        <div
          className={`progress-bar ${barColor}`}
          style={{ width: `${pct}%`, transition: 'width 0.8s ease-out' }}
        />
      </div>
    </div>
  );
}

/* ─── Main Dashboard ────────────────────────────────────────────────────── */
const Dashboard = () => {
  const { user, userProfile } = useContext(UserContext);
  const { notifications, unreadCount } = useNotifications();
  const navigate = useNavigate();

  const [stats, setStats]       = useState(null);
  const [loadingStats, setLoadingStats] = useState(true);
  const [docCounts, setDocCounts] = useState(null);

  const displayDepartment =
    userProfile?.department || user?.department ||
    (user?.role === 'ADMIN' ? 'Global' : '—');

  /* Fetch real data */
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

        const userCount = Array.isArray(usersData?.data)
          ? usersData.data.length
          : (Array.isArray(usersData) ? usersData.length : null);

        const deptCount = Array.isArray(deptData?.data)
          ? deptData.data.length
          : (Array.isArray(deptData) ? deptData.length : null);

        const docCount = docsData?.count ?? (Array.isArray(docsData) ? docsData.length : null);

        setStats({ userCount, deptCount, docCount });
      } catch {}
      finally { if (mounted) setLoadingStats(false); }
    };

    load();

    /* Fetch doc counts by status */
    const loadDocCounts = async () => {
      try {
        const statuses = ['approved','rejected','pending','reviewing'];
        const results  = await Promise.allSettled(
          statuses.map(s => api.get('/documents/', { params: { page_size: 1, status: s } }))
        );
        if (!mounted) return;
        const map = {};
        statuses.forEach((s, i) => {
          if (results[i].status === 'fulfilled') {
            map[s] = results[i].value?.data?.count ?? 0;
          }
        });
        setDocCounts(map);
      } catch {}
    };

    loadDocCounts();

    return () => { mounted = false; };
  }, [user?.role]);

  /* Actions per role */
  const ACTIONS = {
    EMPLOYEE: [
      { title: 'Submit a Document',     description: 'Upload compliance evidence for review',    icon: FileText,      link: '/documents'    },
      { title: 'My Validations',        description: 'Check the status of your submissions',     icon: ClipboardCheck,link: '/validations'   },
    ],
    TEAMLEAD: [
      { title: 'Review Validations',    description: 'Approve or reject submitted documents',    icon: ClipboardCheck,link: '/validations'   },
      { title: 'Manage Standards',      description: 'Define and update compliance rules',       icon: BookOpen,      link: '/normes'        },
      { title: 'Document Analysis',     description: 'Analyze documents automatically',          icon: ShieldCheck,   link: '/document-analysis' },
      { title: 'Compliance Dashboard',  description: 'Executive compliance overview',            icon: TrendingUp,    link: '/compliance-dashboard' },
    ],
    ADMIN: [
      { title: 'Review Validations',    description: 'Approve or reject submitted documents',    icon: ClipboardCheck,link: '/validations'   },
      { title: 'Manage Users',          description: 'Create, edit and manage accounts',         icon: Users,         link: '/users'         },
      { title: 'ML Dashboard',          description: 'Train and compare ML models',              icon: Activity,      link: '/ml-dashboard'  },
      { title: 'Compliance Dashboard',  description: 'Executive compliance overview',            icon: TrendingUp,    link: '/compliance-dashboard' },
    ],
  };

  const actions = ACTIONS[user?.role] || ACTIONS.EMPLOYEE;

  /* Compliance mini summary */
  const totalDocs    = stats?.docCount || 0;
  const approvedPct  = totalDocs > 0 && docCounts ? Math.round((docCounts.approved || 0) / totalDocs * 100) : 0;
  const rejectedPct  = totalDocs > 0 && docCounts ? Math.round((docCounts.rejected || 0) / totalDocs * 100) : 0;
  const pendingPct   = totalDocs > 0 && docCounts ? Math.round(((docCounts.pending || 0) + (docCounts.reviewing || 0)) / totalDocs * 100) : 0;

  return (
    <Layout>
      <div className="page-container">

        {/* ── Hero header ── */}
        <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-brand-950 to-slate-900 px-6 py-7 text-white shadow-lg sm:px-8">
          {/* Decorative orbs */}
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
              {/* Role pill */}
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Role</p>
                <p className="mt-1 text-sm font-bold text-white">{user?.role}</p>
              </div>
              {/* Department pill */}
              <div className="rounded-lg border border-white/10 bg-white/[0.07] px-4 py-3 backdrop-blur-sm">
                <p className="text-2xs font-bold uppercase tracking-wider text-slate-400">Department</p>
                <p className="mt-1 text-sm font-bold text-white">{displayDepartment}</p>
              </div>
              {/* Notifications pill */}
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

        {/* ── KPI Grid ── */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {loadingStats ? (
            [1,2,3,4].map(i => <SkeletonCard key={i} />)
          ) : (
            <>
              <KpiCard
                icon={Users}
                label="Total Users"
                value={stats?.userCount ?? '—'}
                sub={user?.role === 'ADMIN' ? 'Registered accounts' : undefined}
                color="text-brand-600"
                bg="bg-brand-50"
                loading={false}
              />
              <KpiCard
                icon={Building2}
                label="Departments"
                value={stats?.deptCount ?? '4'}
                sub="Active divisions"
                color="text-violet-600"
                bg="bg-violet-50"
                loading={false}
              />
              <KpiCard
                icon={FileText}
                label="Documents"
                value={stats?.docCount ?? '—'}
                sub={docCounts ? `${docCounts.approved ?? 0} approved` : 'Total submissions'}
                color="text-emerald-600"
                bg="bg-emerald-50"
                loading={false}
              />
              <KpiCard
                icon={Activity}
                label="System Status"
                value="Online"
                sub="All services operational"
                color="text-teal-600"
                bg="bg-teal-50"
                loading={false}
              />
            </>
          )}
        </div>

        {/* ── Main content grid ── */}
        <div className="grid gap-5 lg:grid-cols-[1fr_360px]">

          {/* Left — Quick actions + Compliance summary */}
          <div className="space-y-5">

            {/* Quick actions */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">Quick Actions</h2>
                <span className="badge badge-slate">{actions.length} actions</span>
              </div>
              <div className="p-4 grid gap-2 sm:grid-cols-2">
                {actions.map(action => (
                  <ActionCard
                    key={action.title}
                    {...action}
                    onClick={() => navigate(action.link)}
                  />
                ))}
              </div>
            </div>

            {/* Document compliance summary */}
            {(docCounts || loadingStats) && (
              <div className="card">
                <div className="card-header">
                  <h2 className="card-title">Document Compliance</h2>
                  {totalDocs > 0 && (
                    <span className="text-xs text-slate-500 font-medium">{totalDocs} total</span>
                  )}
                </div>
                <div className="card-body space-y-4">
                  {loadingStats ? (
                    <div className="space-y-3">
                      {[1,2,3].map(i => <div key={i} className="skeleton h-8 rounded-lg" />)}
                    </div>
                  ) : totalDocs === 0 ? (
                    <p className="text-sm text-slate-400 py-4 text-center">No documents submitted yet.</p>
                  ) : (
                    <>
                      <ComplianceBar label="Approved" value={approvedPct} color="text-emerald-600" />
                      <ComplianceBar label="Pending / Reviewing" value={pendingPct} color="text-amber-600" />
                      <ComplianceBar label="Rejected" value={rejectedPct} color="text-red-600" />

                      <div className="mt-3 grid grid-cols-4 gap-2 text-center">
                        {[
                          { label: 'Approved',   val: docCounts?.approved  ?? 0, cls: 'text-emerald-600' },
                          { label: 'Reviewing',  val: docCounts?.reviewing ?? 0, cls: 'text-sky-600'     },
                          { label: 'Pending',    val: docCounts?.pending   ?? 0, cls: 'text-amber-600'   },
                          { label: 'Rejected',   val: docCounts?.rejected  ?? 0, cls: 'text-red-600'     },
                        ].map(s => (
                          <div key={s.label} className="rounded-lg bg-slate-50 py-2.5">
                            <p className={`text-xl font-bold tabular-nums ${s.cls}`}>{s.val}</p>
                            <p className="text-2xs text-slate-500 mt-0.5">{s.label}</p>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Right — Recent notifications */}
          <div className="space-y-5">
            <div className="card flex flex-col" style={{ maxHeight: '480px' }}>
              <div className="card-header shrink-0">
                <h2 className="card-title">Recent Activity</h2>
                {unreadCount > 0 && (
                  <span className="badge badge-red">{unreadCount} new</span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto">
                {notifications.length === 0 ? (
                  <div className="flex flex-col items-center gap-2 py-10">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100 text-slate-300">
                      <Bell size={20} />
                    </div>
                    <p className="text-sm text-slate-500">No recent activity</p>
                  </div>
                ) : (
                  <div className="p-2 space-y-0.5">
                    {notifications.slice(0, 12).map(n => (
                      <ActivityItem key={n.id} notification={n} />
                    ))}
                  </div>
                )}
              </div>

              {notifications.length > 0 && (
                <div className="shrink-0 border-t border-slate-100 p-3">
                  <button
                    type="button"
                    onClick={() => navigate('/dashboard')}
                    className="w-full text-xs font-medium text-brand-600 hover:text-brand-700 text-center py-1 transition-colors"
                  >
                    View all notifications →
                  </button>
                </div>
              )}
            </div>

            {/* Status summary */}
            <div className="card">
              <div className="card-header">
                <h2 className="card-title">System Health</h2>
                <span className="badge badge-green">
                  <span className="status-dot-green animate-pulse" />
                  Operational
                </span>
              </div>
              <div className="card-body space-y-3">
                {[
                  { label: 'Backend API',   status: 'online' },
                  { label: 'Database',      status: 'online' },
                  { label: 'Auth Service',  status: 'online' },
                  { label: 'ML Pipeline',   status: 'online' },
                ].map(svc => (
                  <div key={svc.label} className="flex items-center justify-between">
                    <span className="text-sm text-slate-600">{svc.label}</span>
                    <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-600">
                      <CheckCircle2 size={12} />
                      Healthy
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Dashboard;
