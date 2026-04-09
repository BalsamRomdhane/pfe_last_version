import React, { useState } from 'react';
import { Button, TextField, Box, Typography, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow } from '@mui/material';
import api from '../services/api';

const ApiTesting = () => {
  const [endpoint, setEndpoint] = useState('/protected/');
  const [response, setResponse] = useState(null);
  const [status, setStatus] = useState(null);

  const testEndpoint = async () => {
    try {
      const res = await api.get(endpoint);
      setResponse(res.data);
      setStatus(res.status);
    } catch (error) {
      setResponse(error.response?.data || 'Error');
      setStatus(error.response?.status || 'Error');
    }
  };

  const endpoints = ['/protected/', '/admin/', '/teamlead/', '/employee/'];

  return (
    <Box>
      <Typography variant="h6">API Testing</Typography>
      <TextField
        label="Endpoint"
        value={endpoint}
        onChange={(e) => setEndpoint(e.target.value)}
        fullWidth
        margin="normal"
      />
      <Button onClick={testEndpoint} variant="contained">Test</Button>
      <Box sx={{ mt: 2 }}>
        <Typography>Status: {status}</Typography>
        <Typography>Response:</Typography>
        <Paper sx={{ p: 2, mt: 1 }}>
          <pre>{JSON.stringify(response, null, 2)}</pre>
        </Paper>
      </Box>
      <Typography variant="h6" sx={{ mt: 2 }}>Available Endpoints</Typography>
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Endpoint</TableCell>
              <TableCell>Description</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {endpoints.map((ep) => (
              <TableRow key={ep} onClick={() => setEndpoint(ep)} style={{ cursor: 'pointer' }}>
                <TableCell>{ep}</TableCell>
                <TableCell>{ep === '/protected/' ? 'Any authenticated user' : ep.slice(1, -1).toUpperCase() + ' only'}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
};

export default ApiTesting;