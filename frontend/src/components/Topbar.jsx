import React, { useContext, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { UserContext } from '../context/UserContext';
import { useNotifications } from '../context/NotificationContext';
import {
  Bell, Search, Menu, ChevronDown, LogOut, X,
  CheckCheck, AlertTriangle, CheckCircle, XCircle,
  Clock, TrendingDown, Info,
} from 'lucide-react';

// ── Notification type config ──────────────────────────────────────────────────
const TYPE_CFG = {
  DOCUMENT_SUBMITTED:  { icon: Info,          color: 'text-sky-500',    bg: 'bg-sky-50'     },
  DOCUMENT_APPROVED:   { icon: CheckCircle,   color: 'text-emerald-500',bg: 'bg-emerald-50' },
  DOCUMENT_REJECTED:   { icon: XCircle,       color: 'text-rose-500',   bg: 'bg-rose-50'    },
  VALIDATION_REQUIRED: { icon: Clock,         color: 'text-amber-500',  bg: 'bg-amber-50'   },
  AUDIT_DEADLINE:      { icon: Clock,         color: 'text-orange-500', bg: 'bg-orange-50'  },
  COMPLIANCE_GAP:      { icon: AlertTriangle, color: 'text-amber-500',  bg: 'bg-amber-50'   },
  CRITICAL_RISK:       { icon: AlertTriangle, color: 'text-rose-500',   bg: 'bg-rose-50'    },
  ML_DRIFT:            { icon: TrendingDown,  color: 'text-purple-500', bg: 'bg-purple-50'  },
  REVIEW_OVERDUE:      { icon: Clock,         color: 'text-rose-500',   bg: 'bg-rose-50'    },
  GENERAL:             { icon: Bell,          color: 'text-slate-500',  bg: 'bg-slate-50'   },
};

const PRIORITY_BADGE = {
  CRITICAL: 'bg-rose-100 text-rose-700',
  HIGH:     'bg-orange-100 text-orange-700',
  MEDIUM:   'bg-sky-100 text-sky-700',
  LOW:      'bg-slate-100 text-slate-600',
};

function timeAgo(iso) {
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)    return `${diff}s ago`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

// ── Notification Bell Dropdown ────────────────────────────────────────────────
function NotificationBell() {
  const { notifications, unreadCount, loading, markRead, markAllRead } = useNotifications();
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    if (open) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') setOpen(false); };
    if (open) document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open]);

  return (
    <div className="relative" ref={ref}>
      {/* Bell button */}
      <button
        type="button"
        onClick={() => setOpen(v => !v)}
        aria-label={`Notifications${unreadCount > 0 ? `, ${unreadCount} unread` : ''}`}
        className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-500 shadow-sm transition hover:border-slate-300 hover:text-slate-700"
      >
        <Bell size={17} className={unreadCount > 0 ? 'text-sky-600' : ''} />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 flex h-4 min-w-[16px] items-center justify-center rounded-full bg-red-500 px-1 text-[9px] font-bold text-white leading-none">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {/* Dropdown */}
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-96 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-xl">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-slate-900">Notifications</span>
              {unreadCount > 0 && (
                <span className="rounded-full bg-red-500 px-1.5 py-0.5 text-[10px] font-bold text-white">
                  {unreadCount}
                </span>
              )}
            </div>
            <div className="flex items-center gap-1">
              {unreadCount > 0 && (
                <button
                  type="button"
                  onClick={markAllRead}
                  className="flex items-center gap-1 rounded-lg px-2 py-1 text-xs font-medium text-sky-600 hover:bg-sky-50 transition"
                  title="Mark all as read"
                >
                  <CheckCheck size={12} />
                  All read
                </button>
              )}
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 transition"
              >
                <X size={13} />
              </button>
            </div>
          </div>

          {/* List */}
          <div className="max-h-96 overflow-y-auto divide-y divide-slate-50">
            {loading && notifications.length === 0 ? (
              <div className="py-8 text-center text-sm text-slate-400 animate-pulse">Loading…</div>
            ) : notifications.length === 0 ? (
              <div className="flex flex-col items-center gap-2 py-10 text-slate-400">
                <Bell size={24} className="opacity-30" />
                <span className="text-sm">No notifications</span>
              </div>
            ) : (
              notifications.map(n => {
                const cfg  = TYPE_CFG[n.notification_type] || TYPE_CFG.GENERAL;
                const Icon = cfg.icon;
                return (
                  <button
                    key={n.id}
                    type="button"
                    onClick={() => !n.is_read && markRead(n.id)}
                    className={`flex w-full items-start gap-3 px-4 py-3 text-left transition hover:bg-slate-50 ${!n.is_read ? 'bg-sky-50/30' : ''}`}
                  >
                    {/* Icon */}
                    <div className={`mt-0.5 flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-lg ${cfg.bg}`}>
                      <Icon size={13} className={cfg.color} />
                    </div>
                    {/* Content */}
                    <div className="min-w-0 flex-1">
                      <div className="flex items-start justify-between gap-2">
                        <p className={`text-xs font-semibold leading-snug ${n.is_read ? 'text-slate-500' : 'text-slate-900'}`}>
                          {n.title}
                        </p>
                        <span className="flex-shrink-0 text-[10px] text-slate-400">{timeAgo(n.created_at)}</span>
                      </div>
                      <p className="mt-0.5 text-[11px] text-slate-500 line-clamp-2">{n.message}</p>
                      <div className="mt-1 flex items-center gap-1.5">
                        <span className={`rounded-full px-1.5 py-0.5 text-[9px] font-bold uppercase ${PRIORITY_BADGE[n.priority] || PRIORITY_BADGE.MEDIUM}`}>
                          {n.priority}
                        </span>
                        {!n.is_read && <span className="h-1.5 w-1.5 rounded-full bg-sky-500" />}
                      </div>
                    </div>
                  </button>
                );
              })
            )}
          </div>

          {/* Footer */}
          {notifications.length > 0 && (
            <div className="border-t border-slate-100 px-4 py-2 text-center">
              <span className="text-[10px] text-slate-400">{notifications.length} most recent</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Main Topbar ───────────────────────────────────────────────────────────────
const Topbar = ({ onToggleSidebar }) => {
  const { user, logout } = useContext(UserContext);
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef(null);

  const handleLogout = () => { logout(); navigate('/login'); };

  // Close user menu on outside click
  useEffect(() => {
    const handler = (e) => { if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false); };
    if (menuOpen) document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [menuOpen]);

  return (
    <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur-md shadow-sm">
      <div className="flex h-16 items-center justify-between gap-4 px-4 sm:px-6">

        {/* Left: hamburger + search */}
        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={onToggleSidebar}
            aria-label="Toggle sidebar"
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 bg-white text-slate-600 shadow-sm transition hover:bg-slate-50 md:hidden"
          >
            <Menu size={16} />
          </button>

          <div className="hidden items-center gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 sm:flex">
            <Search size={15} className="text-slate-400 flex-shrink-0" />
            <input
              type="search"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search…"
              className="w-48 bg-transparent text-sm text-slate-900 outline-none placeholder:text-slate-400 lg:w-64"
            />
          </div>
        </div>

        {/* Right: notifications + user */}
        <div className="flex items-center gap-2">
          <NotificationBell />

          {/* User menu */}
          <div className="relative" ref={menuRef}>
            <button
              type="button"
              onClick={() => setMenuOpen(v => !v)}
              className="flex items-center gap-2.5 rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm transition hover:border-slate-300"
            >
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-sky-600 text-xs font-bold text-white select-none">
                {user?.username?.charAt(0)?.toUpperCase() || 'A'}
              </div>
              <div className="hidden text-left sm:block">
                <p className="text-xs font-semibold text-slate-900 leading-tight">{user?.username}</p>
                <p className="text-[10px] uppercase tracking-wide text-sky-600">{user?.role}</p>
              </div>
              <ChevronDown size={14} className="text-slate-400" />
            </button>

            {menuOpen && (
              <div className="absolute right-0 z-50 mt-2 w-52 rounded-2xl border border-slate-200 bg-white p-2 shadow-xl">
                <div className="mb-2 rounded-xl bg-slate-50 px-3 py-3">
                  <p className="text-sm font-semibold text-slate-900">{user?.username}</p>
                  <p className="text-xs uppercase tracking-wide text-sky-600 mt-0.5">{user?.role}</p>
                </div>
                <button
                  type="button"
                  onClick={handleLogout}
                  className="flex w-full items-center justify-between rounded-xl bg-slate-100 px-3 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-200"
                >
                  <span>Sign out</span>
                  <LogOut size={14} />
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
