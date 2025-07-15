import { NextRequest } from "next/server";

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || "http://localhost:8000";

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: evaluationId } = await params;

    console.log(`Cancelling BIRD-SQL-DEV evaluation: ${evaluationId}`);

    const response = await fetch(
      `${FASTAPI_BASE_URL}/api/evaluation/bird-sql-dev/${evaluationId}`,
      {
        method: "DELETE",
      }
    );

    console.log(`FastAPI response status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`FastAPI error: ${response.status} - ${errorText}`);
      return Response.json(
        { error: `Failed to cancel evaluation: ${response.status} ${errorText}` },
        { status: response.status }
      );
    }

    const result = await response.json();
    return Response.json(result);

  } catch (error) {
    console.error("Error cancelling BIRD-SQL-DEV evaluation:", error);
    return Response.json(
      { error: `Failed to cancel evaluation: ${error.message}` },
      { status: 500 }
    );
  }
}
