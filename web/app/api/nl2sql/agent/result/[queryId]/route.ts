import { getBackendUrl } from '@/lib/api/config';
import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ queryId: string }> }
) {
  const { queryId } = await params;

  try {
    // Fetch result from backend API
    const response = await fetch(`${API_BASE_URL}/api/nl2sql/agent/result/${queryId}`);

    if (!response.ok) {
      const error = await response.json();
      return NextResponse.json(error, { status: response.status });
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('[Result API] Error fetching result:', error);
    return NextResponse.json({
      query_id: queryId,
      status: 'error',
      error: 'Failed to fetch result'
    }, { status: 500 });
  }
}
