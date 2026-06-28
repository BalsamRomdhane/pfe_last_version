/**
 * NotificationContext
 * Manages notification state — REST polling + WebSocket push.
 * No Redis needed: Django uses InMemoryChannelLayer.
 *
 * FIX: WebSocket reconnection loop and "closed before established" errors
 * were caused by:
 *   1. startPolling() called alongside connectWebSocket() in the effect,
 *      so polling and WS ran simultaneously then raced on close/error.
 *   2. No reconnect delay — on WS failure the code immediately retried,
 *      hammering the server with failed handshakes.
 *   3. wsRef not guarded against double-close during React strict-mode
 *      double-invocation of effects.
 *
 * Solution:
 *   - WS is tried first; polling only starts as fallback on WS close/error.
 *   - Reconnect attempts use exponential backoff (2s → 4s → 8s → max 30s).
 *   - A connecting flag prevents opening a second socket while one is
 *     being established (fixes "closed before connection established").
 *   - Backend must be started with Daphne (ASGI), not runserver (WSGI).
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

const POLL_MS       = 30_000;
const MAX_SHOW      = 50;
const WS_RETRY_BASE = 2_000;   // initial retry delay ms
const WS_RETRY_MAX  = 30_000;  // max retry delay ms

export function NotificationProvider({ children }) {
  const { user, token } = useContext(UserContext);

  const [notifications, setNotifications] = useState([]);
  const [unreadCount,   setUnreadCount]   = useState(0);
  const [loading,       setLoading]       = useState(false);

  const wsRef         = useRef(null);
  const pollRef       = useRef(null);
  const reconnectRef  = useRef(null);   // setTimeout handle for WS retry
  const retryCountRef = useRef(0);      // exponential backoff counter
  const connectingRef = useRef(false);  // guard: WS handshake in progress
  const mounted       = useRef(true);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const _closeWs = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen    = null;
      wsRef.current.onmessage = null;
      wsRef.current.onclose   = null;
      wsRef.current.onerror   = null;
      try { wsRef.current.close(); } catch { /* ignore */ }
      wsRef.current = null;
    }
    connectingRef.current = false;
    if (reconnectRef.current) { clearTimeout(reconnectRef.current); reconnectRef.current = null; }
  }, []);

  // ── Fetch ─────────────────────────────────────────────────────────────────
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

  // ── Polling (fallback when WS unavailable) ────────────────────────────────
  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = setInterval(() => {
      if (mounted.current) fetchNotifications();
    }, POLL_MS);
  }, [fetchNotifications]);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  // ── WebSocket with exponential backoff ────────────────────────────────────
  const connectWebSocket = useCallback(() => {
    if (!token || !user || !mounted.current) return;

    // FIX: prevent double-open while handshake is in progress
    if (connectingRef.current || wsRef.current) return;
    connectingRef.current = true;

    let ws;
    try {
      const base = (process.env.REACT_APP_API_URL || 'http://localhost:8000/api')
        .replace(/\/api\/?$/, '')
        .replace(/^https/, 'wss')
        .replace(/^http/, 'ws');

      ws = new WebSocket(`${base}/api/ws/notifications/?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;
    } catch {
      connectingRef.current = false;
      startPolling();
      return;
    }

    ws.onopen = () => {
      if (!mounted.current) { ws.close(); return; }
      connectingRef.current = false;
      retryCountRef.current = 0;  // reset backoff on success
      stopPolling();              // WS active — stop polling fallback
    };

    ws.onmessage = (e) => {
      try {
        const msg = JSON.parse(e.data);
        if (msg.type === 'notification' && msg.notification) {
          const n = msg.notification;
          setNotifications(prev =>
            prev.some(x => x.id === n.id) ? prev : [n, ...prev].slice(0, MAX_SHOW)
          );
          if (!n.is_read) setUnreadCount(c => c + 1);
        }
      } catch { /* ignore malformed message */ }
    };

    const _onCloseOrError = () => {
      if (wsRef.current === ws) {
        wsRef.current = null;
      }
      connectingRef.current = false;

      if (!mounted.current || !user) return;

      // Start polling immediately as fallback
      startPolling();

      // Schedule WS reconnect with exponential backoff
      retryCountRef.current += 1;
      const delay = Math.min(
        WS_RETRY_BASE * Math.pow(2, retryCountRef.current - 1),
        WS_RETRY_MAX
      );
      reconnectRef.current = setTimeout(() => {
        reconnectRef.current = null;
        if (mounted.current && user) connectWebSocket();
      }, delay);
    };

    ws.onclose = _onCloseOrError;
    ws.onerror = _onCloseOrError;

  }, [token, user, startPolling, stopPolling]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Main effect ───────────────────────────────────────────────────────────
  useEffect(() => {
    mounted.current = true;

    if (!user) {
      setNotifications([]);
      setUnreadCount(0);
      stopPolling();
      _closeWs();
      return;
    }

    fetchNotifications();
    connectWebSocket();

    return () => {
      mounted.current = false;
      stopPolling();
      _closeWs();
    };
  }, [user, token]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <NotificationContext.Provider
      value={{ notifications, unreadCount, loading, markRead, markAllRead, refresh: fetchNotifications }}
    >
      {children}
    </NotificationContext.Provider>
  );
}

export function useNotifications() {
  return useContext(NotificationContext);
}
