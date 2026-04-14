import React, { useState, useContext } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Container,
  InputAdornment,
  IconButton,
} from '@mui/material';
import {
  Visibility as VisibilityIcon,
  VisibilityOff as VisibilityOffIcon,
} from '@mui/icons-material';
import api from '../services/api';
import { UserContext } from '../context/UserContext';
import logoImage from '../Capgemini_Logo.png';

// Capgemini branding colors
const CAPGEMINI_BLUE = '#0070AD';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useContext(UserContext);
  const [formData, setFormData] = useState({
    login: '',
    password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showPassword, setShowPassword] = useState(false);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value,
    }));
    if (error) setError('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError('');

    const loginField = formData.login.trim();
    const payload = loginField.includes('@')
      ? { email: loginField, password: formData.password }
      : { username: loginField, password: formData.password };

    try {
      const response = await api.post('/auth/login/', payload);

      const { access_token, user } = response.data;
      login(access_token, user);
      navigate('/dashboard');
    } catch (err) {
      const errorMsg = err.response?.data?.detail || 'Invalid username or password';
      setError(errorMsg);
      setFormData(prev => ({
        ...prev,
        password: '',
      }));
    } finally {
      setLoading(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !loading) {
      handleSubmit(e);
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: `linear-gradient(135deg, ${CAPGEMINI_BLUE} 0%, #0052A3 100%)`,
        padding: 2,
      }}
    >
      <Container maxWidth="sm">
        <Card
          sx={{
            borderRadius: 3,
            boxShadow: '0 20px 60px rgba(0, 0, 0, 0.25)',
            padding: 4,
            background: 'white',
            animation: 'fadeIn 0.6s ease-in-out',
            '@keyframes fadeIn': {
              from: {
                opacity: 0,
                transform: 'translateY(10px)',
              },
              to: {
                opacity: 1,
                transform: 'translateY(0)',
              },
            },
          }}
        >
          {/* Logo Section */}
          <Box
            sx={{
              textAlign: 'center',
              mb: 3,
            }}
          >
            <Box
              sx={{
                width: 120,
                height: 80,
                margin: '0 auto 16px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
              component="img"
              src={logoImage}
              alt="Capgemini Logo"
            />
            <Typography
              variant="h5"
              sx={{
                fontWeight: 700,
                color: '#1a1a1a',
                mb: 1,
              }}
            >
              Enterprise Platform
            </Typography>
            <Typography
              variant="body2"
              sx={{
                color: '#666',
                fontSize: '14px',
              }}
            >
              Secure Access Portal
            </Typography>
          </Box>

          {/* Error Alert */}
          {error && (
            <Alert
              severity="error"
              sx={{
                mb: 3,
                borderRadius: 2,
              }}
            >
              {error}
            </Alert>
          )}

          {/* Login Form */}
          <Box
            component="form"
            onSubmit={handleSubmit}
            sx={{
              display: 'flex',
              flexDirection: 'column',
              gap: 2.5,
            }}
          >
            {/* Username or Email Field */}
            <TextField
              fullWidth
              label="Username or Email"
              name="login"
              type="text"
              value={formData.login}
              onChange={handleChange}
              onKeyPress={handleKeyPress}
              disabled={loading}
              autoComplete="username"
              autoFocus
              helperText="Enter your username or email address"
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 1.5,
                  backgroundColor: '#f8f9fa',
                  transition: 'all 0.2s',
                  '&:hover': {
                    backgroundColor: '#f0f3f7',
                  },
                  '&.Mui-focused': {
                    backgroundColor: 'white',
                    '& fieldset': {
                      borderColor: CAPGEMINI_BLUE,
                      borderWidth: 2,
                    },
                  },
                },
                '& .MuiInputBase-input': {
                  fontSize: '15px',
                },
              }}
              variant="outlined"
            />

            {/* Password Field */}
            <TextField
              fullWidth
              label="Password"
              name="password"
              type={showPassword ? 'text' : 'password'}
              value={formData.password}
              onChange={handleChange}
              onKeyPress={handleKeyPress}
              disabled={loading}
              autoComplete="current-password"
              InputProps={{
                endAdornment: (
                  <InputAdornment position="end">
                    <IconButton
                      onClick={() => setShowPassword(!showPassword)}
                      edge="end"
                      disabled={loading}
                      sx={{
                        color: showPassword ? CAPGEMINI_BLUE : '#999',
                      }}
                    >
                      {showPassword ? <VisibilityOffIcon /> : <VisibilityIcon />}
                    </IconButton>
                  </InputAdornment>
                ),
              }}
              sx={{
                '& .MuiOutlinedInput-root': {
                  borderRadius: 1.5,
                  backgroundColor: '#f8f9fa',
                  transition: 'all 0.2s',
                  '&:hover': {
                    backgroundColor: '#f0f3f7',
                  },
                  '&.Mui-focused': {
                    backgroundColor: 'white',
                    '& fieldset': {
                      borderColor: CAPGEMINI_BLUE,
                      borderWidth: 2,
                    },
                  },
                },
                '& .MuiInputBase-input': {
                  fontSize: '15px',
                },
              }}
              variant="outlined"
            />

            {/* Login Button */}
            <Button
              fullWidth
              type="submit"
              disabled={loading || !formData.login || !formData.password}
              sx={{
                padding: '12px 16px',
                background: `linear-gradient(135deg, ${CAPGEMINI_BLUE} 0%, #0052A3 100%)`,
                color: 'white',
                fontWeight: 600,
                borderRadius: 1.5,
                fontSize: '15px',
                textTransform: 'none',
                transition: 'all 0.3s ease',
                boxShadow: `0 4px 15px rgba(0, 112, 173, 0.4)`,
                '&:hover:not(:disabled)': {
                  boxShadow: `0 8px 25px rgba(0, 112, 173, 0.6)`,
                  transform: 'translateY(-2px)',
                },
                '&:active:not(:disabled)': {
                  transform: 'translateY(0)',
                },
                '&:disabled': {
                  opacity: 0.6,
                  cursor: 'not-allowed',
                },
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 1,
              }}
            >
              {loading ? (
                <>
                  <CircularProgress size={20} sx={{ color: 'white' }} />
                  <span>Signing in...</span>
                </>
              ) : (
                'Sign In'
              )}
            </Button>
          </Box>

          {/* Footer */}
          <Typography
            variant="caption"
            sx={{
              display: 'block',
              textAlign: 'center',
              marginTop: 3,
              color: '#999',
              fontSize: '12px',
            }}
          >
            © 2026 Enterprise Platform. All rights reserved.
          </Typography>
        </Card>
      </Container>
    </Box>
  );
};

export default Login;