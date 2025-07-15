"""
Standard interface for pipeline components.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .executor import ExecutionResult
from .generator import GenerationResult
from .retriever import RetrievalResult
from .validator import ValidationResult


@dataclass
class PipelineContext:
    """Context passed through pipeline stages."""

    query: str
    session_id: Optional[str] = None
    datasource_id: Optional[str] = None
    use_cache: bool = True
    stream_events: bool = False
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PipelineResult:
    """Final result from pipeline execution."""

    success: bool
    sql: str
    execution_result: Optional[ExecutionResult] = None
    retrieval_result: Optional[RetrievalResult] = None
    generation_result: Optional[GenerationResult] = None
    validation_result: Optional[ValidationResult] = None
    total_time_ms: float = 0.0
    steps_timing: Optional[Dict[str, float]] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Pipeline(ABC):
    """
    Abstract base class for pipeline implementations.

    Pipelines orchestrate the flow from natural language query
    to executed results, coordinating retrieval, generation,
    validation, and execution components.
    """

    @abstractmethod
    async def process(self, context: PipelineContext, **kwargs) -> PipelineResult:
        """
        Process a natural language query through the pipeline.

        Args:
            context: Pipeline context with query and options
            **kwargs: Additional pipeline-specific parameters

        Returns:
            PipelineResult with all intermediate and final results
        """
        pass

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize pipeline components."""
        pass

    @abstractmethod
    async def close(self) -> None:
        """Clean up pipeline resources."""
        pass

    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """Get pipeline capabilities and features."""
        pass
