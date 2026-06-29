import React, { useContext, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import {
  LayoutDashboard, FileText, ClipboardCheck, BookOpen,
  ScanSearch, Layers, Brain, ShieldCheck, Users, Building2,
  Settings, ChevronDown, X, Bell, Activity, Database,
  BarChart3, GitBranch, Sparkles, Lock,
} from 'lucide-react';

/* ─── Navigation tree ──────────────────────────────────────────────────── */
const NAV = [
  {
    title: 'Overview',
    items: [
      { label: 'Dashboard',   icon: LayoutDashboard, path: '/dashboard',  roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
      { label: 'Documents',   icon: FileText,        path: '/documents',  roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
      { label: 'Validations', icon: ClipboardCheck,  path: '/validations',roles: ['ADMIN','TEAMLEAD','EMPLOYEE'] },
    ],
  },
  {
    title: 'Compliance',
    items: [
      { label: 'Standards',            icon: BookOpen,    path: '/normes',               roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Document Analysis',    icon: ScanSearch,  path: '/document-analysis',    roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Evidence Library',     icon: Layers,      path: '/evidence-intelligence',roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Semantic Search',      icon: Brain,       path: '/semantic-search',      roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Compliance Dashboard', icon: ShieldCheck, path: '/compliance-dashboard', roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Document Security',    icon: Lock,        path: '/document-security',    roles: ['ADMIN','TEAMLEAD'] },
    ],
  },
  {
    title: 'AI & Machine Learning',
    items: [
      { label: 'AI Insights',      icon: Sparkles,   path: '/ai-insights',      roles: ['ADMIN','TEAMLEAD'] },
      { label: 'Training Dataset', icon: Database,   path: '/training-dataset', roles: ['ADMIN'] },
      { label: 'Dataset Quality',  icon: BarChart3,  path: '/dataset-quality',  roles: ['ADMIN'] },
      { label: 'ML Dashboard',     icon: Activity,   path: '/ml-dashboard',     roles: ['ADMIN'] },
      { label: 'MLOps Pipeline',   icon: GitBranch,  path: '/admin/mlops',      roles: ['ADMIN'] },
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

/* ─── Role styles ───────────────────────────────────────────────────────── */
const ROLE_CFG = {
  ADMIN:    { badge: 'bg-amber-500/20 text-amber-300',    dot: 'bg-amber-400'   },
  TEAMLEAD: { badge: 'bg-violet-500/20 text-violet-300',  dot: 'bg-violet-400'  },
  EMPLOYEE: { badge: 'bg-emerald-500/20 text-emerald-300',dot: 'bg-emerald-400' },
};

/* ─── Section ───────────────────────────────────────────────────────────── */
function NavSection({ title, items, location, onClose, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!items.length) return null;

  return (
    <div className="mb-0.5">
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        className="flex w-full items-center justify-between px-3 py-2 group"
      >
        <span className="text-2xs font-bold uppercase tracking-[0.15em] text-slate-500 group-hover:text-slate-400 transition-colors">
          {title}
        </span>
        <ChevronDown
          size={12}
          className={`text-slate-600 transition-transform duration-200 ${open ? 'rotate-0' : '-rotate-90'}`}
        />
      </button>

      {open && (
        <div className="space-y-0.5 pb-3">
          {items.map(item => {
            const active =
              location.pathname === item.path ||
              (item.path !== '/dashboard' && location.pathname.startsWith(item.path));
            const Icon = item.icon;

            return (
              <Link
                key={item.path}
                to={item.path}
                onClick={onClose}
                className={`
                  group relative flex items-center gap-3 rounded-lg mx-1.5 px-3 py-2
                  transition-all duration-150
                  ${active
                    ? 'bg-brand-600/20 text-white'
                    : 'text-slate-400 hover:bg-white/[0.05] hover:text-slate-200'
                  }
                `}
              >
                {/* Active indicator */}
                {active && (
                  <span className="absolute left-0 top-1/2 h-4 w-0.5 -translate-y-1/2 rounded-r-full bg-brand-400" />
                )}

                <div className={`
                  flex h-6 w-6 shrink-0 items-center justify-center rounded-md transition-colors
                  ${active ? 'text-brand-300' : 'text-slate-500 group-hover:text-slate-300'}
                `}>
                  <Icon size={14} />
                </div>

                <span className="text-sm font-medium leading-none truncate">{item.label}</span>
              </Link>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Main Sidebar ─────────────────────────────────────────────────────── */
const Sidebar = ({ mobileOpen, onClose }) => {
  const { user } = useContext(UserContext);
  const location = useLocation();
  const { unreadCount } = useNotifications();

  const role      = user?.role || '';
  const roleCfg   = ROLE_CFG[role] || ROLE_CFG.EMPLOYEE;
  const filtered  = NAV.map(s => ({ ...s, items: s.items.filter(i => i.roles.includes(role)) }));

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && (
        <button
          type="button"
          aria-label="Close menu"
          className="fixed inset-0 z-40 bg-slate-950/60 backdrop-blur-sm md:hidden"
          onClick={onClose}
        />
      )}

      {/* Panel */}
      <aside className={`
        fixed inset-y-0 left-0 z-50 flex h-screen w-sidebar flex-col
        bg-slate-950 border-r border-white/[0.04]
        transition-transform duration-300 ease-in-out
        md:z-30 md:translate-x-0
        ${mobileOpen ? 'translate-x-0 shadow-2xl' : '-translate-x-full'}
      `}>

        {/* ── Branding ── */}
        <div className="flex items-center justify-between border-b border-white/[0.06] px-4 h-14 shrink-0">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 shadow-glow">
              <ShieldCheck size={16} className="text-white" />
            </div>
            <div>
              <p className="text-sm font-bold text-white leading-none">Compliance</p>
              <p className="text-2xs text-slate-500 uppercase tracking-widest mt-0.5">Enterprise Suite</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="btn-icon-sm md:hidden text-slate-500 hover:text-slate-300 hover:bg-white/10"
          >
            <X size={14} />
          </button>
        </div>

        {/* ── Navigation ── */}
        <nav className="flex-1 overflow-y-auto py-3 no-scrollbar">
          {filtered.map((section, i) => (
            <NavSection
              key={section.title}
              title={section.title}
              items={section.items}
              location={location}
              onClose={onClose}
              defaultOpen={i < 3}
            />
          ))}
        </nav>

        {/* ── Notifications shortcut ── */}
        <div className="border-t border-white/[0.06] px-3 py-2 shrink-0">
          <Link
            to="/dashboard"
            onClick={onClose}
            className="flex items-center justify-between rounded-lg px-3 py-2 text-slate-500 hover:bg-white/[0.05] hover:text-slate-300 transition-colors"
          >
            <div className="flex items-center gap-2">
              <Bell size={13} />
              <span className="text-xs font-medium">Notifications</span>
            </div>
            {unreadCount > 0 && (
              <span className="flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-2xs font-bold text-white">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </Link>
        </div>

        {/* ── User profile ── */}
        <div className="border-t border-white/[0.06] p-3 shrink-0">
          <div className="flex items-center gap-3 rounded-lg bg-white/[0.05] px-3 py-2.5">
            <div className="relative shrink-0">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-700 text-sm font-bold text-white select-none">
                {user?.username?.charAt(0)?.toUpperCase() || 'A'}
              </div>
              <span className={`absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-slate-950 ${roleCfg.dot}`} />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-xs font-semibold text-white leading-none">
                {user?.username || 'User'}
              </p>
              <span className={`mt-1 inline-flex rounded px-1.5 py-0.5 text-2xs font-bold uppercase tracking-wide ${roleCfg.badge}`}>
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
