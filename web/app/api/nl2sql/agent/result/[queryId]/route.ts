import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ queryId: string }> }
) {
  try {
    const { queryId } = await params;
    const sessionId = request.headers.get('X-Session-Id');

    // Build headers
    const headers: Record<string, string> = {};
    if (sessionId) {
      headers['X-Session-Id'] = sessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/nl2sql/agent/result/${queryId}`, {
      headers,
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to fetch agent results' },
        { status: response.status }
      );
    }

    const data = await response.json();

    console.log('[Agent Result API] Response structure:', {
      hasResult: !!data.result,
      resultKeys: data.result ? Object.keys(data.result) : null,
      hasSql: !!data.result?.sql,
      hasResults: !!data.result?.results,
      resultsKeys: data.result?.results ? Object.keys(data.result.results) : null,
      hasSummary: !!data.result?.results?.summary,
      summary: data.result?.results?.summary,
    });

    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching agent results:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
