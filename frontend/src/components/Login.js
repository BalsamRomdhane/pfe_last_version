import React, { useState, useContext } from 'react';
import { TextField, Button, Container, Typography, Box } from '@mui/material';
import { UserContext } from '../context/UserContext';
import api from '../services/api';

const Login = () => {
  const [loginInput, setLoginInput] = useState('');
  const [password, setPassword] = useState('');
  const [bypassKeycloak, setBypassKeycloak] = useState(false);
  const [error, setError] = useState('');
  const { login } = useContext(UserContext);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    try {
      const response = await api.post('/auth/login/', {
        username: loginInput,
        password,
        bypass_keycloak: bypassKeycloak,
      });
      login(response.data.access_token);
      // Redirect to dashboard
      window.location.href = '/dashboard';
    } catch (error) {
      const detail =
        error.response?.data?.detail ||
        error.response?.data?.error ||
        error.message ||
        'Login failed';
      setError(`${detail}`);
      
      // If Keycloak not fully set up, offer bypass option
      if (detail && (detail.includes('not fully set up') || detail.includes('required action'))) {
        setTimeout(() => {
          setError(`${detail}\n\nTrying fallback authentication...`);
          setBypassKeycloak(true);
        }, 1500);
      }
    }
  };

  return (
    <Container maxWidth="sm">
      <Box sx={{ mt: 8, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        <Typography component="h1" variant="h5">
          Login
        </Typography>
        {error && (
          <Box sx={{ mt: 2, p: 1.5, bgcolor: '#ffebee', borderRadius: 1, width: '100%' }}>
            <Typography variant="body2" color="error" sx={{ whiteSpace: 'pre-wrap' }}>
              {error}
            </Typography>
          </Box>
        )}
        <Box component="form" onSubmit={handleSubmit} sx={{ mt: 1, width: '100%' }}>
          <TextField
            margin="normal"
            required
            fullWidth
            label="Username or email"
            value={loginInput}
            onChange={(e) => setLoginInput(e.target.value)}
            disabled={bypassKeycloak}
          />
          <TextField
            margin="normal"
            required
            fullWidth
            label="Password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            disabled={bypassKeycloak}
          />
          <Button type="submit" fullWidth variant="contained" sx={{ mt: 3, mb: 2 }} disabled={bypassKeycloak}>
            Login
          </Button>
        </Box>
      </Box>
    </Container>
  );
};

export default Login;