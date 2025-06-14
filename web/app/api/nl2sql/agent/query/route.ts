import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const sessionId = request.headers.get('X-Session-Id');

    // Build headers
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
    };
    if (sessionId) {
      headers['X-Session-Id'] = sessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/nl2sql/agent/query`, {
      method: 'POST',
      headers,
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to start agent query' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error starting agent query:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}