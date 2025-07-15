import { NextRequest, NextResponse } from "next/server";

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: evaluationId } = await params;

    const response = await fetch(
      `${FASTAPI_BASE_URL}/api/evaluation/bird-sql-dev/status/${evaluationId}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`FastAPI error: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error getting BIRD-SQL-DEV evaluation status:", error);
    return NextResponse.json(
      { error: "Failed to get evaluation status" },
      { status: 500 }
    );
  }
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: evaluationId } = await params;

    const response = await fetch(
      `${FASTAPI_BASE_URL}/api/evaluation/bird-sql-dev/${evaluationId}`,
      {
        method: "DELETE",
      }
    );

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`FastAPI error: ${response.status} ${errorText}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error("Error cancelling BIRD-SQL-DEV evaluation:", error);
    return NextResponse.json(
      { error: "Failed to cancel evaluation" },
      { status: 500 }
    );
  }
}
