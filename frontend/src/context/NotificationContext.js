/**
 * NotificationContext
 * Manages notification state — REST polling + WebSocket push.
 * No Redis needed: Django uses InMemoryChannelLayer.
 */
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import api from '../services/api';
import { UserContext } from './UserContext';

export const NotificationContext = createContext({
  notifications: [],
  unreadCount: 0,
  loading: false,
  markRead: () => {},
  markAllRead: () => {},
  refresh: () => {},
});

const POLL_MS  = 30_000;
const MAX_SHOW = 50;

export function NotificationProvider({ children }) {
  const { user, token } = useContext(UserContext);

  const [notifications, setNotifications] = useState([]);
  const [unreadCount,   setUnreadCount]   = useState(0);
  const [loading,       setLoading]       = useState(false);

  const wsRef   = useRef(null);
  const pollRef = useRef(null);
  const mounted = useRef(true);

  // ── Fetch ────────────────────────────────────────────────────────────────
  const fetchNotifications = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const { data } = await api.get(`/notifications/?limit=${MAX_SHOW}`);
      if (!mounted.current) return;
      setNotifications(data.results || []);
      setUnreadCount(data.unread_count ?? 0);
    } catch { /* non-critical */ }
    finally { if (mounted.current) setLoading(false); }
  }, [user]);

  // ── Mark single read ──────────────────────────────────────────────────────
  const markRead = useCallback(async (id) => {
    setNotifications(prev => prev.map(n => n.id === id ? { ...n, is_read: true } : n));
    setUnreadCount(c => Math.max(0, c - 1));
    try { await api.post(`/notifications/${id}/read/`); }
    catch { fetchNotifications(); }
  }, [fetchNotifications]);

  // ── Mark all read ─────────────────────────────────────────────────────────
  const markAllRead = useCallback(async () => {
    setNotifications(prev => prev.map(n => ({ ...n, is_read: true })));
    setUnreadCount(0);
    try { await api.post('/notifications/read-all/'); }
    catch { fetchNotifications(); }
  }, [fetchNotifications]);

  // ── Polling ───────────────────────────────────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(() => {
      if (mounted.current) fetchNotifications();
    }, POLL_MS);
  }, [fetchNotifications]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  // ── WebSocket ─────────────────────────────────────────────────────────────
  const connectWebSocket = useCallback(() => {
    if (!token || !user) return;
    if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
    try {
      const base  = (process.env.REACT_APP_API_URL || 'http://localhost:8000/api')
                      .replace(/\/api\/?$/, '')
                      .replace(/^https/, 'wss')
                      .replace(/^http/, 'ws');
      const ws = new WebSocket(`${base}/api/ws/notifications/?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;
      ws.onopen = () => stopPolling();
      ws.onmessage = (e) => {
        try {
          const msg = JSON.parse(e.data);
          if (msg.type === 'notification' && msg.notification) {
            const n = msg.notification;
            setNotifications(prev => prev.some(x => x.id === n.id) ? prev : [n, ...prev].slice(0, MAX_SHOW));
            if (!n.is_read) setUnreadCount(c => c + 1);
          }
        } catch { /* ignore */ }
      };
      ws.onclose = () => { wsRef.current = null; if (mounted.current && user) startPolling(); };
      ws.onerror = () => {
        wsRef.current = null;
        if (mounted.current && user) startPolling();
      };
    } catch { startPolling(); }
  }, [token, user, startPolling, stopPolling]);

  // ── Effect ────────────────────────────────────────────────────────────────
  useEffect(() => {
    mounted.current = true;
    if (!user) {
      setNotifications([]); setUnreadCount(0); stopPolling();
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
      return;
    }
    fetchNotifications();
    connectWebSocket();
    startPolling();
    return () => {
      mounted.current = false;
      stopPolling();
      if (wsRef.current) { wsRef.current.onclose = null; wsRef.current.close(); wsRef.current = null; }
    };
  }, [user, fetchNotifications, connectWebSocket, startPolling, stopPolling]);

  return (
    <NotificationContext.Provider value={{ notifications, unreadCount, loading, markRead, markAllRead, refresh: fetchNotifications }}>
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationContext);
}
