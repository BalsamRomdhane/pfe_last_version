import React, { useContext, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AppBar,
  Toolbar,
  Box,
  Avatar,
  Menu,
  MenuItem,
  Typography,
  IconButton,
  Divider,
  ListItemIcon,
} from '@mui/material';
import {
  Logout as LogoutIcon,
  Menu as MenuIcon,
  Settings as SettingsIcon,
} from '@mui/icons-material';
import { UserContext } from '../context/UserContext';

const CAPGEMINI_BLUE = '#0070AD';

const Topbar = ({ onMenuClick }) => {
  const { user, logout } = useContext(UserContext);
  const navigate = useNavigate();
  const [anchorEl, setAnchorEl] = useState(null);

  const handleMenuOpen = (event) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
    navigate('/login');
  };

  const getInitials = (username) => {
    if (!username) return '?';
    return username.charAt(0).toUpperCase();
  };

  const getAvatarColor = (role) => {
    switch (role) {
      case 'ADMIN':
        return '#ff9800';
      case 'TEAMLEAD':
        return '#2196f3';
      case 'EMPLOYEE':
        return '#4caf50';
      default:
        return '#999';
    }
  };

  return (
    <>
      <AppBar
        position="fixed"
        sx={{
          backgroundColor: 'white',
          color: '#333',
          boxShadow: '0 2px 8px rgba(0, 0, 0, 0.08)',
          borderBottom: `1px solid #e0e0e0`,
          zIndex: 1200,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            onClick={onMenuClick}
            sx={{
              display: { xs: 'flex', md: 'none' },
              mr: 2,
            }}
          >
            <MenuIcon />
          </IconButton>

          <Box sx={{ flexGrow: 1 }} />

          {/* User Section */}
          <Box
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 2,
            }}
          >
            {/* Role Badge */}
            <Box
              sx={{
                px: 2,
                py: 1,
                backgroundColor: 'rgba(0, 112, 173, 0.08)',
                borderRadius: 1,
                display: { xs: 'none', sm: 'block' },
              }}
            >
              <Typography
                variant="caption"
                sx={{
                  color: CAPGEMINI_BLUE,
                  fontWeight: 600,
                  fontSize: '12px',
                }}
              >
                {user?.role}
              </Typography>
            </Box>

            {/* User Avatar */}
            <Avatar
              onClick={handleMenuOpen}
              sx={{
                cursor: 'pointer',
                backgroundColor: getAvatarColor(user?.role),
                fontWeight: 700,
                width: 40,
                height: 40,
                transition: 'transform 0.2s ease, box-shadow 0.2s ease',
                '&:hover': {
                  transform: 'scale(1.05)',
                  boxShadow: `0 4px 12px ${getAvatarColor(user?.role)}40`,
                },
              }}
            >
              {getInitials(user?.username)}
            </Avatar>
          </Box>

          {/* User Menu */}
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            anchorOrigin={{
              vertical: 'bottom',
              horizontal: 'right',
            }}
            transformOrigin={{
              vertical: 'top',
              horizontal: 'right',
            }}
            slotProps={{
              paper: {
                sx: {
                  minWidth: 250,
                  borderRadius: 2,
                  mt: 1,
                  boxShadow: '0 8px 25px rgba(0, 0, 0, 0.12)',
                },
              },
            }}
          >
            {/* User Info Header */}
            <Box sx={{ px: 2, py: 2 }}>
              <Typography variant="subtitle2" sx={{ fontWeight: 700 }}>
                {user?.username}
              </Typography>
              <Typography variant="caption" sx={{ color: '#999' }}>
                {user?.role}
              </Typography>
            </Box>

            <Divider />

            {/* Menu Items */}
            <MenuItem
              onClick={() => {
                handleMenuClose();
                navigate('/dashboard?section=system');
              }}
              sx={{
                fontSize: '14px',
              }}
            >
              <ListItemIcon
                sx={{
                  color: CAPGEMINI_BLUE,
                  minWidth: 40,
                }}
              >
                <SettingsIcon fontSize="small" />
              </ListItemIcon>
              Settings
            </MenuItem>

            <Divider />

            {/* Logout */}
            <MenuItem
              onClick={handleLogout}
              sx={{
                fontSize: '14px',
                color: '#d32f2f',
              }}
            >
              <ListItemIcon sx={{ color: '#d32f2f', minWidth: 40 }}>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
    </>
  );
};

export default Topbar;
