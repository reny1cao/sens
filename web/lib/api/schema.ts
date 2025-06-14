import axios from 'axios';
import type { SchemaResponse } from '@/types/schema';

// Use Next.js API routes instead of directly calling backend
export const fetchSchema = async (sessionId?: string): Promise<SchemaResponse> => {
  const headers = sessionId ? { 'X-Session-Id': sessionId } : {};
  const response = await axios.get('/api/schema', { headers });
  return response.data;
};

export const refreshSchema = async (sessionId?: string): Promise<SchemaResponse> => {
  const headers = sessionId ? { 'X-Session-Id': sessionId } : {};
  const response = await axios.post('/api/schema/refresh', {}, { headers });
  return response.data;
};

export const visualizeSchema = async () => {
  const response = await axios.get('/api/schema/visualize');
  return response.data;
};
