import React, { useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import {
  Users,
  Building,
  Activity,
  CheckCircle,
  ArrowRight,
  ShieldCheck,
  Sparkles,
  BarChart3,
  Bell,
} from 'lucide-react';

const statCards = [
  {
    title: 'Total Users',
    value: '4',
    description: 'Users currently registered',
    icon: Users,
    tone: 'blue',
  },
  {
    title: 'Departments',
    value: '4',
    description: 'Active corporate divisions',
    icon: Building,
    tone: 'orange',
  },
  {
    title: 'Active Sessions',
    value: '1',
    description: 'Currently signed in users',
    icon: Activity,
    tone: 'emerald',
  },
  {
    title: 'System Health',
    value: 'Online',
    description: 'Operational status',
    icon: CheckCircle,
    tone: 'teal',
  },
];

const insights = [
  {
    label: 'Login success rate',
    value: '98.7%',
    percentage: 94,
    status: 'success',
  },
  {
    label: 'Password resets',
    value: '12 this week',
    percentage: 45,
    status: 'warning',
  },
  {
    label: 'Pending approvals',
    value: '3 items',
    percentage: 32,
    status: 'critical',
  },
];

const activityFeed = [
  { id: 1, title: 'New admin profile created', time: '10m ago' },
  { id: 2, title: 'Department structure updated', time: '1h ago' },
  { id: 3, title: 'Password reset link issued', time: 'Yesterday' },
];

const HeaderBadge = ({ label, value }) => (
  <div className="rounded-[1.5rem] border border-white/15 bg-white/10 px-4 py-3 text-sm text-white shadow-sm backdrop-blur-sm">
    <p className="text-xs uppercase tracking-[0.3em] text-white/70">{label}</p>
    <p className="mt-2 text-lg font-semibold text-white">{value}</p>
  </div>
);

const StatCard = ({ title, value, description, icon: Icon, tone }) => {
  const toneStyles = {
    blue: 'text-sky-600 bg-sky-50/80 ring-sky-100',
    orange: 'text-orange-600 bg-orange-50/80 ring-orange-100',
    emerald: 'text-emerald-600 bg-emerald-50/80 ring-emerald-100',
    teal: 'text-teal-600 bg-teal-50/80 ring-teal-100',
  };

  return (
    <article className="group rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm transition duration-200 hover:-translate-y-1 hover:border-slate-300 hover:shadow-xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs uppercase tracking-[0.3em] text-slate-400">{title}</p>
          <p className="mt-4 text-4xl font-semibold tracking-tight text-slate-900">{value}</p>
        </div>
        <div className={`flex h-14 w-14 items-center justify-center rounded-3xl border ${toneStyles[tone]}`}>
          <Icon size={24} />
        </div>
      </div>
      <p className="mt-5 text-sm leading-6 text-slate-500">{description}</p>
    </article>
  );
};

const InsightCard = ({ label, value, percentage, status }) => {
  const tone = {
    success: 'bg-emerald-500',
    warning: 'bg-orange-500',
    critical: 'bg-rose-500',
  }[status];

  const labelColor = {
    success: 'text-emerald-700 bg-emerald-100',
    warning: 'text-orange-700 bg-orange-100',
    critical: 'text-rose-700 bg-rose-100',
  }[status];

  return (
    <div className="rounded-[1.5rem] border border-slate-200 bg-white p-5 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-lg">
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm font-semibold text-slate-800">{label}</p>
        <span className={`inline-flex rounded-full px-3 py-1 text-xs font-semibold ${labelColor}`}>{status.toUpperCase()}</span>
      </div>
      <p className="mt-4 text-3xl font-semibold text-slate-900">{value}</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className={`${tone} h-full rounded-full`} style={{ width: `${percentage}%` }} />
      </div>
      <p className="mt-3 text-sm text-slate-500">{percentage}% performance score</p>
    </div>
  );
};

const ActivityItem = ({ title, time }) => (
  <li className="group flex items-center justify-between gap-4 rounded-[1.5rem] border border-slate-200 bg-white p-4 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:bg-slate-50">
    <div className="flex items-center gap-3">
      <span className="inline-flex h-3.5 w-3.5 rounded-full bg-sky-500" />
      <p className="text-sm font-medium text-slate-900">{title}</p>
    </div>
    <p className="text-xs text-slate-500">{time}</p>
  </li>
);

const Dashboard = () => {
  const { user, userProfile } = useContext(UserContext);
  const navigate = useNavigate();
  const displayDepartment = userProfile?.department || user?.department || (user?.role === 'ADMIN' ? 'Global' : 'N/A');

  const headerActions = [
    {
      title: 'Manage Users',
      description: 'Create, edit and review user accounts',
      icon: ShieldCheck,
      link: '/users',
      roles: ['ADMIN'],
    },
    {
      title: 'Department Overview',
      description: 'Review department structure and status',
      icon: Building,
      link: '/departments',
      roles: ['ADMIN'],
    },
  ];

  return (
    <Layout>
      <div className="space-y-8 px-4 pb-8 pt-6 sm:px-6 lg:px-8">
        <header className="relative overflow-hidden rounded-[2rem] bg-gradient-to-r from-slate-950 via-blue-950 to-sky-800 px-6 py-8 text-white shadow-2xl shadow-slate-950/30 sm:px-10 sm:py-10">
          <div className="pointer-events-none absolute -right-16 top-10 h-72 w-72 rounded-full bg-sky-500/10 blur-3xl" />
          <div className="pointer-events-none absolute left-4 top-16 h-72 w-72 rounded-full bg-violet-500/10 blur-3xl" />
          <div className="relative grid gap-8 lg:grid-cols-[1.5fr_0.95fr] lg:items-center">
            <div className="max-w-2xl">
              <p className="text-xs uppercase tracking-[0.35em] text-slate-300/70">Enterprise overview</p>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-5xl">Powerful analytics for your organisation</h1>
              <p className="mt-4 max-w-xl text-sm leading-7 text-slate-200 sm:text-base">
                Monitor usage, performance, and recent activity in one polished workspace. The dashboard is designed to help teams move faster with confidence.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <HeaderBadge label="Role" value={user?.role || 'N/A'} />
              <HeaderBadge label="Department" value={displayDepartment} />
            </div>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-6 shadow-lg shadow-slate-950/10 backdrop-blur-xl transition duration-200 hover:bg-white/15">
              <div className="flex items-center gap-3">
                <Sparkles size={22} className="text-white" />
                <div>
                  <p className="text-sm text-slate-200">Engagement</p>
                  <p className="mt-1 text-xl font-semibold text-white">+14.2%</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-300">More active users in the last 7 days across your organization.</p>
            </div>
            <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-6 shadow-lg shadow-slate-950/10 backdrop-blur-xl transition duration-200 hover:bg-white/15">
              <div className="flex items-center gap-3">
                <BarChart3 size={22} className="text-white" />
                <div>
                  <p className="text-sm text-slate-200">Optimization</p>
                  <p className="mt-1 text-xl font-semibold text-white">Stable</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-300">Monitoring is active and no critical issues were detected in the last hour.</p>
            </div>
            <div className="rounded-[1.75rem] border border-white/10 bg-white/10 p-6 shadow-lg shadow-slate-950/10 backdrop-blur-xl transition duration-200 hover:bg-white/15">
              <div className="flex items-center gap-3">
                <Bell size={22} className="text-white" />
                <div>
                  <p className="text-sm text-slate-200">Notifications</p>
                  <p className="mt-1 text-xl font-semibold text-white">3 unread</p>
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-300">Review the latest activity and system updates in one place.</p>
            </div>
          </div>
        </header>

        <section className="grid gap-6 xl:grid-cols-[1.35fr_0.85fr]">
          <div className="grid gap-6 sm:grid-cols-2 xl:grid-cols-2">
            {statCards.map((stat) => (
              <StatCard key={stat.title} {...stat} />
            ))}
          </div>

          <aside className="space-y-6">
            <div className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-xl">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Platform insights</p>
                  <p className="mt-2 text-sm text-slate-500">Live performance indicators.</p>
                </div>
                <span className="inline-flex items-center gap-2 rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.22em] text-emerald-700 shadow-sm">
                  <span className="inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
                  LIVE
                </span>
              </div>

              <div className="mt-6 space-y-4">
                {insights.map((item) => (
                  <InsightCard key={item.label} {...item} />
                ))}
              </div>
            </div>

            <div className="rounded-[1.75rem] border border-slate-200 bg-white p-6 shadow-sm transition duration-200 hover:-translate-y-0.5 hover:shadow-xl">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-900">Recent activity</p>
                  <p className="mt-2 text-sm text-slate-500">Timeline of the latest events.</p>
                </div>
              </div>

              <ul className="mt-6 space-y-3">
                {activityFeed.map((event) => (
                  <ActivityItem key={event.id} {...event} />
                ))}
              </ul>
            </div>
          </aside>
        </section>

        {user?.role === 'ADMIN' && (
          <section className="grid gap-6 xl:grid-cols-2">
            {headerActions.map((action) => (
              <button
                key={action.title}
                type="button"
                onClick={() => navigate(action.link)}
                className="group rounded-[1.5rem] border border-slate-200 bg-white p-6 text-left shadow-sm transition duration-200 hover:-translate-y-1 hover:shadow-xl"
              >
                <div className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{action.title}</p>
                    <p className="mt-2 text-sm text-slate-500">{action.description}</p>
                  </div>
                  <div className="flex h-12 w-12 items-center justify-center rounded-3xl bg-slate-100 text-slate-700">
                    <action.icon size={24} />
                  </div>
                </div>
                <div className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-sky-600">
                  Open <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-1" />
                </div>
              </button>
            ))}
          </section>
        )}
      </div>
    </Layout>
  );
};

export default Dashboard;
