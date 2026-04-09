import React, { useContext } from 'react';
import { Box, Drawer, List, ListItem, ListItemText, Typography, Grid, Card, CardContent } from '@mui/material';
import { UserContext } from '../context/UserContext';
import UserManagement from './UserManagement';
import ApiTesting from './ApiTesting';

const drawerWidth = 240;

const Dashboard = () => {
  const { user, logout } = useContext(UserContext);

  const renderContent = () => {
    if (user.role === 'ADMIN') {
      return <UserManagement />;
    } else {
      return (
        <Box>
          <Typography variant="h4">Dashboard for {user.department}</Typography>
          <Grid container spacing={2} sx={{ mt: 2 }}>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6">Department: {user.department}</Typography>
                  <Typography>Role: {user.role}</Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} md={6}>
              <Card>
                <CardContent>
                  <Typography variant="h6">API Testing</Typography>
                  <ApiTesting />
                </CardContent>
              </Card>
            </Grid>
          </Grid>
        </Box>
      );
    }
  };

  return (
    <Box sx={{ display: 'flex' }}>
      <Drawer
        sx={{
          width: drawerWidth,
          flexShrink: 0,
          '& .MuiDrawer-paper': {
            width: drawerWidth,
            boxSizing: 'border-box',
          },
        }}
        variant="permanent"
        anchor="left"
      >
        <List>
          <ListItem>
            <ListItemText primary={`Welcome, ${user.username}`} secondary={`${user.role} - ${user.department || 'Global'}`} />
          </ListItem>
          <ListItem button onClick={() => window.location.href = '/dashboard'}>
            <ListItemText primary="Dashboard" />
          </ListItem>
          {user.role === 'ADMIN' && (
            <ListItem button onClick={() => window.location.href = '/users'}>
              <ListItemText primary="Users" />
            </ListItem>
          )}
          <ListItem button onClick={() => window.location.href = '/api-testing'}>
            <ListItemText primary="API Testing" />
          </ListItem>
          <ListItem button onClick={logout}>
            <ListItemText primary="Logout" />
          </ListItem>
        </List>
      </Drawer>
      <Box component="main" sx={{ flexGrow: 1, p: 3 }}>
        {renderContent()}
      </Box>
    </Box>
  );
};

export default Dashboard;