import { getBackendUrl } from '@/lib/api/config';
import { NextRequest } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ queryId: string }> }
) {
  const { queryId } = await params;
  const sessionId = request.headers.get('X-Session-Id');

  // Build headers
  const headers: Record<string, string> = {};
  if (sessionId) {
    headers['X-Session-Id'] = sessionId;
  }

  try {
    // Create a pass-through stream for SSE
    const response = await fetch(`${API_BASE_URL}/api/nl2sql/agent/stream/${queryId}`, {
      headers,
    });

    if (!response.ok) {
      return new Response(
        `event: error\ndata: ${JSON.stringify({ content: 'Failed to connect to agent stream' })}\n\n`,
        {
          status: response.status,
          headers: {
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
          },
        }
      );
    }

    // Forward the SSE stream
    return new Response(response.body, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
      },
    });
  } catch (error) {
    console.error('Error connecting to agent stream:', error);
    return new Response(
      `event: error\ndata: ${JSON.stringify({ content: 'Internal server error' })}\n\n`,
      {
        status: 500,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      }
    );
  }
}