# LangGraph Implementation Guide - Phase 1

## Overview
This guide provides step-by-step instructions for implementing the LangGraph refactoring, starting with Phase 1 (Foundation). Follow these instructions to begin modernizing your agent architecture.

## Prerequisites

### 1. Install Dependencies
```bash
cd /workspace
poetry add langgraph langchain-core langchain-google-genai langchain-openai
```

### 2. Environment Setup
Add these to your `.env` file:
```bash
# LangGraph Configuration
LANGGRAPH_ENABLE=true
LANGSMITH_API_KEY=your_langsmith_key_here
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sens-agent
```

## Phase 1: Foundation Implementation

### Step 1: Create LangGraph State Schema

Create the central state definition that will manage all agent data:

```python
# src/sens/agents/langgraph/__init__.py
"""LangGraph integration for SENS agents."""

from .state import SensAgentState
from .nodes import *
from .graph import create_sens_agent_graph

__all__ = [
    "SensAgentState",
    "create_sens_agent_graph",
]
```

```python
# src/sens/agents/langgraph/state.py
"""State management for LangGraph SENS agents."""

from typing import TypedDict, Annotated, List, Optional, Dict, Any
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
import operator


class SensAgentState(TypedDict):
    """Central state for SENS agent workflow."""
    
    # Message history (compatible with existing chat system)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Query processing
    user_query: str
    intent: Optional[str]
    query_context: Optional[Dict[str, Any]]
    
    # Schema retrieval (accumulates results from parallel searches)
    retrieved_schema: Annotated[List[Dict], operator.add]
    relevant_tables: Annotated[List[str], operator.add]
    relevant_columns: Annotated[List[Dict], operator.add]
    table_relationships: Annotated[List[Dict], operator.add]
    
    # SQL generation
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    sql_confidence: float
    sql_assumptions: Annotated[List[str], operator.add]
    
    # Execution results
    execution_results: Optional[Any]
    execution_error: Optional[str]
    execution_metadata: Optional[Dict[str, Any]]
    
    # Agent reasoning (for transparency)
    thoughts: Annotated[List[str], operator.add]
    actions_taken: Annotated[List[str], operator.add]
    observations: Annotated[List[str], operator.add]
    
    # Iteration control
    iteration_count: int
    max_iterations: int
    needs_refinement: bool
    refinement_reason: Optional[str]
    
    # Memory and learning
    discovered_mappings: Annotated[List[Dict], operator.add]
    success_patterns: Annotated[List[Dict], operator.add]
    
    # Configuration
    model_config: Optional[Dict[str, Any]]
    retrieval_config: Optional[Dict[str, Any]]
    
    # Status tracking
    current_node: Optional[str]
    start_time: Optional[float]
    end_time: Optional[float]
```

### Step 2: Create Node Functions

Implement the core workflow nodes:

```python
# src/sens/agents/langgraph/nodes.py
"""Node implementations for LangGraph SENS agent."""

import asyncio
import time
from typing import Dict, Any, List
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import HumanMessage, AIMessage

from .state import SensAgentState
from ..base import ActionType
from ...llm.intent_extractor import IntentExtractor
from ...retrieval.hybrid_retriever import HybridRetriever
from ...generation.openrouter_generator import OpenRouterGenerator
from ...execution.executor import SQLExecutor
from ...validation.sql_validator import SQLValidator
from ...common.errors import SensError

import structlog
log = structlog.get_logger()


async def analyze_intent(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze user intent and extract query requirements."""
    
    start_time = time.time()
    log.info("langgraph_node_start", node="analyze_intent", query=state["user_query"])
    
    try:
        # Use existing intent extraction logic
        intent_extractor = IntentExtractor()
        intent_result = await intent_extractor.extract_intent(state["user_query"])
        
        return {
            "intent": intent_result.intent,
            "query_context": intent_result.context,
            "thoughts": [f"Identified intent: {intent_result.intent}"],
            "actions_taken": ["analyze_intent"],
            "observations": [f"Intent extracted with confidence: {intent_result.confidence}"],
            "current_node": "analyze_intent"
        }
    except Exception as e:
        log.error("langgraph_node_error", node="analyze_intent", error=str(e))
        return {
            "thoughts": [f"Intent analysis failed: {str(e)}"],
            "actions_taken": ["analyze_intent"],
            "observations": [f"Error in intent analysis: {str(e)}"],
            "current_node": "analyze_intent"
        }


async def retrieve_schema(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve relevant schema information using existing retrieval system."""
    
    log.info("langgraph_node_start", node="retrieve_schema", intent=state.get("intent"))
    
    try:
        # Use existing hybrid retriever
        retriever = HybridRetriever()
        
        # Retrieve schema based on query and intent
        schema_results = await retriever.retrieve_relevant_schema(
            query=state["user_query"],
            intent=state.get("intent"),
            top_k=10
        )
        
        # Extract different types of schema information
        tables = []
        columns = []
        relationships = []
        
        for result in schema_results:
            if result.get("type") == "table":
                tables.append(result["name"])
            elif result.get("type") == "column":
                columns.append(result)
            elif result.get("type") == "relationship":
                relationships.append(result)
        
        return {
            "retrieved_schema": schema_results,
            "relevant_tables": tables,
            "relevant_columns": columns,
            "table_relationships": relationships,
            "thoughts": [f"Retrieved schema for {len(schema_results)} elements"],
            "actions_taken": ["retrieve_schema"],
            "observations": [f"Found {len(tables)} tables, {len(columns)} columns"],
            "current_node": "retrieve_schema"
        }
    except Exception as e:
        log.error("langgraph_node_error", node="retrieve_schema", error=str(e))
        return {
            "thoughts": [f"Schema retrieval failed: {str(e)}"],
            "actions_taken": ["retrieve_schema"],
            "observations": [f"Error in schema retrieval: {str(e)}"],
            "current_node": "retrieve_schema"
        }


async def generate_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate SQL query based on intent and schema using existing generator."""
    
    log.info("langgraph_node_start", node="generate_sql", 
             tables=len(state.get("relevant_tables", [])))
    
    try:
        # Use existing SQL generator
        generator = OpenRouterGenerator()
        
        # Prepare context for SQL generation
        context = {
            "query": state["user_query"],
            "intent": state.get("intent"),
            "schema": state.get("retrieved_schema", []),
            "tables": state.get("relevant_tables", []),
            "columns": state.get("relevant_columns", []),
            "relationships": state.get("table_relationships", [])
        }
        
        # Generate SQL
        sql_result = await generator.generate_sql(context)
        
        return {
            "generated_sql": sql_result.sql,
            "sql_explanation": sql_result.explanation,
            "sql_confidence": sql_result.confidence,
            "sql_assumptions": sql_result.assumptions if hasattr(sql_result, 'assumptions') else [],
            "thoughts": [f"Generated SQL: {sql_result.sql[:100]}..."],
            "actions_taken": ["generate_sql"],
            "observations": [f"SQL generated with confidence: {sql_result.confidence}"],
            "current_node": "generate_sql"
        }
    except Exception as e:
        log.error("langgraph_node_error", node="generate_sql", error=str(e))
        return {
            "thoughts": [f"SQL generation failed: {str(e)}"],
            "actions_taken": ["generate_sql"],
            "observations": [f"Error in SQL generation: {str(e)}"],
            "current_node": "generate_sql"
        }


async def validate_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Validate the generated SQL before execution."""
    
    log.info("langgraph_node_start", node="validate_sql")
    
    try:
        # Use existing SQL validator
        validator = SQLValidator()
        
        validation_result = await validator.validate(
            sql=state["generated_sql"],
            schema=state.get("retrieved_schema", [])
        )
        
        if validation_result.is_valid:
            return {
                "thoughts": ["SQL validation passed"],
                "actions_taken": ["validate_sql"],
                "observations": [f"SQL is valid: {validation_result.message}"],
                "current_node": "validate_sql"
            }
        else:
            return {
                "needs_refinement": True,
                "refinement_reason": f"SQL validation failed: {validation_result.message}",
                "thoughts": [f"SQL validation failed: {validation_result.message}"],
                "actions_taken": ["validate_sql"],
                "observations": [f"SQL validation errors: {validation_result.errors}"],
                "current_node": "validate_sql"
            }
    except Exception as e:
        log.error("langgraph_node_error", node="validate_sql", error=str(e))
        return {
            "needs_refinement": True,
            "refinement_reason": f"SQL validation error: {str(e)}",
            "thoughts": [f"SQL validation error: {str(e)}"],
            "actions_taken": ["validate_sql"],
            "observations": [f"Error in SQL validation: {str(e)}"],
            "current_node": "validate_sql"
        }


async def execute_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Execute the generated SQL query using existing executor."""
    
    log.info("langgraph_node_start", node="execute_sql", sql=state["generated_sql"][:100])
    
    try:
        # Use existing SQL executor
        executor = SQLExecutor()
        
        # Execute SQL
        execution_result = await executor.execute(
            sql=state["generated_sql"],
            limit=1000  # Safety limit
        )
        
        return {
            "execution_results": execution_result.data,
            "execution_metadata": {
                "row_count": len(execution_result.data) if execution_result.data else 0,
                "columns": execution_result.columns if hasattr(execution_result, 'columns') else [],
                "execution_time": execution_result.execution_time if hasattr(execution_result, 'execution_time') else None
            },
            "thoughts": [f"Query executed successfully, returned {len(execution_result.data) if execution_result.data else 0} rows"],
            "actions_taken": ["execute_sql"],
            "observations": [f"SQL execution completed successfully"],
            "current_node": "execute_sql"
        }
    except Exception as e:
        log.error("langgraph_node_error", node="execute_sql", error=str(e))
        return {
            "execution_error": str(e),
            "needs_refinement": True,
            "refinement_reason": f"SQL execution failed: {str(e)}",
            "thoughts": [f"Query failed: {str(e)}"],
            "actions_taken": ["execute_sql"],
            "observations": [f"SQL execution error: {str(e)}"],
            "current_node": "execute_sql"
        }


async def reflect_and_improve(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Reflect on results and determine if refinement is needed."""
    
    log.info("langgraph_node_start", node="reflect_and_improve", 
             has_error=bool(state.get("execution_error")))
    
    try:
        # Check for execution errors
        if state.get("execution_error"):
            return {
                "needs_refinement": True,
                "refinement_reason": f"Execution error: {state['execution_error']}",
                "thoughts": [f"Execution failed, needs refinement: {state['execution_error']}"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Identified execution error, refinement needed"],
                "current_node": "reflect_and_improve"
            }
        
        # Check for empty results
        results = state.get("execution_results")
        if not results or len(results) == 0:
            return {
                "needs_refinement": True,
                "refinement_reason": "Query returned no results",
                "thoughts": ["Query returned no results, may need refinement"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Empty result set detected"],
                "current_node": "reflect_and_improve"
            }
        
        # Check iteration count
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        
        if iteration_count >= max_iterations:
            return {
                "needs_refinement": False,
                "thoughts": [f"Maximum iterations ({max_iterations}) reached, finalizing"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Maximum iterations reached"],
                "current_node": "reflect_and_improve"
            }
        
        # Results look good
        return {
            "needs_refinement": False,
            "thoughts": ["Query executed successfully with meaningful results"],
            "actions_taken": ["reflect_and_improve"],
            "observations": [f"Successful execution with {len(results)} results"],
            "current_node": "reflect_and_improve"
        }
    
    except Exception as e:
        log.error("langgraph_node_error", node="reflect_and_improve", error=str(e))
        return {
            "needs_refinement": False,  # Stop on reflection error
            "thoughts": [f"Reflection error: {str(e)}"],
            "actions_taken": ["reflect_and_improve"],
            "observations": [f"Error in reflection: {str(e)}"],
            "current_node": "reflect_and_improve"
        }


async def finalize_response(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Finalize the response with results and explanations."""
    
    log.info("langgraph_node_start", node="finalize_response")
    
    try:
        # Prepare final response
        final_message = AIMessage(
            content=f"Query: {state['user_query']}\n\n"
                   f"Generated SQL:\n```sql\n{state.get('generated_sql', '')}\n```\n\n"
                   f"Explanation: {state.get('sql_explanation', '')}\n\n"
                   f"Results: {len(state.get('execution_results', []))} rows returned"
        )
        
        return {
            "messages": [final_message],
            "end_time": time.time(),
            "thoughts": ["Response finalized"],
            "actions_taken": ["finalize_response"],
            "observations": ["Final response prepared"],
            "current_node": "finalize_response"
        }
    
    except Exception as e:
        log.error("langgraph_node_error", node="finalize_response", error=str(e))
        error_message = AIMessage(
            content=f"An error occurred while processing your query: {str(e)}"
        )
        return {
            "messages": [error_message],
            "end_time": time.time(),
            "thoughts": [f"Error in finalization: {str(e)}"],
            "actions_taken": ["finalize_response"],
            "observations": ["Error response prepared"],
            "current_node": "finalize_response"
        }
```

### Step 3: Create Graph Builder

Build the workflow graph with conditional routing:

```python
# src/sens/agents/langgraph/graph.py
"""Graph builder for SENS LangGraph agent."""

from langgraph.graph import StateGraph, START, END
from langchain_core.runnables import RunnableConfig
from typing import Literal

from .state import SensAgentState
from .nodes import (
    analyze_intent,
    retrieve_schema,
    generate_sql,
    validate_sql,
    execute_sql,
    reflect_and_improve,
    finalize_response
)

import structlog
log = structlog.get_logger()


def should_continue_iteration(state: SensAgentState) -> Literal["continue", "finalize"]:
    """Determine if we should continue iterating or finalize."""
    
    # Check if refinement is needed
    if not state.get("needs_refinement", False):
        return "finalize"
    
    # Check iteration count
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if iteration_count >= max_iterations:
        log.info("langgraph_max_iterations_reached", 
                iteration_count=iteration_count, 
                max_iterations=max_iterations)
        return "finalize"
    
    log.info("langgraph_continue_iteration", 
            iteration_count=iteration_count, 
            max_iterations=max_iterations)
    return "continue"


def increment_iteration_count(state: SensAgentState) -> dict:
    """Increment iteration count when continuing."""
    return {
        "iteration_count": state.get("iteration_count", 0) + 1,
        "needs_refinement": False,  # Reset for next iteration
        "thoughts": [f"Starting iteration {state.get('iteration_count', 0) + 1}"],
        "actions_taken": ["increment_iteration_count"]
    }


def create_sens_agent_graph() -> StateGraph:
    """Create the SENS agent workflow graph."""
    
    log.info("langgraph_creating_graph")
    
    # Create graph with state schema
    workflow = StateGraph(SensAgentState)
    
    # Add all nodes
    workflow.add_node("analyze_intent", analyze_intent)
    workflow.add_node("retrieve_schema", retrieve_schema)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("validate_sql", validate_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("reflect_and_improve", reflect_and_improve)
    workflow.add_node("increment_iteration", increment_iteration_count)
    workflow.add_node("finalize_response", finalize_response)
    
    # Define the workflow
    workflow.set_entry_point("analyze_intent")
    
    # Linear flow for main processing
    workflow.add_edge("analyze_intent", "retrieve_schema")
    workflow.add_edge("retrieve_schema", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    # Conditional routing after validation
    workflow.add_conditional_edges(
        "validate_sql",
        lambda state: "execute" if not state.get("needs_refinement") else "reflect",
        {
            "execute": "execute_sql",
            "reflect": "reflect_and_improve"
        }
    )
    
    # After execution, always reflect
    workflow.add_edge("execute_sql", "reflect_and_improve")
    
    # Conditional routing based on reflection
    workflow.add_conditional_edges(
        "reflect_and_improve",
        should_continue_iteration,
        {
            "continue": "increment_iteration",
            "finalize": "finalize_response"
        }
    )
    
    # After incrementing iteration, go back to SQL generation
    workflow.add_edge("increment_iteration", "generate_sql")
    
    # Final response leads to end
    workflow.add_edge("finalize_response", END)
    
    # Compile the graph
    graph = workflow.compile()
    
    log.info("langgraph_graph_created")
    return graph
```

### Step 4: Create Configuration System

Set up configuration management following Google's pattern:

```python
# src/sens/agents/langgraph/config.py
"""Configuration management for LangGraph SENS agent."""

import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from langchain_core.runnables import RunnableConfig


class SensAgentConfig(BaseModel):
    """Configuration for SENS LangGraph agent."""
    
    # Model configuration
    intent_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for intent extraction"
    )
    
    sql_generation_model: str = Field(
        default="openai/gpt-4o",
        description="Model for SQL generation"
    )
    
    reflection_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for reflection and improvement"
    )
    
    # Execution configuration
    max_iterations: int = Field(
        default=3,
        description="Maximum number of refinement iterations"
    )
    
    result_limit: int = Field(
        default=1000,
        description="Maximum number of result rows"
    )
    
    # Retrieval configuration
    retrieval_top_k: int = Field(
        default=10,
        description="Number of schema elements to retrieve"
    )
    
    # Temperature settings
    generation_temperature: float = Field(
        default=0.1,
        description="Temperature for SQL generation"
    )
    
    reflection_temperature: float = Field(
        default=0.3,
        description="Temperature for reflection"
    )
    
    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> "SensAgentConfig":
        """Create configuration from RunnableConfig."""
        
        configurable = config.get("configurable", {}) if config else {}
        
        # Get values from environment or config
        raw_values: Dict[str, Any] = {}
        
        for field_name in cls.model_fields.keys():
            # Check config first, then environment
            value = configurable.get(field_name)
            if value is None:
                env_var = field_name.upper()
                value = os.environ.get(env_var)
            
            if value is not None:
                raw_values[field_name] = value
        
        return cls(**raw_values)
```

### Step 5: Create API Integration

Add LangGraph endpoint to your existing API:

```python
# src/sens/api/routers/langgraph_agent.py
"""LangGraph agent API router."""

import json
import asyncio
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from ...agents.langgraph.graph import create_sens_agent_graph
from ...agents.langgraph.state import SensAgentState
from ...agents.langgraph.config import SensAgentConfig
from ...settings import get_settings
from ..models.query_models import QueryRequest, QueryResponse

import structlog
log = structlog.get_logger()

router = APIRouter(prefix="/api/langgraph", tags=["langgraph-agent"])


@router.post("/query/stream")
async def stream_langgraph_query(
    request: QueryRequest,
    settings = Depends(get_settings)
):
    """Stream LangGraph agent execution with real-time updates."""
    
    log.info("langgraph_query_start", query=request.query)
    
    try:
        # Create graph
        graph = create_sens_agent_graph()
        
        # Create configuration
        config = RunnableConfig(
            configurable={
                "max_iterations": request.max_iterations or 3,
                "result_limit": request.limit or 1000,
                "generation_temperature": 0.1,
                "reflection_temperature": 0.3
            }
        )
        
        # Initial state
        initial_state = SensAgentState(
            messages=[HumanMessage(content=request.query)],
            user_query=request.query,
            iteration_count=0,
            max_iterations=request.max_iterations or 3,
            needs_refinement=False,
            sql_confidence=0.0,
            thoughts=[],
            actions_taken=[],
            observations=[],
            retrieved_schema=[],
            relevant_tables=[],
            relevant_columns=[],
            table_relationships=[],
            sql_assumptions=[],
            discovered_mappings=[],
            success_patterns=[],
            start_time=time.time()
        )
        
        # Stream execution
        async def generate_events():
            try:
                # Send initial event
                yield f"data: {json.dumps({'type': 'started', 'message': 'Agent started'})}\n\n"
                
                # Stream graph execution
                async for event in graph.astream(initial_state, config):
                    # Process the event
                    processed_event = {
                        "type": "node_update",
                        "node": event.get("current_node", "unknown"),
                        "state": {
                            "thoughts": event.get("thoughts", []),
                            "actions_taken": event.get("actions_taken", []),
                            "observations": event.get("observations", []),
                            "iteration_count": event.get("iteration_count", 0),
                            "generated_sql": event.get("generated_sql"),
                            "sql_explanation": event.get("sql_explanation"),
                            "execution_results": event.get("execution_results"),
                            "execution_error": event.get("execution_error"),
                            "needs_refinement": event.get("needs_refinement", False)
                        }
                    }
                    
                    yield f"data: {json.dumps(processed_event)}\n\n"
                    
                    # Small delay to prevent overwhelming the client
                    await asyncio.sleep(0.1)
                
                # Send completion event
                yield f"data: {json.dumps({'type': 'completed', 'message': 'Agent completed'})}\n\n"
                
            except Exception as e:
                log.error("langgraph_stream_error", error=str(e))
                error_event = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_event)}\n\n"
        
        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        log.error("langgraph_query_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/query/sync")
async def sync_langgraph_query(
    request: QueryRequest,
    settings = Depends(get_settings)
) -> QueryResponse:
    """Execute LangGraph agent synchronously."""
    
    log.info("langgraph_sync_query_start", query=request.query)
    
    try:
        # Create graph
        graph = create_sens_agent_graph()
        
        # Create configuration
        config = RunnableConfig(
            configurable={
                "max_iterations": request.max_iterations or 3,
                "result_limit": request.limit or 1000,
            }
        )
        
        # Initial state
        initial_state = SensAgentState(
            messages=[HumanMessage(content=request.query)],
            user_query=request.query,
            iteration_count=0,
            max_iterations=request.max_iterations or 3,
            needs_refinement=False,
            sql_confidence=0.0,
            thoughts=[],
            actions_taken=[],
            observations=[],
            retrieved_schema=[],
            relevant_tables=[],
            relevant_columns=[],
            table_relationships=[],
            sql_assumptions=[],
            discovered_mappings=[],
            success_patterns=[],
            start_time=time.time()
        )
        
        # Execute graph
        result = await graph.ainvoke(initial_state, config)
        
        # Format response
        response = QueryResponse(
            query=request.query,
            sql=result.get("generated_sql"),
            explanation=result.get("sql_explanation"),
            results=result.get("execution_results"),
            error=result.get("execution_error"),
            metadata={
                "iteration_count": result.get("iteration_count", 0),
                "sql_confidence": result.get("sql_confidence", 0.0),
                "execution_time": result.get("end_time", 0) - result.get("start_time", 0),
                "thoughts": result.get("thoughts", []),
                "actions_taken": result.get("actions_taken", [])
            }
        )
        
        log.info("langgraph_sync_query_complete", 
                iterations=result.get("iteration_count", 0),
                success=not bool(result.get("execution_error")))
        
        return response
        
    except Exception as e:
        log.error("langgraph_sync_query_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))
```

### Step 6: Update Main API Router

Add the LangGraph router to your main API:

```python
# src/sens/api/app.py (or wherever you register routers)

# Add to your existing imports
from .routers.langgraph_agent import router as langgraph_router

# Add to your router registration
app.include_router(langgraph_router)
```

### Step 7: Create Basic Frontend Integration

Add a simple hook to test LangGraph integration:

```typescript
// web/hooks/useLangGraphAgent.ts
import { useState, useCallback } from 'react';

interface LangGraphEvent {
  type: 'started' | 'node_update' | 'completed' | 'error';
  node?: string;
  state?: any;
  message?: string;
}

interface LangGraphState {
  events: LangGraphEvent[];
  isConnected: boolean;
  isLoading: boolean;
  error: string | null;
}

export function useLangGraphAgent() {
  const [state, setState] = useState<LangGraphState>({
    events: [],
    isConnected: false,
    isLoading: false,
    error: null
  });

  const startQuery = useCallback(async (query: string) => {
    setState(prev => ({
      ...prev,
      isLoading: true,
      error: null,
      events: []
    }));

    try {
      const eventSource = new EventSource(
        `/api/langgraph/query/stream?query=${encodeURIComponent(query)}`
      );

      eventSource.onopen = () => {
        setState(prev => ({
          ...prev,
          isConnected: true
        }));
      };

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          setState(prev => ({
            ...prev,
            events: [...prev.events, data]
          }));

          // Close connection when completed or error
          if (data.type === 'completed' || data.type === 'error') {
            eventSource.close();
            setState(prev => ({
              ...prev,
              isConnected: false,
              isLoading: false,
              error: data.type === 'error' ? data.message : null
            }));
          }
        } catch (e) {
          console.error('Error parsing event data:', e);
        }
      };

      eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        eventSource.close();
        setState(prev => ({
          ...prev,
          isConnected: false,
          isLoading: false,
          error: 'Connection error'
        }));
      };

      return eventSource;
    } catch (error) {
      setState(prev => ({
        ...prev,
        isLoading: false,
        error: error instanceof Error ? error.message : 'Unknown error'
      }));
      return null;
    }
  }, []);

  return {
    ...state,
    startQuery
  };
}
```

## Testing the Implementation

### Step 8: Create Test Cases

```python
# tests/agents/langgraph/test_basic_flow.py
"""Basic tests for LangGraph agent flow."""

import pytest
from langchain_core.messages import HumanMessage

from src.sens.agents.langgraph.graph import create_sens_agent_graph
from src.sens.agents.langgraph.state import SensAgentState


@pytest.mark.asyncio
async def test_basic_agent_flow():
    """Test basic agent execution flow."""
    
    # Create graph
    graph = create_sens_agent_graph()
    
    # Create initial state
    initial_state = SensAgentState(
        messages=[HumanMessage(content="Show me sales data for last month")],
        user_query="Show me sales data for last month",
        iteration_count=0,
        max_iterations=3,
        needs_refinement=False,
        sql_confidence=0.0,
        thoughts=[],
        actions_taken=[],
        observations=[],
        retrieved_schema=[],
        relevant_tables=[],
        relevant_columns=[],
        table_relationships=[],
        sql_assumptions=[],
        discovered_mappings=[],
        success_patterns=[]
    )
    
    # Execute graph
    result = await graph.ainvoke(initial_state)
    
    # Verify basic flow completed
    assert "analyze_intent" in result.get("actions_taken", [])
    assert "retrieve_schema" in result.get("actions_taken", [])
    assert "generate_sql" in result.get("actions_taken", [])
    assert "finalize_response" in result.get("actions_taken", [])
    
    # Verify state has expected fields
    assert result.get("user_query") == "Show me sales data for last month"
    assert isinstance(result.get("thoughts", []), list)
    assert isinstance(result.get("actions_taken", []), list)


@pytest.mark.asyncio
async def test_agent_with_error_handling():
    """Test agent handles errors gracefully."""
    
    # Create graph
    graph = create_sens_agent_graph()
    
    # Create initial state with problematic query
    initial_state = SensAgentState(
        messages=[HumanMessage(content="")],  # Empty query
        user_query="",
        iteration_count=0,
        max_iterations=3,
        needs_refinement=False,
        sql_confidence=0.0,
        thoughts=[],
        actions_taken=[],
        observations=[],
        retrieved_schema=[],
        relevant_tables=[],
        relevant_columns=[],
        table_relationships=[],
        sql_assumptions=[],
        discovered_mappings=[],
        success_patterns=[]
    )
    
    # Execute graph
    result = await graph.ainvoke(initial_state)
    
    # Should complete even with empty query
    assert "finalize_response" in result.get("actions_taken", [])
    assert isinstance(result.get("thoughts", []), list)
```

### Step 9: Run Tests

```bash
# Run LangGraph tests
pytest tests/agents/langgraph/ -v

# Run specific test
pytest tests/agents/langgraph/test_basic_flow.py::test_basic_agent_flow -v
```

## Next Steps

After completing Phase 1, you'll have:

1. ✅ LangGraph foundation with state management
2. ✅ Basic node implementations using existing components
3. ✅ Graph workflow with conditional routing
4. ✅ API integration with streaming support
5. ✅ Basic frontend integration
6. ✅ Test coverage for core functionality

### Phase 2 Preparation

In Phase 2, you'll add:
- Parallel processing with `Send` objects
- Advanced reflection patterns
- Structured output with Pydantic models
- Enhanced error recovery
- Performance optimizations

### Monitoring and Debugging

Enable LangSmith for detailed tracing:

```python
# Add to your environment
LANGCHAIN_TRACING_V2=true
LANGCHAIN_PROJECT=sens-agent
LANGSMITH_API_KEY=your_key_here
```

Visit [LangSmith](https://smith.langchain.com/) to see detailed execution traces.

## Common Issues and Solutions

1. **Import Errors**: Ensure all LangGraph dependencies are installed
2. **State Type Errors**: Check that your state matches the `SensAgentState` schema
3. **Node Failures**: Add try-catch blocks and proper error handling
4. **Performance Issues**: Use async/await consistently and avoid blocking operations
5. **Memory Issues**: Monitor state size and avoid accumulating too much data

This completes Phase 1 of the LangGraph implementation. The foundation is now in place for building more advanced agent capabilities!