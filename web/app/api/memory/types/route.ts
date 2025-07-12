import { getBackendUrl } from '@/lib/api/config';
import { NextResponse } from 'next/server';

const API_BASE_URL = getBackendUrl();

export async function GET() {
  try {
    const response = await fetch(`${API_BASE_URL}/api/memory/types`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
    });

    if (!response.ok) {
      const error = await response.text();
      return NextResponse.json(
        { error: error || 'Failed to get memory types' },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Memory types error:', error);
    return NextResponse.json(
      {
        memory_types: [
          { type: 'concept', description: 'Business concepts and their database mappings' },
          { type: 'pattern', description: 'Successful SQL patterns and query templates' },
          { type: 'mapping', description: 'Value mappings between user terms and database values' },
          { type: 'rule', description: 'Business rules and constraints' },
          { type: 'calculation', description: 'How to calculate specific metrics' },
          { type: 'error_fix', description: 'Solutions to common errors' },
          { type: 'relationship', description: 'How tables and concepts relate to each other' }
        ]
      },
      { status: 200 }
    );
  }
}
