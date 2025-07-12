"""LangGraph agent API router."""

import json
import asyncio
import time
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse

from ...agents.langgraph.graph import create_sens_agent_graph
from ...agents.langgraph.state import SensAgentState
from ...agents.langgraph.config import SensAgentConfig
from ...settings import get_settings

# Import structlog if available, otherwise create a simple logger
try:
    import structlog
    log = structlog.get_logger()
except ImportError:
    import logging
    log = logging.getLogger(__name__)

# Fallback imports for when LangGraph dependencies are not available
try:
    from langchain_core.messages import HumanMessage
    from langchain_core.runnables import RunnableConfig
except ImportError:
    # Create fallback classes
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content
            self.type = "human"
    
    RunnableConfig = Dict[str, Any]

router = APIRouter(prefix="/api/langgraph", tags=["langgraph-agent"])


@router.post("/query/stream")
async def stream_langgraph_query(
    query: str,
    max_iterations: int = 3,
    limit: int = 1000,
    settings = Depends(get_settings)
):
    """Stream LangGraph agent execution with real-time updates."""
    
    log.info("langgraph_query_start", query=query)
    
    try:
        # Create graph
        graph = create_sens_agent_graph()
        
        # Create configuration
        config = {
            "configurable": {
                "max_iterations": max_iterations,
                "result_limit": limit,
                "generation_temperature": 0.1,
                "reflection_temperature": 0.3
            }
        }
        
        # Initial state
        initial_state = SensAgentState(
            messages=[HumanMessage(content=query)],
            user_query=query,
            iteration_count=0,
            max_iterations=max_iterations,
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
            start_time=time.time(),
            # Optional fields
            intent=None,
            query_context=None,
            generated_sql=None,
            sql_explanation=None,
            execution_results=None,
            execution_error=None,
            execution_metadata=None,
            refinement_reason=None,
            model_config=None,
            retrieval_config=None,
            current_node=None,
            end_time=None
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
    query: str,
    max_iterations: int = 3,
    limit: int = 1000,
    settings = Depends(get_settings)
):
    """Execute LangGraph agent synchronously."""
    
    log.info("langgraph_sync_query_start", query=query)
    
    try:
        # Create graph
        graph = create_sens_agent_graph()
        
        # Create configuration
        config = {
            "configurable": {
                "max_iterations": max_iterations,
                "result_limit": limit,
            }
        }
        
        # Initial state
        initial_state = SensAgentState(
            messages=[HumanMessage(content=query)],
            user_query=query,
            iteration_count=0,
            max_iterations=max_iterations,
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
            start_time=time.time(),
            # Optional fields
            intent=None,
            query_context=None,
            generated_sql=None,
            sql_explanation=None,
            execution_results=None,
            execution_error=None,
            execution_metadata=None,
            refinement_reason=None,
            model_config=None,
            retrieval_config=None,
            current_node=None,
            end_time=None
        )
        
        # Execute graph
        result = await graph.ainvoke(initial_state, config)
        
        # Format response
        response = {
            "query": query,
            "sql": result.get("generated_sql"),
            "explanation": result.get("sql_explanation"),
            "results": result.get("execution_results"),
            "error": result.get("execution_error"),
            "metadata": {
                "iteration_count": result.get("iteration_count", 0),
                "sql_confidence": result.get("sql_confidence", 0.0),
                "execution_time": result.get("end_time", 0) - result.get("start_time", 0),
                "thoughts": result.get("thoughts", []),
                "actions_taken": result.get("actions_taken", [])
            }
        }
        
        log.info("langgraph_sync_query_complete", 
                iterations=result.get("iteration_count", 0),
                success=not bool(result.get("execution_error")))
        
        return response
        
    except Exception as e:
        log.error("langgraph_sync_query_error", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint for LangGraph agent."""
    try:
        # Test graph creation
        graph = create_sens_agent_graph()
        
        return {
            "status": "healthy",
            "message": "LangGraph agent is operational",
            "langgraph_available": hasattr(graph, 'workflow') or hasattr(graph, '_graph')
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


@router.get("/graph/visualization")
async def get_graph_visualization():
    """Get a visual representation of the agent graph."""
    try:
        graph = create_sens_agent_graph()
        
        # Simple graph description
        graph_description = {
            "nodes": [
                {"id": "analyze_intent", "label": "Analyze Intent"},
                {"id": "retrieve_schema", "label": "Retrieve Schema"},
                {"id": "generate_sql", "label": "Generate SQL"},
                {"id": "validate_sql", "label": "Validate SQL"},
                {"id": "execute_sql", "label": "Execute SQL"},
                {"id": "reflect_and_improve", "label": "Reflect & Improve"},
                {"id": "increment_iteration", "label": "Increment Iteration"},
                {"id": "finalize_response", "label": "Finalize Response"}
            ],
            "edges": [
                {"from": "analyze_intent", "to": "retrieve_schema"},
                {"from": "retrieve_schema", "to": "generate_sql"},
                {"from": "generate_sql", "to": "validate_sql"},
                {"from": "validate_sql", "to": "execute_sql", "condition": "valid"},
                {"from": "validate_sql", "to": "reflect_and_improve", "condition": "invalid"},
                {"from": "execute_sql", "to": "reflect_and_improve"},
                {"from": "reflect_and_improve", "to": "increment_iteration", "condition": "needs_refinement"},
                {"from": "reflect_and_improve", "to": "finalize_response", "condition": "done"},
                {"from": "increment_iteration", "to": "generate_sql"}
            ]
        }
        
        return graph_description
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get graph visualization: {str(e)}")