import { NextResponse } from 'next/server';

const BACKEND_URL = process.env.SENS_API_URL || 'http://localhost:8000';

export async function GET() {
  try {
    // Check if backend is available
    const response = await fetch(`${BACKEND_URL}/health`, {
      method: 'GET',
    });

    const backendHealth = response.ok;
    const backendStatus = response.status;

    return NextResponse.json({
      status: 'healthy',
      frontend: 'ok',
      backend: {
        status: backendHealth ? 'ok' : 'error',
        url: BACKEND_URL,
        httpStatus: backendStatus,
      },
      timestamp: new Date().toISOString(),
    });
  } catch (error) {
    return NextResponse.json({
      status: 'error',
      frontend: 'ok',
      backend: {
        status: 'error',
        url: BACKEND_URL,
        error: error instanceof Error ? error.message : 'Unknown error',
      },
      timestamp: new Date().toISOString(),
    });
  }
}
