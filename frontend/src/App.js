import React, { useContext, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { UserProvider, UserContext } from './context/UserContext';
import { themes } from './themes';
import Login from './components/Login';
import Dashboard from './components/Dashboard.jsx';
import Users from './components/Users';
import Departments from './components/Departments';
import System from './components/System';
import ResetPassword from './components/ResetPassword';

// Admin panel redirect component
function AdminRedirect() {
  useEffect(() => {
    // Redirect to Django admin panel
    window.location.href = 'http://localhost:8000/admin/';
  }, []);

  return null;
}

function App() {
  return (
    <UserProvider>
      <AppContent />
    </UserProvider>
  );
}

function AppContent() {
  const { user, userProfile } = useContext(UserContext);

  const getTheme = () => {
    if (userProfile?.theme_color || user?.department) {
      return themes[user?.department] || themes.default;
    }
    return themes.default;
  };

  // Protected route wrapper - requires authentication
  const ProtectedRoute = ({ children }) => {
    if (!user) {
      return <Navigate to="/login" />;
    }
    return children;
  };

  const RoleProtectedRoute = ({ children, roles }) => {
    if (!user) {
      return <Navigate to="/login" />;
    }
    if (!roles.includes(user.role)) {
      return <Navigate to="/dashboard" />;
    }
    return children;
  };

  return (
    <ThemeProvider theme={getTheme()}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/login" element={!user ? <Login /> : <Navigate to="/dashboard" />} />
          <Route path="/reset-password" element={<ResetPassword />} />
          
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          
          <Route
            path="/users"
            element={
              <RoleProtectedRoute roles={['ADMIN']}>
                <Users />
              </RoleProtectedRoute>
            }
          />
          
          <Route
            path="/departments"
            element={
              <RoleProtectedRoute roles={['ADMIN']}>
                <Departments />
              </RoleProtectedRoute>
            }
          />
          
          <Route
            path="/system"
            element={
              <ProtectedRoute>
                <System />
              </ProtectedRoute>
            }
          />
          
          {/* Redirect to Django admin panel */}
          <Route
            path="/admin/*"
            element={<AdminRedirect />}
          />
          
          <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
