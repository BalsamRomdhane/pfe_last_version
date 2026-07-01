import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNotifications } from '../../context/NotificationContext';
import Layout from '../../components/Layout';
import {
  Bell, CheckCheck, X, Filter, Search,
  CheckCircle, XCircle, Clock, TrendingDown,
  AlertTriangle, Info, FileText, ChevronRight,
  Inbox,
} from 'lucide-react';

/* ─── Notification type config ─────────────────────────────────────────── */
const N_CFG = {
  DOCUMENT_SUBMITTED:  { icon: Info,          color: 'text-sky-600',    bg: 'bg-sky-50',      label: 'Soumission'   },
  DOCUMENT_APPROVED:   { icon: CheckCircle,   color: 'text-emerald-600',bg: 'bg-emerald-50',  label: 'Approbation'  },
  DOCUMENT_REJECTED:   { icon: XCircle,       color: 'text-red-600',    bg: 'bg-red-50',      label: 'Rejet'        },
  VALIDATION_REQUIRED: { icon: Clock,         color: 'text-amber-600',  bg: 'bg-amber-50',    label: 'Validation'   },
  AUDIT_DEADLINE:      { icon: Clock,         color: 'text-orange-600', bg: 'bg-orange-50',   label: 'Échéance'     },
  COMPLIANCE_GAP:      { icon: AlertTriangle, color: 'text-amber-600',  bg: 'bg-amber-50',    label: 'Écart'        },
  CRITICAL_RISK:       { icon: AlertTriangle, color: 'text-red-600',    bg: 'bg-red-50',      label: 'Risque'       },
  ML_DRIFT:            { icon: TrendingDown,  color: 'text-purple-600', bg: 'bg-purple-50',   label: 'ML Drift'     },
  REVIEW_OVERDUE:      { icon: Clock,         color: 'text-red-600',    bg: 'bg-red-50',      label: 'En retard'    },
  GENERAL:             { icon: Bell,          color: 'text-slate-500',  bg: 'bg-slate-100',   label: 'Général'      },
};

const PRIORITY_CFG = {
  CRITICAL: { cls: 'bg-red-100 text-red-700 ring-1 ring-red-200',       label: 'Critique'  },
  HIGH:     { cls: 'bg-orange-100 text-orange-700 ring-1 ring-orange-200', label: 'Haute'  },
  MEDIUM:   { cls: 'bg-sky-100 text-sky-700 ring-1 ring-sky-200',        label: 'Moyenne'   },
  LOW:      { cls: 'bg-slate-100 text-slate-600 ring-1 ring-slate-200',  label: 'Basse'     },
};

/* ─── helpers ─────────────────────────────────────────────────────────── */
function timeAgo(iso) {
  if (!iso) return '';
  const diff = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (diff < 60)    return `${diff}s`;
  if (diff < 3600)  return `${Math.floor(diff / 60)}min`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h`;
  if (diff < 604800)return `${Math.floor(diff / 86400)}j`;
  return new Date(iso).toLocaleDateString('fr-FR', { day: '2-digit', month: 'short' });
}

function getDocumentLink(n) {
  if (!n.related_object_type || !n.related_object_id) return null;
  if (n.related_object_type === 'Document') return `/documents/${n.related_object_id}`;
  return null;
}

/* ─── Notification card ────────────────────────────────────────────────── */
function NotifCard({ n, onMark }) {
  const navigate = useNavigate();
  const cfg  = N_CFG[n.notification_type] || N_CFG.GENERAL;
  const prio = PRIORITY_CFG[n.priority] || PRIORITY_CFG.MEDIUM;
  const Icon = cfg.icon;
  const docLink = getDocumentLink(n);

  const handleClick = () => {
    if (!n.is_read) onMark(n.id);
    if (docLink) navigate(docLink);
  };

  return (
    <div className={`group relative rounded-xl border transition-all duration-150
      ${!n.is_read ? 'border-brand-200 bg-brand-50/40 hover:bg-brand-50' : 'border-slate-200 bg-white hover:bg-slate-50'}
    `}>
      {/* Unread indicator */}
      {!n.is_read && (
        <span className="absolute left-3 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-brand-500" />
      )}

      <div className={`flex items-start gap-4 p-4 ${!n.is_read ? 'pl-8' : ''}`}>
        {/* Icon */}
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${cfg.bg}`}>
          <Icon size={16} className={cfg.color} />
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-start gap-2">
            <p className={`text-sm font-semibold leading-snug flex-1 ${n.is_read ? 'text-slate-600' : 'text-slate-900'}`}>
              {n.title}
            </p>
            <div className="flex items-center gap-1.5 shrink-0">
              <span className={`badge text-2xs ${prio.cls}`}>{prio.label}</span>
              <span className="text-2xs text-slate-400">{timeAgo(n.created_at)}</span>
            </div>
          </div>
          {n.message && (
            <p className="mt-1 text-xs text-slate-500 truncate-2 leading-relaxed">{n.message}</p>
          )}
          <div className="mt-2 flex items-center gap-2 flex-wrap">
            <span className="badge badge-slate text-2xs">{cfg.label}</span>
            {docLink && (
              <button
                type="button"
                onClick={handleClick}
                className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-800 transition-colors"
              >
                <FileText size={11} />
                Voir le document <ChevronRight size={11} />
              </button>
            )}
            {!n.is_read && (
              <button
                type="button"
                onClick={() => onMark(n.id)}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors ml-auto"
              >
                Marquer comme lu
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Filter chip ─────────────────────────────────────────────────────── */
function FilterChip({ label, active, count, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-all
        ${active
          ? 'border-brand-400 bg-brand-50 text-brand-700'
          : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50'
        }`}
    >
      {label}
      {count !== undefined && (
        <span className={`rounded-full px-1.5 py-0.5 text-2xs font-bold
          ${active ? 'bg-brand-100 text-brand-700' : 'bg-slate-100 text-slate-500'}`}>
          {count}
        </span>
      )}
    </button>
  );
}

/* ═══════════════════════════════════════════════════════════════════════════
   EMPLOYEE NOTIFICATIONS PAGE
═══════════════════════════════════════════════════════════════════════════ */
export default function EmployeeNotifications() {
  const { notifications, unreadCount, loading, markRead, markAllRead } = useNotifications();

  const [search,     setSearch]     = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [readFilter, setReadFilter] = useState('ALL'); // ALL | UNREAD | READ

  /* ── Computed ── */
  const filtered = useMemo(() => {
    let list = notifications;

    if (readFilter === 'UNREAD') list = list.filter(n => !n.is_read);
    if (readFilter === 'READ')   list = list.filter(n =>  n.is_read);

    if (typeFilter !== 'ALL') {
      list = list.filter(n => n.notification_type === typeFilter);
    }

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      list = list.filter(n =>
        n.title?.toLowerCase().includes(q) ||
        n.message?.toLowerCase().includes(q)
      );
    }

    return list;
  }, [notifications, search, typeFilter, readFilter]);

  /* ── Unique types present ── */
  const types = useMemo(() => {
    const seen = new Set(notifications.map(n => n.notification_type));
    return Array.from(seen);
  }, [notifications]);

  /* ── Count by type ── */
  const countByType = useMemo(() => {
    const map = {};
    notifications.forEach(n => {
      map[n.notification_type] = (map[n.notification_type] || 0) + 1;
    });
    return map;
  }, [notifications]);

  /* ── Group by date ── */
  const grouped = useMemo(() => {
    const today     = new Date().toDateString();
    const yesterday = new Date(Date.now() - 86400000).toDateString();
    const groups    = {};

    filtered.forEach(n => {
      const d = new Date(n.created_at);
      let key;
      if (d.toDateString() === today)     key = "Aujourd'hui";
      else if (d.toDateString() === yesterday) key = 'Hier';
      else key = d.toLocaleDateString('fr-FR', { weekday: 'long', day: '2-digit', month: 'long' });

      if (!groups[key]) groups[key] = [];
      groups[key].push(n);
    });
    return groups;
  }, [filtered]);

  return (
    <Layout>
      <div className="page-container">

        {/* ── Header ── */}
        <div className="page-header">
          <div>
            <p className="section-label">Mon espace</p>
            <h1 className="page-title mt-1">Notifications</h1>
            <p className="page-subtitle">
              {unreadCount > 0
                ? `${unreadCount} notification${unreadCount > 1 ? 's' : ''} non lue${unreadCount > 1 ? 's' : ''}`
                : 'Toutes vos notifications sont lues'}
            </p>
          </div>
          {unreadCount > 0 && (
            <button type="button" onClick={markAllRead}
              className="btn-secondary">
              <CheckCheck size={14} />
              Tout marquer comme lu
            </button>
          )}
        </div>

        {/* ── Search bar ── */}
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="search"
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Rechercher dans les notifications…"
            className="form-input pl-9"
          />
          {search && (
            <button type="button" onClick={() => setSearch('')}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600">
              <X size={13} />
            </button>
          )}
        </div>

        {/* ── Filter chips ── */}
        <div className="flex flex-wrap gap-2 items-center">
          <span className="flex items-center gap-1.5 text-xs font-medium text-slate-500">
            <Filter size={12} /> Filtres :
          </span>

          {/* Read status */}
          <FilterChip label="Toutes"         active={readFilter === 'ALL'}    onClick={() => setReadFilter('ALL')}    count={notifications.length} />
          <FilterChip label="Non lues"       active={readFilter === 'UNREAD'} onClick={() => setReadFilter('UNREAD')} count={unreadCount} />
          <FilterChip label="Lues"           active={readFilter === 'READ'}   onClick={() => setReadFilter('READ')} />

          {notifications.length > 0 && <span className="text-slate-200 select-none">|</span>}

          {/* Type filters */}
          <FilterChip label="Tous les types" active={typeFilter === 'ALL'} onClick={() => setTypeFilter('ALL')} />
          {types.map(t => {
            const cfg = N_CFG[t] || N_CFG.GENERAL;
            return (
              <FilterChip
                key={t}
                label={cfg.label}
                active={typeFilter === t}
                count={countByType[t]}
                onClick={() => setTypeFilter(typeFilter === t ? 'ALL' : t)}
              />
            );
          })}
        </div>

        {/* ── Content ── */}
        {loading && notifications.length === 0 ? (
          <div className="space-y-3">
            {[1,2,3,4].map(i => (
              <div key={i} className="rounded-xl border border-slate-200 bg-white p-4 animate-pulse">
                <div className="flex gap-3">
                  <div className="skeleton h-9 w-9 rounded-xl shrink-0" />
                  <div className="flex-1 space-y-2">
                    <div className="skeleton h-4 w-3/4" />
                    <div className="skeleton h-3 w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-20">
            <div className="flex h-16 w-16 items-center justify-center rounded-2xl bg-slate-100">
              <Inbox size={28} className="text-slate-300" />
            </div>
            <p className="text-base font-semibold text-slate-700">
              {search || typeFilter !== 'ALL' || readFilter !== 'ALL'
                ? 'Aucune notification correspond à vos filtres'
                : 'Aucune notification'}
            </p>
            <p className="text-sm text-slate-400">
              {search || typeFilter !== 'ALL' || readFilter !== 'ALL'
                ? 'Essayez de modifier les filtres ci-dessus.'
                : "Vous n'avez pas encore reçu de notifications."}
            </p>
            {(search || typeFilter !== 'ALL' || readFilter !== 'ALL') && (
              <button type="button"
                onClick={() => { setSearch(''); setTypeFilter('ALL'); setReadFilter('ALL'); }}
                className="btn-secondary btn-sm mt-1">
                Réinitialiser les filtres
              </button>
            )}
          </div>
        ) : (
          <div className="space-y-6">
            {Object.entries(grouped).map(([date, items]) => (
              <div key={date}>
                <div className="flex items-center gap-3 mb-3">
                  <p className="text-xs font-bold uppercase tracking-wider text-slate-400">{date}</p>
                  <div className="flex-1 h-px bg-slate-100" />
                  <span className="text-2xs text-slate-400">{items.length} notification{items.length > 1 ? 's' : ''}</span>
                </div>
                <div className="space-y-2">
                  {items.map(n => (
                    <NotifCard key={n.id} n={n} onMark={markRead} />
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}

        {/* ── Stats footer ── */}
        {notifications.length > 0 && (
          <div className="flex items-center justify-between text-xs text-slate-400 pt-2 border-t border-slate-100">
            <span>{notifications.length} notification{notifications.length > 1 ? 's' : ''} au total</span>
            <span>{filtered.length} affichée{filtered.length > 1 ? 's' : ''}</span>
          </div>
        )}
      </div>
    </Layout>
  );
}
