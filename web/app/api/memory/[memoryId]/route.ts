import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ memoryId: string }> }
) {
  try {
    const { memoryId } = await params;
    const sessionId = request.headers.get('X-Session-Id');
    const body = await request.json();

    // Build query parameters
    const queryParams = new URLSearchParams();
    if (sessionId) {
      queryParams.append('session_id', sessionId);
    } else {
      queryParams.append('session_id', 'global');
    }

    const response = await fetch(`${API_BASE_URL}/api/memory/${memoryId}?${queryParams}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to delete memory' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory delete error:', error);
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
