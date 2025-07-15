import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const category = searchParams.get('category') || 'all';
    const search = searchParams.get('search') || '';

    // Call the real backend API
    const backendUrl = new URL('/api/knowledge/data', BACKEND_URL);
    backendUrl.searchParams.set('category', category);
    backendUrl.searchParams.set('search', search);

    const response = await fetch(backendUrl.toString());

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`);
    }

    const data = await response.json();

    // Return the real data from the backend
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error fetching knowledge data:', error);
    return NextResponse.json(
      { error: 'Failed to fetch knowledge data' },
      { status: 500 }
    );
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();

    // Call the real backend API
    const backendUrl = new URL('/api/knowledge/action', BACKEND_URL);

    const response = await fetch(backendUrl.toString(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(`Backend API error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error processing knowledge action:', error);
    return NextResponse.json(
      { error: 'Failed to process action' },
      { status: 500 }
    );
  }
}
