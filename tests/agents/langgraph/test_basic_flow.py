"""Basic tests for LangGraph agent flow."""

import pytest
import asyncio
from typing import Dict, Any

from src.sens.agents.langgraph.graph import create_sens_agent_graph
from src.sens.agents.langgraph.state import SensAgentState

# Import message classes with fallback
try:
    from langchain_core.messages import HumanMessage
except ImportError:
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content
            self.type = "human"


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
        success_patterns=[],
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
        start_time=None,
        end_time=None
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
        success_patterns=[],
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
        start_time=None,
        end_time=None
    )
    
    # Execute graph
    result = await graph.ainvoke(initial_state)
    
    # Should complete even with empty query
    assert "finalize_response" in result.get("actions_taken", [])
    assert isinstance(result.get("thoughts", []), list)


@pytest.mark.asyncio
async def test_agent_streaming():
    """Test agent streaming functionality."""
    
    # Create graph
    graph = create_sens_agent_graph()
    
    # Create initial state
    initial_state = SensAgentState(
        messages=[HumanMessage(content="SELECT * FROM users")],
        user_query="SELECT * FROM users",
        iteration_count=0,
        max_iterations=1,
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
        start_time=None,
        end_time=None
    )
    
    # Test streaming
    events = []
    async for event in graph.astream(initial_state):
        events.append(event)
    
    # Should have at least one event
    assert len(events) > 0
    
    # Last event should be the final state
    final_event = events[-1]
    assert isinstance(final_event.get("actions_taken", []), list)


def test_graph_creation():
    """Test that graph can be created without errors."""
    
    graph = create_sens_agent_graph()
    assert graph is not None
    
    # Check if it has the expected structure
    assert hasattr(graph, 'ainvoke') or hasattr(graph, 'workflow')


def test_state_schema():
    """Test that the state schema is properly defined."""
    
    # Test state creation with all required fields
    state = SensAgentState(
        messages=[],
        user_query="test query",
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
        success_patterns=[],
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
        start_time=None,
        end_time=None
    )
    
    assert state["user_query"] == "test query"
    assert state["iteration_count"] == 0
    assert state["max_iterations"] == 3


@pytest.mark.asyncio
async def test_agent_with_sql_query():
    """Test agent with a specific SQL-related query."""
    
    graph = create_sens_agent_graph()
    
    initial_state = SensAgentState(
        messages=[HumanMessage(content="How many users are in the system?")],
        user_query="How many users are in the system?",
        iteration_count=0,
        max_iterations=2,
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
        start_time=None,
        end_time=None
    )
    
    result = await graph.ainvoke(initial_state)
    
    # Should have some SQL-related output
    assert result.get("generated_sql") is not None or "fallback" in str(result.get("thoughts", []))
    assert result.get("iteration_count", 0) >= 0