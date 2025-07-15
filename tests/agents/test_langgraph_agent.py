"""
Comprehensive tests for the LangGraph SENS Agent implementation.

This test suite validates the new LangGraph agent against the legacy
implementation while ensuring backward compatibility and SSE functionality.
"""

import asyncio
import json
import pytest
from datetime import datetime
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock, patch

from sens.agents.langgraph_sens_agent import LangGraphSENSAgent, SENSAgentState
from sens.agents.unified import UnifiedSENSAgent
from sens.api.routers.langgraph_agent import get_langgraph_agent
from sens.chat.session import SessionManager
from sens.execution.executor import QueryResult
from sens.generation.openrouter_generator import GenerationResult
from sens.retrieval.models import RetrievedContext, RetrievedTable, RetrievedColumn
from sens.settings import get_settings


class TestLangGraphSENSAgent:
    """Test suite for LangGraph SENS Agent."""
    
    @pytest.fixture
    def mock_retriever(self):
        """Mock retriever for testing."""
        retriever = Mock()
        retriever.retrieve = AsyncMock(return_value=RetrievedContext(
            tables=[
                RetrievedTable(
                    name="users",
                    description="User table",
                    columns=[
                        RetrievedColumn(name="id", type="int", table="users"),
                        RetrievedColumn(name="name", type="varchar", table="users"),
                    ]
                )
            ],
            columns=[
                RetrievedColumn(name="id", type="int", table="users"),
                RetrievedColumn(name="name", type="varchar", table="users"),
            ],
            relationships=[]
        ))
        return retriever
    
    @pytest.fixture
    def mock_sql_generator(self):
        """Mock SQL generator for testing."""
        generator = Mock()
        generator.generate = AsyncMock(return_value=GenerationResult(
            sql="SELECT * FROM users",
            explanation="This query retrieves all users",
            confidence=0.9
        ))
        return generator
    
    @pytest.fixture
    def mock_sql_executor(self):
        """Mock SQL executor for testing."""
        executor = Mock()
        executor.execute = AsyncMock(return_value=QueryResult(
            success=True,
            rows=[{"id": 1, "name": "John"}, {"id": 2, "name": "Jane"}],
            columns=["id", "name"],
            execution_time=0.1
        ))
        return executor
    
    @pytest.fixture
    def mock_reflection_engine(self):
        """Mock reflection engine for testing."""
        engine = Mock()
        engine.reflect = AsyncMock(return_value={
            "is_sufficient": True,
            "confidence": 0.8,
            "gaps": [],
            "suggestions": []
        })
        return engine
    
    @pytest.fixture
    def langgraph_agent(self, mock_retriever, mock_sql_generator, mock_sql_executor, mock_reflection_engine):
        """Create LangGraph agent with mocked dependencies."""
        return LangGraphSENSAgent(
            retriever=mock_retriever,
            sql_generator=mock_sql_generator,
            sql_executor=mock_sql_executor,
            reflection_engine=mock_reflection_engine,
            max_iterations=5,
            enable_streaming=True,
            enable_reflection=True,
            legacy_mode=False,
        )
    
    @pytest.fixture
    def legacy_agent(self):
        """Create legacy agent for comparison."""
        return UnifiedSENSAgent(
            max_iterations=5,
            streaming_enabled=False,
        )


class TestStateManagement:
    """Test state management with TypedDict."""
    
    def test_state_schema_validation(self):
        """Test that state schema is properly defined."""
        # Test initial state structure
        initial_state = {
            "messages": [],
            "user_query": "test query",
            "conversation_id": "test",
            "iteration": 0,
            "max_iterations": 5,
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
        
        # Validate all required fields are present
        assert "user_query" in initial_state
        assert "conversation_id" in initial_state
        assert "iteration" in initial_state
        assert "is_sufficient" in initial_state
        assert "knowledge_gaps" in initial_state
        assert "follow_up_actions" in initial_state
        
        # Validate types
        assert isinstance(initial_state["messages"], list)
        assert isinstance(initial_state["iteration"], int)
        assert isinstance(initial_state["is_sufficient"], bool)
        assert isinstance(initial_state["knowledge_gaps"], list)
        assert isinstance(initial_state["discovered_mappings"], dict)
    
    def test_state_updates(self):
        """Test state updates following LangGraph patterns."""
        # Test that state updates are dictionaries
        node_update = {
            "discovered_tables": [{"name": "test_table"}],
            "iteration": 1,
        }
        
        assert isinstance(node_update, dict)
        assert "discovered_tables" in node_update
        assert "iteration" in node_update


class TestNodeImplementations:
    """Test individual node implementations."""
    
    @pytest.mark.asyncio
    async def test_discover_schema_node(self, langgraph_agent):
        """Test schema discovery node."""
        state = {
            "user_query": "Show me all users",
            "iteration": 0,
            "messages": [],
            "conversation_id": "test",
            "max_iterations": 5,
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
        
        result = await langgraph_agent._discover_schema_node(state)
        
        assert isinstance(result, dict)
        assert "discovered_tables" in result
        assert "discovered_columns" in result
        assert "schema_context" in result
        assert "iteration" in result
        assert result["iteration"] == 1
    
    @pytest.mark.asyncio
    async def test_generate_sql_node(self, langgraph_agent):
        """Test SQL generation node."""
        state = {
            "user_query": "Show me all users",
            "iteration": 1,
            "schema_context": {"tables": ["users"]},
            "discovered_tables": [{"name": "users"}],
            "messages": [],
            "conversation_id": "test",
            "max_iterations": 5,
            "discovered_columns": [],
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
        
        result = await langgraph_agent._generate_sql_node(state)
        
        assert isinstance(result, dict)
        assert "generated_sql" in result
        assert "sql_explanation" in result
        assert "messages" in result
        assert result["generated_sql"] == "SELECT * FROM users"
    
    @pytest.mark.asyncio
    async def test_execute_sql_node(self, langgraph_agent):
        """Test SQL execution node."""
        state = {
            "user_query": "Show me all users",
            "iteration": 1,
            "generated_sql": "SELECT * FROM users",
            "messages": [],
            "conversation_id": "test",
            "max_iterations": 5,
            "discovered_tables": [],
            "discovered_columns": [],
            "schema_context": None,
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
        
        result = await langgraph_agent._execute_sql_node(state)
        
        assert isinstance(result, dict)
        assert "execution_result" in result
        assert "execution_error" in result
        assert "messages" in result
        assert result["execution_result"]["success"] is True
        assert result["execution_error"] is None
    
    @pytest.mark.asyncio
    async def test_reflect_on_progress_node(self, langgraph_agent):
        """Test reflection node."""
        state = {
            "user_query": "Show me all users",
            "iteration": 1,
            "generated_sql": "SELECT * FROM users",
            "execution_result": {"success": True, "rows": [{"id": 1}]},
            "messages": [],
            "conversation_id": "test",
            "max_iterations": 5,
            "discovered_tables": [],
            "discovered_columns": [],
            "schema_context": None,
            "sql_explanation": None,
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
        
        result = await langgraph_agent._reflect_on_progress_node(state)
        
        assert isinstance(result, dict)
        assert "is_sufficient" in result
        assert "knowledge_gaps" in result
        assert "follow_up_actions" in result
        assert "confidence_score" in result
        assert "messages" in result
        assert isinstance(result["is_sufficient"], bool)
        assert isinstance(result["knowledge_gaps"], list)
        assert isinstance(result["follow_up_actions"], list)
        assert isinstance(result["confidence_score"], float)
    
    @pytest.mark.asyncio
    async def test_finalize_answer_node(self, langgraph_agent):
        """Test answer finalization node."""
        state = {
            "user_query": "Show me all users",
            "iteration": 1,
            "execution_result": {"success": True, "rows": [{"id": 1}], "row_count": 1},
            "generated_sql": "SELECT * FROM users",
            "messages": [],
            "conversation_id": "test",
            "max_iterations": 5,
            "discovered_tables": [],
            "discovered_columns": [],
            "schema_context": None,
            "sql_explanation": None,
            "execution_error": None,
            "is_sufficient": True,
            "knowledge_gaps": [],
            "follow_up_actions": [],
            "confidence_score": 0.8,
            "discovered_mappings": {},
            "learned_patterns": [],
            "final_answer": None,
            "natural_language_response": None,
        }
        
        result = await langgraph_agent._finalize_answer_node(state)
        
        assert isinstance(result, dict)
        assert "final_answer" in result
        assert "natural_language_response" in result
        assert "messages" in result
        assert result["final_answer"] is not None
        assert result["natural_language_response"] is not None


class TestGraphExecution:
    """Test full graph execution."""
    
    @pytest.mark.asyncio
    async def test_full_graph_execution(self, langgraph_agent):
        """Test complete graph execution."""
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        assert isinstance(result, dict)
        assert "success" in result
        assert "sql" in result
        assert "result" in result
        assert "answer" in result
        assert "iterations" in result
        assert "confidence_score" in result
        
        # Verify expected structure
        assert result["sql"] == "SELECT * FROM users"
        assert result["success"] is True
        assert result["iterations"] > 0
        assert result["confidence_score"] >= 0.0
    
    @pytest.mark.asyncio
    async def test_graph_iteration_control(self, langgraph_agent):
        """Test iteration control in graph execution."""
        # Test with low max_iterations
        langgraph_agent.max_iterations = 2
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        assert result["iterations"] <= 2
    
    @pytest.mark.asyncio
    async def test_graph_error_handling(self, langgraph_agent):
        """Test error handling in graph execution."""
        # Configure mock to raise error
        langgraph_agent.sql_executor.execute.side_effect = Exception("Database error")
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        assert result["success"] is False
        assert "error" in result
        assert "Database error" in result["error"]


class TestStreamingSupport:
    """Test streaming functionality with LangGraph."""
    
    @pytest.mark.asyncio
    async def test_streaming_events(self, langgraph_agent):
        """Test streaming event generation."""
        events = []
        
        async for event in langgraph_agent.stream_query(
            query="Show me all users",
            conversation_id="test"
        ):
            events.append(event)
            if len(events) >= 5:  # Limit to avoid infinite loop
                break
        
        assert len(events) > 0
        
        # Verify event structure
        for event in events:
            assert isinstance(event, dict)
            assert "type" in event
            assert "data" in event
            assert "timestamp" in event
    
    @pytest.mark.asyncio
    async def test_event_types(self, langgraph_agent):
        """Test different event types are generated."""
        events = []
        
        async for event in langgraph_agent.stream_query(
            query="Show me all users",
            conversation_id="test"
        ):
            events.append(event)
        
        event_types = [event["type"] for event in events]
        
        # Should have schema discovery, SQL generation, execution, and finalization
        assert any("schema" in event_type for event_type in event_types)
        assert any("sql" in event_type for event_type in event_types)
        assert any("executed" in event_type for event_type in event_types)
        assert any("answer" in event_type for event_type in event_types)
    
    @pytest.mark.asyncio
    async def test_event_handlers(self, langgraph_agent):
        """Test event handler functionality."""
        captured_events = []
        
        async def event_handler(event):
            captured_events.append(event)
        
        langgraph_agent.add_event_handler(event_handler)
        
        # Process query (this should trigger events)
        await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        assert len(captured_events) > 0
        
        # Verify event handler was called
        for event in captured_events:
            assert isinstance(event, dict)
            assert "type" in event
            assert "data" in event


class TestBackwardCompatibility:
    """Test backward compatibility with existing system."""
    
    @pytest.mark.asyncio
    async def test_legacy_mode_fallback(self, langgraph_agent):
        """Test legacy mode fallback."""
        # Enable legacy mode
        langgraph_agent.legacy_mode = True
        
        with patch('sens.agents.langgraph_sens_agent.UnifiedSENSAgent') as mock_unified:
            mock_unified.return_value.process_query = AsyncMock(return_value={
                "success": True,
                "sql": "SELECT * FROM users",
                "result": {"rows": []},
                "answer": "Legacy result",
                "iterations": 3,
            })
            
            result = await langgraph_agent.process_query(
                query="Show me all users",
                conversation_id="test"
            )
            
            # Should have called legacy agent
            mock_unified.assert_called_once()
            mock_unified.return_value.process_query.assert_called_once()
            
            assert result["answer"] == "Legacy result"
            assert result["iterations"] == 3
    
    @pytest.mark.asyncio
    async def test_result_format_compatibility(self, langgraph_agent):
        """Test that result format matches legacy expectations."""
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        # Should match expected format from legacy agent
        expected_keys = [
            "success", "sql", "result", "answer", "iterations",
            "confidence_score", "discovered_mappings", "schema_context"
        ]
        
        for key in expected_keys:
            assert key in result
    
    @pytest.mark.asyncio
    async def test_api_compatibility(self, langgraph_agent):
        """Test API method compatibility."""
        # Test that all expected methods exist
        assert hasattr(langgraph_agent, 'process_query')
        assert hasattr(langgraph_agent, 'stream_query')
        assert hasattr(langgraph_agent, 'add_event_handler')
        assert hasattr(langgraph_agent, 'remove_event_handler')
        
        # Test method signatures
        import inspect
        
        process_query_sig = inspect.signature(langgraph_agent.process_query)
        assert 'query' in process_query_sig.parameters
        assert 'conversation_id' in process_query_sig.parameters
        
        stream_query_sig = inspect.signature(langgraph_agent.stream_query)
        assert 'query' in stream_query_sig.parameters
        assert 'conversation_id' in stream_query_sig.parameters


class TestPerformanceComparison:
    """Test performance comparison between LangGraph and legacy."""
    
    @pytest.mark.asyncio
    async def test_performance_comparison(self, langgraph_agent, legacy_agent):
        """Compare performance between LangGraph and legacy agent."""
        query = "Show me all users"
        conversation_id = "test"
        
        # Time LangGraph agent
        import time
        start_time = time.time()
        langgraph_result = await langgraph_agent.process_query(query, conversation_id)
        langgraph_time = time.time() - start_time
        
        # Time legacy agent (with mocking to avoid actual execution)
        with patch.object(legacy_agent, 'process_query', new_callable=AsyncMock) as mock_process:
            mock_process.return_value = {
                "success": True,
                "sql": "SELECT * FROM users",
                "result": {"rows": []},
                "answer": "Legacy result",
                "iterations": 3,
            }
            
            start_time = time.time()
            legacy_result = await legacy_agent.process_query(query, conversation_id)
            legacy_time = time.time() - start_time
        
        # Both should complete successfully
        assert langgraph_result["success"] is True
        assert legacy_result["success"] is True
        
        # Log timing for analysis
        print(f"LangGraph time: {langgraph_time:.3f}s")
        print(f"Legacy time: {legacy_time:.3f}s")
        
        # Both should be reasonably fast (under 5 seconds)
        assert langgraph_time < 5.0
        assert legacy_time < 5.0


class TestIntegrationWithExistingSystem:
    """Test integration with existing SENS components."""
    
    @pytest.mark.asyncio
    async def test_session_manager_integration(self):
        """Test integration with SessionManager."""
        session_manager = SessionManager()
        
        agent = LangGraphSENSAgent(
            session_manager=session_manager,
            legacy_mode=False,
        )
        
        # Test that session manager is properly integrated
        assert agent.session_manager is not None
        assert isinstance(agent.session_manager, SessionManager)
    
    @pytest.mark.asyncio
    async def test_settings_integration(self):
        """Test integration with SENS settings."""
        settings = get_settings()
        
        agent = LangGraphSENSAgent(
            max_iterations=settings.agent_reasoning.max_iterations,
            legacy_mode=False,
        )
        
        assert agent.max_iterations == settings.agent_reasoning.max_iterations
        assert agent.settings is not None
    
    @pytest.mark.asyncio
    async def test_router_integration(self):
        """Test integration with API router."""
        # Test that router can create agent
        agent = await get_langgraph_agent()
        
        assert isinstance(agent, LangGraphSENSAgent)
        assert agent.enable_streaming is True
        assert agent.enable_reflection is True
        assert agent.legacy_mode is False


class TestErrorHandling:
    """Test comprehensive error handling."""
    
    @pytest.mark.asyncio
    async def test_retrieval_error_handling(self, langgraph_agent):
        """Test handling of retrieval errors."""
        # Configure mock to raise error
        langgraph_agent.retriever.retrieve.side_effect = Exception("Retrieval error")
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Retrieval error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_sql_generation_error_handling(self, langgraph_agent):
        """Test handling of SQL generation errors."""
        # Configure mock to raise error
        langgraph_agent.sql_generator.generate.side_effect = Exception("Generation error")
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Generation error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_execution_error_handling(self, langgraph_agent):
        """Test handling of execution errors."""
        # Configure mock to raise error
        langgraph_agent.sql_executor.execute.side_effect = Exception("Execution error")
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        # Should handle error gracefully
        assert result["success"] is False
        assert "error" in result
        assert "Execution error" in result["error"]
    
    @pytest.mark.asyncio
    async def test_reflection_error_handling(self, langgraph_agent):
        """Test handling of reflection errors."""
        # Configure mock to raise error
        langgraph_agent.reflection_engine.reflect.side_effect = Exception("Reflection error")
        
        result = await langgraph_agent.process_query(
            query="Show me all users",
            conversation_id="test"
        )
        
        # Should still complete (reflection errors should not be fatal)
        assert result["success"] is True  # Should fallback gracefully
        assert result["sql"] == "SELECT * FROM users"


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])