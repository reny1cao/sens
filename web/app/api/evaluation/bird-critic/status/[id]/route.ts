import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.SENS_API_URL || 'http://localhost:8000';

export async function GET(
  request: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const evaluationId = params.id;

    const response = await fetch(
      `${BACKEND_URL}/api/evaluation/bird-critic/status/${evaluationId}`,
      {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      }
    );

    if (!response.ok) {
      throw new Error(`Backend error: ${response.status} ${response.statusText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Status proxy error:', error);
    return NextResponse.json(
      { error: 'Failed to get evaluation status' },
      { status: 500 }
    );
  }
}
