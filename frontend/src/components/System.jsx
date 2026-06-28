import React, { useContext, useEffect, useState } from 'react';
import { UserContext } from '../context/UserContext';
import Layout from './Layout';
import api from '../services/api';
import {
  Server, Database, Shield, Activity, RefreshCw,
  CheckCircle2, AlertCircle, Clock, Zap,
} from 'lucide-react';

/* ─── Service status card ──────────────────────────────────────────────── */
function ServiceCard({ icon: Icon, title, details, status, loading }) {
  const isOk = status === 'online' || status === 'connected' || status === 'active' || status === 'running';

  return (
    <div className={`card p-5 border-l-4 ${isOk ? 'border-l-emerald-500' : 'border-l-amber-500'}`}>
      <div className="flex items-start justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${isOk ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'}`}>
            <Icon size={17} />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">{title}</p>
            {loading ? (
              <div className="skeleton h-3 w-12 mt-1" />
            ) : (
              <span className={`badge text-2xs mt-0.5 ${isOk ? 'badge-green' : 'badge-amber'}`}>
                {isOk ? <CheckCircle2 size={9}/> : <AlertCircle size={9}/>}
                {status}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="space-y-2">
        {details.map(d => (
          <div key={d.label} className="flex items-center justify-between text-xs">
            <span className="text-slate-500">{d.label}</span>
            {loading
              ? <div className="skeleton h-3 w-20 rounded" />
              : <span className="font-medium text-slate-800">{d.value}</span>
            }
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Metric pill ──────────────────────────────────────────────────────── */
function MetricPill({ label, value, unit, color, loading }) {
  return (
    <div className="kpi-card text-center">
      {loading
        ? <div className="skeleton h-8 w-20 mx-auto rounded my-2" />
        : <p className={`kpi-value ${color || 'text-slate-900'}`}>{value}{unit}</p>
      }
      <p className="kpi-label mt-1">{label}</p>
    </div>
  );
}

/* ─── System page ──────────────────────────────────────────────────────── */
const System = () => {
  const { user } = useContext(UserContext);
  const [health,   setHealth]   = useState(null);
  const [loading,  setLoading]  = useState(true);
  const [lastPing, setLastPing] = useState(null);

  const fetchHealth = async () => {
    setLoading(true);
    try {
      /* Try a lightweight API call to verify backend health */
      const start = Date.now();
      await api.get('/normes/', { params: { page_size: 1 } });
      const latency = Date.now() - start;
      setHealth({ status: 'online', latency });
      setLastPing(new Date());
    } catch {
      setHealth({ status: 'degraded', latency: null });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchHealth(); }, []);

  const apiBase = process.env.REACT_APP_API_URL || 'http://localhost:8000/api';

  const SERVICES = [
    {
      icon: Server,
      title: 'Backend API',
      status: health?.status || 'unknown',
      details: [
        { label: 'Framework',  value: 'Django REST Framework 5.2' },
        { label: 'Python',     value: '3.11' },
        { label: 'API Base',   value: apiBase },
        { label: 'Latency',    value: health?.latency != null ? `${health.latency} ms` : '—' },
      ],
    },
    {
      icon: Database,
      title: 'Database',
      status: health?.status === 'online' ? 'connected' : 'unknown',
      details: [
        { label: 'Engine',     value: 'PostgreSQL / SQLite' },
        { label: 'ORM',        value: 'Django ORM' },
        { label: 'Migrations', value: 'Up to date' },
        { label: 'Status',     value: health?.status === 'online' ? 'Connected' : '—' },
      ],
    },
    {
      icon: Shield,
      title: 'Authentication',
      status: health?.status === 'online' ? 'active' : 'unknown',
      details: [
        { label: 'Provider',   value: 'Django + JWT' },
        { label: 'Token type', value: 'Bearer JWT' },
        { label: 'Expiry',     value: 'Configurable' },
        { label: 'CSRF',       value: 'Enabled' },
      ],
    },
    {
      icon: Activity,
      title: 'Frontend',
      status: 'running',
      details: [
        { label: 'Framework',  value: 'React 19' },
        { label: 'UI Library', value: 'TailwindCSS 3 + Framer Motion' },
        { label: 'Router',     value: 'React Router v7 (HashRouter)' },
        { label: 'State',      value: 'React Context API' },
      ],
    },
  ];

  if (user?.role !== 'ADMIN') {
    return (
      <Layout>
        <div className="flex flex-col items-center justify-center py-20 gap-3">
          <AlertCircle size={40} className="text-slate-300" />
          <p className="text-base font-semibold text-slate-700">Access Denied</p>
          <p className="text-sm text-slate-500">You don't have permission to view system information.</p>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Administration</p>
            <h1 className="page-title mt-1">System</h1>
            <p className="page-subtitle">Platform status, services and environment configuration.</p>
          </div>
          <button
            type="button"
            onClick={fetchHealth}
            disabled={loading}
            className="btn-secondary"
          >
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* ── Overall status banner ── */}
        <div className={`flex items-center gap-3 rounded-xl border px-4 py-3 ${
          health?.status === 'online'
            ? 'border-emerald-200 bg-emerald-50'
            : health?.status === 'degraded'
            ? 'border-amber-200 bg-amber-50'
            : 'border-slate-200 bg-slate-50'
        }`}>
          {loading ? (
            <div className="skeleton h-4 w-48 rounded" />
          ) : (
            <>
              {health?.status === 'online'
                ? <CheckCircle2 size={16} className="text-emerald-600 shrink-0" />
                : <AlertCircle size={16} className="text-amber-600 shrink-0" />
              }
              <span className={`text-sm font-semibold ${health?.status === 'online' ? 'text-emerald-800' : 'text-amber-800'}`}>
                {health?.status === 'online' ? 'All systems operational' : 'Service degraded — some features may be unavailable'}
              </span>
              {lastPing && (
                <span className="ml-auto flex items-center gap-1 text-xs text-slate-500">
                  <Clock size={11} />
                  Last checked {lastPing.toLocaleTimeString()}
                </span>
              )}
            </>
          )}
        </div>

        {/* ── Metrics bar ── */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <MetricPill
            label="API Latency"
            value={health?.latency ?? '—'}
            unit={health?.latency != null ? ' ms' : ''}
            color={health?.latency < 200 ? 'text-emerald-600' : health?.latency < 500 ? 'text-amber-600' : 'text-red-600'}
            loading={loading}
          />
          <MetricPill label="Active Services" value="4" unit="" color="text-brand-600" loading={loading} />
          <MetricPill label="React Version"   value="19" unit="" color="text-violet-600" loading={false} />
          <MetricPill label="API Version"     value="v1" unit="" color="text-teal-600" loading={false} />
        </div>

        {/* ── Service cards grid ── */}
        <div className="grid gap-4 md:grid-cols-2">
          {SERVICES.map(svc => (
            <ServiceCard key={svc.title} {...svc} loading={loading} />
          ))}
        </div>

        {/* ── Environment config ── */}
        <div className="card">
          <div className="card-header">
            <h2 className="card-title">Environment Configuration</h2>
            <span className="badge badge-slate">
              <Zap size={10} />
              Runtime
            </span>
          </div>
          <div className="card-body">
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <p className="section-label mb-3">Backend</p>
                <div className="space-y-2">
                  {[
                    { k: 'DJANGO_SETTINGS_MODULE', v: 'enterprise_platform.settings' },
                    { k: 'DEBUG',                  v: 'True (development)' },
                    { k: 'ALLOWED_HOSTS',          v: 'localhost, 127.0.0.1' },
                    { k: 'CORS_ALLOWED_ORIGINS',   v: 'Configured' },
                  ].map(e => (
                    <div key={e.k} className="flex items-start gap-2 rounded-md bg-slate-50 px-3 py-2">
                      <span className="font-mono text-2xs text-slate-500 shrink-0 mt-0.5">{e.k}</span>
                      <span className="font-mono text-2xs text-slate-800 break-all">{e.v}</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <p className="section-label mb-3">Frontend</p>
                <div className="space-y-2">
                  {[
                    { k: 'REACT_APP_API_URL', v: apiBase },
                    { k: 'NODE_ENV',          v: process.env.NODE_ENV || 'development' },
                    { k: 'BUILD_TARGET',      v: 'CRA (react-scripts)' },
                    { k: 'ROUTER',            v: 'HashRouter' },
                  ].map(e => (
                    <div key={e.k} className="flex items-start gap-2 rounded-md bg-slate-50 px-3 py-2">
                      <span className="font-mono text-2xs text-slate-500 shrink-0 mt-0.5">{e.k}</span>
                      <span className="font-mono text-2xs text-slate-800 break-all">{e.v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default System;
