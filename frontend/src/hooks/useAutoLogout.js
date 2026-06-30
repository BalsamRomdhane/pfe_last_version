import { useCallback, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const INACTIVITY_WARNING_MS  = 19 * 60 * 1000;   // 19 min
const INACTIVITY_LOGOUT_MS   = 20 * 60 * 1000;   // 20 min
const LOGOUT_STORAGE_KEY     = 'app_auto_logout';
const WARNING_ELEMENT_ID     = 'auto-logout-warning';

const clearAuthentication = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userProfile');
};

const broadcastLogout = () => {
  try {
    localStorage.setItem(LOGOUT_STORAGE_KEY, Date.now().toString());
  } catch (error) {
    console.warn('Logout broadcast failed', error);
  }
};

/** Show a non-blocking toast instead of window.alert() */
const showWarningToast = () => {
  // Reuse if already present
  let el = document.getElementById(WARNING_ELEMENT_ID);
  if (!el) {
    el = document.createElement('div');
    el.id = WARNING_ELEMENT_ID;
    Object.assign(el.style, {
      position:     'fixed',
      bottom:       '24px',
      right:        '24px',
      zIndex:       '99999',
      background:   '#1e293b',
      color:        '#f8fafc',
      padding:      '12px 20px',
      borderRadius: '12px',
      boxShadow:    '0 8px 32px rgba(0,0,0,0.35)',
      fontSize:     '13px',
      fontFamily:   'system-ui, sans-serif',
      maxWidth:     '320px',
      lineHeight:   '1.5',
      borderLeft:   '4px solid #f59e0b',
    });
    document.body.appendChild(el);
  }
  el.textContent = '⚠ Vous serez déconnecté dans 1 minute en raison d\'inactivité.';
  el.style.display = 'block';
};

const hideWarningToast = () => {
  const el = document.getElementById(WARNING_ELEMENT_ID);
  if (el) el.style.display = 'none';
};

const useAutoLogout = () => {
  const navigate        = useNavigate();
  const warningRef      = useRef(null);
  const logoutRef       = useRef(null);

  const performLogout = useCallback(() => {
    hideWarningToast();
    clearAuthentication();
    broadcastLogout();
    navigate('/login');
  }, [navigate]);

  const resetTimers = useCallback(() => {
    clearTimeout(warningRef.current);
    clearTimeout(logoutRef.current);
    hideWarningToast();

    warningRef.current = setTimeout(showWarningToast, INACTIVITY_WARNING_MS);
    logoutRef.current  = setTimeout(performLogout,    INACTIVITY_LOGOUT_MS);
  }, [performLogout]);

  useEffect(() => {
    const events = ['mousemove', 'keydown', 'click', 'touchstart'];

    const handleActivity    = () => resetTimers();
    const handleStorageEvent = (e) => {
      if (e.key === LOGOUT_STORAGE_KEY) {
        clearAuthentication();
        navigate('/login');
      }
    };

    events.forEach(ev => globalThis.addEventListener(ev, handleActivity, { passive: true }));
    globalThis.addEventListener('storage', handleStorageEvent);
    resetTimers();

    return () => {
      events.forEach(ev => globalThis.removeEventListener(ev, handleActivity));
      globalThis.removeEventListener('storage', handleStorageEvent);
      clearTimeout(warningRef.current);
      clearTimeout(logoutRef.current);
      hideWarningToast();
    };
  }, [navigate, resetTimers]);
};

export default useAutoLogout;
