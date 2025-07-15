import { getBackendUrl } from '@/lib/api/config';
import { NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/memory/health`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to get memory health' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory health check error:', error);
    return NextResponse.json(
      {
        memory_enabled: false,
        status: 'error',
        error: 'Failed to connect to backend'
      },
      { status: 500 }
    );
  }
}
