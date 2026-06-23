import axios from 'axios';

const api = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://localhost:8000/api',
  withCredentials: true, // Enable credentials for CORS
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
});

// Get CSRF token from cookie
const getCookie = (name) => {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
};

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token');
    
    // Add Bearer token if available
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    // Add CSRF token for POST/PUT/DELETE/PATCH requests
    if (['post', 'put', 'delete', 'patch'].includes(config.method?.toLowerCase())) {
      const csrfToken = getCookie('csrftoken');
      if (csrfToken) {
        config.headers['X-CSRFToken'] = csrfToken;
      }
    }
    
    return config;
  },
  (error) => Promise.reject(error)
);

// Add response interceptor for better error logging
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      let responseData = error.response.data;
      if (typeof responseData === 'object') {
        try {
          responseData = JSON.stringify(responseData, null, 2);
        } catch {
          responseData = error.response.data;
        }
      }

      const status = error.response.status;
      const message = typeof responseData === 'string' ? responseData : '';
      if ((status === 401 || status === 403) && /token|expired|invalid token/i.test(message)) {
        localStorage.removeItem('token');
        localStorage.removeItem('userProfile');
      }

      console.error('API Error:', {
        status,
        data: responseData,
        url: error.config?.url,
        method: error.config?.method,
      });
    } else if (error.request) {
      console.error('No response received:', error.request);
    } else {
      console.error('Error setting up request:', error.message);
    }
    return Promise.reject(error);
  }
);

export default api;