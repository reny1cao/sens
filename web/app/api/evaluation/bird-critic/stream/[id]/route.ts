import { NextRequest } from 'next/server';

const BACKEND_URL = process.env.SENS_API_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: evaluationId } = await params;

    // Create a proxy stream to the FastAPI backend
    const response = await fetch(
      `${BACKEND_URL}/api/evaluation/bird-critic/stream/${evaluationId}`,
      {
        method: 'GET',
        headers: {
          'Accept': 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status} ${response.statusText}`);
    }

    // Return the stream directly
    return new Response(response.body, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no', // Disable Nginx buffering
      },
    });
  } catch (error) {
    console.error('Stream proxy error:', error);

    // Return error as SSE event
    const errorEvent = `data: ${JSON.stringify({
      type: 'evaluation_error',
      error: 'Failed to connect to evaluation stream'
    })}\n\n`;

    return new Response(errorEvent, {
      status: 200,
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });
  }
}
