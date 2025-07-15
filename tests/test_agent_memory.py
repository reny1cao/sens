"""
Tests for the Agent Memory System
"""

import os
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

from sens.memory import AgentMemory, AgentMemoryTools, Memory, MemoryType


@pytest.fixture
def temp_db():
    """Create a temporary database directory for testing."""
    import shutil
    import tempfile

    temp_dir = tempfile.mkdtemp(prefix="kuzu_test_")
    db_path = os.path.join(temp_dir, "test_db")

    yield db_path

    # Cleanup
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)


@pytest.fixture
def memory(temp_db):
    """Create an AgentMemory instance for testing."""
    return AgentMemory(db_path=temp_db)


@pytest.fixture
def memory_tools(memory):
    """Create AgentMemoryTools instance for testing."""
    return AgentMemoryTools(memory)


class TestAgentMemory:
    """Test the core AgentMemory functionality."""

    @pytest.mark.asyncio
    async def test_remember_concept(self, memory):
        """Test remembering a business concept."""
        memory_id = await memory.remember(
            memory_type=MemoryType.CONCEPT,
            name="annual_revenue",
            content={
                "description": "Total revenue for a year",
                "business_terms": ["yearly revenue", "annual sales"],
                "database_mapping": {
                    "table": "revenue",
                    "column": "amount",
                    "aggregation": "SUM",
                },
            },
            context={"database": "financial_db"},
        )

        assert memory_id is not None
        assert memory_id.startswith("concept_")

        # Verify it was stored
        memories = await memory.recall(
            query="annual revenue", context={"database": "financial_db"}
        )

        assert len(memories) == 1
        assert memories[0].name == "annual_revenue"
        assert memories[0].memory_type == MemoryType.CONCEPT

    @pytest.mark.asyncio
    async def test_remember_pattern(self, memory):
        """Test remembering a SQL pattern."""
        memory_id = await memory.remember(
            memory_type=MemoryType.PATTERN,
            name="monthly_aggregation",
            content={
                "trigger": "monthly revenue",
                "sql_template": "SELECT DATE_TRUNC('month', date) as month, SUM(amount) FROM revenue GROUP BY 1",
                "tables": ["revenue"],
                "success_rate": 1.0,
            },
            context={"database": "financial_db"},
        )

        assert memory_id is not None
        assert memory_id.startswith("pattern_")

        # Test recall
        memories = await memory.recall(
            query="monthly", memory_types=[MemoryType.PATTERN]
        )

        assert len(memories) == 1
        assert memories[0].content["trigger"] == "monthly revenue"

    @pytest.mark.asyncio
    async def test_connect_memories(self, memory):
        """Test connecting two memories."""
        # Create two memories
        concept_id = await memory.remember(
            memory_type=MemoryType.CONCEPT,
            name="revenue",
            content={"description": "Revenue concept"},
            context={},
        )

        pattern_id = await memory.remember(
            memory_type=MemoryType.PATTERN,
            name="revenue_calculation",
            content={"sql": "SELECT SUM(amount) FROM revenue"},
            context={},
        )

        # Connect them
        success = await memory.connect(
            from_memory_id=pattern_id,
            to_memory_id=concept_id,
            relationship_type="implements",
            strength=0.9,
        )

        assert success is True

    @pytest.mark.asyncio
    async def test_reflect_on_memory(self, memory):
        """Test reflecting on memory performance."""
        memory_id = await memory.remember(
            memory_type=MemoryType.PATTERN,
            name="test_pattern",
            content={"sql": "SELECT * FROM test"},
            context={},
        )

        # Simulate some usage
        memory.conn.execute(
            """
            MATCH (m:Memory {id: $id})
            SET m.usage_count = 5,
                m.success_count = 4,
                m.confidence = 0.8
        """,
            {"id": memory_id},
        )

        analysis = await memory.reflect(memory_id)

        assert analysis["memory_id"] == memory_id
        assert analysis["usage_count"] == 5
        assert analysis["success_count"] == 4
        assert analysis["success_rate"] == 0.8
        assert analysis["confidence"] == 0.8
        assert "recommendation" in analysis

    @pytest.mark.asyncio
    async def test_forget_memory(self, memory):
        """Test forgetting a memory."""
        memory_id = await memory.remember(
            memory_type=MemoryType.PATTERN,
            name="obsolete_pattern",
            content={"sql": "SELECT * FROM old_table"},
            context={},
        )

        # Verify it exists
        memories = await memory.recall(query="obsolete_pattern")
        assert len(memories) == 1

        # Forget it
        success = await memory.forget(memory_id, "pattern is obsolete")
        assert success is True

        # Verify it's gone
        memories = await memory.recall(query="obsolete_pattern")
        assert len(memories) == 0

    @pytest.mark.asyncio
    async def test_consolidate_memories(self, memory):
        """Test consolidating multiple similar memories."""
        # Create similar memories
        memory_ids = []
        for i in range(3):
            memory_id = await memory.remember(
                memory_type=MemoryType.PATTERN,
                name=f"similar_pattern_{i}",
                content={"sql": f"SELECT * FROM table_{i}"},
                context={},
            )
            memory_ids.append(memory_id)

        # Consolidate them
        consolidated_id = await memory.consolidate(memory_ids)

        assert consolidated_id is not None
        assert consolidated_id.startswith("pattern_")

        # Verify old memories are gone
        for memory_id in memory_ids:
            memories = await memory.recall(query=memory_id)
            assert len(memories) == 0

        # Verify consolidated memory exists
        memories = await memory.recall(query="consolidated")
        assert len(memories) == 1

    @pytest.mark.asyncio
    async def test_get_stats(self, memory):
        """Test getting memory statistics."""
        # Add some memories
        await memory.remember(
            memory_type=MemoryType.CONCEPT, name="test_concept", content={}, context={}
        )

        await memory.remember(
            memory_type=MemoryType.PATTERN, name="test_pattern", content={}, context={}
        )

        stats = await memory.get_stats()

        assert "total_memories" in stats
        assert "memories_by_type" in stats
        assert "total_relationships" in stats
        assert "performance" in stats

        assert stats["total_memories"] >= 2
        assert stats["memories_by_type"]["concept"] >= 1
        assert stats["memories_by_type"]["pattern"] >= 1


class TestAgentMemoryTools:
    """Test the AgentMemoryTools interface."""

    @pytest.mark.asyncio
    async def test_remember_concept_tool(self, memory_tools):
        """Test the remember_concept tool."""
        result = await memory_tools.remember_concept(
            name="customer_lifetime_value",
            description="Total value of a customer over their lifetime",
            business_terms=["CLV", "customer value", "lifetime value"],
            database_mapping={
                "calculation": "SUM(order_amount) / COUNT(DISTINCT customer_id)",
                "tables": ["orders", "customers"],
            },
            context={"database": "crm_db"},
        )

        assert result.success is True
        assert "memory_id" in result.data
        assert result.data["memory_id"].startswith("concept_")

    @pytest.mark.asyncio
    async def test_remember_pattern_tool(self, memory_tools):
        """Test the remember_pattern tool."""
        result = await memory_tools.remember_pattern(
            name="customer_segmentation",
            trigger_phrase="high value customers",
            sql_template="SELECT * FROM customers WHERE lifetime_value > $threshold",
            tables_used=["customers"],
            success_context={"threshold": 10000, "result_count": 150},
            context={"database": "crm_db"},
        )

        assert result.success is True
        assert "memory_id" in result.data
        assert result.data["memory_id"].startswith("pattern_")

    @pytest.mark.asyncio
    async def test_recall_knowledge_tool(self, memory_tools):
        """Test the recall_knowledge tool."""
        # First, store some knowledge
        await memory_tools.remember_concept(
            name="revenue_metrics",
            description="Financial revenue calculations",
            business_terms=["revenue", "sales", "income"],
            database_mapping={"table": "transactions", "column": "amount"},
            context={"database": "finance_db"},
        )

        # Now recall it
        result = await memory_tools.recall_knowledge(
            query="revenue", context={"database": "finance_db"}
        )

        assert result.success is True
        assert "memories" in result.data
        assert len(result.data["memories"]) >= 1

        memory = result.data["memories"][0]
        assert memory["name"] == "revenue_metrics"
        assert memory["type"] == "concept"

    @pytest.mark.asyncio
    async def test_connect_memories_tool(self, memory_tools):
        """Test the connect_memories tool."""
        # Create two memories
        concept_result = await memory_tools.remember_concept(
            name="profit_margin",
            description="Profit margin calculation",
            business_terms=["margin", "profit"],
            database_mapping={"calculation": "(revenue - cost) / revenue"},
            context={},
        )

        pattern_result = await memory_tools.remember_pattern(
            name="margin_analysis",
            trigger_phrase="profit margin by product",
            sql_template="SELECT product, (revenue - cost) / revenue as margin FROM sales",
            tables_used=["sales"],
            success_context={},
            context={},
        )

        # Connect them
        result = await memory_tools.connect_memories(
            from_memory_id=pattern_result.data["memory_id"],
            to_memory_id=concept_result.data["memory_id"],
            relationship_type="implements",
            strength=0.9,
            reason="Pattern implements the concept",
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_reflect_on_memory_tool(self, memory_tools):
        """Test the reflect_on_memory tool."""
        # Create a memory
        result = await memory_tools.remember_pattern(
            name="test_reflection",
            trigger_phrase="test query",
            sql_template="SELECT * FROM test",
            tables_used=["test"],
            success_context={},
            context={},
        )

        memory_id = result.data["memory_id"]

        # Reflect on it
        reflection = await memory_tools.reflect_on_memory(memory_id)

        assert reflection.success is True
        assert "memory_id" in reflection.data
        assert reflection.data["memory_id"] == memory_id
        assert "usage_count" in reflection.data
        assert "success_rate" in reflection.data
        assert "recommendation" in reflection.data

    @pytest.mark.asyncio
    async def test_get_memory_stats_tool(self, memory_tools):
        """Test the get_memory_stats tool."""
        # Add some memories
        await memory_tools.remember_concept(
            name="test_concept",
            description="Test concept",
            business_terms=["test"],
            database_mapping={},
            context={},
        )

        result = await memory_tools.get_memory_stats()

        assert result.success is True
        assert "total_memories" in result.data
        assert "memories_by_type" in result.data
        assert "performance" in result.data

        assert result.data["total_memories"] >= 1

    def test_get_tool_descriptions(self, memory_tools):
        """Test getting tool descriptions."""
        descriptions = memory_tools.get_tool_descriptions()

        assert len(descriptions) > 0

        # Check that each description has required fields
        for desc in descriptions:
            assert "name" in desc
            assert "description" in desc
            assert "parameters" in desc

        # Check for key tools
        tool_names = [desc["name"] for desc in descriptions]
        assert "remember_concept" in tool_names
        assert "remember_pattern" in tool_names
        assert "recall_knowledge" in tool_names
        assert "reflect_on_memory" in tool_names


class TestMemoryIntegration:
    """Test memory system integration scenarios."""

    @pytest.mark.asyncio
    async def test_knowledge_retrieval_workflow(self, memory_tools):
        """Test a complete knowledge retrieval workflow."""
        # 1. Agent discovers a successful pattern
        pattern_result = await memory_tools.remember_pattern(
            name="tech_companies_query",
            trigger_phrase="large tech companies",
            sql_template="SELECT * FROM companies WHERE sector='Technology' AND market_cap > 100000000000",
            tables_used=["companies"],
            success_context={"result_count": 5, "execution_time": 0.15},
            context={"database": "financial_db"},
        )

        # 2. Agent creates a mapping
        mapping_result = await memory_tools.remember_mapping(
            name="tech_sector_mapping",
            user_term="tech companies",
            database_value="sector='Technology'",
            mapping_type="categorical",
            context={"database": "financial_db"},
        )

        # 3. Agent connects the pattern and mapping
        connect_result = await memory_tools.connect_memories(
            from_memory_id=pattern_result.data["memory_id"],
            to_memory_id=mapping_result.data["memory_id"],
            relationship_type="uses",
            strength=0.8,
            reason="Pattern uses this sector mapping",
        )

        # 4. Later, agent receives similar query
        recall_result = await memory_tools.recall_knowledge(
            query="technology companies", context={"database": "financial_db"}
        )

        # 5. Verify relevant knowledge was retrieved
        assert recall_result.success is True
        memories = recall_result.data["memories"]
        assert len(memories) >= 2

        # Check that both pattern and mapping were retrieved
        memory_names = [m["name"] for m in memories]
        assert "tech_companies_query" in memory_names
        assert "tech_sector_mapping" in memory_names

    @pytest.mark.asyncio
    async def test_memory_evolution_workflow(self, memory_tools):
        """Test how memories evolve over time."""
        # 1. Agent learns initial pattern
        initial_result = await memory_tools.remember_pattern(
            name="revenue_calculation_v1",
            trigger_phrase="monthly revenue",
            sql_template="SELECT SUM(amount) FROM sales WHERE MONTH(date) = $month",
            tables_used=["sales"],
            success_context={"version": 1},
            context={"database": "sales_db"},
        )

        # 2. Agent discovers improved pattern
        improved_result = await memory_tools.remember_pattern(
            name="revenue_calculation_v2",
            trigger_phrase="monthly revenue",
            sql_template="SELECT DATE_TRUNC('month', date) as month, SUM(amount) FROM sales GROUP BY 1",
            tables_used=["sales"],
            success_context={"version": 2, "improvement": "better performance"},
            context={"database": "sales_db"},
        )

        # 3. Agent marks the relationship
        await memory_tools.connect_memories(
            from_memory_id=improved_result.data["memory_id"],
            to_memory_id=initial_result.data["memory_id"],
            relationship_type="supersedes",
            strength=0.9,
            reason="Improved version with better performance",
        )

        # 4. Agent reflects on old pattern
        reflection = await memory_tools.reflect_on_memory(
            initial_result.data["memory_id"]
        )

        assert reflection.success is True
        assert len(reflection.data["relationships"]) >= 1

        # 5. Agent might decide to deprecate old pattern
        # (This would be agent's decision based on reflection)
        assert reflection.data["relationships"][0]["type"] == "supersedes"
