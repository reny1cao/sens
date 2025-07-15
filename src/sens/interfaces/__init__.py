"""
Standard interfaces for SENS components.

These interfaces define contracts that all implementations must follow,
enabling component substitution and reducing coupling.
"""

from .executor import ExecutionContext, ExecutionResult, QueryExecutor
from .generator import GenerationContext, GenerationResult, SQLGenerator
from .pipeline import Pipeline, PipelineContext, PipelineResult
from .retriever import RetrievalResult, RetrievalStrategy, Retriever
from .validator import ValidationLevel, ValidationResult, Validator

__all__ = [
    # Retriever
    "Retriever",
    "RetrievalResult",
    "RetrievalStrategy",
    # Generator
    "SQLGenerator",
    "GenerationResult",
    "GenerationContext",
    # Validator
    "Validator",
    "ValidationResult",
    "ValidationLevel",
    # Executor
    "QueryExecutor",
    "ExecutionResult",
    "ExecutionContext",
    # Pipeline
    "Pipeline",
    "PipelineResult",
    "PipelineContext",
]
