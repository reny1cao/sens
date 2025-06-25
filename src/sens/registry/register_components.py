"""
Register default components in the component registry.

This module is called during application startup to register
all available component implementations.
"""

import structlog

from .component_registry import ComponentType, component_registry
from .factories import (
    ExecutorFactory,
    GeneratorFactory,
    PipelineFactory,
    RetrieverFactory,
    ValidatorFactory,
)

logger = structlog.get_logger(__name__)


def register_default_components():
    """Register all default component implementations."""

    # Register Retrievers
    component_registry.register(
        name="token_retriever",
        component_type=ComponentType.RETRIEVER,
        implementation_class=type("TokenRetriever", (), {}),  # Placeholder
        factory=RetrieverFactory.create_token_retriever,
        singleton=True,
        config={},
    )

    component_registry.register(
        name="embedding_retriever",
        component_type=ComponentType.RETRIEVER,
        implementation_class=type("EmbeddingRetriever", (), {}),  # Placeholder
        factory=RetrieverFactory.create_embedding_retriever,
        singleton=True,
        config={},
    )

    component_registry.register(
        name="hybrid_retriever",
        component_type=ComponentType.RETRIEVER,
        implementation_class=type("HybridRetriever", (), {}),  # Placeholder
        factory=RetrieverFactory.create_hybrid_retriever,
        singleton=True,
        config={},
    )

    # Register Generators
    component_registry.register(
        name="openrouter_generator",
        component_type=ComponentType.GENERATOR,
        implementation_class=type("OpenRouterGenerator", (), {}),  # Placeholder
        factory=GeneratorFactory.create_openrouter_generator,
        singleton=True,
        config={},
    )

    # Register Validators
    component_registry.register(
        name="sql_validator",
        component_type=ComponentType.VALIDATOR,
        implementation_class=type("SQLValidator", (), {}),  # Placeholder
        factory=ValidatorFactory.create_sql_validator,
        singleton=True,
        config={},
    )

    # Register Executors
    component_registry.register(
        name="postgres_executor",
        component_type=ComponentType.EXECUTOR,
        implementation_class=type("PostgresExecutor", (), {}),  # Placeholder
        factory=ExecutorFactory.create_postgres_executor,
        singleton=True,
        config={},
    )

    # Register Pipelines
    from ..pipeline.orchestrator import OrchestratorPipeline

    component_registry.register(
        name="orchestrator_pipeline",
        component_type=ComponentType.PIPELINE,
        implementation_class=OrchestratorPipeline,
        factory=PipelineFactory.create_orchestrator_pipeline,
        singleton=False,  # New instance per request for session handling
        config={},
    )

    logger.info(
        "default_components_registered", count=len(component_registry.list_components())
    )
