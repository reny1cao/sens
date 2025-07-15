# Agent Query System Flow Analysis

## Overview
The agent query system uses a two-step process:
1. **POST /api/nl2sql/agent/query** - Initiates query and returns query_id
2. **GET /api/nl2sql/agent/stream/{query_id}** - SSE stream for real-time events

## Complete Event Flow

### 1. Frontend Initiates Query (useAgentQueryV2.ts)
- Calls POST `/api/nl2sql/agent/query` with question
- Receives `query_id` in response
- Opens EventSource to `/api/nl2sql/agent/stream/{query_id}`

### 2. Backend Processing (nl2sql_unified.py)
- **agent_query**: Stores query data and returns query_id
- **agent_stream**:
  - Retrieves stored query data
  - Sets up event handler to capture agent events
  - Processes query asynchronously
  - Transforms and streams events via SSE

### 3. SSE Event Sequence
The backend emits these events in order:
1. **start** - Processing begins
2. **thought** - Agent reasoning steps
3. **action** - Actions taken (e.g., "Executing SQL query")
4. **observation** - Results of actions
5. **answer** - Natural language response
6. **result** - Complete result object with SQL and data
7. **complete** - Processing finished

### 4. Frontend Event Handling (useAgentQueryV2.ts)
- Listens for each event type
- Updates `steps` array with thought/action/observation/answer events
- Sets `result` when result event is received
- Marks `isComplete=true` on complete event
- Implements retry logic to fetch final result if needed

### 5. UI State Updates (ChatInterfaceV6.tsx)
- Monitors agentQuery state changes
- Updates message status based on:
  - `isStreaming` → status="processing"
  - `isComplete` + `result` → status="complete"
  - `isComplete` + `error` → status="error"
  - `isComplete` + no result → status="failed"

## Identified Issues

### Issue 1: Missing `/agent/query` Endpoint
**Problem**: Frontend expects POST `/api/nl2sql/agent/query` but it wasn't defined
**Fix**: Added the endpoint to store query data and return query_id

### Issue 2: Flashing States
**Root Cause**: Race condition between `isComplete` becoming true and `result` being available

**Sequence of events causing the flash**:
1. Backend sends `complete` event
2. Frontend sets `isComplete=true` immediately
3. ChatInterfaceV6 sees `isComplete=true` but `result` is still null
4. UI briefly shows "failed" state
5. Frontend fetches result via polling
6. Result becomes available, UI updates to "complete"

**Why this happens**:
- The `complete` event is sent AFTER the `result` event
- But due to async nature and event processing delays, the UI might update before the result is fully processed
- The retry logic (lines 269-335 in useAgentQueryV2) helps but introduces a delay

### Issue 3: Inconsistent Result Structure
The backend returns results in different formats:
- SQL execution: `{result: {columns: [], rows: [], row_count: N}}`
- Direct answers: `{answer: "...", direct_answer: "..."}`
- Errors: `{error: "...", success: false}`

The frontend has to handle all these cases (lines 197-258 in useAgentQueryV2).

## Recommendations

### 1. Fix Event Ordering
Ensure `result` is always available before `complete`:
- Store result immediately when available
- Add small delay before sending `complete` event
- Or combine result and complete into a single event

### 2. Simplify State Management
Instead of separate `isComplete` and `result` states:
```typescript
type QueryState = 'idle' | 'streaming' | 'complete' | 'failed' | 'error';
```

### 3. Standardize Result Format
Always return consistent structure:
```typescript
{
  success: boolean,
  sql?: string,
  results?: {columns, data, row_count},
  answer?: string,
  error?: string
}
```

### 4. Add Loading States
The UI currently shows "Query completed" with loading spinner when waiting for data.
Better to show more specific states:
- "Executing query..."
- "Processing results..."
- "Generating response..."

### 5. Improve Error Handling
Currently, empty results show as "Query failed" which is incorrect.
Should distinguish between:
- Query executed successfully with 0 results
- Query failed due to error
- No results available yet (loading)

## Current Workarounds

1. **Retry Logic**: Frontend polls `/agent/result/{query_id}` up to 5 times with exponential backoff
2. **State Checks**: UI checks multiple conditions to determine actual state
3. **Manual Result Transformation**: Frontend transforms various result formats to consistent structure

These workarounds add complexity and potential points of failure.
