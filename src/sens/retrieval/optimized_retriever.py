"""Optimized schema retriever using pre-computed indexes.

This module provides an optimized version of schema retrieval that leverages
pre-computed indexes for faster performance.
"""

import time
from datetime import timedelta
from typing import Dict, List, Optional, Set, Tuple

import structlog

from sens.caching.manager import CacheManager
from sens.exceptions import RetrievalError
from sens.monitoring.metrics import PipelineMetrics, track_step
from sens.monitoring.metrics_collector import RetrievalMetricsCollector, track_latency
from sens.schema.context import LLMSchemaContext
from sens.schema.graph import SchemaGraph
from sens.schema.precomputed_index import PrecomputedSchemaIndex

from .models import RetrievedColumn, RetrievedContext, RetrievedTable
from .orchestrator import RetrievalOrchestrator

log = structlog.get_logger()


class OptimizedSchemaRetriever:
    """Optimized schema retriever that uses pre-computed indexes and caching.

    This retriever improves performance by:
    1. Using pre-computed schema indexes for fast lookups
    2. Caching retrieval results
    3. Batch processing related schema elements
    4. Minimizing graph traversals
    """

    def __init__(
        self,
        token_index,
        embedding_index,
        schema_graph: Optional[SchemaGraph] = None,
        cache_manager: Optional[CacheManager] = None,
        enable_caching: bool = True,
    ):
        """Initialize the optimized retriever.

        Args:
            token_index: Token-based search index
            embedding_index: Embedding-based search index
            schema_graph: Optional SchemaGraph instance
            cache_manager: Optional cache manager for result caching
            enable_caching: Whether to enable result caching
        """
        self.token_index = token_index
        self.embedding_index = embedding_index
        self.schema_graph = schema_graph or SchemaGraph.get_instance()
        self.cache_manager = cache_manager
        self.enable_caching = enable_caching and cache_manager is not None

        # Initialize pre-computed index
        self.precomputed_index = PrecomputedSchemaIndex(self.schema_graph)

        # Fallback to original orchestrator for complex cases
        self.fallback_orchestrator = RetrievalOrchestrator(
            token_index, embedding_index, schema_graph
        )

        # Initialize metrics collector
        self.metrics_collector = RetrievalMetricsCollector()

        log.info(
            "optimized_retriever_initialized",
            caching_enabled=self.enable_caching,
            table_count=len(self.precomputed_index.table_indexes),
        )

    async def get_relevant_context(
        self, question: str, k: int = 5, metrics: Optional[PipelineMetrics] = None
    ) -> RetrievedContext:
        """Retrieve relevant schema context using optimized methods.

        Args:
            question: Natural language question
            k: Maximum number of columns to retrieve
            metrics: Optional metrics tracker

        Returns:
            RetrievedContext with relevant schema information
        """
        # Check cache first
        if self.enable_caching:
            cache_key = self.cache_manager.generate_key(
                "schema_retrieval", question=question, k=k
            )
            cached_result = await self.cache_manager.get(cache_key)
            if cached_result:
                log.info("schema_retrieval_cache_hit", question=question[:50])
                # Reconstruct objects from cached dictionaries
                tables = [RetrievedTable(**t) for t in cached_result.get("tables", [])]
                columns = [
                    RetrievedColumn(**c) for c in cached_result.get("columns", [])
                ]
                return RetrievedContext(
                    query=cached_result["query"],
                    tables=tables,
                    columns=columns,
                )

        # Track metrics if provided
        if metrics:
            with track_step(metrics, "optimized_schema_retrieval") as step:
                result = await self._retrieve_context(question, k)
                step.metadata["table_count"] = len(result.tables)
                step.metadata["column_count"] = len(result.columns)
        else:
            result = await self._retrieve_context(question, k)

        # Cache result
        if self.enable_caching:
            await self.cache_manager.set(
                cache_key,
                result.model_dump(),
                ttl=timedelta(hours=1),  # 1 hour cache
            )

        return result

    async def _retrieve_context(self, question: str, k: int) -> RetrievedContext:
        """Internal method to retrieve context with optimizations."""
        # Start metrics collection
        self.metrics_collector.start_retrieval(question)
        start_time = time.perf_counter()

        try:
            # Phase 1: Get initial search results (parallelized)
            token_hits, embedding_hits = await self._parallel_search(question, k)

            # If no hits from search, try to get all tables for basic matching
            if not token_hits and not embedding_hits:
                # Try to get some basic matches from token search
                all_tables = list(self.precomputed_index.table_indexes.keys())
                if all_tables:
                    # Create basic matches for tables that might match the query
                    query_words = question.lower().split()
                    
                    # First try to find tables that contain query words
                    matched = False
                    for table in all_tables:
                        table_lower = table.lower()
                        # Check if any query word appears in the table name
                        if any(word in table_lower for word in query_words if len(word) > 2):
                            token_hits.append(
                                RetrievedColumn(
                                    table_name=table,
                                    column_name="*",
                                    score=0.5,
                                    source="fallback",
                                    metadata={"type": "table_match"}
                                )
                            )
                            matched = True
                    
                    # If no matches, provide top tables as fallback
                    if not matched:
                        # For financial queries, prioritize certain tables
                        priority_tables = ['securities', 'daily_prices', 'market_data', 'economic_indicators', 
                                         'financial_statements', 'trades', 'portfolio_holdings']
                        
                        for table in all_tables[:15]:  # Provide more tables as fallback
                            # Give higher score to priority tables
                            score = 0.3 if table in priority_tables else 0.2
                            token_hits.append(
                                RetrievedColumn(
                                    table_name=table,
                                    column_name="*",
                                    score=score,
                                    source="fallback",
                                    metadata={"type": "fallback_match"}
                                )
                            )
                
                if not token_hits:
                    log.warning(
                        "no_schema_matches_found",
                        question=question,
                        available_tables=len(all_tables),
                        sample_tables=all_tables[:5] if all_tables else []
                    )
                    raise RetrievalError(
                        "No schema matches found. The system may still be initializing. Please try again.",
                        details={"question": question, "k_requested": k, "available_tables": len(all_tables)},
                    )

            # Phase 2: Merge and deduplicate
            merged_columns = self._merge_results(token_hits, embedding_hits)

            # Phase 3: Fast schema expansion using pre-computed indexes
            expanded_context = self._fast_expand_schema(merged_columns, k, question)

            # Record retrieved schema for metrics
            retrieved_tables = {table.table_name for table in expanded_context.tables}
            retrieved_columns = {
                (col.table_name, col.column_name) for col in expanded_context.columns
            }
            self.metrics_collector.record_retrieved_schema(
                retrieved_tables, retrieved_columns
            )

            # Complete metrics collection
            total_ms = (time.perf_counter() - start_time) * 1000
            self.metrics_collector.complete_retrieval(total_ms)

            log.info(
                "optimized_retrieval_complete",
                question=question[:50],
                initial_hits=len(merged_columns),
                final_tables=len(expanded_context.tables),
                final_columns=len(expanded_context.columns),
                total_ms=total_ms,
            )

            return expanded_context

        except Exception as e:
            # Complete metrics even on error
            total_ms = (time.perf_counter() - start_time) * 1000
            self.metrics_collector.complete_retrieval(total_ms)

            log.error(
                "optimized_retrieval_failed",
                error=str(e),
                fallback_to_original=True,
            )
            # Fallback to original orchestrator
            return await self.fallback_orchestrator.get_relevant_context(question, k)

    async def _parallel_search(
        self, question: str, k: int
    ) -> Tuple[List[RetrievedColumn], List[RetrievedColumn]]:
        """Execute token and embedding searches in parallel."""
        import asyncio

        # Create search tasks
        token_task = self._safe_search(self.token_index, question, k * 2)
        embedding_task = self._safe_search(self.embedding_index, question, k * 2)

        # Execute in parallel
        token_hits, embedding_hits = await asyncio.gather(token_task, embedding_task)

        return token_hits, embedding_hits

    async def _safe_search(self, index, question: str, k: int) -> List[RetrievedColumn]:
        """Safe wrapper for search operations."""
        search_type = (
            "token" if "token" in index.__class__.__name__.lower() else "embedding"
        )
        start_time = time.perf_counter()

        try:
            result = await index.search(question, k=k)
            latency_ms = (time.perf_counter() - start_time) * 1000

            # Track search latency (cache hit detection would need to be implemented in the index)
            self.metrics_collector.record_search_latency(
                search_type, latency_ms, cache_hit=False
            )

            return result
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            self.metrics_collector.record_search_latency(
                search_type, latency_ms, cache_hit=False
            )

            log.warning(
                f"{index.__class__.__name__}_search_failed",
                error=str(e),
            )
            return []

    def _merge_results(
        self,
        token_hits: List[RetrievedColumn],
        embedding_hits: List[RetrievedColumn],
    ) -> List[RetrievedColumn]:
        """Merge and deduplicate search results."""
        merged: Dict[Tuple[str, str], RetrievedColumn] = {}

        # Process all hits
        for hit in token_hits + embedding_hits:
            key = (hit.table_name, hit.column_name)
            if key not in merged or hit.score > merged[key].score:
                merged[key] = hit

        # Sort by score
        return sorted(merged.values(), key=lambda x: x.score, reverse=True)

    def _fast_expand_schema(
        self, initial_columns: List[RetrievedColumn], k: int, question: str
    ) -> RetrievedContext:
        """Fast schema expansion using pre-computed indexes."""
        # Extract initial tables
        initial_tables = {col.table_name for col in initial_columns}

        # Use pre-computed index for fast expansion
        expanded_tables, sticky_columns_by_table = (
            self.precomputed_index.get_expanded_schema_fast(
                initial_tables, max_expansion=1
            )
        )

        # Build column list with sticky columns
        all_columns = list(initial_columns)
        seen_columns = {(col.table_name, col.column_name) for col in initial_columns}

        # Add sticky columns
        for table, sticky_cols in sticky_columns_by_table.items():
            for sticky_col in sticky_cols:
                col_key = (table, sticky_col)
                if col_key not in seen_columns:
                    seen_columns.add(col_key)
                    all_columns.append(
                        RetrievedColumn(
                            table_name=table,
                            column_name=sticky_col,
                            score=0.1,  # Small positive score
                            source="sticky",
                            is_sticky=True,
                            metadata={"type": "sticky"},
                        )
                    )

        # Add structural columns (PKs and FKs) using pre-computed data
        for table in expanded_tables:
            table_index = self.precomputed_index.get_table_index(table)
            if not table_index:
                continue

            # Add primary keys
            for pk_col in table_index.primary_keys:
                col_key = (table, pk_col)
                if col_key not in seen_columns:
                    seen_columns.add(col_key)
                    all_columns.append(
                        RetrievedColumn(
                            table_name=table,
                            column_name=pk_col,
                            score=0.0,
                            source="structural",
                            metadata={"type": "PK"},
                        )
                    )

            # Add foreign keys that connect to other expanded tables
            for fk_col, (ref_table, ref_col) in table_index.foreign_key_columns.items():
                if ref_table in expanded_tables:
                    col_key = (table, fk_col)
                    if col_key not in seen_columns:
                        seen_columns.add(col_key)
                        all_columns.append(
                            RetrievedColumn(
                                table_name=table,
                                column_name=fk_col,
                                score=0.0,
                                source="structural",
                                metadata={
                                    "type": "FK",
                                    "references_table": ref_table,
                                    "references_column": ref_col,
                                },
                            )
                        )

        # Select top columns
        selected_columns = self._select_top_columns(all_columns, k)

        # Build table objects
        final_tables = []
        tables_with_columns = {col.table_name for col in selected_columns}

        for table in tables_with_columns:
            reason = "direct_hit" if table in initial_tables else "join_expansion"
            final_tables.append(
                RetrievedTable(
                    table_name=table,
                    reason=reason,
                    metadata={},
                )
            )

        return RetrievedContext(
            query=question,
            tables=final_tables,
            columns=selected_columns,
        )

    def _select_top_columns(
        self, columns: List[RetrievedColumn], k: int
    ) -> List[RetrievedColumn]:
        """Select top k columns, preserving sticky and structural columns."""
        # Separate by type
        sticky = [c for c in columns if getattr(c, "is_sticky", False)]
        structural = [
            c
            for c in columns
            if not getattr(c, "is_sticky", False)
            and c.metadata.get("type") in ("PK", "FK")
        ]
        regular = [
            c
            for c in columns
            if not getattr(c, "is_sticky", False)
            and c.metadata.get("type") not in ("PK", "FK")
        ]

        # Sort regular columns by score
        regular.sort(key=lambda x: x.score, reverse=True)

        # Build final list: all sticky + all structural + top regular
        result = sticky + structural

        # Add top regular columns up to k total
        remaining_slots = max(0, k - len(result))
        result.extend(regular[:remaining_slots])

        return result

    def convert_to_llm_context(
        self, retrieved_context: RetrievedContext
    ) -> LLMSchemaContext:
        """Convert RetrievedContext to LLMSchemaContext format.

        Args:
            retrieved_context: Retrieved context from search

        Returns:
            LLMSchemaContext suitable for SQL generation
        """
        # Group columns by table
        tables_columns: Dict[str, List[str]] = {}
        for col in retrieved_context.columns:
            if col.table_name not in tables_columns:
                tables_columns[col.table_name] = []
            tables_columns[col.table_name].append(col.column_name)

        # Get primary keys from pre-computed index
        primary_keys: Dict[str, List[str]] = {}
        for table in tables_columns:
            table_index = self.precomputed_index.get_table_index(table)
            if table_index:
                primary_keys[table] = table_index.primary_keys

        # Build foreign keys list
        foreign_keys = []
        for table in tables_columns:
            table_index = self.precomputed_index.get_table_index(table)
            if not table_index:
                continue

            for fk_col, (ref_table, ref_col) in table_index.foreign_key_columns.items():
                if (
                    ref_table in tables_columns
                ):  # Only include FKs between selected tables
                    foreign_keys.append(
                        {
                            "from_table": table,
                            "from_columns": fk_col,
                            "to_table": ref_table,
                            "to_columns": ref_col,
                        }
                    )

        # Get column descriptions
        column_descriptions: Dict[str, Dict[str, str]] = {}
        for table, columns in tables_columns.items():
            table_index = self.precomputed_index.get_table_index(table)
            if table_index:
                column_descriptions[table] = {
                    col: table_index.column_descriptions.get(col, "")
                    for col in columns
                    if col in table_index.column_descriptions
                }

        # Get sticky columns
        sticky_columns: Dict[str, List[str]] = {}
        for table in tables_columns:
            table_index = self.precomputed_index.get_table_index(table)
            if table_index and table_index.sticky_columns:
                sticky_columns[table] = table_index.sticky_columns

        return LLMSchemaContext(
            tables=set(tables_columns.keys()),
            tables_columns=tables_columns,
            primary_keys=primary_keys,
            foreign_keys=foreign_keys,
            column_descriptions=column_descriptions,
            sticky_columns=sticky_columns,
        )
