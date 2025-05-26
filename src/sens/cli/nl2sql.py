#!/usr/bin/env python3
"""CLI tool for natural language to SQL conversion.

This module provides a command-line interface for converting natural language questions
into SQL queries using the Sens pipeline components.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import structlog

from sens.execution import SQLExecutor
from sens.llm.intent_extractor import IntentExtractor
from sens.llm.intent_validator import ClarificationRequest, IntentValidator
from sens.llm.sql_generator import SQLGenerator
from sens.postprocessing.response_builder import ResponseBuilder
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.retrieval.models import RetrievedColumn
from sens.retrieval.orchestrator import RetrievalOrchestrator
from sens.retrieval.token.enhanced_builder import EnhancedTokenIndexBuilder
from sens.retrieval.token.enhanced_models import SchemaItem
from sens.schema.graph import SchemaGraph
from sens.schema.schema_extractor import DatabaseSchema, SchemaExtractor
from sens.settings import get_settings

# Configure structured logging
log = structlog.get_logger(__name__)


class TokenIndexCLIAdapter:
    """Adapter for TokenIndex operations in CLI context."""

    def __init__(self):
        """Initialize the token index adapter."""
        self.builder = EnhancedTokenIndexBuilder()  # Use enhanced builder
        self.index = None
        self.schema_graph = SchemaGraph.get_instance()
        self.settings = get_settings()

    async def initialize(self):
        """Build or load the token index."""
        try:
            # Get schema information from schema graph
            table_names = self.schema_graph.list_all_tables()

            # Create schema items list
            schema_items = []

            # Add tables
            for table_name in table_names:
                schema_items.append(
                    SchemaItem(
                        name=table_name,
                        item_type="table",
                    )
                )

                # Add columns for each table
                columns = self.schema_graph.get_table_columns(table_name)
                for column_name in columns:
                    schema_items.append(
                        SchemaItem(
                            name=column_name,
                            item_type="column",
                            parent_table=table_name,
                            metadata={
                                "is_pk": column_name
                                in self.schema_graph.get_table_pks(table_name),
                                "is_fk": column_name
                                in self.schema_graph.get_table_fks_involved(
                                    table_name, table_names
                                ),
                            },
                        )
                    )

            # Build the enhanced index
            self.builder.build_index(schema_items)
            self.index = self.builder.index

            log.info(
                "token_index_initialized",
                table_count=len(table_names),
                column_count=len(
                    [item for item in schema_items if item.item_type == "column"]
                ),
                environment=self.settings.environment,
            )

        except Exception as e:
            log.error(
                "token_index_initialization_failed",
                error=str(e),
                error_type=e.__class__.__name__,
                environment=self.settings.environment,
            )
            raise RuntimeError(f"Failed to initialize token index: {e}")

    async def search(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        """Search the token index for relevant columns and tables."""
        if not self.index:
            raise RuntimeError("Token index not initialized")

        log.debug(
            "token_index_search",
            query=query,
            k=k,
            environment=self.settings.environment,
        )

        # Use the enhanced search functionality
        matches = self.builder.search(query, k=k)

        # Convert TokenMatch objects to RetrievedColumn objects
        results = []
        for match in matches:
            results.append(
                RetrievedColumn(
                    table_name=match.table_name,
                    column_name=match.column_name
                    or "*",  # Use "*" for table-level matches
                    score=match.score,
                    source="token",
                    metadata={
                        "match_type": match.match_type,
                        "token_overlap": match.token_overlap,
                    },
                )
            )

        log.debug(
            "token_index_search_complete",
            result_count=len(results),
            match_types={r.metadata["match_type"]: r.score for r in results},
            environment=self.settings.environment,
        )
        return results


class EmbeddingSearchCLIAdapter:
    """Adapter for EmbeddingSearch operations in CLI context."""

    def __init__(self):
        """Initialize the embedding search adapter."""
        self.search = EmbeddingSearch()
        self.settings = get_settings()

    async def initialize(self):
        """Initialize the embedding search index."""
        try:
            self.search.load_index()
            log.info(
                "embedding_search_initialized",
                environment=self.settings.environment,
            )
        except Exception as e:
            log.error(
                "embedding_search_initialization_failed",
                error=str(e),
                error_type=e.__class__.__name__,
                environment=self.settings.environment,
            )
            raise RuntimeError(f"Failed to initialize embedding search: {e}")

    async def search_similar(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        """Search for semantically similar columns."""
        log.debug(
            "embedding_search",
            query=query,
            k=k,
            environment=self.settings.environment,
        )

        # Convert embedding search results to RetrievedColumn objects
        results = []
        for table_name, column_name, score in self.search.search(query, k=k):
            results.append(
                RetrievedColumn(
                    table_name=table_name,
                    column_name=column_name,
                    score=score,
                    source="embedding",
                )
            )

        log.debug(
            "embedding_search_complete",
            result_count=len(results),
            environment=self.settings.environment,
        )
        return results


class NL2SQLPipeline:
    """Pipeline for converting natural language to SQL queries."""

    def __init__(self):
        """Initialize pipeline components."""
        self.settings = get_settings()
        self.schema_graph = SchemaGraph.get_instance()
        self.schema_extractor = SchemaExtractor()
        self.token_index = TokenIndexCLIAdapter()
        self.embedding_search = EmbeddingSearchCLIAdapter()
        self.intent_extractor = IntentExtractor()
        self.intent_validator = IntentValidator()
        self.sql_generator = SQLGenerator()
        self.sql_executor = SQLExecutor()
        self.response_builder = ResponseBuilder()

        # Initialize orchestrator after adapters are ready
        self.orchestrator = None
        # Will be loaded during initialization
        self.schema_data = None

        log.info(
            "nl2sql_pipeline_created",
            environment=self.settings.environment,
        )

    async def initialize(self):
        """Initialize all pipeline components."""
        try:
            # Initialize search components
            await self.token_index.initialize()
            await self.embedding_search.initialize()

            # Create orchestrator with initialized components
            self.orchestrator = RetrievalOrchestrator(
                token_index=self.token_index,
                embedding_index=self.embedding_search,
                schema_graph=self.schema_graph,
            )

            # Load schema from the same file used by SchemaGraph
            self.schema_data = DatabaseSchema.model_validate_json(
                Path(self.schema_graph.schema_path).read_text()
            )

            log.info(
                "pipeline_initialized",
                schema_path=str(self.schema_graph.schema_path),
                environment=self.settings.environment,
            )

        except Exception as e:
            log.error(
                "pipeline_initialization_failed",
                error=str(e),
                error_type=e.__class__.__name__,
                environment=self.settings.environment,
            )
            raise RuntimeError(f"Failed to initialize pipeline: {e}")

    async def process_question(self, question: str, k: int = 5) -> Dict:
        """
        Process a natural language question through the pipeline.

        Args:
            question: The natural language question
            k: Number of top results to retrieve

        Returns:
            Dictionary containing the pipeline results
        """
        try:
            # Step 1: Schema Retrieval
            log.info(
                "retrieving_schema_context",
                question=question,
                k=k,
                environment=self.settings.environment,
            )
            context = await self.orchestrator.get_relevant_context(
                question=question, k=k
            )

            # Format schema for LLM using the loaded schema data
            schema_snippet = self.schema_extractor.format_for_llm(
                schema=self.schema_data,
                tables={table.table_name for table in context.tables},
            )

            # Step 2: Intent Extraction
            log.info(
                "extracting_intent",
                question=question,
                environment=self.settings.environment,
            )
            intent = await self.intent_extractor.extract(
                question=question, schema_snippet=schema_snippet
            )

            # Step 3: Intent Validation
            log.info(
                "validating_intent",
                question=question,
                environment=self.settings.environment,
            )
            validation_result = self.intent_validator.validate(intent)
            if isinstance(validation_result, ClarificationRequest):
                log.info(
                    "clarification_needed",
                    reason=validation_result.reason,
                    message=validation_result.message,
                    environment=self.settings.environment,
                )
                return {
                    "status": "clarification_needed",
                    "message": validation_result.message,
                    "reason": validation_result.reason,
                }

            # Step 4: SQL Generation - only proceed if we have a ValidIntent
            log.info(
                "generating_sql",
                question=question,
                environment=self.settings.environment,
            )
            start_time = time.time()
            sql_result = await self.sql_generator.generate(
                question=question,
                intent=validation_result,  # validation_result is ValidIntent here
            )

            # Log successful completion
            log.info(
                "question_processed",
                question=question,
                duration=time.time() - start_time,
                environment=self.settings.environment,
            )

            return sql_result

        except Exception as e:
            log.error(
                "question_processing_failed",
                error=str(e),
                error_type=e.__class__.__name__,
                question=question,
                environment=self.settings.environment,
            )
            raise


async def main():
    """Main CLI entrypoint."""
    parser = argparse.ArgumentParser(
        description="Convert natural language questions to SQL queries."
    )
    parser.add_argument(
        "--question",
        "-q",
        type=str,
        required=True,
        help="Natural language question to convert to SQL",
    )
    parser.add_argument(
        "--k",
        type=int,
        default=5,
        help="Number of top results to retrieve (default: 5)",
    )
    args = parser.parse_args()

    try:
        # Initialize pipeline
        pipeline = NL2SQLPipeline()
        await pipeline.initialize()

        # Process question
        result = await pipeline.process_question(question=args.question, k=args.k)

        # Print result as formatted JSON
        print(json.dumps(result, indent=2))

        # Exit with appropriate status code
        sys.exit(0 if result["status"] == "success" else 1)

    except Exception as e:
        log.error("cli_execution_failed", error=str(e))
        print(json.dumps({"status": "error", "message": str(e)}, indent=2))
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
