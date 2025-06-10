import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ tableName: string }> }
) {
  try {
    const { tableName } = await params;
    const sessionId = request.headers.get('X-Session-Id');

    if (!sessionId) {
      return NextResponse.json(
        { error: 'Session ID required' },
        { status: 400 }
      );
    }

    const url = new URL(request.url);
    const limit = url.searchParams.get('limit') || '100';

    const response = await fetch(
      `${API_URL}/api/datasource/preview/${tableName}?limit=${limit}`,
      {
        headers: {
          'X-Session-Id': sessionId,
        },
      }
    );

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(
        { error: error.detail || 'Failed to preview table' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Table Preview Error:', error);
    return NextResponse.json(
      { error: 'Failed to preview table' },
      { status: 500 }
    );
  }
}
