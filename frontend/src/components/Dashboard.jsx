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
  Layers,
  ShieldCheck,
} from 'lucide-react';

const Dashboard = () => {
  const { user, userProfile } = useContext(UserContext);
  const navigate = useNavigate();

  const displayDepartment = userProfile?.department || user?.department || (user?.role === 'ADMIN' ? 'Global' : 'N/A');

  const stats = [
    {
      title: 'Total Users',
      value: '4',
      description: 'Users in the enterprise directory',
      icon: <Users size={20} className="text-blue-600" />,
      border: 'border-blue-100',
      bg: 'bg-blue-50',
    },
    {
      title: 'Departments',
      value: '4',
      description: 'Active teams across the business',
      icon: <Building size={20} className="text-orange-600" />,
      border: 'border-orange-100',
      bg: 'bg-orange-50',
    },
    {
      title: 'Active Sessions',
      value: '1',
      description: 'Active authenticated sessions',
      icon: <Activity size={20} className="text-emerald-600" />,
      border: 'border-emerald-100',
      bg: 'bg-emerald-50',
    },
    {
      title: 'System Health',
      value: 'Online',
      description: 'All systems operational',
      icon: <CheckCircle size={20} className="text-emerald-600" />,
      border: 'border-emerald-100',
      bg: 'bg-emerald-50',
    },
  ];

  const actions = [
    {
      title: 'Manage Users',
      description: 'Create, edit and review user accounts',
      icon: <ShieldCheck size={24} className="text-blue-600" />,
      link: '/users',
    },
    {
      title: 'Department Overview',
      description: 'Review department structure and status',
      icon: <Building size={24} className="text-orange-600" />,
      link: '/departments',
    },
    {
      title: 'API Diagnostics',
      description: 'Inspect API health and workflow tests',
      icon: <Layers size={24} className="text-sky-600" />,
      link: '/api-testing',
    },
  ];

  return (
    <Layout>
      <div className="space-y-6 animate-fadeIn">
        <section className="rounded-[2rem] bg-gradient-to-r from-blue-700 via-slate-900 to-sky-700 px-8 py-10 text-white shadow-2xl overflow-hidden">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
            <div className="max-w-2xl">
              <p className="text-sm uppercase tracking-[0.3em] text-blue-200/70">Enterprise Overview</p>
              <h1 className="mt-4 text-4xl font-semibold tracking-tight">System performance and management</h1>
              <p className="mt-4 max-w-xl text-sm text-blue-100/90 leading-7">
                Executive view of the administration platform. Monitor usage, resources and organizational structure from one premium dashboard.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/10">
                <p className="text-xs uppercase tracking-[0.24em] text-blue-100/80">Role</p>
                <p className="mt-3 text-xl font-semibold">{user?.role || 'N/A'}</p>
              </div>
              <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/10">
                <p className="text-xs uppercase tracking-[0.24em] text-blue-100/80">Department</p>
                <p className="mt-3 text-xl font-semibold">{displayDepartment}</p>
              </div>
              <div className="rounded-3xl bg-white/10 p-4 ring-1 ring-white/10">
                <p className="text-xs uppercase tracking-[0.24em] text-blue-100/80">User</p>
                <p className="mt-3 text-xl font-semibold">{user?.username}</p>
              </div>
            </div>
          </div>
        </section>

        <section className="grid grid-cols-1 gap-6 xl:grid-cols-4">
          {stats.map((item) => (
            <div
              key={item.title}
              className="group rounded-[1.5rem] border border-slate-200 bg-white p-6 shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-xl"
            >
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-semibold text-slate-500">{item.title}</p>
                  <p className="mt-3 text-3xl font-bold text-slate-900">{item.value}</p>
                </div>
                <div className={`rounded-2xl p-3 ${item.bg} ${item.border}`}>
                  {item.icon}
                </div>
              </div>
              <p className="mt-4 text-sm leading-6 text-slate-500">{item.description}</p>
            </div>
          ))}
        </section>

        <section className="space-y-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-sm uppercase tracking-[0.24em] text-slate-500">Quick Actions</p>
              <h2 className="text-2xl font-semibold text-slate-900">Run enterprise workflows</h2>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            {actions.map((action) => (
              <button
                key={action.title}
                onClick={() => navigate(action.link)}
                className="group rounded-[1.5rem] border border-slate-200 bg-white p-6 text-left shadow-sm transition-all duration-200 hover:-translate-y-1 hover:shadow-xl"
              >
                <div className="flex items-center justify-between gap-4">
                  <div className="rounded-3xl bg-slate-50 p-4 text-slate-700">{action.icon}</div>
                  <div className="rounded-full bg-blue-100 px-3 py-2 text-xs font-semibold uppercase tracking-[0.24em] text-blue-700">
                    Go
                  </div>
                </div>
                <div className="mt-6">
                  <p className="text-lg font-semibold text-slate-900">{action.title}</p>
                  <p className="mt-2 text-sm text-slate-500">{action.description}</p>
                </div>
                <div className="mt-6 inline-flex items-center gap-2 text-sm font-semibold text-blue-600">
                  <span>Open</span>
                  <ArrowRight size={16} className="transition-transform duration-200 group-hover:translate-x-1" />
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
    </Layout>
  );
};

export default Dashboard;
