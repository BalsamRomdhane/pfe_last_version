import React, { useState } from 'react';
import { TextField, Button, Select, MenuItem, FormControl, InputLabel, Box, Typography, Alert } from '@mui/material';
import api from '../services/api';

const UserManagement = () => {
  const [form, setForm] = useState({ username: '', email: '', role: '', department: '' });
  const [message, setMessage] = useState('');

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    try {
      const response = await api.post('/auth/users/', form);
      setMessage(`User created successfully. Temporary password: ${response.data.temporary_password}`);
    } catch (error) {
      setMessage('Error creating user');
    }
  };

  return (
    <Box>
      <Typography variant="h4">User Management</Typography>
      {message && <Alert severity="info">{message}</Alert>}
      <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
        <TextField
          name="username"
          label="Username"
          value={form.username}
          onChange={handleChange}
          required
          fullWidth
          margin="normal"
        />
        <TextField
          name="email"
          label="Email"
          type="email"
          value={form.email}
          onChange={handleChange}
          required
          fullWidth
          margin="normal"
        />
        <FormControl fullWidth margin="normal">
          <InputLabel>Role</InputLabel>
          <Select name="role" value={form.role} onChange={handleChange} required>
            <MenuItem value="ADMIN">ADMIN</MenuItem>
            <MenuItem value="TEAMLEAD">TEAMLEAD</MenuItem>
            <MenuItem value="EMPLOYEE">EMPLOYEE</MenuItem>
          </Select>
        </FormControl>
        {form.role !== 'ADMIN' && (
          <FormControl fullWidth margin="normal">
            <InputLabel>Department</InputLabel>
            <Select name="department" value={form.department} onChange={handleChange} required>
              <MenuItem value="DIGITAL">DIGITAL</MenuItem>
              <MenuItem value="AERONAUTIQUE">AERONAUTIQUE</MenuItem>
              <MenuItem value="AUTOMOBILE">AUTOMOBILE</MenuItem>
              <MenuItem value="QUALITE">QUALITE</MenuItem>
            </Select>
          </FormControl>
        )}
        <Button type="submit" variant="contained" sx={{ mt: 2 }}>
          Create User
        </Button>
      </Box>
    </Box>
  );
};

export default UserManagement;