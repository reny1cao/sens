"""Tests for the enhanced NL2SQL pipeline."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from sens.cli.enhanced_pipeline import EnhancedNL2SQLPipeline


@pytest.fixture
def mock_components():
    """Create mock components for pipeline."""
    components = {
        "retrieval_orchestrator": MagicMock(),
        "intent_extractor": MagicMock(),
        "sql_generator": MagicMock(),
        "sql_validator": MagicMock(),
        "response_builder": MagicMock(),
    }
    return components


@pytest.fixture
def pipeline(mock_components):
    """Create pipeline with mocked components."""
    with patch(
        "sens.cli.enhanced_pipeline.RetrievalOrchestrator",
        return_value=mock_components["retrieval_orchestrator"],
    ):
        with patch(
            "sens.cli.enhanced_pipeline.IntentExtractor",
            return_value=mock_components["intent_extractor"],
        ):
            with patch(
                "sens.cli.enhanced_pipeline.SQLGenerator",
                return_value=mock_components["sql_generator"],
            ):
                with patch(
                    "sens.cli.enhanced_pipeline.SQLValidator",
                    return_value=mock_components["sql_validator"],
                ):
                    with patch(
                        "sens.cli.enhanced_pipeline.ResponseBuilder",
                        return_value=mock_components["response_builder"],
                    ):
                        return EnhancedNL2SQLPipeline()


class TestEnhancedNL2SQLPipeline:
    """Test the enhanced NL2SQL pipeline."""

    @pytest.mark.asyncio
    async def test_pipeline_initialization(self):
        """Test pipeline initialization."""
        with patch("sens.cli.enhanced_pipeline.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock()

            pipeline = EnhancedNL2SQLPipeline()

            assert pipeline.retrieval_orchestrator is not None
            assert pipeline.intent_extractor is not None
            assert pipeline.sql_generator is not None
            assert pipeline.sql_validator is not None
            assert pipeline.response_builder is not None

    def test_run_success(self, pipeline, mock_components):
        """Test successful pipeline run."""
        # Set up mocks
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(
                tables=[MagicMock(table_name="users")],
                columns=[MagicMock(table_name="users", column_name="id")],
                format_for_llm=lambda: "TABLE users (id, name, email)",
            )
        )

        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(
                query_type="simple", confidence=0.95, tables=["users"]
            )
        )

        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(
                sql="SELECT * FROM users", confidence=0.93, tables_used=["users"]
            )
        )

        mock_components["sql_validator"].validate = MagicMock(
            return_value=MagicMock(is_valid=True, errors=[], warnings=[])
        )

        mock_components["response_builder"].build = MagicMock(
            return_value={
                "success": True,
                "sql": "SELECT * FROM users",
                "confidence": 0.93,
                "tables_used": ["users"],
                "intent": {"type": "simple", "confidence": 0.95},
            }
        )

        # Run pipeline
        result = pipeline.run("Show all users")

        # Verify result
        assert result["success"] is True
        assert result["sql"] == "SELECT * FROM users"
        assert result["confidence"] == 0.93

        # Verify components were called
        mock_components[
            "retrieval_orchestrator"
        ].get_relevant_context.assert_called_once()
        mock_components["intent_extractor"].extract.assert_called_once()
        mock_components["sql_generator"].generate.assert_called_once()

    def test_run_with_validation_disabled(self, pipeline, mock_components):
        """Test pipeline run without validation."""
        # Set up basic mocks
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(format_for_llm=lambda: "TABLE users (id)")
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(query_type="simple", confidence=0.9)
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(sql="SELECT * FROM users", confidence=0.9)
        )
        mock_components["response_builder"].build = MagicMock(
            return_value={"success": True, "sql": "SELECT * FROM users"}
        )

        # Run without validation
        result = pipeline.run("Show users", validate=False)

        # Validator should not be called
        mock_components["sql_validator"].validate.assert_not_called()
        assert result["success"] is True

    def test_run_retrieval_failure(self, pipeline, mock_components):
        """Test pipeline with retrieval failure."""
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            side_effect=Exception("Schema not available")
        )

        result = pipeline.run("Show data")

        assert result["success"] is False
        assert "error" in result
        assert "Schema not available" in result["error"]

    def test_run_intent_extraction_failure(self, pipeline, mock_components):
        """Test pipeline with intent extraction failure."""
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(format_for_llm=lambda: "TABLE users (id)")
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        result = pipeline.run("Complex query")

        assert result["success"] is False
        assert "LLM service unavailable" in result["error"]

    def test_run_sql_generation_failure(self, pipeline, mock_components):
        """Test pipeline with SQL generation failure."""
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(format_for_llm=lambda: "TABLE users (id)")
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(query_type="complex", confidence=0.8)
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(
                sql=None, error="Could not generate SQL", confidence=0.2
            )
        )

        result = pipeline.run("Unclear query")

        assert result["success"] is False
        assert "Could not generate SQL" in str(result.get("error", ""))

    def test_run_validation_failure(self, pipeline, mock_components):
        """Test pipeline with validation failure."""
        # Set up mocks for successful generation
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(format_for_llm=lambda: "TABLE users (id)")
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(query_type="simple", confidence=0.9)
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(sql="DELETE FROM users", confidence=0.95)
        )
        mock_components["sql_validator"].validate = MagicMock(
            return_value=MagicMock(
                is_valid=False, errors=["DELETE operations not allowed"], warnings=[]
            )
        )

        result = pipeline.run("Delete all users", validate=True)

        assert result["success"] is False
        assert "validation_errors" in result
        assert "DELETE operations not allowed" in result["validation_errors"]

    def test_run_with_explain(self, pipeline, mock_components):
        """Test pipeline with explain mode."""
        # Set up mocks
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(
                format_for_llm=lambda: "TABLE users (id, name)",
                tables=[MagicMock(table_name="users")],
            )
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(
                query_type="filter",
                confidence=0.92,
                reasoning="User wants to filter by name",
            )
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(
                sql="SELECT * FROM users WHERE name = 'John'",
                confidence=0.91,
                explanation="Filtering users table by name column",
            )
        )
        mock_components["response_builder"].build = MagicMock(
            return_value={
                "success": True,
                "sql": "SELECT * FROM users WHERE name = 'John'",
                "explanation": {
                    "intent_reasoning": "User wants to filter by name",
                    "sql_explanation": "Filtering users table by name column",
                },
            }
        )

        result = pipeline.run("Find users named John", explain=True)

        assert result["success"] is True
        assert "explanation" in result
        assert "intent_reasoning" in result["explanation"]

    def test_run_with_low_confidence(self, pipeline, mock_components):
        """Test pipeline with low confidence results."""
        mock_components["retrieval_orchestrator"].get_relevant_context = AsyncMock(
            return_value=MagicMock(format_for_llm=lambda: "TABLE users (id)")
        )
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(
                query_type="unknown",
                confidence=0.3,
                suggestions=["Please be more specific"],
            )
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(sql="SELECT * FROM users", confidence=0.4)
        )
        mock_components["response_builder"].build = MagicMock(
            return_value={
                "success": True,
                "sql": "SELECT * FROM users",
                "confidence": 0.4,
                "warnings": ["Low confidence result"],
                "suggestions": ["Please be more specific"],
            }
        )

        result = pipeline.run("Vague query")

        assert result["success"] is True
        assert result["confidence"] < 0.5
        assert "warnings" in result
        assert "suggestions" in result

    @pytest.mark.asyncio
    async def test_async_component_handling(self, pipeline, mock_components):
        """Test proper handling of async components."""

        # Create a future that resolves after a delay
        async def delayed_context():
            await asyncio.sleep(0.1)
            return MagicMock(format_for_llm=lambda: "TABLE test (id)")

        mock_components["retrieval_orchestrator"].get_relevant_context = delayed_context

        # Other async mocks
        mock_components["intent_extractor"].extract = AsyncMock(
            return_value=MagicMock(query_type="simple", confidence=0.9)
        )
        mock_components["sql_generator"].generate = AsyncMock(
            return_value=MagicMock(sql="SELECT * FROM test", confidence=0.9)
        )
        mock_components["response_builder"].build = MagicMock(
            return_value={"success": True, "sql": "SELECT * FROM test"}
        )

        # Run should handle async properly
        result = pipeline.run("Test query")
        assert result["success"] is True
