"""
LightRAG API Client for SENS Learning System

This module provides a clean API client for interacting with the LightRAG server,
replacing the old direct library integration.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

log = structlog.get_logger()


class LightRAGAPIClient:
    """Client for interacting with LightRAG server API."""

    def __init__(
        self, base_url: str = "http://127.0.0.1:9621", api_key: Optional[str] = None
    ):
        """
        Initialize the LightRAG API client.

        Args:
            base_url: Base URL of the LightRAG server
            api_key: Optional API key for authentication
        """
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def ensure_session(self):
        """Ensure aiohttp session is available."""
        if not self.session:
            self.session = aiohttp.ClientSession()

    async def check_health(self) -> Dict[str, Any]:
        """
        Check the health status of the LightRAG server.

        Returns:
            Dict containing health status information
        """
        await self.ensure_session()
        try:
            async with self.session.get(
                f"{self.base_url}/health", headers=self._get_headers()
            ) as response:
                return await response.json()
        except Exception as e:
            log.error("lightrag_health_check_failed", error=str(e))
            return {"status": "unhealthy", "error": str(e)}

    async def insert_text(
        self, text: str, file_source: str = "SENS Learning System"
    ) -> Dict[str, Any]:
        """
        Insert text into the LightRAG knowledge base.

        Args:
            text: The text content to insert
            file_source: Source identifier for the text

        Returns:
            Dict containing the insertion result
        """
        await self.ensure_session()
        try:
            payload = {"text": text, "file_source": file_source}

            async with self.session.post(
                f"{self.base_url}/documents/text",
                json=payload,
                headers=self._get_headers(),
            ) as response:
                result = await response.json()
                log.info(
                    "lightrag_text_inserted",
                    status=result.get("status"),
                    message=result.get("message"),
                )
                return result

        except Exception as e:
            log.error("lightrag_insert_failed", error=str(e))
            return {"status": "error", "message": str(e)}

    async def query(
        self,
        query: str,
        mode: str = "hybrid",
        only_need_context: bool = False,
        response_type: str = "Multiple Paragraphs",
        top_k: int = 60,
        conversation_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Query the LightRAG knowledge base.

        Args:
            query: The query text
            mode: Query mode (local, global, hybrid, naive, mix)
            only_need_context: If True, only return context without generating response
            response_type: Type of response format
            top_k: Number of top results to retrieve
            conversation_history: Optional conversation history

        Returns:
            Dict containing the query response
        """
        await self.ensure_session()
        try:
            payload = {
                "query": query,
                "mode": mode,
                "only_need_context": only_need_context,
                "response_type": response_type,
                "top_k": top_k,
            }

            if conversation_history:
                payload["conversation_history"] = conversation_history

            async with self.session.post(
                f"{self.base_url}/query", json=payload, headers=self._get_headers()
            ) as response:
                result = await response.json()
                log.debug(
                    "lightrag_query_completed",
                    query=query[:50] + "..." if len(query) > 50 else query,
                    mode=mode,
                )
                return result

        except Exception as e:
            log.error("lightrag_query_failed", error=str(e), query=query)
            return {"response": "", "error": str(e)}

    async def get_documents_status(self) -> Dict[str, Any]:
        """
        Get the status of all documents in the system.

        Returns:
            Dict containing document statuses grouped by status type
        """
        await self.ensure_session()
        try:
            async with self.session.get(
                f"{self.base_url}/documents", headers=self._get_headers()
            ) as response:
                return await response.json()
        except Exception as e:
            log.error("lightrag_documents_status_failed", error=str(e))
            return {"statuses": {}}

    async def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get the current status of the document processing pipeline.

        Returns:
            Dict containing pipeline status information
        """
        await self.ensure_session()
        try:
            async with self.session.get(
                f"{self.base_url}/documents/pipeline_status",
                headers=self._get_headers(),
            ) as response:
                return await response.json()
        except Exception as e:
            log.error("lightrag_pipeline_status_failed", error=str(e))
            return {"busy": False, "error": str(e)}

    async def get_graph_labels(self) -> List[str]:
        """
        Get all graph labels from the knowledge graph.

        Returns:
            List of graph labels
        """
        await self.ensure_session()
        try:
            async with self.session.get(
                f"{self.base_url}/graph/label/list", headers=self._get_headers()
            ) as response:
                return await response.json()
        except Exception as e:
            log.error("lightrag_graph_labels_failed", error=str(e))
            return []

    async def get_knowledge_graph(
        self, label: str, max_depth: int = 3, max_nodes: int = 1000
    ) -> Dict[str, Any]:
        """
        Get the knowledge graph for a specific label.

        Args:
            label: The label to get the graph for
            max_depth: Maximum depth of the graph
            max_nodes: Maximum number of nodes to return

        Returns:
            Dict containing the knowledge graph
        """
        await self.ensure_session()
        try:
            params = {"label": label, "max_depth": max_depth, "max_nodes": max_nodes}

            async with self.session.get(
                f"{self.base_url}/graphs", params=params, headers=self._get_headers()
            ) as response:
                return await response.json()
        except Exception as e:
            log.error("lightrag_knowledge_graph_failed", error=str(e), label=label)
            return {"nodes": [], "edges": []}
