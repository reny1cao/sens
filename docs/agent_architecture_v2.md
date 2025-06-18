# Agent Architecture V2 - Based on Anthropic Best Practices

## Core Principles

1. **Augment Workflows, Don't Control Them**: The agent augments the SQL generation process, not controls it
2. **Simple, Composable Patterns**: Each component has a single responsibility
3. **Clear Separation of Concerns**: Reasoning, data retrieval, and presentation are separate
4. **Reliable Real-time Updates**: SSE events are atomic and stateless

## Architecture Overview

### 1. Agent Event Types (Backend)

```python
class AgentEventType(Enum):
    # Lifecycle events
    STARTED = "started"
    COMPLETED = "completed"
    FAILED = "failed"

    # Progress events
    THINKING = "thinking"           # Agent is reasoning about next step
    EXECUTING = "executing"         # Agent is executing an action
    RESULT_READY = "result_ready"   # Data is ready to display

    # Content events
    SQL_GENERATED = "sql_generated"
    DATA_RETRIEVED = "data_retrieved"
    ANSWER_READY = "answer_ready"
```

### 2. Frontend Message Flow

```typescript
// Clear message types for different content
enum MessageType {
  USER_QUERY = "user_query",
  AGENT_THINKING = "agent_thinking",    // Collapsible reasoning steps
  SQL_DISPLAY = "sql_display",          // Generated SQL
  DATA_RESULTS = "data_results",        // Table/chart data
  ANSWER = "answer",                    // Natural language response
  ERROR = "error"
}

// Each message is self-contained
interface Message {
  id: string;
  type: MessageType;
  content: any;
  metadata: {
    timestamp: Date;
    status: 'pending' | 'complete' | 'error';
    parentQueryId?: string;
  };
}
```

### 3. SSE Event Flow

```
User Query
    ↓
[started] → Frontend creates AGENT_THINKING message
    ↓
[thinking] → Updates reasoning steps in real-time
    ↓
[sql_generated] → Frontend creates SQL_DISPLAY message
    ↓
[executing] → Shows execution status
    ↓
[data_retrieved] → Frontend creates DATA_RESULTS message
    ↓
[answer_ready] → Frontend creates ANSWER message
    ↓
[completed] → Marks all messages as complete
```

### 4. Backend Agent Implementation

```python
class EventEmittingAgent:
    async def process_query(self, query: str) -> Dict[str, Any]:
        # Emit started event
        await self.emit({
            "type": "started",
            "query": query,
            "queryId": query_id
        })

        # Reasoning loop
        for iteration in range(max_iterations):
            # Emit thinking event
            await self.emit({
                "type": "thinking",
                "iteration": iteration,
                "content": reasoning_text
            })

            # Execute action
            if action_type == "generate_sql":
                sql = await self.generate_sql()
                await self.emit({
                    "type": "sql_generated",
                    "sql": sql
                })

            elif action_type == "execute_sql":
                await self.emit({
                    "type": "executing",
                    "what": "Running SQL query"
                })

                results = await self.execute_sql()
                await self.emit({
                    "type": "data_retrieved",
                    "row_count": len(results),
                    "preview": results[:5]
                })

                # Generate answer
                answer = await self.generate_answer(results)
                await self.emit({
                    "type": "answer_ready",
                    "answer": answer
                })
                break

        # Final event
        await self.emit({
            "type": "completed",
            "summary": {
                "sql": sql,
                "row_count": len(results),
                "answer": answer
            }
        })
```

### 5. Frontend SSE Handler

```typescript
class AgentEventHandler {
  private messages = new Map<string, Message>();

  handleEvent(event: AgentEvent) {
    switch (event.type) {
      case 'started':
        this.createThinkingMessage(event.queryId);
        break;

      case 'thinking':
        this.updateThinkingSteps(event.queryId, event.content);
        break;

      case 'sql_generated':
        this.createSqlMessage(event.queryId, event.sql);
        break;

      case 'data_retrieved':
        this.createDataMessage(event.queryId, event);
        break;

      case 'answer_ready':
        this.createAnswerMessage(event.queryId, event.answer);
        break;

      case 'completed':
        this.markAllComplete(event.queryId);
        break;
    }
  }

  // Each create method adds a new message
  createThinkingMessage(queryId: string) {
    const message: Message = {
      id: `${queryId}-thinking`,
      type: MessageType.AGENT_THINKING,
      content: { steps: [] },
      metadata: {
        timestamp: new Date(),
        status: 'pending',
        parentQueryId: queryId
      }
    };
    this.addMessage(message);
  }

  // Update methods modify existing messages
  updateThinkingSteps(queryId: string, step: string) {
    const message = this.messages.get(`${queryId}-thinking`);
    if (message) {
      message.content.steps.push({
        timestamp: new Date(),
        content: step
      });
      this.updateMessage(message);
    }
  }
}
```

### 6. Key Improvements

1. **No Race Conditions**: Each event creates or updates a specific message
2. **Clear Data Flow**: Events → Messages → UI Updates
3. **Separation of Concerns**:
   - Agent handles reasoning
   - Event system handles communication
   - Frontend handles presentation
4. **Extensible**: Easy to add new event types (graphs, charts, etc.)

### 7. Future Enhancements

1. **Visualization Events**:
   ```typescript
   case 'visualization_ready':
     this.createVisualizationMessage(event.queryId, event.chartData);
     break;
   ```

2. **Progressive Enhancement**:
   - Start with table
   - Agent suggests visualizations
   - User can toggle between views

3. **Caching & Performance**:
   - Cache successful query patterns
   - Reuse visualizations for similar queries

## Implementation Priority

1. **Phase 1**: Fix current SSE flow
   - Implement new event types
   - Update frontend handler
   - Ensure messages display correctly

2. **Phase 2**: Enhance agent reasoning
   - Better error handling
   - Smarter retry logic
   - Context awareness

3. **Phase 3**: Add visualizations
   - Chart suggestions
   - Interactive graphs
   - Export capabilities
