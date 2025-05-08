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
from sens.retrieval.token.builder import TokenIndexBuilder
from sens.schema.graph import SchemaGraph
from sens.schema.schema_extractor import DatabaseSchema, SchemaExtractor

# Configure structured logging
log = structlog.get_logger()


class TokenIndexCLIAdapter:
    """Adapter for TokenIndex operations in CLI context."""

    def __init__(self):
        """Initialize the token index adapter."""
        self.builder = TokenIndexBuilder()
        self.index = None
        self.schema_graph = SchemaGraph.get_instance()

    async def initialize(self):
        """Build or load the token index."""
        try:
            # Get table names from schema graph
            table_names = self.schema_graph.list_all_tables()
            # Run synchronous build_index in a thread pool
            self.builder.build_index(table_names)
            self.index = self.builder.index
            log.info("token_index_initialized", table_count=len(table_names))
        except Exception as e:
            log.error("token_index_initialization_failed", error=str(e))
            raise RuntimeError(f"Failed to initialize token index: {e}")

    async def search(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        """Search the token index for relevant columns."""
        if not self.index:
            raise RuntimeError("Token index not initialized")

        # Convert token matches to RetrievedColumn objects
        results = []
        for table_name, score in self.index.search(query, k=k):
            results.append(
                RetrievedColumn(
                    table_name=table_name,
                    column_name="*",  # Token index matches are at table level
                    score=score,
                    source="token",
                )
            )
        return results


class EmbeddingSearchCLIAdapter:
    """Adapter for EmbeddingSearch operations in CLI context."""

    def __init__(self):
        """Initialize the embedding search adapter."""
        self.search = EmbeddingSearch()

    async def initialize(self):
        """Initialize the embedding search index."""
        try:
            self.search.load_index()
            log.info("embedding_search_initialized")
        except Exception as e:
            log.error("embedding_search_initialization_failed", error=str(e))
            raise RuntimeError(f"Failed to initialize embedding search: {e}")

    async def search_similar(self, query: str, k: int = 5) -> List[RetrievedColumn]:
        """Search for semantically similar columns."""
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
        return results


class NL2SQLPipeline:
    """Pipeline for converting natural language to SQL queries."""

    def __init__(self):
        """Initialize pipeline components."""
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

            log.info("pipeline_initialized")

        except Exception as e:
            log.error("pipeline_initialization_failed", error=str(e))
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
            log.info("retrieving_schema_context", question=question)
            context = await self.orchestrator.get_relevant_context(
                question=question, k=k
            )

            # Format schema for LLM using the loaded schema data
            schema_snippet = self.schema_extractor.format_for_llm(
                schema=self.schema_data,
                tables={table.table_name for table in context.tables},
            )

            # Step 2: Intent Extraction
            log.info("extracting_intent")
            intent = await self.intent_extractor.extract(
                question=question, schema_snippet=schema_snippet
            )

            # Step 3: Intent Validation
            log.info("validating_intent")
            validation_result = self.intent_validator.validate(intent)
            if isinstance(validation_result, ClarificationRequest):
                return {
                    "status": "clarification_needed",
                    "message": validation_result.message,
                    "reason": validation_result.reason,
                }

            # Step 4: SQL Generation
            log.info("generating_sql")
            start_time = time.time()
            sql_result = await self.sql_generator.generate(
                question=question,
                intent=validation_result,  # validation_result is ValidIntent here
            )

            # Step 5: Execute SQL
            log.info("executing_sql", sql=sql_result.sql)
            query_result = self.sql_executor.execute(sql_result.sql)
            execution_time_ms = (time.time() - start_time) * 1000

            if query_result.error:
                return {
                    "status": "error",
                    "message": f"Query execution failed: {query_result.error}",
                    "sql": sql_result.sql,
                }

            # Step 6: Build Response
            log.info("building_response")
            response = self.response_builder.build(
                question=question,
                intent=intent,
                result=query_result,
                sql=sql_result.sql,
                execution_time_ms=execution_time_ms,
            )

            return {
                "status": "success",
                "summary": response.summary,
                "sql": sql_result.sql,
                "result": {
                    "preview": response.table_preview,
                    "row_count": response.row_count,
                    "columns": query_result.columns,
                },
                "metadata": {
                    "tables_used": sql_result.tables_used,
                    "columns_used": sql_result.columns_used,
                    "model_used": sql_result.model_used,
                    "generation_ms": sql_result.generation_ms,
                    "execution_ms": execution_time_ms,
                    "token_usage": (
                        sql_result.token_usage.model_dump()
                        if sql_result.token_usage
                        else None
                    ),
                    "intent_type": intent.query_type,
                    "tables": intent.tables,
                    "operations": intent.operations,
                    "confidence": intent.confidence,
                    "generated_at": response.generated_at,
                },
            }

        except Exception as e:
            log.error("pipeline_processing_failed", error=str(e))
            return {"status": "error", "message": str(e)}


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
