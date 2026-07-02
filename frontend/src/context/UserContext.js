import React, { createContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';

export const UserContext = createContext();

const getStoredProfile = () => {
  try {
    const rawProfile = localStorage.getItem('userProfile');
    return rawProfile ? JSON.parse(rawProfile) : null;
  } catch (error) {
    localStorage.removeItem('userProfile');
    console.warn('Invalid stored user profile removed:', error);
    return null;
  }
};

const buildUserFromToken = (tokenValue, profile) => {
  const decoded = jwtDecode(tokenValue);
  let role = profile?.role || null;
  if (!role) {
    const BUSINESS_ROLES = ['ADMIN', 'TEAMLEAD', 'EMPLOYEE'];
    role = decoded.realm_access?.roles?.find(r => BUSINESS_ROLES.includes(r)) || null;
    if (!role && decoded.resource_access) {
      const client = Object.values(decoded.resource_access)[0];
      role = client?.roles?.find(r => BUSINESS_ROLES.includes(r)) || null;
    }
  }

  const department = profile?.department || decoded.attributes?.department?.[0] || decoded.groups?.[0] || null;

  return {
    role,
    department,
    username: decoded.preferred_username || profile?.username || null,
  };
};

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userProfile, setUserProfile] = useState(getStoredProfile);

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userProfile');
    setToken(null);
    setUser(null);
    setUserProfile(null);
    setLoading(false);
  };

  const isTokenExpired = (candidateToken) => {
    try {
      const decoded = jwtDecode(candidateToken);
      if (!decoded.exp) return false;
      return decoded.exp * 1000 <= Date.now();
    } catch {
      return true;
    }
  };

  useEffect(() => {
    let isMounted = true;

    const initializeUser = () => {
      if (!token || isTokenExpired(token)) {
        if (isMounted) {
          logout();
        }
        return;
      }

      try {
        const nextUser = buildUserFromToken(token, userProfile);

        if (isMounted) {
          setUser(nextUser);
        }
      } catch (error) {
        console.error('Invalid token', error);
        if (isMounted) {
          logout();
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    setLoading(true);
    initializeUser();

    return () => {
      isMounted = false;
    };
  }, [token, userProfile]);

  const login = (newToken, profile = null) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);

    if (profile) {
      localStorage.setItem('userProfile', JSON.stringify(profile));
      setUserProfile(profile);
      setUser(buildUserFromToken(newToken, profile));
      setLoading(false);
      return;
    }

    setLoading(true);
  };

  return (
    <UserContext.Provider value={{ user, userProfile, token, loading, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};