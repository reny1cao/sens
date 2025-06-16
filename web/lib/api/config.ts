// Server-side API configuration
export const getBackendUrl = () => {
  // For server-side API routes, use non-public env vars
  // Vercel automatically provides these at runtime
  return process.env.BACKEND_URL || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
};
