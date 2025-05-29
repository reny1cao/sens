import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Forward request to FastAPI backend
    const response = await fetch(`${API_URL}/api/nl2sql`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to process query' },
        { status: response.status }
      );
    }

    const data = await response.json();

    // Log the response for debugging
    console.log('Backend response:', {
      sql: data.sql?.substring(0, 100) + '...',
      resultsKeys: Object.keys(data.results || {}),
      columns: data.results?.columns,
      dataLength: data.results?.data?.length,
      firstRow: data.results?.data?.[0],
    });

    return NextResponse.json(data);
  } catch (error) {
    console.error('API Error:', error);

    return NextResponse.json(
      { error: 'Failed to connect to backend' },
      { status: 500 }
    );
  }
}
