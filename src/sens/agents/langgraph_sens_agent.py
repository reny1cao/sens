"""
LangGraph-based SENS Agent following Google Gemini patterns.

This implementation adopts the architectural patterns from Google's Gemini LangGraph
quickstart while maintaining compatibility with our existing SSE streaming infrastructure.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Annotated, Any, AsyncGenerator, Dict, List, Optional, Union

import structlog
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict
from pydantic import BaseModel

from sens.agents.reasoning import ReasoningEngine
from sens.agents.reflection import ReflectionEngine
from sens.agents.tools import AgentTools
from sens.chat.session import SessionManager
from sens.execution.executor import SQLExecutor
from sens.generation.openrouter_generator import OpenRouterGenerator
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

log = structlog.get_logger()


class SENSAgentState(TypedDict):
    """LangGraph-compatible state for SENS agent following Google patterns."""
    
    # Core conversation (following LangGraph patterns)
    messages: Annotated[List[BaseMessage], add_messages]
    user_query: str
    conversation_id: str
    
    # Iteration control
    iteration: int
    max_iterations: int
    
    # Schema discovery
    discovered_tables: List[Dict[str, Any]]
    discovered_columns: List[Dict[str, Any]]
    schema_context: Optional[Dict[str, Any]]
    
    # SQL generation
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    
    # Execution results
    execution_result: Optional[Dict[str, Any]]
    execution_error: Optional[str]
    
    # Reflection and gaps (following Google's reflection pattern)
    is_sufficient: bool
    knowledge_gaps: List[str]
    follow_up_actions: List[str]
    confidence_score: float
    
    # Memory and learning
    discovered_mappings: Dict[str, str]
    learned_patterns: List[Dict[str, Any]]
    
    # Final output
    final_answer: Optional[str]
    natural_language_response: Optional[str]


class ReflectionResult(BaseModel):
    """Structured reflection output following Google's patterns."""
    is_sufficient: bool
    confidence_score: float
    knowledge_gaps: List[str]
    follow_up_actions: List[str]
    reasoning: str


class LangGraphSENSAgent:
    """
    LangGraph-based SENS agent following Google Gemini patterns.
    
    This implementation provides:
    - TypedDict state management with automatic propagation
    - Node-based architecture with clear separation of concerns
    - Structured reflection with knowledge gap analysis
    - Built-in streaming support via LangGraph
    - Backward compatibility with existing systems
    """
    
    def __init__(
        self,
        retriever: Optional[OptimizedSchemaRetriever] = None,
        sql_generator: Optional[OpenRouterGenerator] = None,
        sql_executor: Optional[SQLExecutor] = None,
        reasoning_engine: Optional[ReasoningEngine] = None,
        reflection_engine: Optional[ReflectionEngine] = None,
        session_manager: Optional[SessionManager] = None,
        max_iterations: int = 10,
        enable_streaming: bool = True,
        enable_reflection: bool = True,
        legacy_mode: bool = False,
    ):
        """Initialize the LangGraph SENS agent."""
        
        self.settings = get_settings()
        self.max_iterations = max_iterations
        self.enable_streaming = enable_streaming
        self.enable_reflection = enable_reflection
        self.legacy_mode = legacy_mode
        
        # Initialize core components
        self.retriever = retriever or self._create_default_retriever()
        self.sql_generator = sql_generator or OpenRouterGenerator()
        self.sql_executor = sql_executor or SQLExecutor()
        self.reasoning_engine = reasoning_engine or ReasoningEngine()
        self.reflection_engine = reflection_engine or ReflectionEngine()
        self.session_manager = session_manager
        
        # Build the LangGraph
        self.graph = self._build_graph()
        
        # Event handlers for streaming
        self.event_handlers = []
        
        log.info(
            "langgraph_sens_agent_initialized",
            max_iterations=max_iterations,
            enable_streaming=enable_streaming,
            enable_reflection=enable_reflection,
            legacy_mode=legacy_mode,
        )
    
    def _create_default_retriever(self) -> OptimizedSchemaRetriever:
        """Create default retriever if none provided."""
        from sens.caching.factory import get_cache_manager
        from sens.retrieval.embedding.search import EmbeddingSearch
        from sens.retrieval.token.builder import TokenIndexBuilder
        
        schema_graph = SchemaGraph.get_instance()
        token_index = TokenIndexBuilder().build()
        embedding_index = EmbeddingSearch()
        cache_manager = get_cache_manager()
        
        return OptimizedSchemaRetriever(
            token_index=token_index,
            embedding_index=embedding_index,
            schema_graph=schema_graph,
            cache_manager=cache_manager,
        )
    
    def _build_graph(self) -> StateGraph:
        """Build the LangGraph workflow following Google patterns."""
        
        workflow = StateGraph(SENSAgentState)
        
        # Add nodes (following Google's pattern)
        workflow.add_node("discover_schema", self._discover_schema_node)
        workflow.add_node("generate_sql", self._generate_sql_node)
        workflow.add_node("execute_sql", self._execute_sql_node)
        workflow.add_node("reflect_on_progress", self._reflect_on_progress_node)
        workflow.add_node("finalize_answer", self._finalize_answer_node)
        
        # Set entry point
        workflow.set_entry_point("discover_schema")
        
        # Add conditional edges (following Google's routing pattern)
        workflow.add_conditional_edges(
            "reflect_on_progress",
            self._should_continue_research,
            {
                "discover_schema": "discover_schema",
                "generate_sql": "generate_sql",
                "execute_sql": "execute_sql",
                "finalize_answer": "finalize_answer",
                END: END,
            },
        )
        
        # Add normal edges
        workflow.add_edge("discover_schema", "generate_sql")
        workflow.add_edge("generate_sql", "execute_sql")
        workflow.add_edge("execute_sql", "reflect_on_progress")
        workflow.add_edge("finalize_answer", END)
        
        return workflow.compile()
    
    # Node implementations following Google's patterns
    
    async def _discover_schema_node(self, state: SENSAgentState) -> Dict[str, Any]:
        """Discover relevant schema elements (following Google's node pattern)."""
        
        await self._emit_event("schema_discovery_start", {
            "iteration": state["iteration"],
            "query": state["user_query"]
        })
        
        try:
            # Use existing retrieval system
            retrieval_result = await self.retriever.retrieve(
                query=state["user_query"],
                max_tables=10,
                max_columns=20
            )
            
            # Transform to our format
            tables = [
                {
                    "name": table.name,
                    "description": table.description,
                    "columns": [col.name for col in table.columns]
                }
                for table in retrieval_result.tables
            ]
            
            columns = [
                {
                    "table": col.table,
                    "name": col.name,
                    "type": col.type,
                    "description": col.description
                }
                for col in retrieval_result.columns
            ]
            
            schema_context = {
                "tables": tables,
                "columns": columns,
                "relationships": retrieval_result.relationships
            }
            
            await self._emit_event("schema_discovery_complete", {
                "tables_count": len(tables),
                "columns_count": len(columns),
                "schema_context": schema_context
            })
            
            return {
                "discovered_tables": tables,
                "discovered_columns": columns,
                "schema_context": schema_context,
                "iteration": state["iteration"] + 1,
            }
            
        except Exception as e:
            log.error("schema_discovery_error", error=str(e))
            await self._emit_event("schema_discovery_error", {"error": str(e)})
            return {
                "discovered_tables": [],
                "discovered_columns": [],
                "schema_context": None,
                "iteration": state["iteration"] + 1,
            }
    
    async def _generate_sql_node(self, state: SENSAgentState) -> Dict[str, Any]:
        """Generate SQL query from discovered schema (following Google's node pattern)."""
        
        await self._emit_event("sql_generation_start", {
            "iteration": state["iteration"],
            "schema_tables": len(state["discovered_tables"]),
        })
        
        try:
            # Use existing SQL generator
            generation_result = await self.sql_generator.generate(
                query=state["user_query"],
                schema_context=state["schema_context"]
            )
            
            await self._emit_event("sql_generation_complete", {
                "sql": generation_result.sql,
                "explanation": generation_result.explanation
            })
            
            return {
                "generated_sql": generation_result.sql,
                "sql_explanation": generation_result.explanation,
                "messages": [AIMessage(content=f"Generated SQL: {generation_result.sql}")],
            }
            
        except Exception as e:
            log.error("sql_generation_error", error=str(e))
            await self._emit_event("sql_generation_error", {"error": str(e)})
            return {
                "generated_sql": None,
                "sql_explanation": f"Error generating SQL: {str(e)}",
            }
    
    async def _execute_sql_node(self, state: SENSAgentState) -> Dict[str, Any]:
        """Execute the generated SQL (following Google's node pattern)."""
        
        if not state["generated_sql"]:
            return {
                "execution_result": None,
                "execution_error": "No SQL to execute",
            }
        
        await self._emit_event("sql_execution_start", {
            "sql": state["generated_sql"]
        })
        
        try:
            # Use existing SQL executor
            execution_result = await self.sql_executor.execute(
                state["generated_sql"]
            )
            
            # Transform result to our format
            result_data = {
                "success": execution_result.success,
                "rows": execution_result.rows,
                "columns": execution_result.columns,
                "row_count": len(execution_result.rows) if execution_result.rows else 0,
            }
            
            await self._emit_event("sql_execution_complete", {
                "result": result_data,
                "row_count": result_data["row_count"]
            })
            
            return {
                "execution_result": result_data,
                "execution_error": None,
                "messages": [AIMessage(content=f"Executed SQL successfully. Retrieved {result_data['row_count']} rows.")],
            }
            
        except Exception as e:
            log.error("sql_execution_error", error=str(e))
            await self._emit_event("sql_execution_error", {"error": str(e)})
            return {
                "execution_result": None,
                "execution_error": str(e),
            }
    
    async def _reflect_on_progress_node(self, state: SENSAgentState) -> Dict[str, Any]:
        """Analyze current progress and identify gaps (following Google's reflection pattern)."""
        
        if not self.enable_reflection:
            return {
                "is_sufficient": True,
                "knowledge_gaps": [],
                "follow_up_actions": [],
                "confidence_score": 0.8,
            }
        
        await self._emit_event("reflection_start", {
            "iteration": state["iteration"],
            "has_sql": bool(state["generated_sql"]),
            "has_result": bool(state["execution_result"]),
        })
        
        try:
            # Use existing reflection engine with structured analysis
            reflection_result = await self.reflection_engine.reflect(
                query=state["user_query"],
                current_sql=state["generated_sql"],
                execution_result=state["execution_result"],
                schema_context=state["schema_context"]
            )
            
            # Extract structured information
            is_sufficient = self._assess_sufficiency(state, reflection_result)
            knowledge_gaps = self._identify_knowledge_gaps(state, reflection_result)
            follow_up_actions = self._determine_next_actions(state, knowledge_gaps)
            confidence_score = self._calculate_confidence(state, reflection_result)
            
            await self._emit_event("reflection_complete", {
                "is_sufficient": is_sufficient,
                "knowledge_gaps": knowledge_gaps,
                "follow_up_actions": follow_up_actions,
                "confidence_score": confidence_score,
            })
            
            return {
                "is_sufficient": is_sufficient,
                "knowledge_gaps": knowledge_gaps,
                "follow_up_actions": follow_up_actions,
                "confidence_score": confidence_score,
                "messages": [AIMessage(content=f"Reflection: {'Sufficient' if is_sufficient else 'Needs improvement'}")],
            }
            
        except Exception as e:
            log.error("reflection_error", error=str(e))
            await self._emit_event("reflection_error", {"error": str(e)})
            return {
                "is_sufficient": True,  # Default to sufficient on error
                "knowledge_gaps": [],
                "follow_up_actions": [],
                "confidence_score": 0.5,
            }
    
    async def _finalize_answer_node(self, state: SENSAgentState) -> Dict[str, Any]:
        """Generate final answer (following Google's finalization pattern)."""
        
        await self._emit_event("finalization_start", {
            "iteration": state["iteration"],
            "has_result": bool(state["execution_result"]),
        })
        
        try:
            # Generate natural language response
            if state["execution_result"] and state["execution_result"]["success"]:
                # Use existing response generation
                natural_response = await self._generate_natural_response(
                    state["user_query"],
                    state["execution_result"],
                    state["generated_sql"]
                )
            else:
                natural_response = f"I apologize, but I couldn't successfully process your query: {state['user_query']}"
                if state["execution_error"]:
                    natural_response += f" Error: {state['execution_error']}"
            
            await self._emit_event("finalization_complete", {
                "natural_response": natural_response,
                "final_answer": natural_response,
            })
            
            return {
                "final_answer": natural_response,
                "natural_language_response": natural_response,
                "messages": [AIMessage(content=natural_response)],
            }
            
        except Exception as e:
            log.error("finalization_error", error=str(e))
            await self._emit_event("finalization_error", {"error": str(e)})
            return {
                "final_answer": f"Error generating final answer: {str(e)}",
                "natural_language_response": f"Error generating final answer: {str(e)}",
            }
    
    # Routing logic (following Google's conditional edge pattern)
    
    def _should_continue_research(self, state: SENSAgentState) -> str:
        """Determine next action based on current state (following Google's routing pattern)."""
        
        # Check iteration limit
        if state["iteration"] >= state["max_iterations"]:
            return "finalize_answer"
        
        # If reflection indicates sufficiency, finalize
        if state["is_sufficient"]:
            return "finalize_answer"
        
        # Determine next action based on knowledge gaps
        follow_up_actions = state.get("follow_up_actions", [])
        
        if "discover_schema" in follow_up_actions:
            return "discover_schema"
        elif "generate_sql" in follow_up_actions:
            return "generate_sql"
        elif "execute_sql" in follow_up_actions:
            return "execute_sql"
        else:
            return "finalize_answer"
    
    # Helper methods
    
    def _assess_sufficiency(self, state: SENSAgentState, reflection_result: Any) -> bool:
        """Assess if current information is sufficient."""
        
        # Basic sufficiency check
        has_sql = bool(state["generated_sql"])
        has_result = bool(state["execution_result"])
        result_success = state["execution_result"] and state["execution_result"]["success"]
        
        # If we have successful execution, likely sufficient
        if has_sql and has_result and result_success:
            return True
        
        # If we've reached max iterations, consider sufficient
        if state["iteration"] >= state["max_iterations"]:
            return True
        
        return False
    
    def _identify_knowledge_gaps(self, state: SENSAgentState, reflection_result: Any) -> List[str]:
        """Identify knowledge gaps from current state."""
        
        gaps = []
        
        if not state["schema_context"]:
            gaps.append("Missing schema context")
        
        if not state["generated_sql"]:
            gaps.append("No SQL generated")
        
        if state["execution_error"]:
            gaps.append(f"SQL execution error: {state['execution_error']}")
        
        if not state["execution_result"]:
            gaps.append("No execution result")
        
        return gaps
    
    def _determine_next_actions(self, state: SENSAgentState, knowledge_gaps: List[str]) -> List[str]:
        """Determine next actions based on knowledge gaps."""
        
        actions = []
        
        for gap in knowledge_gaps:
            if "schema" in gap.lower():
                actions.append("discover_schema")
            elif "sql" in gap.lower() and "error" not in gap.lower():
                actions.append("generate_sql")
            elif "execution" in gap.lower() or "error" in gap.lower():
                actions.append("execute_sql")
        
        return actions
    
    def _calculate_confidence(self, state: SENSAgentState, reflection_result: Any) -> float:
        """Calculate confidence score for current state."""
        
        score = 0.0
        
        if state["schema_context"]:
            score += 0.3
        
        if state["generated_sql"]:
            score += 0.3
        
        if state["execution_result"] and state["execution_result"]["success"]:
            score += 0.4
        
        return min(score, 1.0)
    
    async def _generate_natural_response(self, query: str, result: Dict[str, Any], sql: str) -> str:
        """Generate natural language response from results."""
        
        # Simple response generation - can be enhanced
        row_count = result.get("row_count", 0)
        
        if row_count == 0:
            return f"I found no results for your query: {query}"
        elif row_count == 1:
            return f"I found 1 result for your query: {query}"
        else:
            return f"I found {row_count} results for your query: {query}"
    
    # Event handling for streaming
    
    async def _emit_event(self, event_type: str, data: Dict[str, Any]):
        """Emit event for streaming (compatible with existing SSE system)."""
        
        if not self.enable_streaming:
            return
        
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }
        
        # Notify all registered handlers
        for handler in self.event_handlers:
            try:
                await handler(event)
            except Exception as e:
                log.error("event_handler_error", error=str(e))
    
    def add_event_handler(self, handler):
        """Add event handler for streaming."""
        self.event_handlers.append(handler)
    
    def remove_event_handler(self, handler):
        """Remove event handler."""
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
    
    # Main processing methods
    
    async def process_query(self, query: str, conversation_id: str) -> Dict[str, Any]:
        """Process query using LangGraph (main entry point)."""
        
        if self.legacy_mode:
            # Fallback to existing system
            return await self._legacy_process(query, conversation_id)
        
        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "conversation_id": conversation_id,
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "discovered_tables": [],
            "discovered_columns": [],
            "schema_context": None,
            "generated_sql": None,
            "sql_explanation": None,
            "execution_result": None,
            "execution_error": None,
            "is_sufficient": False,
            "knowledge_gaps": [],
            "follow_up_actions": [],
            "confidence_score": 0.0,
            "discovered_mappings": {},
            "learned_patterns": [],
            "final_answer": None,
            "natural_language_response": None,
        }
        
        try:
            # Process through LangGraph
            final_state = await self.graph.ainvoke(initial_state)
            
            # Transform to expected format
            return self._transform_state_to_result(final_state)
            
        except Exception as e:
            log.error("langgraph_processing_error", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "sql": None,
                "result": None,
                "answer": f"Error processing query: {str(e)}",
                "iterations": initial_state["iteration"],
            }
    
    async def stream_query(self, query: str, conversation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Stream query processing using LangGraph streaming."""
        
        if self.legacy_mode:
            # Fallback to existing streaming
            async for event in self._legacy_stream(query, conversation_id):
                yield event
            return
        
        # Initialize state
        initial_state = {
            "messages": [HumanMessage(content=query)],
            "user_query": query,
            "conversation_id": conversation_id,
            "iteration": 0,
            "max_iterations": self.max_iterations,
            "discovered_tables": [],
            "discovered_columns": [],
            "schema_context": None,
            "generated_sql": None,
            "sql_explanation": None,
            "execution_result": None,
            "execution_error": None,
            "is_sufficient": False,
            "knowledge_gaps": [],
            "follow_up_actions": [],
            "confidence_score": 0.0,
            "discovered_mappings": {},
            "learned_patterns": [],
            "final_answer": None,
            "natural_language_response": None,
        }
        
        try:
            # Stream with LangGraph's built-in streaming
            async for state in self.graph.astream(initial_state, stream_mode="values"):
                # Transform state to SSE event format
                event = self._transform_state_to_event(state)
                if event:
                    yield event
                    
        except Exception as e:
            log.error("langgraph_streaming_error", error=str(e))
            yield {
                "type": "error",
                "data": {"error": str(e)},
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def _transform_state_to_event(self, state: SENSAgentState) -> Optional[Dict[str, Any]]:
        """Transform LangGraph state to SSE event format."""
        
        # Determine event type based on state changes
        if state.get("discovered_tables") and not state.get("generated_sql"):
            return {
                "type": "schema_discovery",
                "data": {
                    "tables": state["discovered_tables"],
                    "columns": state["discovered_columns"],
                    "iteration": state["iteration"],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        elif state.get("generated_sql") and not state.get("execution_result"):
            return {
                "type": "sql_generated",
                "data": {
                    "sql": state["generated_sql"],
                    "explanation": state["sql_explanation"],
                    "iteration": state["iteration"],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        elif state.get("execution_result"):
            return {
                "type": "sql_executed",
                "data": {
                    "result": state["execution_result"],
                    "error": state["execution_error"],
                    "iteration": state["iteration"],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        elif state.get("knowledge_gaps"):
            return {
                "type": "reflection",
                "data": {
                    "gaps": state["knowledge_gaps"],
                    "actions": state["follow_up_actions"],
                    "confidence": state["confidence_score"],
                    "is_sufficient": state["is_sufficient"],
                    "iteration": state["iteration"],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        elif state.get("final_answer"):
            return {
                "type": "final_answer",
                "data": {
                    "answer": state["final_answer"],
                    "iteration": state["iteration"],
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        
        return None
    
    def _transform_state_to_result(self, state: SENSAgentState) -> Dict[str, Any]:
        """Transform final state to expected result format."""
        
        success = bool(state.get("execution_result") and state["execution_result"]["success"])
        
        return {
            "success": success,
            "sql": state.get("generated_sql"),
            "result": state.get("execution_result"),
            "answer": state.get("final_answer") or state.get("natural_language_response"),
            "iterations": state.get("iteration", 0),
            "confidence_score": state.get("confidence_score", 0.0),
            "discovered_mappings": state.get("discovered_mappings", {}),
            "schema_context": state.get("schema_context"),
            "execution_error": state.get("execution_error"),
        }
    
    # Legacy compatibility methods
    
    async def _legacy_process(self, query: str, conversation_id: str) -> Dict[str, Any]:
        """Fallback to existing UnifiedSENSAgent."""
        from sens.agents.unified import UnifiedSENSAgent
        
        legacy_agent = UnifiedSENSAgent(
            max_iterations=self.max_iterations,
            streaming_enabled=False,
        )
        
        return await legacy_agent.process_query(query, conversation_id)
    
    async def _legacy_stream(self, query: str, conversation_id: str) -> AsyncGenerator[Dict[str, Any], None]:
        """Fallback to existing streaming."""
        from sens.agents.unified import UnifiedSENSAgent
        
        legacy_agent = UnifiedSENSAgent(
            max_iterations=self.max_iterations,
            streaming_enabled=True,
        )
        
        # This would need to be implemented based on existing streaming logic
        result = await legacy_agent.process_query(query, conversation_id)
        yield {
            "type": "result",
            "data": result,
            "timestamp": datetime.utcnow().isoformat(),
        }