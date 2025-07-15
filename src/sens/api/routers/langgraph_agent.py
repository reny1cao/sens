"""
LangGraph Agent API Router with Feature Flags and Backward Compatibility.

This router provides endpoints for the new LangGraph-based agent implementation
while maintaining backward compatibility with the existing system.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any, AsyncGenerator, Dict, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from sens.agents.langgraph_sens_agent import LangGraphSENSAgent
from sens.agents.unified import UnifiedSENSAgent
from sens.api.common.sse import create_sse_response
from sens.api.models import NL2SQLRequest, NL2SQLResponse
from sens.chat.session import SessionManager
from sens.common.errors import ValidationError
from sens.settings import get_settings

logger = structlog.get_logger(__name__)

# Router configuration
router = APIRouter(
    prefix="/langgraph",
    tags=["langgraph-agent"],
    responses={
        400: {"description": "Bad request"},
        500: {"description": "Internal server error"},
    },
)

# Global instances
_langgraph_agent: Optional[LangGraphSENSAgent] = None
_session_manager: Optional[SessionManager] = None
_settings = get_settings()


class LangGraphQueryRequest(BaseModel):
    """Request model for LangGraph agent queries."""
    question: str
    conversation_id: Optional[str] = None
    max_iterations: Optional[int] = None
    enable_streaming: bool = True
    enable_reflection: bool = True
    legacy_mode: bool = False


class LangGraphQueryResponse(BaseModel):
    """Response model for LangGraph agent queries."""
    success: bool
    sql: Optional[str] = None
    result: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None
    iterations: int
    confidence_score: float
    execution_error: Optional[str] = None
    processing_time_ms: float


async def get_langgraph_agent() -> LangGraphSENSAgent:
    """Get or create the LangGraph agent instance."""
    global _langgraph_agent, _session_manager
    
    if _langgraph_agent is None:
        # Initialize session manager
        _session_manager = SessionManager()
        
        # Initialize LangGraph agent
        _langgraph_agent = LangGraphSENSAgent(
            session_manager=_session_manager,
            max_iterations=_settings.agent_reasoning.max_iterations,
            enable_streaming=True,
            enable_reflection=True,
            legacy_mode=False,
        )
        
        logger.info("langgraph_agent_initialized")
    
    return _langgraph_agent


# Feature flag endpoints

@router.get("/features")
async def get_features():
    """Get current feature flags for LangGraph agent."""
    return {
        "langgraph_enabled": True,
        "streaming_enabled": True,
        "reflection_enabled": True,
        "legacy_fallback": True,
        "max_iterations": _settings.agent_reasoning.max_iterations,
    }


@router.post("/features")
async def update_features(features: Dict[str, Any]):
    """Update feature flags (for testing/admin purposes)."""
    # In a real implementation, this would be protected by auth
    logger.info("feature_flags_updated", features=features)
    return {"message": "Feature flags updated", "features": features}


# Query processing endpoints

@router.post("/query", response_model=LangGraphQueryResponse)
async def process_query(request: LangGraphQueryRequest):
    """Process a query using the LangGraph agent."""
    
    start_time = time.time()
    
    try:
        agent = await get_langgraph_agent()
        
        # Override agent settings if provided
        if request.max_iterations:
            agent.max_iterations = request.max_iterations
        
        if request.legacy_mode:
            agent.legacy_mode = True
        
        # Process the query
        result = await agent.process_query(
            query=request.question,
            conversation_id=request.conversation_id or "default"
        )
        
        processing_time = (time.time() - start_time) * 1000
        
        return LangGraphQueryResponse(
            success=result.get("success", False),
            sql=result.get("sql"),
            result=result.get("result"),
            answer=result.get("answer"),
            iterations=result.get("iterations", 0),
            confidence_score=result.get("confidence_score", 0.0),
            execution_error=result.get("execution_error"),
            processing_time_ms=processing_time,
        )
        
    except Exception as e:
        logger.error("langgraph_query_error", error=str(e))
        processing_time = (time.time() - start_time) * 1000
        
        return LangGraphQueryResponse(
            success=False,
            answer=f"Error processing query: {str(e)}",
            iterations=0,
            confidence_score=0.0,
            execution_error=str(e),
            processing_time_ms=processing_time,
        )


@router.post("/stream")
async def stream_query(request: LangGraphQueryRequest):
    """Stream query processing using LangGraph agent."""
    
    try:
        agent = await get_langgraph_agent()
        
        # Override agent settings if provided
        if request.max_iterations:
            agent.max_iterations = request.max_iterations
        
        if request.legacy_mode:
            agent.legacy_mode = True
        
        async def event_generator():
            """Generate SSE events from LangGraph agent."""
            
            # Start event
            yield create_sse_response(
                {
                    "type": "start",
                    "data": {
                        "question": request.question,
                        "conversation_id": request.conversation_id,
                        "max_iterations": agent.max_iterations,
                        "legacy_mode": agent.legacy_mode,
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            
            try:
                # Stream events from LangGraph agent
                async for event in agent.stream_query(
                    query=request.question,
                    conversation_id=request.conversation_id or "default"
                ):
                    yield create_sse_response(event)
                
                # End event
                yield create_sse_response(
                    {
                        "type": "complete",
                        "data": {"message": "Query processing complete"},
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
                
            except Exception as e:
                logger.error("langgraph_streaming_error", error=str(e))
                yield create_sse_response(
                    {
                        "type": "error",
                        "data": {"error": str(e)},
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        
    except Exception as e:
        logger.error("langgraph_stream_init_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to initialize streaming: {str(e)}"}
        )


# Comparison endpoints

@router.post("/compare")
async def compare_agents(request: LangGraphQueryRequest):
    """Compare LangGraph agent with legacy agent."""
    
    try:
        # Process with both agents
        start_time = time.time()
        
        # LangGraph agent
        langgraph_agent = await get_langgraph_agent()
        langgraph_result = await langgraph_agent.process_query(
            query=request.question,
            conversation_id=request.conversation_id or "default"
        )
        langgraph_time = (time.time() - start_time) * 1000
        
        # Legacy agent
        start_time = time.time()
        legacy_agent = UnifiedSENSAgent(
            max_iterations=request.max_iterations or _settings.agent_reasoning.max_iterations,
            streaming_enabled=False,
        )
        legacy_result = await legacy_agent.process_query(
            user_query=request.question,
            conversation_id=request.conversation_id or "default"
        )
        legacy_time = (time.time() - start_time) * 1000
        
        return {
            "langgraph": {
                "result": langgraph_result,
                "processing_time_ms": langgraph_time,
            },
            "legacy": {
                "result": legacy_result,
                "processing_time_ms": legacy_time,
            },
            "comparison": {
                "langgraph_faster": langgraph_time < legacy_time,
                "time_difference_ms": abs(langgraph_time - legacy_time),
                "both_successful": langgraph_result.get("success", False) and legacy_result.get("success", False),
            }
        }
        
    except Exception as e:
        logger.error("agent_comparison_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Comparison failed: {str(e)}"}
        )


# Debug and monitoring endpoints

@router.get("/status")
async def get_status():
    """Get LangGraph agent status."""
    try:
        agent = await get_langgraph_agent()
        
        return {
            "status": "healthy",
            "agent_initialized": agent is not None,
            "max_iterations": agent.max_iterations if agent else None,
            "streaming_enabled": agent.enable_streaming if agent else None,
            "reflection_enabled": agent.enable_reflection if agent else None,
            "legacy_mode": agent.legacy_mode if agent else None,
        }
        
    except Exception as e:
        logger.error("status_check_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"status": "error", "error": str(e)}
        )


@router.get("/graph")
async def get_graph_visualization():
    """Get LangGraph visualization (for debugging)."""
    try:
        agent = await get_langgraph_agent()
        
        # Get graph structure
        graph_dict = agent.graph.get_graph()
        
        return {
            "nodes": list(graph_dict.nodes.keys()),
            "edges": [
                {"from": edge[0], "to": edge[1]} 
                for edge in graph_dict.edges
            ],
            "entry_point": graph_dict.entry_point,
            "visualization_available": True,
        }
        
    except Exception as e:
        logger.error("graph_visualization_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"error": f"Graph visualization failed: {str(e)}"}
        )


# Testing endpoints

@router.post("/test")
async def test_agent(
    question: str = Query(..., description="Test question"),
    legacy_mode: bool = Query(False, description="Use legacy mode"),
    max_iterations: int = Query(5, description="Maximum iterations"),
):
    """Quick test endpoint for the LangGraph agent."""
    
    try:
        agent = await get_langgraph_agent()
        
        # Override settings for test
        agent.legacy_mode = legacy_mode
        agent.max_iterations = max_iterations
        
        result = await agent.process_query(
            query=question,
            conversation_id="test"
        )
        
        return {
            "test_successful": True,
            "question": question,
            "legacy_mode": legacy_mode,
            "max_iterations": max_iterations,
            "result": result,
        }
        
    except Exception as e:
        logger.error("agent_test_error", error=str(e))
        return JSONResponse(
            status_code=500,
            content={"test_successful": False, "error": str(e)}
        )


# Migration utilities

@router.post("/migrate")
async def migrate_to_langgraph(
    enable_gradual: bool = Query(True, description="Enable gradual migration"),
    percentage: int = Query(10, description="Percentage of traffic to migrate"),
):
    """Migrate traffic from legacy to LangGraph agent."""
    
    # This would be implemented with proper feature flags and A/B testing
    return {
        "migration_started": True,
        "gradual_migration": enable_gradual,
        "traffic_percentage": percentage,
        "message": "Migration configuration updated",
    }


@router.get("/migration/status")
async def get_migration_status():
    """Get current migration status."""
    
    # This would track actual migration metrics
    return {
        "migration_active": False,
        "traffic_percentage": 0,
        "success_rate": 0.0,
        "performance_comparison": {
            "langgraph_avg_time": 0.0,
            "legacy_avg_time": 0.0,
        },
    }


# Health check endpoint

@router.get("/health")
async def health_check():
    """Health check for LangGraph agent."""
    
    try:
        agent = await get_langgraph_agent()
        
        # Quick functionality test
        test_result = await agent.process_query("SELECT 1", "health_check")
        
        return {
            "status": "healthy",
            "agent_responsive": True,
            "test_successful": test_result.get("success", False),
            "timestamp": datetime.utcnow().isoformat(),
        }
        
    except Exception as e:
        logger.error("health_check_error", error=str(e))
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )