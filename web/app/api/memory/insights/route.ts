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

    const response = await fetch(`${API_BASE_URL}/api/memory/insights?${params}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to get memory insights' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory insights error:', error);
    return NextResponse.json(
      {
        success: false,
        learned_concepts: [],
        successful_patterns: [],
        value_mappings: [],
        error_fixes: [],
        total_learned_items: 0,
        error: 'Failed to connect to backend'
      },
      { status: 500 }
    );
  }
}
