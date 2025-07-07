import { NextRequest } from "next/server";

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || "http://localhost:8000";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id: evaluationId } = await params;

    console.log(`Attempting to stream from: ${FASTAPI_BASE_URL}/api/evaluation/bird-sql-dev/stream/${evaluationId}`);

    const response = await fetch(
      `${FASTAPI_BASE_URL}/api/evaluation/bird-sql-dev/stream/${evaluationId}`,
      {
        method: "GET",
        headers: {
          "Accept": "text/event-stream",
          "Cache-Control": "no-cache",
        },
      }
    );

    console.log(`FastAPI response status: ${response.status}`);

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`FastAPI error: ${response.status} - ${errorText}`);
      throw new Error(`FastAPI error: ${response.status} ${errorText}`);
    }

    // Stream the response
    return new Response(response.body, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "*",
      },
    });
  } catch (error) {
    console.error("Error streaming BIRD-SQL-DEV evaluation:", error);

    // Send initial error message
    const errorStream = new ReadableStream({
      start(controller) {
        const errorMessage = `data: ${JSON.stringify({
          type: "error",
          error: `Failed to connect to backend: ${error.message}. Make sure FastAPI is running on ${FASTAPI_BASE_URL}`
        })}\n\n`;
        controller.enqueue(new TextEncoder().encode(errorMessage));
        controller.close();
      }
    });

    return new Response(errorStream, {
      headers: {
        "Content-Type": "text/event-stream",
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
      },
    });
  }
}
