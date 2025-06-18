# Agent UI Architecture & Best Practices

## Current State Analysis

### Problems with Current Implementation
1. **Single Message Approach**: Everything (reasoning, answer, data) is crammed into one message object
2. **Poor Content Separation**: Natural language answer is mixed with reasoning steps and data tables
3. **Limited Extensibility**: Hard to add new content types (graphs, charts, explanations)
4. **Unclear Information Hierarchy**: Users can't easily distinguish between reasoning process and final answer

## Proposed Architecture

### 1. Message Type System

Instead of a single message with mixed content, use a **multi-message approach** where each message has a specific type:

```typescript
enum MessageType {
  USER_QUERY = 'user_query',
  AGENT_THINKING = 'agent_thinking',      // Collapsible reasoning steps
  NATURAL_LANGUAGE = 'natural_language',  // Main answer
  SQL_QUERY = 'sql_query',               // Generated SQL
  DATA_TABLE = 'data_table',             // Results table
  DATA_VISUALIZATION = 'data_viz',       // Future: Charts/graphs
  ERROR = 'error',
  SYSTEM = 'system'
}

interface Message {
  id: string;
  type: MessageType;
  content: any;
  metadata: {
    parentId?: string;      // Link related messages
    timestamp: Date;
    status: 'pending' | 'streaming' | 'complete' | 'error';
    isCollapsible?: boolean;
    defaultCollapsed?: boolean;
  };
}
```

### 2. Message Flow Pattern

When user submits a query, create a sequence of messages:

```
[User Query]
    ↓
[Agent Thinking] (real-time streaming, collapsible)
    ↓
[Natural Language Answer] (main response)
    ↓
[SQL Query] (optional, collapsible)
    ↓
[Data Table/Visualization] (if applicable)
```

### 3. Implementation Strategy

#### Phase 1: Message Separation
```typescript
// When agent completes, create multiple messages
const createAgentResponseMessages = (result: AgentResult) => {
  const messages: Message[] = [];
  const parentId = `response-${Date.now()}`;

  // 1. Thinking/Reasoning message (already exists during processing)
  // Just update its status to complete and make collapsible

  // 2. Natural Language Answer (new separate message)
  if (result.answer) {
    messages.push({
      id: `${parentId}-answer`,
      type: MessageType.NATURAL_LANGUAGE,
      content: result.answer,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete'
      }
    });
  }

  // 3. SQL Query (if needed)
  if (result.sql) {
    messages.push({
      id: `${parentId}-sql`,
      type: MessageType.SQL_QUERY,
      content: result.sql,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete',
        isCollapsible: true,
        defaultCollapsed: true
      }
    });
  }

  // 4. Data Results
  if (result.data) {
    messages.push({
      id: `${parentId}-data`,
      type: MessageType.DATA_TABLE,
      content: result.data,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete'
      }
    });
  }

  return messages;
};
```

#### Phase 2: Component Architecture

```typescript
// Dedicated component for each message type
const MessageRenderer: React.FC<{ message: Message }> = ({ message }) => {
  switch (message.type) {
    case MessageType.USER_QUERY:
      return <UserMessage {...message} />;

    case MessageType.AGENT_THINKING:
      return <AgentThinkingMessage {...message} />;

    case MessageType.NATURAL_LANGUAGE:
      return <NaturalLanguageAnswer {...message} />;

    case MessageType.SQL_QUERY:
      return <SQLQueryMessage {...message} />;

    case MessageType.DATA_TABLE:
      return <DataTableMessage {...message} />;

    case MessageType.DATA_VISUALIZATION:
      return <DataVisualization {...message} />;

    default:
      return null;
  }
};
```

### 4. UI/UX Best Practices

#### Visual Hierarchy
1. **User Query**: Right-aligned, distinct background
2. **Agent Thinking**: Subtle background, collapsible, smaller font
3. **Natural Language Answer**: Prominent, left-aligned, larger font, distinct styling
4. **Supporting Content**: SQL, data tables as secondary elements

#### Animation & Transitions
1. **Streaming**: Thinking steps appear with subtle fade-in
2. **Completion**: Thinking box auto-collapses after 3s
3. **Answer Appearance**: Smooth slide-in from bottom
4. **Data Loading**: Skeleton loaders for tables

#### Interaction Patterns
1. **Click to Expand**: Collapsed sections expand on click
2. **Copy Actions**: Easy copy for SQL, data
3. **Export Options**: Download CSV, copy as JSON
4. **View Toggles**: Switch between table/chart views

### 5. Real-time Streaming Strategy

```typescript
// Enhanced SSE handling
interface StreamEvent {
  type: 'thinking' | 'answer_start' | 'answer_chunk' | 'answer_complete' | 'data_ready';
  content: any;
}

// Stream natural language answer in chunks
const handleAnswerStream = (chunks: string[]) => {
  // Create answer message on first chunk
  if (chunks.length === 1) {
    addMessage({
      type: MessageType.NATURAL_LANGUAGE,
      content: chunks[0],
      metadata: { status: 'streaming' }
    });
  } else {
    // Update existing message
    updateMessage(id, {
      content: chunks.join(''),
      metadata: { status: 'streaming' }
    });
  }
};
```

### 6. Future Extensibility

#### Data Visualizations
```typescript
// Automatic chart generation based on data type
const suggestVisualization = (data: QueryResult) => {
  if (hasTimeSeries(data)) return 'line_chart';
  if (hasCategorical(data)) return 'bar_chart';
  if (hasGeographic(data)) return 'map';
  return null;
};
```

#### Interactive Features
1. **Drill-down**: Click data points for details
2. **Query Refinement**: "Show me more about X"
3. **Export Options**: PNG, SVG, CSV
4. **Sharing**: Generate shareable links

## Implementation Roadmap

### Phase 1: Message Separation (Current Priority)
1. Refactor message structure to support multiple types
2. Create separate message for natural language answer
3. Update ChatInterface to handle message sequences
4. Implement proper visual hierarchy

### Phase 2: Enhanced Interactions
1. Add collapsible behavior with animations
2. Implement copy/export functionality
3. Add loading states and skeletons
4. Improve mobile responsiveness

### Phase 3: Data Visualizations
1. Integrate charting library (Recharts/D3)
2. Auto-detect visualization opportunities
3. Create visualization message type
4. Add interactive features

### Phase 4: Advanced Features
1. Query refinement UI
2. Conversation branching
3. Result comparison
4. Saved queries/dashboards

## Example Implementation

```typescript
// ChatInterface.tsx - Updated completion handler
useEffect(() => {
  if (!isProcessing || !useAgent || !agentQuery.result) return;

  const messages: Message[] = [];
  const parentId = `response-${Date.now()}`;

  // Update thinking message to complete
  updateMessage(thinkingMessageId, {
    status: 'complete',
    metadata: {
      isCollapsible: true,
      defaultCollapsed: true
    }
  });

  // Add natural language answer as separate message
  if (agentQuery.result.answer) {
    messages.push({
      id: `${parentId}-answer`,
      type: MessageType.NATURAL_LANGUAGE,
      content: agentQuery.result.answer,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete'
      }
    });
  }

  // Add SQL if exists
  if (agentQuery.result.sql) {
    messages.push({
      id: `${parentId}-sql`,
      type: MessageType.SQL_QUERY,
      content: agentQuery.result.sql,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete',
        isCollapsible: true,
        defaultCollapsed: false
      }
    });
  }

  // Add data table
  if (agentQuery.result.data) {
    messages.push({
      id: `${parentId}-data`,
      type: MessageType.DATA_TABLE,
      content: agentQuery.result.data,
      metadata: {
        parentId,
        timestamp: new Date(),
        status: 'complete'
      }
    });
  }

  // Add all messages to chat
  setMessages(prev => [...prev, ...messages]);

}, [agentQuery.result]);
```

This architecture provides:
- Clear separation of concerns
- Better user experience
- Easy extensibility
- Modern UI patterns similar to ChatGPT/Claude
- Scalable for future features
