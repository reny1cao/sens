import { NextRequest, NextResponse } from 'next/server';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const sessionId = request.headers.get('X-Session-Id');

    // Determine which endpoint to use based on session
    const endpoint = sessionId 
      ? `${API_URL}/api/nl2sql/session/query`
      : `${API_URL}/api/nl2sql`;

    // Forward request to FastAPI backend
    const response = await fetch(endpoint, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(sessionId && { 'X-Session-Id': sessionId }),
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

    // Transform the response to match frontend expectations
    if (data.results && data.results.rows && data.results.columns) {
      // Convert rows (array of arrays) to data (array of objects)
      data.results.data = data.results.rows.map((row: any[]) => {
        const obj: Record<string, any> = {};
        data.results.columns.forEach((col: string, idx: number) => {
          obj[col] = row[idx];
        });
        return obj;
      });
      
      // Remove the rows field to avoid confusion
      delete data.results.rows;
    }

    // Transform metadata to match frontend expectations
    if (data.metadata) {
      // Ensure execution_time_ms exists
      if (data.metadata.execution_time !== undefined && data.metadata.execution_time_ms === undefined) {
        data.metadata.execution_time_ms = data.metadata.execution_time * 1000;
      }
      
      // Default values for required fields
      data.metadata.tables_used = data.metadata.tables_used || [];
      data.metadata.query_type = data.metadata.query_type || 'select';
    }

    // Log the transformed response for debugging
    console.log('Transformed response:', {
      sql: data.sql?.substring(0, 100) + '...',
      resultsKeys: Object.keys(data.results || {}),
      columns: data.results?.columns,
      dataLength: data.results?.data?.length,
      dataType: Array.isArray(data.results?.data) ? 'array' : typeof data.results?.data,
      columnsType: Array.isArray(data.results?.columns) ? 'array' : typeof data.results?.columns,
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
