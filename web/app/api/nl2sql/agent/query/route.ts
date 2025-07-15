import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

// Use global to persist across HMR in development
declare global {
  var activeQueries: Map<string, { question: string; sessionId?: string }> | undefined;
  var queryResults: Map<string, any> | undefined;
}

// Store active queries for streaming
export const activeQueries = global.activeQueries || new Map<string, { question: string; sessionId?: string }>();
if (!global.activeQueries) {
  global.activeQueries = activeQueries;
}

// Store query results
export const queryResults = global.queryResults || new Map<string, any>();
if (!global.queryResults) {
  global.queryResults = queryResults;
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const sessionId = request.headers.get('X-Session-Id');

    // Generate a unique query ID
    const queryId = `query-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
    console.log('[Query API] Creating query with ID:', queryId);

    // Store query info for streaming endpoint
    activeQueries.set(queryId, {
      question: body.question,
      sessionId: sessionId || undefined,
    });
    console.log('[Query API] Stored query. Active queries:', activeQueries.size);

    // Clean up old queries after 5 minutes
    setTimeout(() => {
      activeQueries.delete(queryId);
    }, 5 * 60 * 1000);

    // Return query ID immediately so frontend can connect to stream
    return NextResponse.json({
      query_id: queryId,
      status: 'pending'
    });
  } catch (error) {
    console.error('Error starting agent query:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
