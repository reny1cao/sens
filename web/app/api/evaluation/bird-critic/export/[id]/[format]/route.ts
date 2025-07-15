import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.SENS_API_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string; format: string }> }
) {
  try {
    const { id: evaluationId, format } = await params;

    const response = await fetch(
      `${BACKEND_URL}/api/evaluation/bird-critic/export/${evaluationId}/${format}`,
      {
        method: 'GET',
      }
    );

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status} ${response.statusText}`);
    }

    // Get the content type and filename from backend
    const contentType = response.headers.get('content-type') || 'application/json';
    const contentDisposition = response.headers.get('content-disposition');

    // Stream the file content
    const body = await response.arrayBuffer();

    const headers: Record<string, string> = {
      'Content-Type': contentType,
    };

    if (contentDisposition) {
      headers['Content-Disposition'] = contentDisposition;
    }

    return new Response(body, {
      status: 200,
      headers,
    });
  } catch (error) {
    console.error('Export proxy error:', error);
    return new Response(
      JSON.stringify({ error: 'Failed to export evaluation results' }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
