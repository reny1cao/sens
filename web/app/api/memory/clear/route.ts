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
    }

    // Include confirm parameter from body if present
    if (body.confirm) {
      params.append('confirm', 'true');
    }

    const response = await fetch(`${API_BASE_URL}/api/memory/clear?${params}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to clear memory' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory clear error:', error);
    return NextResponse.json(
      {
        success: false,
        message: '',
        error: 'Failed to connect to backend'
      },
      { status: 500 }
    );
  }
}
