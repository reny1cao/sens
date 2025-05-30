import { NextRequest, NextResponse } from 'next/server';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function DELETE(
  request: NextRequest,
  { params }: { params: { sessionId: string; tableName: string } }
) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/datasource/session/${params.sessionId}/table/${params.tableName}`,
      {
        method: 'DELETE',
        headers: {
          'X-Session-Id': params.sessionId,
        },
      }
    );

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to delete table' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error deleting table:', error);
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    );
  }
}