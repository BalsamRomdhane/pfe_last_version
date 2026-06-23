import React, { useContext, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import {
  LayoutDashboard,
  FileText,
  ScanSearch,
  BookOpen,
  ClipboardCheck,
  Layers,
  Database,
  BarChart3,
  Brain,
  GitBranch,
  ShieldCheck,
  Users,
  Building2,
  Settings,
  ChevronDown,
  ChevronRight,
  X,
  Bell,
  Activity,
} from 'lucide-react';

// ── Navigation config ─────────────────────────────────────────────────────────
const NAV = [
  {
    title: 'Overview',
    items: [
      { label: 'Dashboard',     icon: LayoutDashboard, path: '/dashboard',             roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
      { label: 'Documents',     icon: FileText,         path: '/documents',             roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
      { label: 'Validations',   icon: ClipboardCheck,   path: '/validations',           roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
    ],
  },
  {
    title: 'Compliance',
    items: [
      { label: 'Standards',           icon: BookOpen,    path: '/normes',               roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Document Analysis',   icon: ScanSearch,  path: '/document-analysis',    roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Evidence Library',    icon: Layers,      path: '/evidence-intelligence',roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Semantic Search',     icon: Brain,       path: '/semantic-search',      roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Compliance Dashboard',icon: ShieldCheck, path: '/compliance-dashboard', roles: ['ADMIN','TEAMLEAD'] },
    ],
  },
  {
    title: 'AI & ML',
    items: [
      { label: 'AI Insights',       icon: Activity,   path: '/ai-insights',        roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Training Dataset',  icon: Database,   path: '/training-dataset',   roles: ['ADMIN'] },
      { label: 'Dataset Quality',   icon: BarChart3,  path: '/dataset-quality',    roles: ['ADMIN'] },
      { label: 'ML Dashboard',      icon: BarChart3,  path: '/ml-dashboard',       roles: ['ADMIN'] },
      { label: 'MLOps Pipeline',    icon: GitBranch,  path: '/admin/mlops',        roles: ['ADMIN'] },
    ],
  },
  {
    title: 'Administration',
    items: [
      { label: 'Users',       icon: Users,     path: '/users',       roles: ['ADMIN'] },
      { label: 'Departments', icon: Building2, path: '/departments', roles: ['ADMIN'] },
      { label: 'System',      icon: Settings,  path: '/system',      roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
    ],
  },
];

// ── Role colour ───────────────────────────────────────────────────────────────
const ROLE_STYLE = {
  ADMIN:    { bg: 'bg-sky-500/20',     text: 'text-sky-300',    dot: 'bg-sky-400' },
  TEAMLEAD: { bg: 'bg-violet-500/20',  text: 'text-violet-300', dot: 'bg-violet-400' },
  EMPLOYEE: { bg: 'bg-emerald-500/20', text: 'text-emerald-300',dot: 'bg-emerald-400' },
};

// ── Section component ─────────────────────────────────────────────────────────
function Section({ title, items, location, onClose, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  if (items.length === 0) return null;

  return (
    <div className="mb-1">
      {/* Section header */}
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-slate-500 hover:text-slate-400 transition-colors"
      >
        <span>{title}</span>
        {open
          ? <ChevronDown size={11} className="text-slate-600" />
          : <ChevronRight size={11} className="text-slate-600" />
        }
      </button>

      {/* Items */}
      {open && (
        <div className="space-y-0.5 pb-2">
          {items.map(item => {
            const active = location.pathname === item.path ||
                           (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
            const Icon = item.icon;
            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={`group relative flex items-center gap-3 rounded-xl px-3 py-2.5 transition-all duration-150 ${
                  active
                    ? 'bg-sky-500/15 text-white'
                    : 'text-slate-400 hover:bg-white/5 hover:text-slate-200'
                }`}
              >
                {/* Active indicator pill */}
                {active && (
                  <span className="absolute left-0 top-1/2 h-5 w-0.5 -translate-y-1/2 rounded-full bg-sky-400" />
                )}

                {/* Icon */}
                <div className={`flex h-7 w-7 items-center justify-center rounded-lg flex-shrink-0 transition-colors ${
                  active ? 'bg-sky-500/20 text-sky-400' : 'text-slate-500 group-hover:text-slate-300'
                }`}>
                  <Icon size={15} />
                </div>

                {/* Label */}
                <span className={`text-sm font-medium leading-none ${active ? 'text-white' : ''}`}>
                  {item.label}
                </span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Main Sidebar ──────────────────────────────────────────────────────────────
const Sidebar = ({ mobileOpen, onClose }) => {
  const { user } = useContext(UserContext);
  const location = useLocation();
  const { unreadCount } = useNotifications();

  const role = user?.role || '';
  const roleStyle = ROLE_STYLE[role] || ROLE_STYLE.EMPLOYEE;

  // Filter sections by role
  const filtered = NAV.map(section => ({
    ...section,
    items: section.items.filter(i => i.roles.includes(role)),
  }));

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <button
          type="button"
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-label="Close sidebar"
        />
      )}

      {/* Sidebar panel */}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 flex-col bg-slate-950 shadow-2xl transition-transform duration-300 md:z-30 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        }`}
      >
        {/* ── Logo / Brand ── */}
        <div className="flex items-center justify-between border-b border-white/5 px-4 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-sky-500 shadow-lg shadow-sky-500/30">
              <ShieldCheck size={18} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold leading-tight text-white">Compliance</p>
              <p className="text-[10px] uppercase tracking-[0.2em] text-slate-500">Enterprise Suite</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-lg text-slate-500 hover:bg-white/5 hover:text-slate-300 transition-colors md:hidden"
          >
            <X size={15} />
          </button>
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 overflow-y-auto px-3 py-4 scrollbar-thin scrollbar-track-transparent scrollbar-thumb-white/10">
          {filtered.map((section, i) => (
            <Section
              key={section.title}
              title={section.title}
              items={section.items}
              location={location}
              onClose={onClose}
              defaultOpen={i < 3}
            />
          ))}
        </nav>

        {/* ── Quick links ── */}
        <div className="border-t border-white/5 px-3 py-3">
          <Link
            to="/dashboard"
            onClick={onClose}
            className="flex items-center justify-between rounded-xl px-3 py-2 text-slate-500 hover:bg-white/5 hover:text-slate-300 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Bell size={13} />
              <span className="text-xs font-medium">Notifications</span>
            </div>
            {unreadCount > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white leading-none">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </Link>
        </div>

        {/* ── User profile ── */}
        <div className="border-t border-white/5 p-3">
          <div className="flex items-center gap-3 rounded-xl bg-white/5 px-3 py-3">
            {/* Avatar */}
            <div className="relative flex-shrink-0">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-700 text-sm font-bold text-white select-none">
                {user?.username?.charAt(0)?.toUpperCase() || 'A'}
              </div>
              {/* Online dot */}
              <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-slate-950 ${roleStyle.dot}`} />
            </div>

            {/* Info */}
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold leading-tight text-white">
                {user?.username || 'User'}
              </p>
              <span className={`mt-0.5 inline-flex items-center rounded-md px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wide ${roleStyle.bg} ${roleStyle.text}`}>
                {role || '—'}
              </span>
            </div>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
