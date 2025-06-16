"""Test the agent notes system."""

from unittest.mock import AsyncMock, Mock

import pytest

from sens.agents.base import AgentState
from sens.agents.core import SENSAgent
from sens.agents.reasoning import ReasoningEngine
from sens.agents.tools import AgentTools


class TestAgentNotes:
    """Test agent notes functionality."""

    def test_agent_state_notes_initialization(self):
        """Test that agent state initializes with empty notes."""
        state = AgentState(
            user_query="test query",
            conversation_id="test-123",
        )
        assert state.agent_notes == ""

    def test_agent_state_update_notes(self):
        """Test updating agent notes."""
        state = AgentState(
            user_query="test query",
            conversation_id="test-123",
        )

        # First update
        state.update_notes("Found table: daily_prices")
        assert "Agent Notes:" in state.agent_notes
        assert "Found table: daily_prices" in state.agent_notes

        # Second update (should append)
        state.update_notes("Columns: symbol, trade_date, close_price")
        assert "Found table: daily_prices" in state.agent_notes
        assert "Columns: symbol, trade_date, close_price" in state.agent_notes

    @pytest.mark.asyncio
    async def test_reasoning_engine_with_notes(self):
        """Test that reasoning engine accepts and uses agent notes."""
        # Mock the LLM client
        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content="""THOUGHT: I have schema information in my notes.
NOTES_UPDATE: Found securities table with symbol mappings
CONFIDENCE: 0.9
ACTION: GENERATE_SQL
PARAMETERS: {}"""
                        )
                    )
                ]
            )
        )

        reasoning_engine = ReasoningEngine()
        reasoning_engine.client = mock_client

        result = await reasoning_engine.analyze_situation(
            user_query="Find Apple stock prices",
            context="Previous exploration",
            iteration=2,
            discovered_mappings={"Apple": "AAPL"},
            agent_notes="Agent Notes:\nFound tables: securities, daily_prices",
        )

        assert result["thought"] == "I have schema information in my notes."
        assert result["notes_update"] == "Found securities table with symbol mappings"
        assert result["confidence"] == 0.9
        assert result["suggested_action"]["type"] == "GENERATE_SQL"

    @pytest.mark.asyncio
    async def test_tools_receive_agent_notes(self):
        """Test that tools receive agent notes in their methods."""
        tools = AgentTools()

        # Mock the LLM client for SQL generation
        mock_client = Mock()
        mock_client.chat = Mock()
        mock_client.chat.completions = Mock()
        mock_client.chat.completions.create = AsyncMock(
            return_value=Mock(
                choices=[
                    Mock(
                        message=Mock(
                            content="SELECT * FROM daily_prices WHERE symbol = 'AAPL'"
                        )
                    )
                ]
            )
        )
        tools._llm_client = mock_client

        # Test that generate_sql accepts agent_notes
        sql = await tools.generate_sql(
            query="Find Apple stock",
            exploration_results={
                "discovered_tables": ["daily_prices"],
                "table_schemas": {
                    "daily_prices": ["symbol", "trade_date", "close_price"]
                },
            },
            mappings={"Apple": "AAPL"},
            agent_notes="Agent Notes:\nFound Apple maps to AAPL",
        )

        assert sql == "SELECT * FROM daily_prices WHERE symbol = 'AAPL'"

        # Verify the prompt included agent notes
        call_args = mock_client.chat.completions.create.call_args
        prompt = call_args[1]["messages"][0]["content"]
        assert "Agent Notes:" in prompt
        assert "Found Apple maps to AAPL" in prompt

    @pytest.mark.asyncio
    async def test_agent_propagates_notes(self):
        """Test that the agent propagates notes through the reasoning cycle."""
        # Create agent with mocked components
        mock_tools = Mock(spec=AgentTools)
        mock_memory = Mock()
        mock_reasoning = Mock(spec=ReasoningEngine)

        # Mock reasoning to return notes update
        mock_reasoning.analyze_situation = AsyncMock(
            return_value={
                "thought": "I found important information",
                "notes_update": "Table daily_prices has columns: symbol, close_price",
                "confidence": 0.9,
                "suggested_action": {"type": "GENERATE_SQL", "parameters": {}},
            }
        )

        agent = SENSAgent(
            tools=mock_tools,
            memory=mock_memory,
            reasoning_engine=mock_reasoning,
            max_iterations=3,
        )

        # Create initial state
        state = AgentState(user_query="Find stock prices", conversation_id="test-123")

        # Run one reasoning cycle
        await agent.reason(state)

        # Verify notes were updated
        assert (
            "Table daily_prices has columns: symbol, close_price" in state.agent_notes
        )

        # Verify reasoning was called with notes on subsequent call
        await agent.reason(state)
        second_call_args = mock_reasoning.analyze_situation.call_args[1]
        assert "agent_notes" in second_call_args
        assert (
            "Table daily_prices has columns: symbol, close_price"
            in second_call_args["agent_notes"]
        )
