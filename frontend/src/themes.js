import { createTheme } from '@mui/material/styles';

export const themes = {
  DIGITAL: createTheme({
    palette: {
      primary: { main: '#1976d2' }, // blue
      secondary: { main: '#dc004e' },
    },
  }),
  AERONAUTIQUE: createTheme({
    palette: {
      primary: { main: '#9c27b0' }, // purple
      secondary: { main: '#dc004e' },
    },
  }),
  AUTOMOBILE: createTheme({
    palette: {
      primary: { main: '#4caf50' }, // green
      secondary: { main: '#dc004e' },
    },
  }),
  QUALITE: createTheme({
    palette: {
      primary: { main: '#ff9800' }, // orange
      secondary: { main: '#dc004e' },
    },
  }),
  default: createTheme({
    palette: {
      primary: { main: '#1976d2' },
      secondary: { main: '#dc004e' },
    },
  }),
};