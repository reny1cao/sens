import { getBackendUrl } from '@/lib/api/config';
import { NextRequest } from 'next/server';
import { activeQueries } from '../../query/route';

const API_BASE_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ queryId: string }> }
) {
  const { queryId } = await params;

  // Get query info from storage
  console.log('[Stream API] Looking for query ID:', queryId);
  console.log('[Stream API] Active queries:', activeQueries.size);
  console.log('[Stream API] Active query IDs:', Array.from(activeQueries.keys()));

  const queryInfo = activeQueries.get(queryId);

  if (!queryInfo) {
    console.error('[Stream API] Query not found:', queryId);
    return new Response(
      `event: error\ndata: ${JSON.stringify({ content: 'Query not found or expired' })}\n\n`,
      {
        status: 404,
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      }
    );
  }

  try {
    // Prepare request body for streaming
    const requestBody = {
      question: queryInfo.question,
      mode: 'agent',
      query_id: queryId, // Pass the query ID to backend
      ...(queryInfo.sessionId && { session_id: queryInfo.sessionId }),
    };

    // Connect to the new streaming endpoint
    const response = await fetch(`${API_BASE_URL}/api/nl2sql/agent/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
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

    // Clean up query info after streaming completes (5 minutes)
    setTimeout(() => {
      activeQueries.delete(queryId);
    }, 5 * 60 * 1000);

    // Forward the SSE stream with event type mapping
    const reader = response.body?.getReader();
    const encoder = new TextEncoder();

    return new Response(
      new ReadableStream({
        async start(controller) {
          if (!reader) {
            controller.close();
            return;
          }

          // Send initial connection event
          controller.enqueue(encoder.encode(`event: connection\ndata: ${JSON.stringify({ status: 'connected' })}\n\n`));

          let buffer = '';

          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              // Convert chunk to string and add to buffer
              const chunk = new TextDecoder().decode(value);
              buffer += chunk;

              // Parse complete SSE events from buffer
              let eventBoundary = buffer.lastIndexOf('\n\n');
              if (eventBoundary !== -1) {
                const completeEvents = buffer.substring(0, eventBoundary);
                buffer = buffer.substring(eventBoundary + 2);

                // Parse each event
                const events = completeEvents.split('\n\n').filter(e => e.trim());

                for (const event of events) {
                  const lines = event.split('\n');
                  let eventType = '';
                  let eventData = '';

                  for (const line of lines) {
                    if (line.startsWith('event: ')) {
                      eventType = line.substring(7).trim();
                    } else if (line.startsWith('data: ')) {
                      eventData = line.substring(6).trim();
                    }
                  }

                  // Log all events for debugging
                  if (eventType && eventData) {
                    console.log(`[Stream] Event: ${eventType}, Data length: ${eventData.length}`);
                  }

                  // Log result event for debugging (no longer storing it here)
                  if (eventType === 'result' && eventData) {
                    try {
                      const parsed = JSON.parse(eventData);
                      console.log('[Stream] Result event received:', {
                        hasContent: !!parsed.content,
                        contentKeys: parsed.content ? Object.keys(parsed.content) : null
                      });
                    } catch (e) {
                      console.error('[Stream] Failed to parse result event:', e);
                    }
                  }
                }
              }

              // Forward the chunk as-is
              controller.enqueue(value);
            }
          } catch (error) {
            console.error('Stream error:', error);
            controller.enqueue(encoder.encode(`event: error\ndata: ${JSON.stringify({ content: 'Stream error' })}\n\n`));
          } finally {
            controller.close();
          }
        },
      }),
      {
        headers: {
          'Content-Type': 'text/event-stream',
          'Cache-Control': 'no-cache',
          'Connection': 'keep-alive',
        },
      }
    );
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
