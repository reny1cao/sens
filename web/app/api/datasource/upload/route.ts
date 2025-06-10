import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_URL = getBackendUrl();

export async function POST(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-Id');
    const formData = await request.formData();

    console.log('Uploading to:', `${API_URL}/api/datasource/upload`);
    console.log('Session ID:', sessionId);

    // Forward to FastAPI backend
    const response = await fetch(`${API_URL}/api/datasource/upload`, {
      method: 'POST',
      headers: {
        'X-Session-Id': sessionId || '',
      },
      body: formData,
    });

    console.log('Backend response status:', response.status);

    if (!response.ok) {
      const error = await response.json();
      console.error('Backend error:', error);
      return NextResponse.json(
        { error: error.detail || 'Failed to upload files' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Upload Error:', error);
    console.error('Error details:', error instanceof Error ? error.message : 'Unknown error');
    return NextResponse.json(
      { error: 'Failed to upload files', detail: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}
