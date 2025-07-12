"""
Enhanced Agent Stream with Memory Integration
Provides real-time agent processing with memory learning and recall
"""

import asyncio
import json
import uuid
from typing import Any, AsyncGenerator, Dict, Optional

import structlog
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from sens.agents.event_emitter import EventEmittingAgent
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tool_registry import EvaluationContext, tool_registry
from sens.memory import AgentMemory, AgentMemoryTools

log = structlog.get_logger()

router = APIRouter(prefix="/nl2sql/agent/memory", tags=["agent-memory-stream"])


class MemoryEnabledQueryRequest(BaseModel):
    question: str
    max_iterations: int = 10
    session_id: Optional[str] = None
    memory_enabled: bool = True
    evaluation_context: Optional[str] = None
    database_path: Optional[str] = None
    memory_learning: bool = True  # Whether to learn from this query
    memory_recall: bool = True  # Whether to recall previous knowledge


async def generate_memory_enhanced_stream(
    query: str,
    max_iterations: int = 10,
    session_id: str = None,
    memory_enabled: bool = True,
    evaluation_context: Optional[str] = None,
    database_path: Optional[str] = None,
    memory_learning: bool = True,
    memory_recall: bool = True,
) -> AsyncGenerator[str, None]:
    """Generate agent stream with memory integration"""

    # Generate transaction ID
    tx_id = uuid.uuid4().hex
    if not session_id:
        session_id = f"session_{tx_id}"

    yield f"event: start\ndata: {json.dumps({'transaction_id': tx_id, 'session_id': session_id})}\n\n"

    try:
        # Initialize memory system
        memory = None
        memory_tools = None

        if memory_enabled:
            memory = AgentMemory(db_path=f"session_memory_{session_id}.db")
            memory_tools = AgentMemoryTools(memory)

            yield f"event: memory_initialized\ndata: {json.dumps({'session_id': session_id, 'memory_enabled': True})}\n\n"

            # Get memory stats before query
            stats_result = await memory_tools.get_memory_stats()
            if stats_result.success:
                yield f"event: memory_stats_before\ndata: {json.dumps(stats_result.data)}\n\n"

        # Initialize context-aware tools
        tools = None
        if evaluation_context and database_path:
            try:
                eval_ctx = EvaluationContext(evaluation_context)
                tool_config = tool_registry.get_tools_for_context(
                    eval_ctx, db_path=database_path
                )
                tools = tool_config["tools"]

                yield f"event: tools_initialized\ndata: {json.dumps({'context': evaluation_context, 'database_type': tool_config['database_type']})}\n\n"
            except Exception as e:
                log.warning("context_tools_failed", error=str(e))
                # Fall back to default tools
                from sens.agents.tools import AgentTools

                tools = AgentTools()
        else:
            from sens.agents.tools import AgentTools

            tools = AgentTools()

        # Integrate memory tools if enabled
        if memory_tools:
            tools.remember_concept = memory_tools.remember_concept
            tools.remember_pattern = memory_tools.remember_pattern
            tools.remember_mapping = memory_tools.remember_mapping
            tools.remember_error_fix = memory_tools.remember_error_fix
            tools.recall_knowledge = memory_tools.recall_knowledge
            tools.connect_memories = memory_tools.connect_memories
            tools.reflect_on_memory = memory_tools.reflect_on_memory
            tools.forget_memory = memory_tools.forget_memory
            tools.consolidate_memories = memory_tools.consolidate_memories
            tools.get_memory_stats = memory_tools.get_memory_stats

            yield f"event: memory_tools_integrated\ndata: {json.dumps({'tool_count': 10})}\n\n"

        # Memory recall phase
        relevant_memories = []
        if memory_enabled and memory_recall:
            yield f"event: memory_recall_start\ndata: {json.dumps({'query': query})}\n\n"

            recall_result = await memory_tools.recall_knowledge(
                query=query,
                context={
                    "evaluation_context": evaluation_context,
                    "database": database_path,
                },
                limit=5,
            )

            if recall_result.success and recall_result.data["memories"]:
                relevant_memories = recall_result.data["memories"]
                yield f"event: memory_recalled\ndata: {json.dumps({'count': len(relevant_memories), 'memories': relevant_memories})}\n\n"

                # Mark recalled memories as used
                for memory in relevant_memories:
                    await memory_tools.mark_memory_used(memory["id"], success=True)
            else:
                yield f"event: memory_recall_empty\ndata: {json.dumps({'message': 'No relevant memories found'})}\n\n"

        # Initialize reasoning engine and agent
        reasoning_engine = ReasoningEngine()
        agent = EventEmittingAgent(
            tools=tools,
            memory=memory,
            reasoning_engine=reasoning_engine,
            max_iterations=max_iterations,
        )

        # Enhance query with memory context
        enhanced_query = query
        if relevant_memories:
            memory_context = []
            for mem in relevant_memories:
                memory_context.append(
                    f"[{mem['type'].upper()}] {mem['name']}: {json.dumps(mem['content'])}"
                )

            enhanced_query = f"""
RELEVANT MEMORIES:
{chr(10).join(memory_context)}

USER QUESTION: {query}
"""

            yield f"event: query_enhanced\ndata: {json.dumps({'enhanced': True, 'memory_count': len(relevant_memories)})}\n\n"

        # Process query with agent
        result = {"success": False, "error": None, "iterations": 0}

        # Event handler for streaming
        async def handle_agent_event(event: Dict):
            event_type = event.get("type", "unknown")
            event_data = event.get("data", {})

            # Stream agent events
            yield f"event: agent_{event_type}\ndata: {json.dumps(event_data)}\n\n"

            # Handle memory learning events
            if event_type == "action_success" and memory_learning:
                action_type = event_data.get("action_type")
                if action_type == "execute_sql":
                    # Learn from successful SQL execution
                    await _learn_from_sql_success(
                        memory_tools, query, event_data, evaluation_context
                    )
                elif action_type == "generate_sql":
                    # Learn from successful SQL generation
                    await _learn_from_sql_generation(
                        memory_tools, query, event_data, evaluation_context
                    )

        # Add event handler
        agent.add_event_handler(handle_agent_event)

        # Process the query
        try:
            result = await agent.process_query(
                user_query=enhanced_query,
                conversation_id=session_id,
            )

            yield f"event: agent_complete\ndata: {json.dumps({'success': result.get('success', False), 'iterations': result.get('iterations', 0)})}\n\n"

        except Exception as e:
            log.error("agent_processing_failed", error=str(e), session_id=session_id)
            result = {"success": False, "error": str(e), "iterations": 0}
            yield f"event: agent_error\ndata: {json.dumps({'error': str(e)})}\n\n"

        # Post-processing memory learning
        if memory_enabled and memory_learning and result.get("success"):
            await _post_process_memory_learning(
                memory_tools, query, result, evaluation_context
            )
            yield f"event: memory_learning_complete\ndata: {json.dumps({'learned': True})}\n\n"

        # Final memory stats
        if memory_enabled:
            final_stats = await memory_tools.get_memory_stats()
            if final_stats.success:
                yield f"event: memory_stats_after\ndata: {json.dumps(final_stats.data)}\n\n"

        # Final result
        yield f"event: complete\ndata: {json.dumps(result)}\n\n"

    except Exception as e:
        log.error("stream_generation_failed", error=str(e), session_id=session_id)
        yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"

    finally:
        # Cleanup
        if memory:
            memory.close()
        yield f"event: end\ndata: {tx_id}\n\n"


async def _learn_from_sql_success(memory_tools, query, event_data, evaluation_context):
    """Learn from successful SQL execution"""
    try:
        sql = event_data.get("sql", "")
        result = event_data.get("result", {})

        if sql and result.get("success"):
            # Extract table names from SQL (simple heuristic)
            tables_used = []
            sql_lower = sql.lower()
            if "from" in sql_lower:
                # Simple table extraction
                parts = sql_lower.split("from")[1].split("where")[0].split("join")[0]
                tables_used = [t.strip() for t in parts.split(",") if t.strip()]

            # Remember the successful pattern
            await memory_tools.remember_pattern(
                name=f"sql_pattern_{hash(query)}",
                trigger_phrase=query,
                sql_template=sql,
                tables_used=tables_used,
                success_context={
                    "row_count": result.get("row_count", 0),
                    "execution_time": result.get("execution_time", 0),
                    "evaluation_context": evaluation_context,
                },
            )

    except Exception as e:
        log.warning("memory_learning_failed", error=str(e))


async def _learn_from_sql_generation(
    memory_tools, query, event_data, evaluation_context
):
    """Learn from successful SQL generation"""
    try:
        sql = event_data.get("sql", "")
        confidence = event_data.get("confidence", 1.0)

        if sql:
            # Remember the generation pattern
            await memory_tools.remember_concept(
                name=f"sql_concept_{hash(query)}",
                description=f"SQL concept for: {query}",
                business_terms=query.lower().split(),
                database_mapping={"sql_pattern": sql},
                context={
                    "evaluation_context": evaluation_context,
                    "confidence": confidence,
                },
            )

    except Exception as e:
        log.warning("concept_learning_failed", error=str(e))


async def _post_process_memory_learning(
    memory_tools, query, result, evaluation_context
):
    """Post-process memory learning after successful query"""
    try:
        # Create connections between related memories
        recent_memories = await memory_tools.recall_knowledge(query, limit=2)

        if recent_memories.success and len(recent_memories.data["memories"]) >= 2:
            memories = recent_memories.data["memories"]

            # Connect pattern to concept if both exist
            pattern_memory = None
            concept_memory = None

            for mem in memories:
                if mem["type"] == "pattern":
                    pattern_memory = mem
                elif mem["type"] == "concept":
                    concept_memory = mem

            if pattern_memory and concept_memory:
                await memory_tools.connect_memories(
                    from_memory_id=pattern_memory["id"],
                    to_memory_id=concept_memory["id"],
                    relationship_type="implements",
                    strength=0.8,
                    reason="Pattern implements concept from successful query",
                )

    except Exception as e:
        log.warning("post_process_learning_failed", error=str(e))


@router.post("/stream")
async def stream_memory_enhanced_query(request: MemoryEnabledQueryRequest):
    """Stream agent processing with memory integration"""

    return StreamingResponse(
        generate_memory_enhanced_stream(
            query=request.question,
            max_iterations=request.max_iterations,
            session_id=request.session_id,
            memory_enabled=request.memory_enabled,
            evaluation_context=request.evaluation_context,
            database_path=request.database_path,
            memory_learning=request.memory_learning,
            memory_recall=request.memory_recall,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@router.get("/sessions")
async def list_active_sessions():
    """List all active memory sessions"""
    import glob
    import os

    session_files = glob.glob("session_memory_*.db")
    sessions = []

    for file in session_files:
        session_id = file.replace("session_memory_", "").replace(".db", "")

        try:
            memory = AgentMemory(db_path=file)
            tools = AgentMemoryTools(memory)
            stats = await tools.get_memory_stats()

            sessions.append(
                {
                    "session_id": session_id,
                    "database_file": file,
                    "stats": stats.data if stats.success else None,
                    "file_size": os.path.getsize(file),
                }
            )

            memory.close()

        except Exception as e:
            log.warning("session_stats_failed", session_id=session_id, error=str(e))

    return {
        "status": "success",
        "data": {"active_sessions": len(sessions), "sessions": sessions},
    }
