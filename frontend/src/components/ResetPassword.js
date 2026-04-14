import React, { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Card,
  TextField,
  Button,
  Typography,
  Alert,
  CircularProgress,
  Container,
} from '@mui/material';
import api from '../services/api';
import logoImage from '../Capgemini_Logo.png';

const CAPGEMINI_BLUE = '#0070AD';

const ResetPassword = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const searchParams = new URLSearchParams(location.search);
  const token = searchParams.get('token') || '';

  const [formData, setFormData] = useState({
    new_password: '',
    confirm_password: '',
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (error) setError('');
    if (success) setSuccess('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccess('');

    if (!token) {
      setError('Le jeton de réinitialisation est manquant ou invalide.');
      return;
    }

    if (!formData.new_password || !formData.confirm_password) {
      setError('Veuillez saisir et confirmer le nouveau mot de passe.');
      return;
    }

    if (formData.new_password !== formData.confirm_password) {
      setError('Les mots de passe ne correspondent pas.');
      return;
    }

    setLoading(true);

    try {
      const response = await api.post('/auth/reset-password/', {
        token,
        new_password: formData.new_password,
        confirm_password: formData.confirm_password,
      });

      setSuccess(response.data?.message || 'Votre mot de passe a été mis à jour avec succès.');
      setTimeout(() => {
        navigate('/login');
      }, 1500);
    } catch (err) {
      const detail = err.response?.data?.detail;
      const message = err.response?.data?.error || detail || 'Impossible de réinitialiser le mot de passe.';
      setError(message);
    } finally {
      setLoading(false);
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
          }}
        >
          <Box sx={{ textAlign: 'center', mb: 3 }}>
            <Box
              component="img"
              src={logoImage}
              alt="Capgemini Logo"
              sx={{ width: 120, height: 80, mx: 'auto' }}
            />
            <Typography variant="h5" sx={{ fontWeight: 700, color: '#1a1a1a', mb: 1 }}>
              Réinitialisation de mot de passe
            </Typography>
            <Typography variant="body2" sx={{ color: '#666', fontSize: '14px' }}>
              Entrez un nouveau mot de passe pour continuer.
            </Typography>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2, borderRadius: 2 }}>
              {error}
            </Alert>
          )}
          {success && (
            <Alert severity="success" sx={{ mb: 2, borderRadius: 2 }}>
              {success}
            </Alert>
          )}

          <Box component="form" onSubmit={handleSubmit} sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <TextField
              fullWidth
              label="Nouveau mot de passe"
              name="new_password"
              type="password"
              value={formData.new_password}
              onChange={handleChange}
              disabled={loading}
              autoComplete="new-password"
              variant="outlined"
            />

            <TextField
              fullWidth
              label="Confirmer le mot de passe"
              name="confirm_password"
              type="password"
              value={formData.confirm_password}
              onChange={handleChange}
              disabled={loading}
              autoComplete="new-password"
              variant="outlined"
            />

            <Button type="submit" variant="contained" size="large" disabled={loading} sx={{ bgcolor: CAPGEMINI_BLUE }}>
              {loading ? <CircularProgress size={20} color="inherit" /> : 'Modifier mon mot de passe'}
            </Button>
          </Box>
        </Card>
      </Container>
    </Box>
  );
};

export default ResetPassword;
