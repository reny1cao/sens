"""
Factory functions for creating components with proper configuration.
"""

import logging

from ..interfaces import Pipeline, QueryExecutor, Retriever, SQLGenerator, Validator
from ..settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RetrieverFactory:
    """Factory for creating retriever instances."""

    @staticmethod
    def create_token_retriever(**kwargs) -> Retriever:
        """Create a token-based retriever."""
        from ..retrieval.token import TokenIndex
        from ..retrieval.token_retriever_adapter import TokenRetrieverAdapter

        # Create token index
        token_index = TokenIndex()

        # Wrap in adapter to implement Retriever interface
        return TokenRetrieverAdapter(token_index, **kwargs)

    @staticmethod
    def create_embedding_retriever(**kwargs) -> Retriever:
        """Create an embedding-based retriever."""
        from ..retrieval.embedding import EmbeddingSearch
        from ..retrieval.embedding_retriever_adapter import EmbeddingRetrieverAdapter

        # Get configuration
        model_name = kwargs.get("model_name", "all-MiniLM-L6-v2")
        index_dir = kwargs.get("index_dir", "embedding_index")

        # Create embedding search
        embedding_search = EmbeddingSearch(model_name=model_name, index_dir=index_dir)

        # Wrap in adapter
        return EmbeddingRetrieverAdapter(embedding_search, **kwargs)

    @staticmethod
    def create_hybrid_retriever(**kwargs) -> Retriever:
        """Create a hybrid retriever combining token and embedding."""
        from ..retrieval.hybrid_retriever import HybridRetriever

        # Create sub-retrievers
        token_retriever = RetrieverFactory.create_token_retriever()
        embedding_retriever = RetrieverFactory.create_embedding_retriever()

        return HybridRetriever(
            token_retriever=token_retriever,
            embedding_retriever=embedding_retriever,
            **kwargs,
        )


class GeneratorFactory:
    """Factory for creating SQL generator instances."""

    @staticmethod
    def create_openrouter_generator(**kwargs) -> SQLGenerator:
        """Create an OpenRouter-based SQL generator."""
        from ..generation.openrouter_generator import OpenRouterGenerator

        return OpenRouterGenerator(
            api_key=kwargs.get("api_key", settings.openrouter_api_key),
            base_url=kwargs.get("base_url", settings.openrouter_base_url),
            model=kwargs.get("model", settings.openrouter_default_model),
            **kwargs,
        )

    @staticmethod
    def create_local_generator(**kwargs) -> SQLGenerator:
        """Create a local model SQL generator."""
        # Placeholder for local model implementation
        raise NotImplementedError("Local SQL generator not yet implemented")


class ValidatorFactory:
    """Factory for creating validator instances."""

    @staticmethod
    def create_sql_validator(**kwargs) -> Validator:
        """Create a SQL validator."""
        from ..validation.sql_validator import SQLValidator
        from ..validation.validator_adapter import ValidatorAdapter

        # Create base validator
        sql_validator = SQLValidator()

        # Wrap in adapter
        return ValidatorAdapter(sql_validator, **kwargs)

    @staticmethod
    def create_safety_validator(**kwargs) -> Validator:
        """Create a safety-focused validator."""
        from ..validation.safety_validator import SafetyValidator

        return SafetyValidator(**kwargs)


class ExecutorFactory:
    """Factory for creating query executor instances."""

    @staticmethod
    def create_postgres_executor(**kwargs) -> QueryExecutor:
        """Create a PostgreSQL executor."""
        from ..execution.postgres_executor import PostgresExecutor

        return PostgresExecutor(
            connection_string=kwargs.get("connection_string", settings.db_url), **kwargs
        )

    @staticmethod
    def create_session_executor(**kwargs) -> QueryExecutor:
        """Create a session-aware executor."""
        from ..execution.session_aware import SessionAwareExecutor

        return SessionAwareExecutor(**kwargs)


class PipelineFactory:
    """Factory for creating pipeline instances."""

    @staticmethod
    def create_sequential_pipeline(**kwargs) -> Pipeline:
        """Create a sequential pipeline."""
        from ..pipeline.sequential import SequentialPipeline
        from .component_registry import component_registry

        # Get components from registry or create defaults
        retriever = kwargs.get("retriever") or component_registry.get_by_type(
            "retriever"
        )
        generator = kwargs.get("generator") or component_registry.get_by_type(
            "generator"
        )
        validator = kwargs.get("validator") or component_registry.get_by_type(
            "validator"
        )
        executor = kwargs.get("executor") or component_registry.get_by_type("executor")

        return SequentialPipeline(
            retriever=retriever,
            generator=generator,
            validator=validator,
            executor=executor,
            **kwargs,
        )

    @staticmethod
    def create_agent_pipeline(**kwargs) -> Pipeline:
        """Create an agent-based pipeline."""
        from ..pipeline.agent import AgentPipeline

        return AgentPipeline(**kwargs)

    @staticmethod
    def create_orchestrator_pipeline(**kwargs) -> Pipeline:
        """Create a ChatOrchestrator-based pipeline."""
        from ..chat.orchestrator import ChatOrchestrator
        from ..pipeline.orchestrator import OrchestratorPipeline

        # Create or get orchestrator
        orchestrator = kwargs.get("orchestrator") or ChatOrchestrator()

        return OrchestratorPipeline(orchestrator=orchestrator, **kwargs)
