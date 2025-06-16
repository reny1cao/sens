import axios from 'axios';
import type { QueryRequest, QueryResponse, SchemaTable } from '@/types';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

// Create axios instance with default config
const apiClient = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor for auth (if needed later)
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    // const token = getAuthToken();
    // if (token) {
    //   config.headers.Authorization = `Bearer ${token}`;
    // }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response) {
      // Server responded with error
      const errorMessage = error.response.data?.detail || error.response.data?.message || 'An error occurred';
      throw new Error(errorMessage);
    } else if (error.request) {
      // Request made but no response
      throw new Error('Unable to connect to the server. Please check your connection.');
    } else {
      // Something else happened
      throw new Error('An unexpected error occurred');
    }
  }
);

// API Functions
export const api = {
  // Execute natural language query
  async executeQuery(request: QueryRequest): Promise<QueryResponse> {
    const response = await apiClient.post<QueryResponse>('/api/nl2sql', request);
    return response.data;
  },

  // Get schema information
  async getSchema(): Promise<SchemaTable[]> {
    const response = await apiClient.get<{ tables: SchemaTable[] }>('/api/schema');
    return response.data.tables;
  },

  // Search for tables
  async searchTables(query: string): Promise<SchemaTable[]> {
    const response = await apiClient.get<{ tables: SchemaTable[] }>('/api/tables/search', {
      params: { q: query }
    });
    return response.data.tables;
  },

  // Search for columns
  async searchColumns(query: string): Promise<any[]> {
    const response = await apiClient.get('/api/columns/search', {
      params: { q: query }
    });
    return response.data.columns;
  },

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await apiClient.get('/health');
      return response.data.status === 'healthy';
    } catch {
      return false;
    }
  },
};

export default api;
