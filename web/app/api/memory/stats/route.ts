import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-Id');

    // Build query parameters
    const params = new URLSearchParams();
    if (sessionId) {
      params.append('session_id', sessionId);
    } else {
      params.append('session_id', 'global');
    }

    const response = await fetch(`${API_BASE_URL}/api/memory/stats?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to get memory stats' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory stats error:', error);
    return NextResponse.json(
      {
        success: false,
        total_memories: 0,
        memories_by_type: {},
        total_relationships: 0,
        performance: {},
        configuration: {},
        error: 'Failed to connect to backend'
      },
      { status: 500 }
    );
  }
}
