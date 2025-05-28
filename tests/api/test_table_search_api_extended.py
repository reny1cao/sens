"""Extended tests for the table search API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from sens.api.app import app
from sens.api.routers.table_search.models import (
    DetailedIndexResponse,
    IndexStatsResponse,
    RefreshResponse,
    TableSearchResponse,
)
from sens.api.routers.table_search.service import TableSearchService


@pytest.fixture
def client():
    """Create a test client for the API."""
    return TestClient(app)


@pytest.fixture
def mock_service():
    """Create a mock table search service."""
    service = MagicMock(spec=TableSearchService)

    # Set up default return values
    service.search_tables.return_value = {
        "query": "users",
        "results": [
            {
                "table_name": "users",
                "score": 1.0,
                "matched_tokens": ["users"],
                "match_type": "exact",
            },
            {
                "table_name": "user_profiles",
                "score": 0.8,
                "matched_tokens": ["user"],
                "match_type": "partial",
            },
        ],
        "total_results": 2,
        "search_time_ms": 12.5,
    }

    service.get_index_stats.return_value = {
        "total_tables": 50,
        "total_tokens": 250,
        "avg_tokens_per_table": 5.0,
        "index_size_kb": 128.5,
        "last_updated": "2024-01-15T10:30:00Z",
    }

    service.get_detailed_index.return_value = {
        "tables": [
            {"table_name": "users", "tokens": ["users", "user"], "token_count": 2},
            {"table_name": "orders", "tokens": ["orders", "order"], "token_count": 2},
        ],
        "token_frequencies": {"users": 1, "user": 5, "orders": 1, "order": 3},
        "metadata": {"version": "1.0", "created_at": "2024-01-15T09:00:00Z"},
    }

    service.refresh_index.return_value = {
        "success": True,
        "message": "Index refreshed successfully",
        "tables_added": 2,
        "tables_removed": 0,
        "tables_updated": 5,
        "refresh_time_ms": 245.8,
    }

    return service


class TestTableSearchAPI:
    """Test the table search API endpoints."""

    def test_search_tables_success(self, client, mock_service):
        """Test successful table search."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=users&limit=10")

            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert "query" in data
            assert "results" in data
            assert "total_results" in data
            assert "search_time_ms" in data

            # Verify content
            assert data["query"] == "users"
            assert len(data["results"]) == 2
            assert data["results"][0]["table_name"] == "users"
            assert data["results"][0]["score"] == 1.0
            assert data["results"][0]["match_type"] == "exact"

            # Verify service was called correctly
            mock_service.search_tables.assert_called_once_with("users", 10)

    def test_search_tables_default_limit(self, client, mock_service):
        """Test table search with default limit."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=products")

            assert response.status_code == 200

            # Verify default limit=10 was used
            mock_service.search_tables.assert_called_once_with("products", 10)

    def test_search_tables_empty_query(self, client, mock_service):
        """Test table search with empty query."""
        mock_service.search_tables.return_value = {
            "query": "",
            "results": [],
            "total_results": 0,
            "search_time_ms": 0.5,
        }

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=")

            assert response.status_code == 200
            data = response.json()
            assert data["results"] == []
            assert data["total_results"] == 0

    def test_search_tables_special_characters(self, client, mock_service):
        """Test table search with special characters."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=user%2Borders&limit=5")

            assert response.status_code == 200
            mock_service.search_tables.assert_called_with("user/orders", 5)

    def test_search_tables_large_limit(self, client, mock_service):
        """Test table search with large limit."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=test&limit=1000")

            assert response.status_code == 200
            mock_service.search_tables.assert_called_with("test", 1000)

    def test_search_tables_service_error(self, client, mock_service):
        """Test error handling when service fails."""
        mock_service.search_tables.side_effect = Exception("Index corrupted")

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=test")

            assert response.status_code == 500
            assert "Index corrupted" in response.json()["detail"]

    def test_get_index_stats_success(self, client, mock_service):
        """Test successful index stats retrieval."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/stats")

            assert response.status_code == 200
            data = response.json()

            # Verify structure and content
            assert data["total_tables"] == 50
            assert data["total_tokens"] == 250
            assert data["avg_tokens_per_table"] == 5.0
            assert data["index_size_kb"] == 128.5
            assert data["last_updated"] == "2024-01-15T10:30:00Z"

            mock_service.get_index_stats.assert_called_once()

    def test_get_index_stats_error(self, client, mock_service):
        """Test error handling for index stats."""
        mock_service.get_index_stats.side_effect = Exception("Stats unavailable")

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/stats")

            assert response.status_code == 500
            assert "Stats unavailable" in response.json()["detail"]

    def test_get_index_structure_success(self, client, mock_service):
        """Test successful index structure retrieval."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/structure")

            assert response.status_code == 200
            data = response.json()

            # Verify structure
            assert "tables" in data
            assert "token_frequencies" in data
            assert "metadata" in data

            # Verify content
            assert len(data["tables"]) == 2
            assert data["tables"][0]["table_name"] == "users"
            assert data["tables"][0]["tokens"] == ["users", "user"]
            assert data["token_frequencies"]["user"] == 5
            assert data["metadata"]["version"] == "1.0"

            mock_service.get_detailed_index.assert_called_once()

    def test_get_index_structure_empty(self, client, mock_service):
        """Test index structure with empty index."""
        mock_service.get_detailed_index.return_value = {
            "tables": [],
            "token_frequencies": {},
            "metadata": {"version": "1.0"},
        }

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/structure")

            assert response.status_code == 200
            data = response.json()
            assert data["tables"] == []
            assert data["token_frequencies"] == {}

    def test_refresh_index_success(self, client, mock_service):
        """Test successful index refresh."""
        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.post("/table-search/refresh")

            assert response.status_code == 200
            data = response.json()

            # Verify response
            assert data["success"] is True
            assert data["message"] == "Index refreshed successfully"
            assert data["tables_added"] == 2
            assert data["tables_removed"] == 0
            assert data["tables_updated"] == 5
            assert data["refresh_time_ms"] == 245.8

            mock_service.refresh_index.assert_called_once()

    def test_refresh_index_partial_failure(self, client, mock_service):
        """Test index refresh with partial failure."""
        mock_service.refresh_index.return_value = {
            "success": False,
            "message": "Index refresh partially failed",
            "tables_added": 1,
            "tables_removed": 0,
            "tables_updated": 3,
            "refresh_time_ms": 180.2,
            "errors": ["Failed to process table 'invalid_table'"],
        }

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.post("/table-search/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is False
            assert "partially failed" in data["message"]

    def test_refresh_index_error(self, client, mock_service):
        """Test error handling for index refresh."""
        mock_service.refresh_index.side_effect = Exception("Schema file not found")

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.post("/table-search/refresh")

            assert response.status_code == 500
            assert "Schema file not found" in response.json()["detail"]

    def test_service_singleton(self, client):
        """Test that service uses singleton pattern."""
        from sens.api.routers.table_search.router import get_service

        # Mock the singleton method
        with patch.object(TableSearchService, "get_instance") as mock_get_instance:
            mock_instance = MagicMock()
            mock_get_instance.return_value = mock_instance

            # Call get_service multiple times
            service1 = get_service()
            service2 = get_service()

            # Should return same instance
            assert service1 is service2
            assert service1 is mock_instance

            # get_instance should be called multiple times (no caching in get_service)
            assert mock_get_instance.call_count == 2

    def test_concurrent_searches(self, client, mock_service):
        """Test handling of concurrent search requests."""
        from concurrent.futures import ThreadPoolExecutor

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):

            def make_search(query):
                return client.get(f"/table-search/search?query={query}")

            # Make multiple concurrent requests
            queries = ["users", "orders", "products", "customers", "transactions"]
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [executor.submit(make_search, q) for q in queries]
                responses = [f.result() for f in futures]

            # All should succeed
            for response in responses:
                assert response.status_code == 200

            # Verify all calls were made
            assert mock_service.search_tables.call_count == 5

    def test_search_response_validation(self, client, mock_service):
        """Test that invalid service responses are handled."""
        # Return invalid response (missing required field)
        mock_service.search_tables.return_value = {
            "query": "test",
            "results": [{"invalid": "data"}],  # Missing required fields
            # Missing total_results and search_time_ms
        }

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get("/table-search/search?query=test")

            # Should get validation error
            assert response.status_code == 500

    def test_search_with_unicode(self, client, mock_service):
        """Test search with unicode characters."""
        unicode_query = "用户订单"
        mock_service.search_tables.return_value = {
            "query": unicode_query,
            "results": [],
            "total_results": 0,
            "search_time_ms": 5.5,
        }

        with patch(
            "sens.api.routers.table_search.router.get_service",
            return_value=mock_service,
        ):
            response = client.get(f"/table-search/search?query={unicode_query}")

            assert response.status_code == 200
            data = response.json()
            assert data["query"] == unicode_query
