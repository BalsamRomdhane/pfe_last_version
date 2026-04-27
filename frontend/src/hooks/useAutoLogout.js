import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';

const INACTIVITY_WARNING_MS = 19 * 60 * 1000;
const INACTIVITY_LOGOUT_MS = 20 * 60 * 1000;
const LOGOUT_STORAGE_KEY = 'app_auto_logout';

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

const useAutoLogout = () => {
  const navigate = useNavigate();
  const warningTimeoutRef = useRef(null);
  const logoutTimeoutRef = useRef(null);

  const performLogout = () => {
    clearAuthentication();
    broadcastLogout();
    navigate('/login');
  };

  const resetTimers = () => {
    if (warningTimeoutRef.current) {
      clearTimeout(warningTimeoutRef.current);
    }
    if (logoutTimeoutRef.current) {
      clearTimeout(logoutTimeoutRef.current);
    }

    warningTimeoutRef.current = setTimeout(() => {
      window.alert('You will be logged out in 1 minute due to inactivity.');
    }, INACTIVITY_WARNING_MS);

    logoutTimeoutRef.current = setTimeout(() => {
      performLogout();
    }, INACTIVITY_LOGOUT_MS);
  };

  useEffect(() => {
    const activityEvents = ['mousemove', 'keydown', 'click'];

    const handleActivity = () => {
      resetTimers();
    };

    const handleStorageEvent = (event) => {
      if (event.key === LOGOUT_STORAGE_KEY) {
        clearAuthentication();
        navigate('/login');
      }
    };

    activityEvents.forEach((eventName) => window.addEventListener(eventName, handleActivity));
    window.addEventListener('storage', handleStorageEvent);

    resetTimers();

    return () => {
      activityEvents.forEach((eventName) => window.removeEventListener(eventName, handleActivity));
      window.removeEventListener('storage', handleStorageEvent);
      if (warningTimeoutRef.current) {
        clearTimeout(warningTimeoutRef.current);
      }
      if (logoutTimeoutRef.current) {
        clearTimeout(logoutTimeoutRef.current);
      }
    };
  }, [navigate]);
};

export default useAutoLogout;
