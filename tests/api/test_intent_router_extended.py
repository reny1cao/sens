"""Extended tests for the intent router with realistic data."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sens.api.app_unified import app
from sens.api.models.intent import IntentRequest, IntentResponse, SchemaSnippet
from sens.api.routers.intent.router import format_schema_snippet
from sens.llm.models import Intent, QueryType


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_intent_extractor():
    """Create a mock intent extractor."""
    extractor = MagicMock()

    # Create async mock for extract method
    async def mock_extract(question, schema_snippet):
        return Intent(
            query_type=QueryType.AGGREGATE,
            confidence=0.95,
            tables=["orders", "customers"],
            operations=["COUNT", "GROUP BY"],
            reasoning="User wants to aggregate order amounts by customer",
        )

    extractor.extract = AsyncMock(side_effect=mock_extract)
    return extractor


@pytest.fixture
def sample_request():
    """Create a sample intent request."""
    return {
        "query": "What is the total amount of orders per customer?",
        "schema_snippets": [
            {
                "table_name": "orders",
                "columns": ["order_id", "customer_id", "total_amount", "order_date"],
                "description": "Customer orders table with order details",
            },
            {
                "table_name": "customers",
                "columns": ["customer_id", "name", "email", "join_date"],
                "description": "Customer information and metadata",
            },
        ],
        "context": {"source": "api_test"},
    }


class TestIntentRouter:
    """Test the intent extraction API endpoints."""

    def test_extract_intent_success(
        self, client, mock_intent_extractor, sample_request
    ):
        """Test successful intent extraction."""
        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=sample_request)

            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert "intent" in data
            assert "confidence" in data
            assert "relevant_tables" in data
            assert "operations" in data

            # Verify content
            assert data["intent"] == "aggregate"
            assert data["confidence"] == 0.95
            assert set(data["relevant_tables"]) == {"orders", "customers"}
            assert set(data["operations"]) == {"COUNT", "GROUP BY"}

            # Verify extractor was called correctly
            mock_intent_extractor.extract.assert_called_once()
            call_args = mock_intent_extractor.extract.call_args
            assert call_args[1]["question"] == sample_request["query"]
            assert "TABLE orders" in call_args[1]["schema_snippet"]
            assert "TABLE customers" in call_args[1]["schema_snippet"]

    def test_extract_intent_simple_query(self, client, mock_intent_extractor):
        """Test intent extraction with simple SELECT query."""

        async def mock_simple_extract(question, schema_snippet):
            return Intent(
                query_type=QueryType.SIMPLE,
                confidence=0.99,
                tables=["users"],
                operations=["SELECT"],
                reasoning="Simple data retrieval from users table",
            )

        mock_intent_extractor.extract = AsyncMock(side_effect=mock_simple_extract)

        request = {
            "query": "Show me all users",
            "schema_snippets": [
                {
                    "table_name": "users",
                    "columns": ["id", "name", "email"],
                    "description": "User accounts",
                }
            ],
        }

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=request)

            assert response.status_code == 200
            data = response.json()
            assert data["intent"] == "simple"
            assert data["confidence"] == 0.99
            assert data["relevant_tables"] == ["users"]

    def test_extract_intent_no_extractor(self, client, sample_request):
        """Test error when intent extractor is not available."""
        with patch("sens.api.routers.intent.router.intent_extractor_instance", None):
            response = client.post("/intent/extract", json=sample_request)

            assert response.status_code == 500
            assert "Intent Extractor unavailable" in response.json()["detail"]

    def test_extract_intent_validation_error(self, client, mock_intent_extractor):
        """Test handling of validation errors."""
        mock_intent_extractor.extract = AsyncMock(
            side_effect=ValueError("Invalid query format")
        )

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post(
                "/intent/extract",
                json={"query": "Invalid query", "schema_snippets": []},
            )

            assert response.status_code == 400
            assert "Invalid query format" in response.json()["detail"]

    def test_extract_intent_general_error(self, client, mock_intent_extractor):
        """Test handling of general errors."""
        mock_intent_extractor.extract = AsyncMock(
            side_effect=Exception("LLM service unavailable")
        )

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post(
                "/intent/extract", json={"query": "Test query", "schema_snippets": []}
            )

            assert response.status_code == 500
            assert "Internal server error" in response.json()["detail"]

    def test_extract_intent_empty_schema(self, client, mock_intent_extractor):
        """Test intent extraction with empty schema."""
        request = {"query": "Show me the data", "schema_snippets": []}

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=request)

            assert response.status_code == 200

            # Verify empty schema was passed
            call_args = mock_intent_extractor.extract.call_args
            assert call_args[1]["schema_snippet"] == ""

    def test_extract_intent_complex_schema(self, client, mock_intent_extractor):
        """Test intent extraction with complex schema."""
        request = {
            "query": "Calculate monthly revenue trends with customer segments",
            "schema_snippets": [
                {
                    "table_name": "sales",
                    "columns": ["id", "amount", "date", "customer_id"],
                    "description": "Sales transactions",
                },
                {
                    "table_name": "customers",
                    "columns": ["id", "name", "segment", "created_at"],
                    "description": "Customer data with segmentation",
                },
                {
                    "table_name": "products",
                    "columns": ["id", "name", "category", "price"],
                    "description": "Product catalog",
                },
            ],
            "context": {"analysis_type": "revenue"},
        }

        async def mock_complex_extract(question, schema_snippet):
            return Intent(
                query_type=QueryType.COMPLEX,
                confidence=0.88,
                tables=["sales", "customers"],
                operations=["GROUP BY", "DATE_TRUNC", "SUM", "JOIN"],
                reasoning="Complex time-series analysis with segmentation",
            )

        mock_intent_extractor.extract = AsyncMock(side_effect=mock_complex_extract)

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=request)

            assert response.status_code == 200
            data = response.json()
            assert data["intent"] == "complex"
            assert data["confidence"] == 0.88
            assert len(data["operations"]) == 4

    def test_get_sample_request(self, client):
        """Test getting sample request endpoint."""
        response = client.get("/intent/sample")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "query" in data
        assert "schema_snippets" in data
        assert "context" in data

        # Verify content
        assert data["query"] == "What is the total amount of orders per customer?"
        assert len(data["schema_snippets"]) == 2
        assert data["schema_snippets"][0]["table_name"] == "orders"
        assert data["context"]["mode"] == "test"

    def test_format_schema_snippet():
        """Test schema snippet formatting."""
        # Test with description
        snippet = SchemaSnippet(
            table_name="users",
            columns=["id", "name", "email"],
            description="User accounts table",
        )
        formatted = format_schema_snippet(snippet)
        assert formatted == "TABLE users (id, name, email); -- User accounts table"

        # Test without description
        snippet_no_desc = SchemaSnippet(
            table_name="orders", columns=["id", "amount"], description=None
        )
        formatted_no_desc = format_schema_snippet(snippet_no_desc)
        assert formatted_no_desc == "TABLE orders (id, amount);"

    def test_extract_intent_missing_fields(self, client):
        """Test validation for missing required fields."""
        # Missing query
        response = client.post("/intent/extract", json={"schema_snippets": []})
        assert response.status_code == 422

        # Missing schema_snippets
        response = client.post("/intent/extract", json={"query": "Test"})
        assert response.status_code == 422

    def test_extract_intent_invalid_schema_snippet(self, client):
        """Test validation for invalid schema snippet."""
        request = {
            "query": "Test query",
            "schema_snippets": [
                {
                    "table_name": "test",
                    # Missing required 'columns' field
                    "description": "Test table",
                }
            ],
        }

        response = client.post("/intent/extract", json=request)
        assert response.status_code == 422

    def test_extract_intent_with_special_characters(
        self, client, mock_intent_extractor
    ):
        """Test intent extraction with special characters."""
        request = {
            "query": "What's the avg(price) for items where name LIKE '%test%'?",
            "schema_snippets": [
                {
                    "table_name": "items",
                    "columns": ["id", "name", "price"],
                    "description": 'Item catalog with special chars: & < > "',
                }
            ],
        }

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=request)

            assert response.status_code == 200

            # Verify special characters were preserved
            call_args = mock_intent_extractor.extract.call_args
            assert "%" in call_args[1]["question"]
            assert "&" in call_args[1]["schema_snippet"]

    def test_extract_intent_rate_limiting(self, client, mock_intent_extractor):
        """Test that rate limiting is applied."""
        # This test verifies the rate_limiter dependency is present
        # Actual rate limiting behavior would require more complex testing
        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            with patch("sens.api.routers.intent.router.rate_limiter"):
                response = client.post(
                    "/intent/extract", json={"query": "Test", "schema_snippets": []}
                )

                assert response.status_code == 200

    def test_extract_intent_unicode(self, client, mock_intent_extractor):
        """Test intent extraction with unicode characters."""
        request = {
            "query": "显示所有用户订单",  # Chinese: Show all user orders
            "schema_snippets": [
                {
                    "table_name": "用户订单",
                    "columns": ["订单ID", "用户ID", "金额"],
                    "description": "用户订单表",
                }
            ],
        }

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):
            response = client.post("/intent/extract", json=request)

            assert response.status_code == 200

            # Verify unicode was handled correctly
            call_args = mock_intent_extractor.extract.call_args
            assert "显示所有用户订单" in call_args[1]["question"]
            assert "用户订单" in call_args[1]["schema_snippet"]

    def test_concurrent_intent_extraction(self, client, mock_intent_extractor):
        """Test handling of concurrent intent extraction requests."""
        from concurrent.futures import ThreadPoolExecutor

        request_template = {
            "query": "Query {}",
            "schema_snippets": [
                {
                    "table_name": "table{}",
                    "columns": ["col1", "col2"],
                    "description": "Test table {}",
                }
            ],
        }

        with patch(
            "sens.api.routers.intent.router.intent_extractor_instance",
            mock_intent_extractor,
        ):

            def make_request(i):
                request = {
                    "query": request_template["query"].format(i),
                    "schema_snippets": [
                        {
                            "table_name": s["table_name"].format(i),
                            "columns": s["columns"],
                            "description": s["description"].format(i),
                        }
                        for s in request_template["schema_snippets"]
                    ],
                }
                return client.post("/intent/extract", json=request)

            # Make multiple concurrent requests
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_request, i) for i in range(5)]
                responses = [f.result() for f in futures]

            # All should succeed
            for response in responses:
                assert response.status_code == 200

            # Verify all calls were made
            assert mock_intent_extractor.extract.call_count == 5
