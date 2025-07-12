# Agent Architecture Refactoring Analysis & Plan

## Executive Summary

Based on analysis of the Google Gemini LangGraph quickstart and our current architecture, we have identified significant opportunities to improve our agent system's effectiveness, maintainability, and user experience. This document outlines a comprehensive refactoring plan that adopts LangGraph's proven patterns while maintaining compatibility with our existing domain-specific requirements.

## Current Architecture Analysis

### Current State (Custom Implementation)
- **Base Agent Pattern**: Custom abstract classes with `think()`, `act()`, `observe()`, `reflect()` methods
- **State Management**: Custom `AgentState` class with manual state tracking
- **Orchestration**: Custom reasoning engine with LLM-based decision making
- **Memory**: Redis-based caching with custom patterns
- **Communication**: Custom tool-calling system
- **Error Handling**: Manual error recovery without structured retry logic

### Pain Points Identified

1. **Lack of Visual Workflow**: No clear visualization of agent decision paths
2. **Manual State Management**: Error-prone state passing between components
3. **Limited Parallelization**: Sequential processing of independent tasks
4. **No Structured Retry**: Failures require manual intervention
5. **Complex Tool Integration**: Custom abstractions make tool additions difficult
6. **No Reflection Loop**: Missing iterative improvement patterns
7. **Difficult Debugging**: No clear execution traces or intermediate states

## Google LangGraph Best Practices Analysis

### Key Patterns from Google Implementation

1. **Graph-Based Workflow**: State flows through nodes connected by edges
2. **Structured State Management**: TypedDict with automatic merging
3. **Parallel Execution**: `Send` objects for concurrent processing
4. **Reflection Pattern**: Dedicated nodes for gap analysis and iteration
5. **Conditional Routing**: Dynamic path selection based on state
6. **Structured Outputs**: Pydantic models for reliable LLM responses
7. **Configuration Management**: Centralized, hierarchical configuration
8. **Citation Handling**: Automatic source tracking and formatting

### LangGraph Architecture Strengths

```python
# Clear node definitions
builder.add_node("generate_query", generate_query)
builder.add_node("web_research", web_research)
builder.add_node("reflection", reflection)
builder.add_node("finalize_answer", finalize_answer)

# Explicit state flow
builder.add_edge("web_research", "reflection")
builder.add_conditional_edges("reflection", evaluate_research, ["web_research", "finalize_answer"])

# Automatic state merging
class OverallState(TypedDict):
    messages: Annotated[list, add_messages]
    search_results: Annotated[list, operator.add]
```

## Refactoring Strategy

### Phase 1: Foundation (Weeks 1-2)
**Goal**: Establish LangGraph infrastructure without breaking existing functionality

#### 1.1 Install LangGraph Dependencies
```bash
poetry add langgraph langchain-core langchain-google-genai
```

#### 1.2 Create LangGraph State Schema
```python
# src/sens/agents/langgraph/state.py
from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph.message import add_messages
import operator

class SensAgentState(TypedDict):
    """Central state for SENS agent workflow."""
    
    # Message history
    messages: Annotated[List, add_messages]
    
    # Query processing
    user_query: str
    intent: Optional[str]
    
    # Schema retrieval
    retrieved_schema: Annotated[List[Dict], operator.add]
    relevant_tables: Annotated[List[str], operator.add]
    
    # SQL generation
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    
    # Execution results
    execution_results: Optional[Any]
    execution_error: Optional[str]
    
    # Agent reasoning
    thoughts: Annotated[List[str], operator.add]
    actions_taken: Annotated[List[str], operator.add]
    
    # Iteration control
    iteration_count: int
    max_iterations: int
    needs_refinement: bool
    
    # Memory and learning
    discovered_mappings: Annotated[List[Dict], operator.add]
    success_patterns: Annotated[List[Dict], operator.add]
```

#### 1.3 Create Node Functions
```python
# src/sens/agents/langgraph/nodes.py
from typing import Dict, Any
from langchain_core.runnables import RunnableConfig

async def analyze_intent(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze user intent and extract query requirements."""
    # Use existing intent extraction logic
    intent_result = await intent_extractor.extract_intent(state["user_query"])
    
    return {
        "intent": intent_result.intent,
        "thoughts": [f"Identified intent: {intent_result.intent}"],
        "actions_taken": ["analyze_intent"]
    }

async def retrieve_schema(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve relevant schema information."""
    # Use existing retrieval logic
    schema_results = await schema_retriever.retrieve(state["user_query"])
    
    return {
        "retrieved_schema": schema_results,
        "relevant_tables": [s["table_name"] for s in schema_results],
        "thoughts": [f"Retrieved schema for {len(schema_results)} tables"],
        "actions_taken": ["retrieve_schema"]
    }

async def generate_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate SQL query based on intent and schema."""
    # Use existing SQL generation logic
    sql_result = await sql_generator.generate(
        query=state["user_query"],
        schema=state["retrieved_schema"],
        intent=state["intent"]
    )
    
    return {
        "generated_sql": sql_result.sql,
        "sql_explanation": sql_result.explanation,
        "thoughts": [f"Generated SQL: {sql_result.sql[:50]}..."],
        "actions_taken": ["generate_sql"]
    }

async def execute_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Execute the generated SQL query."""
    try:
        results = await executor.execute(state["generated_sql"])
        return {
            "execution_results": results,
            "thoughts": [f"Query executed successfully, returned {len(results)} rows"],
            "actions_taken": ["execute_sql"]
        }
    except Exception as e:
        return {
            "execution_error": str(e),
            "needs_refinement": True,
            "thoughts": [f"Query failed: {str(e)}"],
            "actions_taken": ["execute_sql"]
        }

async def reflect_and_improve(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Reflect on results and determine if refinement is needed."""
    
    # Analyze execution results or errors
    if state.get("execution_error"):
        # Use LLM to analyze error and suggest fixes
        analysis = await error_analyzer.analyze(
            sql=state["generated_sql"],
            error=state["execution_error"],
            schema=state["retrieved_schema"]
        )
        
        return {
            "needs_refinement": True,
            "thoughts": [f"Error analysis: {analysis.suggestion}"],
            "actions_taken": ["reflect_and_improve"]
        }
    
    elif state.get("execution_results"):
        # Check if results are meaningful
        results = state["execution_results"]
        if not results or len(results) == 0:
            return {
                "needs_refinement": True,
                "thoughts": ["Query returned no results, may need refinement"],
                "actions_taken": ["reflect_and_improve"]
            }
    
    return {
        "needs_refinement": False,
        "thoughts": ["Query executed successfully with meaningful results"],
        "actions_taken": ["reflect_and_improve"]
    }
```

#### 1.4 Create Graph Builder
```python
# src/sens/agents/langgraph/graph.py
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from .state import SensAgentState
from .nodes import (
    analyze_intent,
    retrieve_schema,
    generate_sql,
    execute_sql,
    reflect_and_improve,
    finalize_response
)

def create_sens_agent_graph():
    """Create the SENS agent workflow graph."""
    
    # Create graph
    workflow = StateGraph(SensAgentState)
    
    # Add nodes
    workflow.add_node("analyze_intent", analyze_intent)
    workflow.add_node("retrieve_schema", retrieve_schema)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("reflect_and_improve", reflect_and_improve)
    workflow.add_node("finalize_response", finalize_response)
    
    # Define workflow edges
    workflow.set_entry_point("analyze_intent")
    workflow.add_edge("analyze_intent", "retrieve_schema")
    workflow.add_edge("retrieve_schema", "generate_sql")
    workflow.add_edge("generate_sql", "execute_sql")
    workflow.add_edge("execute_sql", "reflect_and_improve")
    
    # Conditional routing based on reflection
    workflow.add_conditional_edges(
        "reflect_and_improve",
        should_continue_iteration,
        {
            "continue": "generate_sql",  # Try again
            "finalize": "finalize_response"  # We're done
        }
    )
    
    workflow.add_edge("finalize_response", END)
    
    return workflow.compile()

def should_continue_iteration(state: SensAgentState) -> str:
    """Determine if we should continue iterating or finalize."""
    
    if state["needs_refinement"] and state["iteration_count"] < state["max_iterations"]:
        return "continue"
    else:
        return "finalize"
```

### Phase 2: Advanced Patterns (Weeks 3-4)
**Goal**: Implement advanced LangGraph patterns for improved functionality

#### 2.1 Parallel Schema Retrieval
```python
async def dispatch_schema_retrieval(state: SensAgentState) -> List[Send]:
    """Dispatch parallel schema retrieval tasks."""
    
    # Break down retrieval into parallel tasks
    tasks = [
        Send("retrieve_tables", {"query": state["user_query"], "focus": "tables"}),
        Send("retrieve_columns", {"query": state["user_query"], "focus": "columns"}),
        Send("retrieve_relationships", {"query": state["user_query"], "focus": "relationships"})
    ]
    
    return tasks
```

#### 2.2 Reflection Loop Pattern
```python
async def analyze_query_gaps(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze current query results for gaps and improvements."""
    
    # Use structured output for gap analysis
    gap_analysis = await gap_analyzer.analyze(
        query=state["user_query"],
        current_sql=state["generated_sql"],
        results=state["execution_results"],
        schema=state["retrieved_schema"]
    )
    
    return {
        "needs_refinement": gap_analysis.has_gaps,
        "refinement_suggestions": gap_analysis.suggestions,
        "thoughts": [f"Gap analysis: {gap_analysis.summary}"],
        "actions_taken": ["analyze_query_gaps"]
    }
```

#### 2.3 Structured Output Integration
```python
from pydantic import BaseModel, Field
from typing import List, Optional

class SQLGenerationResult(BaseModel):
    """Structured output for SQL generation."""
    
    sql: str = Field(description="The generated SQL query")
    explanation: str = Field(description="Explanation of the query logic")
    confidence: float = Field(description="Confidence score 0-1")
    assumptions: List[str] = Field(description="Assumptions made during generation")
    potential_issues: List[str] = Field(description="Potential issues with the query")

class GapAnalysis(BaseModel):
    """Structured output for gap analysis."""
    
    has_gaps: bool = Field(description="Whether gaps were identified")
    gap_types: List[str] = Field(description="Types of gaps found")
    suggestions: List[str] = Field(description="Specific improvement suggestions")
    summary: str = Field(description="Summary of the analysis")
```

### Phase 3: Integration & Migration (Weeks 5-6)
**Goal**: Integrate LangGraph implementation with existing API and UI

#### 3.1 API Integration
```python
# src/sens/api/routers/langgraph_agent.py
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from ..dependencies import get_settings
from ...agents.langgraph.graph import create_sens_agent_graph
from ...agents.langgraph.state import SensAgentState

router = APIRouter(prefix="/api/langgraph", tags=["langgraph-agent"])

@router.post("/query/stream")
async def stream_agent_query(
    query: str,
    settings: Settings = Depends(get_settings)
):
    """Stream agent execution with real-time updates."""
    
    # Create graph
    graph = create_sens_agent_graph()
    
    # Initial state
    initial_state = SensAgentState(
        messages=[],
        user_query=query,
        iteration_count=0,
        max_iterations=3,
        needs_refinement=False
    )
    
    # Stream execution
    async def generate_events():
        async for event in graph.astream(initial_state):
            yield f"data: {json.dumps(event)}\n\n"
    
    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
```

#### 3.2 Frontend Integration
```typescript
// web/hooks/useLangGraphAgent.ts
import { useEffect, useState } from 'react';

interface LangGraphEvent {
  node: string;
  state: any;
  timestamp: string;
}

export function useLangGraphAgent() {
  const [events, setEvents] = useState<LangGraphEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  
  const startQuery = async (query: string) => {
    const eventSource = new EventSource(
      `/api/langgraph/query/stream?query=${encodeURIComponent(query)}`
    );
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setEvents(prev => [...prev, data]);
    };
    
    eventSource.onopen = () => setIsConnected(true);
    eventSource.onerror = () => setIsConnected(false);
    
    return eventSource;
  };
  
  return { events, isConnected, startQuery };
}
```

### Phase 4: Advanced Features (Weeks 7-8)
**Goal**: Add advanced LangGraph features for production readiness

#### 4.1 Checkpointing & Persistence
```python
from langgraph.checkpoint.postgres import PostgresCheckpointer

# Add to graph creation
checkpointer = PostgresCheckpointer.from_conn_string(settings.db_url)
graph = workflow.compile(checkpointer=checkpointer)
```

#### 4.2 Human-in-the-Loop
```python
async def request_human_feedback(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Request human feedback for ambiguous queries."""
    
    if state.get("needs_clarification"):
        # Pause execution and request human input
        return {
            "awaiting_human_input": True,
            "clarification_request": state["clarification_needed"],
            "thoughts": ["Requesting human clarification"],
            "actions_taken": ["request_human_feedback"]
        }
    
    return {"awaiting_human_input": False}
```

#### 4.3 LangSmith Integration
```python
import os
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "sens-agent"
os.environ["LANGCHAIN_API_KEY"] = settings.langsmith_api_key
```

## Migration Strategy

### Backwards Compatibility
1. **Dual Implementation**: Run both old and new systems in parallel
2. **Feature Flags**: Toggle between implementations per user/query
3. **Gradual Migration**: Move complex queries to LangGraph first
4. **Fallback Mechanism**: Automatic fallback to old system if LangGraph fails

### Testing Strategy
1. **Unit Tests**: Test each node function independently
2. **Integration Tests**: Test complete graph execution
3. **Performance Tests**: Compare execution times
4. **A/B Testing**: Compare user satisfaction metrics

### Monitoring & Observability
1. **LangSmith Traces**: Automatic execution tracing
2. **Custom Metrics**: Track success rates, execution times
3. **Error Tracking**: Enhanced error visibility
4. **Performance Dashboards**: Real-time monitoring

## Expected Benefits

### Immediate Benefits (Phase 1)
- **Visual Debugging**: Clear workflow visualization
- **Structured State**: Reliable state management
- **Error Traceability**: Better error tracking

### Medium-term Benefits (Phase 2-3)
- **Parallel Processing**: Faster query execution
- **Iterative Improvement**: Self-correcting queries
- **Better User Experience**: Real-time progress updates

### Long-term Benefits (Phase 4)
- **Production Reliability**: Checkpointing and recovery
- **Human Oversight**: Guided query refinement
- **Continuous Learning**: Pattern recognition and improvement

## Implementation Timeline

```
Week 1-2: Foundation
├── LangGraph setup
├── State schema design
├── Basic node implementation
└── Simple graph workflow

Week 3-4: Advanced Patterns
├── Parallel processing
├── Reflection loops
├── Structured outputs
└── Complex routing

Week 5-6: Integration
├── API integration
├── Frontend updates
├── Backward compatibility
└── Testing framework

Week 7-8: Production Features
├── Checkpointing
├── Human-in-the-loop
├── Monitoring setup
└── Performance optimization
```

## Risk Mitigation

### Technical Risks
1. **Performance Impact**: Monitor execution times closely
2. **Complexity Increase**: Maintain clear documentation
3. **Dependency Management**: Pin LangGraph versions

### Business Risks
1. **User Experience**: Maintain seamless transition
2. **Feature Regression**: Comprehensive testing
3. **Development Velocity**: Parallel development tracks

## Success Metrics

### Technical Metrics
- **Query Success Rate**: Target 95%+ (vs current baseline)
- **Error Recovery**: 80% automatic recovery
- **Execution Time**: No regression in P95 latency
- **Memory Usage**: Monitor resource consumption

### User Experience Metrics
- **User Satisfaction**: Net Promoter Score improvement
- **Query Completion Rate**: Reduction in abandoned queries
- **Support Tickets**: Reduction in query-related issues

## Conclusion

Adopting LangGraph patterns will significantly improve our agent architecture's reliability, maintainability, and user experience. The phased approach ensures minimal disruption while maximizing benefits. The investment in modern agent orchestration patterns will position SENS as a leader in intelligent SQL generation systems.

The key to success is maintaining our domain expertise while adopting proven patterns from the LangGraph ecosystem. This balanced approach ensures we get the best of both worlds: cutting-edge agent architecture and domain-specific intelligence.