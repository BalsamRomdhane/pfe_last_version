import React, { useContext } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { ThemeProvider } from '@mui/material/styles';
import { CssBaseline } from '@mui/material';
import { UserProvider, UserContext } from './context/UserContext';
import { themes } from './themes';
import Login from './components/Login';
import Dashboard from './components/Dashboard';
import ApiTesting from './components/ApiTesting';

function App() {
  return (
    <UserProvider>
      <AppContent />
    </UserProvider>
  );
}

function AppContent() {
  const { user } = useContext(UserContext);

  const getTheme = () => {
    if (user && user.department) {
      return themes[user.department] || themes.default;
    }
    return themes.default;
  };

  return (
    <ThemeProvider theme={getTheme()}>
      <CssBaseline />
      <Router>
        <Routes>
          <Route path="/login" element={!user ? <Login /> : <Navigate to="/dashboard" />} />
          <Route path="/dashboard" element={user ? <Dashboard /> : <Navigate to="/login" />} />
          <Route path="/api-testing" element={user ? <ApiTesting /> : <Navigate to="/login" />} />
          <Route path="/" element={<Navigate to={user ? "/dashboard" : "/login"} />} />
        </Routes>
      </Router>
    </ThemeProvider>
  );
}

export default App;
