import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_URL = getBackendUrl();

export async function GET(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-Id');

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
    };

    if (sessionId) {
      headers['X-Session-Id'] = sessionId;
    }

    // Forward to backend schema visualize endpoint
    const response = await fetch(`${API_URL}/api/schema/visualize`, {
      method: 'GET',
      headers,
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to fetch schema' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);

  } catch (error) {
    console.error('Schema fetch error:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
