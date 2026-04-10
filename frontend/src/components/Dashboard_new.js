import React, { useContext, useState, useEffect } from 'react';
import {
  Box,
  Container,
  Card,
  CardContent,
  Typography,
  Divider,
  Grid,
} from '@mui/material';
import { UserContext } from '../context/UserContext';
import Sidebar from './Sidebar';
import Topbar from './Topbar';
import UserManagement from './UserManagement';
import DepartmentManagement from './DepartmentManagement';
import ApiTesting from './ApiTesting';

const drawerWidth = 280;
const CAPGEMINI_BLUE = '#0070AD';

const Dashboard = () => {
  const { user, userProfile } = useContext(UserContext);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [currentView, setCurrentView] = useState('overview');

  // Get view from URL if available
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const section = params.get('section');
    if (section) {
      setCurrentView(section);
    }
  }, []);

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const renderContent = () => {
    switch (currentView) {
      case 'overview':
        return <OverviewPage user={user} userProfile={userProfile} />;
      case 'users':
        return user?.role === 'ADMIN' ? <UserManagement /> : null;
      case 'departments':
        return user?.role === 'ADMIN' ? <DepartmentManagement /> : null;
      case 'api':
        return <ApiTesting />;
      case 'system':
        return user?.role === 'ADMIN' ? <SystemPage /> : null;
      default:
        return <OverviewPage user={user} userProfile={userProfile} />;
    }
  };

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh', backgroundColor: '#f5f7fa' }}>
      {/* Sidebar */}
      <Sidebar open={mobileOpen} onClose={() => setMobileOpen(false)} />

      {/* Main Content */}
      <Box
        sx={{
          flexGrow: 1,
          display: 'flex',
          flexDirection: 'column',
          marginLeft: { xs: 0, md: `${drawerWidth}px` },
        }}
      >
        {/* Topbar */}
        <Topbar onMenuClick={handleDrawerToggle} />

        {/* Content Area */}
        <Box
          component="main"
          sx={{
            flexGrow: 1,
            p: 3,
            mt: 8,
            overflow: 'auto',
          }}
        >
          <Container maxWidth="lg">
            {renderContent()}
          </Container>
        </Box>
      </Box>
    </Box>
  );
};

// Overview Page Component
const OverviewPage = ({ user, userProfile }) => {
  const displayDepartment = userProfile?.department || user?.department || (user?.role === 'ADMIN' ? 'Global' : 'N/A');

  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700, color: '#1a1a1a' }}>
        Dashboard Overview
      </Typography>

      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
        {/* User Info Card */}
        <Box>
          <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                User Information
              </Typography>
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 700 }}>
                {user?.username}
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  <strong>Role:</strong> 
                  <Box component="span" sx={{ ml: 1, px: 1.5, py: 0.5, backgroundColor: '#0070AD15', borderRadius: 1, color: '#0070AD', fontWeight: 600, fontSize: '12px' }}>
                    {user?.role}
                  </Box>
                </Typography>
                <Typography variant="body2">
                  <strong>Department:</strong> <span style={{ fontWeight: 500 }}>{displayDepartment}</span>
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>

        {/* System Status Card */}
        <Box>
          <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                System Status
              </Typography>
              <Typography variant="h6" sx={{ mb: 2, color: '#4caf50', fontWeight: 700 }}>
                ✓ Online
              </Typography>
              <Divider sx={{ my: 1 }} />
              <Box sx={{ mt: 2 }}>
                <Typography variant="body2" sx={{ mb: 1 }}>
                  <strong>Authentication:</strong> Keycloak + Django
                </Typography>
                <Typography variant="body2">
                  <strong>Database:</strong> SQLite (Development)
                </Typography>
              </Box>
            </CardContent>
          </Card>
        </Box>
      </Box>

      {user?.role === 'ADMIN' && (
        <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr 1fr' }, gap: 3, mt: 3 }}>
          {/* Total Users */}
          <Box>
            <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
              <CardContent>
                <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                  Total Users
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#0070AD' }}>
                  ---
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: '#999' }}>
                  Go to User Management to view
                </Typography>
              </CardContent>
            </Card>
          </Box>

          {/* Departments */}
          <Box>
            <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
              <CardContent>
                <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                  Departments
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#ff9800' }}>
                  4
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: '#999' }}>
                  DIGITAL, AERONAUTIQUE, AUTOMOBILE, QUALITE
                </Typography>
              </CardContent>
            </Card>
          </Box>

          {/* Roles */}
          <Box>
            <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
              <CardContent>
                <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                  Available Roles
                </Typography>
                <Typography variant="h5" sx={{ fontWeight: 700, color: '#2196f3' }}>
                  3
                </Typography>
                <Typography variant="body2" sx={{ mt: 1, color: '#999' }}>
                  ADMIN, TEAMLEAD, EMPLOYEE
                </Typography>
              </CardContent>
            </Card>
          </Box>
        </Box>
      )}
    </Box>
  );
};

// System Page Component
const SystemPage = () => {
  return (
    <Box>
      <Typography variant="h4" sx={{ mb: 3, fontWeight: 700 }}>
        System Information
      </Typography>
      <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' }, gap: 3 }}>
        <Box>
          <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                Backend
              </Typography>
              <Typography variant="body2" sx={{ mt: 2 }}>
                <strong>Framework:</strong> Django REST Framework
              </Typography>
              <Typography variant="body2">
                <strong>Authentication:</strong> Keycloak + Django
              </Typography>
              <Typography variant="body2">
                <strong>Database:</strong> SQLite (Development)
              </Typography>
            </CardContent>
          </Card>
        </Box>

        <Box>
          <Card sx={{ borderRadius: 2, boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)' }}>
            <CardContent>
              <Typography color="textSecondary" gutterBottom sx={{ fontSize: '13px', fontWeight: 600 }}>
                Frontend
              </Typography>
              <Typography variant="body2" sx={{ mt: 2 }}>
                <strong>Framework:</strong> React
              </Typography>
              <Typography variant="body2">
                <strong>UI Library:</strong> Material-UI (MUI)
              </Typography>
              <Typography variant="body2">
                <strong>State Management:</strong> React Context
              </Typography>
            </CardContent>
          </Card>
        </Box>
      </Box>
    </Box>
  );
};

export default Dashboard;
