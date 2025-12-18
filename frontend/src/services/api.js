import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000/api';

// Create axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ============================================================================
// Authentication API
// ============================================================================

export const login = async (email) => {
  const response = await api.post('/auth/login', { email });
  return response.data;
};

export const logout = async (sessionToken) => {
  const response = await api.post('/auth/logout', null, {
    params: { session_token: sessionToken }
  });
  return response.data;
};

export const verifySession = async (sessionToken) => {
  const response = await api.get(`/auth/session/${sessionToken}`);
  return response.data;
};

// ============================================================================
// Synthesis API
// ============================================================================

export const getSynthesisFields = async () => {
  const response = await api.get('/synthesis/fields');
  return response.data;
};

export const uploadSynthesisData = async (uploadData) => {
  const response = await api.post('/synthesis/upload', uploadData);
  return response.data;
};

// ============================================================================
// Batch API
// ============================================================================

export const resolveBatch = async (batchId, orcid, project) => {
  const response = await api.post('/batch/resolve', {
    batch_id: batchId,
    orcid,
    project
  });
  return response.data;
};

export const createBatch = async (batchData) => {
  const response = await api.post('/batch/create', batchData);
  return response.data;
};

export default api;
