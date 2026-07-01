import React, { useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import {
  Bell, Search, Menu, ChevronDown, LogOut, X,
  CheckCheck, AlertTriangle, CheckCircle, XCircle,
  Clock, TrendingDown, Info, Settings,
} from 'lucide-react';

/* ─── Notification type config ─────────────────────────────────────────── */
const N_CFG = {
  DOCUMENT_SUBMITTED:  { icon: Info,          color: 'text-sky-500',    bg: 'bg-sky-50/80'      },
  DOCUMENT_APPROVED:   { icon: CheckCircle,   color: 'text-emerald-500',bg: 'bg-emerald-50/80'  },
  DOCUMENT_REJECTED:   { icon: XCircle,       color: 'text-red-500',    bg: 'bg-red-50/80'      },
  VALIDATION_REQUIRED: { icon: Clock,         color: 'text-amber-500',  bg: 'bg-amber-50/80'    },
  AUDIT_DEADLINE:      { icon: Clock,         color: 'text-orange-500', bg: 'bg-orange-50/80'   },
  COMPLIANCE_GAP:      { icon: AlertTriangle, color: 'text-amber-500',  bg: 'bg-amber-50/80'    },
  CRITICAL_RISK:       { icon: AlertTriangle, color: 'text-red-500',    bg: 'bg-red-50/80'      },
  ML_DRIFT:            { icon: TrendingDown,  color: 'text-purple-500', bg: 'bg-purple-50/80'   },
  REVIEW_OVERDUE:      { icon: Clock,         color: 'text-red-500',    bg: 'bg-red-50/80'      },
  GENERAL:             { icon: Bell,          color: 'text-slate-400',  bg: 'bg-slate-50'       },
};

const PRIORITY_CLS = {
  CRITICAL: 'badge-red',
  HIGH:     'bg-orange-50 text-orange-700 ring-1 ring-orange-200',
  MEDIUM:   'badge-sky',
  LOW:      'badge-slate',
};

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)    return `${diff}s`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  return `${Math.floor(diff / 86400)}d`;
}

/* ─── Notification Bell ─────────────────────────────────────────────────── */
function NotificationBell() {
  const { notifications, unreadCount, loading, markRead, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const h = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    if (open) document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [open]);

  useEffect(() => {
    const h = (e) => { if (e.key === 'Escape') setOpen(false); };
    if (open) document.addEventListener('keydown', h);
    return () => document.removeEventListener('keydown', h);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        className={`
          relative flex h-9 w-9 items-center justify-center rounded-lg
          border transition-all duration-150
          ${open
            ? 'border-brand-300 bg-brand-50 text-brand-600'
            : 'border-slate-200 bg-white text-slate-500 hover:border-slate-300 hover:text-slate-700'
          }
          shadow-sm
        `}
      >
        <Bell size={16} />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-2xs font-bold text-white shadow-sm">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 z-50 mt-2 w-96 animate-scale-in overflow-hidden rounded-xl border border-slate-200 bg-white shadow-dropdown">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-slate-900">Notifications</span>
              {unreadCount > 0 && (
                <span className="badge badge-red">{unreadCount}</span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-brand-600 hover:bg-brand-50 transition-colors"
                >
                  <CheckCheck size={12} />
                  All read
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="btn-icon-sm"
              >
                <X size={13} />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-80 overflow-y-auto divide-y divide-slate-50">
            {loading && notifications.length === 0 ? (
              <div className="space-y-3 p-4">
                {[1,2,3].map(i => (
                  <div key={i} className="flex gap-3">
                    <div className="skeleton h-7 w-7 rounded-lg shrink-0" />
                    <div className="flex-1 space-y-1.5">
                      <div className="skeleton skeleton-text w-3/4" />
                      <div className="skeleton skeleton-text w-1/2" />
                    </div>
                  </div>
                ))}
              </div>
            ) : notifications.length === 0 ? (
              <div className="empty-state py-10">
                <div className="empty-state-icon">
                  <Bell size={20} />
                </div>
                <p className="empty-state-title text-sm">All caught up</p>
                <p className="text-xs text-slate-400">No notifications yet</p>
              </div>
            ) : (
              notifications.map(n => {
                const cfg  = N_CFG[n.notification_type] || N_CFG.GENERAL;
                const Icon = cfg.icon;
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => !n.is_read && markRead(n.id)}
                    className={`
                      flex w-full items-start gap-3 px-4 py-3 text-left
                      transition-colors hover:bg-slate-50
                      ${!n.is_read ? 'bg-brand-50/30' : ''}
                    `}
                  >
                    <div className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${cfg.bg}`}>
                      <Icon size={13} className={cfg.color} />
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-xs font-semibold leading-snug ${n.is_read ? 'text-slate-500' : 'text-slate-900'}`}>
                          {n.title}
                        </p>
                        <span className="shrink-0 text-2xs text-slate-400">{timeAgo(n.created_at)}</span>
                      </div>
                      <p className="mt-0.5 text-xs text-slate-500 truncate-2">{n.message}</p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className={`badge text-2xs ${PRIORITY_CLS[n.priority] || PRIORITY_CLS.MEDIUM}`}>
                          {n.priority}
                        </span>
                        {!n.is_read && (
                          <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                        )}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {notifications.length > 0 && (
            <div className="border-t border-slate-100 px-4 py-2 text-center">
              <span className="text-2xs text-slate-400">{notifications.length} most recent shown</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Main Topbar ───────────────────────────────────────────────────────── */
const Topbar = ({ onToggleSidebar }) => {
  const { user, logout } = useContext(UserContext);
  const navigate = useNavigate();
  const [search, setSearch]     = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const handleLogout = () => { logout(); navigate('/login'); };

  /* Navigate on Enter / submit search */
  const handleSearchSubmit = (e) => {
    e.preventDefault();
    const q = search.trim();
    if (!q) return;
    navigate(`/documents?search=${encodeURIComponent(q)}`);
    setSearch('');
  };

  useEffect(() => {
    const h = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    if (menuOpen) document.addEventListener('mousedown', h);
    return () => document.removeEventListener('mousedown', h);
  }, [menuOpen]);

  const ROLE_COLOR = { ADMIN: 'text-amber-600', TEAMLEAD: 'text-violet-600', EMPLOYEE: 'text-emerald-600' };

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between gap-4 px-4 sm:px-6">

        {/* Left */}
        <div className="flex items-center gap-3">
          {/* Mobile menu toggle */}
          <button
            type="button"
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
            className="btn-icon-md md:hidden border border-slate-200 shadow-sm hover:bg-slate-50"
          >
            <Menu size={16} />
          </button>

          {/* Search bar */}
          <form
            onSubmit={handleSearchSubmit}
            className="hidden items-center gap-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-1.5 sm:flex"
          >
            <Search size={14} className="text-slate-400 shrink-0" />
            <input
              type="search"
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Rechercher des documents…"
              className="w-44 bg-transparent text-sm text-slate-900 placeholder:text-slate-400 outline-none lg:w-60"
            />
            {search && (
              <button type="button" onClick={() => setSearch('')} className="text-slate-400 hover:text-slate-600">
                <X size={13} />
              </button>
            )}
          </form>
        </div>

        {/* Right */}
        <div className="flex items-center gap-2">
          <NotificationBell />

          {/* User menu */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen(v => !v)}
              className={`
                flex items-center gap-2.5 rounded-lg border px-2.5 py-1.5
                transition-all duration-150 shadow-sm
                ${menuOpen
                  ? 'border-brand-300 bg-brand-50'
                  : 'border-slate-200 bg-white hover:border-slate-300'
                }
              `}
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-md bg-brand-600 text-xs font-bold text-white select-none">
                {user?.username?.charAt(0)?.toUpperCase() || 'A'}
              </div>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-semibold text-slate-900 leading-none">{user?.username}</p>
                <p className={`text-2xs font-semibold uppercase tracking-wider mt-0.5 ${ROLE_COLOR[user?.role] || 'text-slate-500'}`}>
                  {user?.role}
                </p>
              </div>
              <ChevronDown size={13} className={`text-slate-400 transition-transform ${menuOpen ? 'rotate-180' : ''}`} />
            </button>

            {menuOpen && (
              <div className="absolute right-0 z-50 mt-2 w-56 animate-scale-in rounded-xl border border-slate-200 bg-white p-1.5 shadow-dropdown">
                {/* User info */}
                <div className="mb-1 rounded-lg bg-slate-50 px-3 py-3">
                  <p className="text-sm font-semibold text-slate-900 truncate">{user?.username}</p>
                  <p className={`text-xs font-semibold uppercase tracking-wider mt-0.5 ${ROLE_COLOR[user?.role] || 'text-slate-500'}`}>
                    {user?.role}
                  </p>
                </div>

                <button
                  type="button"
                  onClick={() => { navigate('/system'); setMenuOpen(false); }}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900"
                >
                  <Settings size={14} />
                  Settings
                </button>

                <div className="my-1 border-t border-slate-100" />

                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-sm text-red-600 transition-colors hover:bg-red-50"
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Topbar;
