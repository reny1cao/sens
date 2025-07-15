"""
SENS Learning System (Legacy)

This module contains the legacy LightRAG API client that may still be used
for advanced semantic search capabilities. The main learning system has been
replaced with the agent-controlled memory system in sens.memory.
"""

from .lightrag_api_client import LightRAGAPIClient

__all__ = [
    "LightRAGAPIClient",
]
