# Agent Integration Implementation Plan

## Overview
This document outlines the implementation plan for integrating the SENS Agent (with its 3-tool approach: EXPLORE_DATABASE, GENERATE_SQL, EXECUTE_SQL) into the main API with real-time updates for the frontend.

## Architecture Design

### 1. Backend Changes

#### Server-Sent Events (SSE) for Real-time Updates
We'll use SSE instead of WebSockets for simplicity and compatibility with the existing FastAPI setup.

```
Client (Browser) <--SSE--> FastAPI Endpoint <--> SENSAgent
                     |                              |
                     |-- Event Stream ---------------|
                     |-- Agent Steps in Real-time --|
```

#### New API Router: `nl2sql_agent.py`
Location: `/src/sens/api/routers/nl2sql_agent.py`

Key endpoints:
- `POST /api/nl2sql/agent/query` - Initiates agent query (returns query_id)
- `GET /api/nl2sql/agent/stream/{query_id}` - SSE endpoint for real-time updates
- `GET /api/nl2sql/agent/result/{query_id}` - Get final results

### 2. Frontend Changes

#### New Components
1. `AgentProcessingSteps.tsx` - Enhanced version showing agent reasoning
2. `useAgentQuery.ts` - Hook for agent queries with SSE support
3. `AgentThoughtDisplay.tsx` - Display agent's thinking process

#### Real-time Flow
1. User submits query
2. Frontend receives query_id
3. Opens EventSource connection to SSE endpoint
4. Receives and displays agent steps in real-time
5. Shows final results when complete

## Implementation Steps

### Phase 1: Backend SSE Infrastructure

1. **Create SSE utilities** (`/src/sens/api/common/sse.py`)
   - SSE message formatting
   - Event types: thought, action, observation, complete, error

2. **Implement Agent API Router** (`/src/sens/api/routers/nl2sql_agent.py`)
   - Query initiation endpoint
   - SSE streaming endpoint
   - Result retrieval endpoint

3. **Create Agent Event Emitter** (`/src/sens/agents/event_emitter.py`)
   - Wrapper around SENSAgent that emits events
   - Captures thoughts, actions, observations

### Phase 2: Frontend SSE Integration

1. **Create SSE Hook** (`/web/hooks/useAgentSSE.ts`)
   - EventSource management
   - Automatic reconnection
   - Event parsing

2. **Update Query Interface**
   - Add "Agent Mode" toggle
   - Route to agent endpoint when enabled

3. **Create Agent UI Components**
   - Real-time step visualization
   - Thought bubble display
   - Action/observation formatting

### Phase 3: Enhanced Visualization

1. **Agent Timeline View**
   - Visual timeline of agent actions
   - Expandable details for each step

2. **Database Exploration Viewer**
   - Show tables/columns discovered
   - Display sample data found

3. **SQL Generation Progress**
   - Show SQL being built incrementally
   - Highlight mappings discovered

## Technical Implementation Details

### SSE Event Format
```typescript
interface AgentEvent {
  id: string;
  type: 'thought' | 'action' | 'observation' | 'complete' | 'error';
  timestamp: number;
  data: {
    iteration: number;
    content: string;
    metadata?: Record<string, any>;
  };
}
```

### Agent State Management
- Use Redis to store agent state during processing
- Query results cached for retrieval
- Timeout handling for long-running queries

### Error Handling
- Graceful SSE connection failures
- Agent timeout limits
- Fallback to standard nl2sql endpoint

## Benefits

1. **Real-time Visibility**: Users see agent thinking process
2. **Better UX**: No more waiting without feedback
3. **Debugging**: Easier to understand why queries fail
4. **Learning**: Users learn how to write better queries

## Timeline

- Phase 1: 2-3 days (Backend SSE)
- Phase 2: 2-3 days (Frontend integration)
- Phase 3: 1-2 days (Enhanced visualization)

Total: ~1 week for full implementation
