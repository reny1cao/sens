import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET(request: NextRequest) {
  try {
    const sessionId = request.headers.get('X-Session-Id');

    console.log('[Suggestions API] GET request received', {
      sessionId,
      API_BASE_URL,
      fullUrl: `${API_BASE_URL}/api/datasource/suggestions`
    });

    // Build headers - session ID is optional
    const headers: Record<string, string> = {};
    if (sessionId) {
      headers['X-Session-Id'] = sessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/datasource/suggestions`, {
      headers,
    });

    console.log('[Suggestions API] Backend response status:', response.status);

    if (!response.ok) {
      const error = await response.text();
      console.error('[Suggestions API] Backend error:', error);
      return NextResponse.json(
        { error: error || 'Failed to fetch suggestions' },
        { status: response.status }
      );
    }

    const data = await response.json();
    console.log('[Suggestions API] Backend data:', {
      source: data.source,
      suggestionsCount: data.suggestions?.length || 0,
      firstSuggestion: data.suggestions?.[0]
    });

    return NextResponse.json(data);
  } catch (error) {
    console.error('[Suggestions API] Error fetching suggestions:', error);
    // Return fallback suggestions if backend is not available
    return NextResponse.json({
      source: 'fallback',
      suggestions: [
        "Show me the latest Apple stock prices",
        "What are the top 10 stocks by volume today?",
        "Show me stocks with price changes over 5%",
        "List all technology sector stocks"
      ]
    });
  }
}

export async function POST(request: NextRequest) {
  // Refresh endpoint
  try {
    const sessionId = request.headers.get('X-Session-Id');

    // Build headers - session ID is optional
    const headers: Record<string, string> = {};
    if (sessionId) {
      headers['X-Session-Id'] = sessionId;
    }

    const response = await fetch(`${API_BASE_URL}/api/datasource/suggestions/refresh`, {
      method: 'POST',
      headers,
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to refresh suggestions' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error refreshing suggestions:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}
