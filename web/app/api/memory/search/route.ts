import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-Id');
    const body = await request.json();

    // Build query parameters
    const params = new URLSearchParams();
    if (sessionId) {
      params.append('session_id', sessionId);
    } else {
      params.append('session_id', 'global');
    }

    const response = await fetch(`${API_BASE_URL}/api/memory/search?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to search memories' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory search error:', error);
    return NextResponse.json(
      {
        success: false,
        memories: [],
        count: 0,
        error: 'Failed to connect to backend'
      },
      { status: 500 }
    );
  }
}
