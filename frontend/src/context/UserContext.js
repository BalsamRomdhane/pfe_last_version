import React, { createContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';

export const UserContext = createContext();

export const UserProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(localStorage.getItem('token'));
  const [userProfile, setUserProfile] = useState(localStorage.getItem('userProfile') ? JSON.parse(localStorage.getItem('userProfile')) : null);

  useEffect(() => {
    if (token) {
      try {
        const decoded = jwtDecode(token);
        // Priority 1: Use role from userProfile (from Django), fallback to JWT
        let role = userProfile?.role || null;
        if (!role) {
          role = decoded.realm_access?.roles?.[0] || null;
          if (!role && decoded.resource_access) {
            const client = Object.values(decoded.resource_access)[0];
            role = client?.roles?.[0] || null;
          }
        }

        const department = userProfile?.department || decoded.attributes?.department?.[0] || decoded.groups?.[0] || null;

        setUser({
          role,
          department,
          username: decoded.preferred_username,
        });
      } catch (error) {
        console.error('Invalid token', error);
        logout();
      }
    }
  }, [token, userProfile]);

  const login = (newToken, profile = null) => {
    localStorage.setItem('token', newToken);
    setToken(newToken);
    if (profile) {
      localStorage.setItem('userProfile', JSON.stringify(profile));
      setUserProfile(profile);
    }
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userProfile');
    setToken(null);
    setUser(null);
    setUserProfile(null);
  };

  return (
    <UserContext.Provider value={{ user, userProfile, token, login, logout }}>
      {children}
    </UserContext.Provider>
  );
};