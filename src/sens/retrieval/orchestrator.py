import logging
from typing import Dict, List, Optional

import structlog

from sens.exceptions import RetrievalError

from .models import RetrievedColumn, RetrievedContext, RetrievedTable

# Use only structlog
log = structlog.get_logger()


class RetrievalOrchestrator:
    """Orchestrates retrieval from multiple sources to produce a unified, ranked list of relevant schema items.

    This class combines results from token-based and embedding-based search, handles deduplication,
    expands the schema based on relationships, and ranks the final results.
    """

    def __init__(self, token_index, embedding_index, schema_graph):
        """Initializes the orchestrator with necessary index components.

        Args:
            token_index: An instance capable of token-based retrieval.
            embedding_index: An instance capable of embedding-based retrieval.
            schema_graph: An instance providing schema structure and relationships.
        """
        self.token_index = token_index
        self.embedding_index = embedding_index
        self.schema_graph = schema_graph
        log.info("retrieval_orchestrator_initialized")

    async def get_relevant_context(self, question: str, k: int = 5) -> RetrievedContext:
        """Retrieves relevant schema context for a given natural language question.

        Combines results from token and embedding indices, deduplicates,
        expands based on schema relationships, and ranks the final set.

        Args:
            question: The natural language question.
            k: The maximum number of top columns/tables to return
               (based on column scores).

        Returns:
            A RetrievedContext object containing the relevant schema slice.
        """
        log.debug("orchestrating_retrieval", details={"question": question, "k": k})

        try:
            # 1. Call token index
            try:
                token_hits = await self.token_index.search(question, k=k * 2)
            except AttributeError:
                log.error(
                    "token_index_search_failed", details={"error": "method_not_found"}
                )
                token_hits: List[RetrievedColumn] = []
            except Exception as e:
                log.error("token_index_search_failed", details={"error": str(e)})
                token_hits: List[RetrievedColumn] = []
            log.debug(
                "token_index_search_complete", details={"hit_count": len(token_hits)}
            )

            # 2. Call embedding index
            try:
                embedding_hits = await self.embedding_index.search(question, k=k * 2)
            except AttributeError:
                log.error(
                    "embedding_index_search_failed",
                    details={"error": "method_not_found"},
                )
                embedding_hits: List[RetrievedColumn] = []
            except Exception as e:
                log.error("embedding_index_search_failed", details={"error": str(e)})
                embedding_hits: List[RetrievedColumn] = []
            log.debug(
                "embedding_index_search_complete",
                details={"hit_count": len(embedding_hits)},
            )

            # 3. Merge scores and deduplicate columns
            merged_columns = self._merge_and_deduplicate(token_hits, embedding_hits)
            log.debug(
                "columns_merged",
                details={
                    "merged_count": len(merged_columns),
                    "tables_used": list({col.table_name for col in merged_columns}),
                    "columns_by_table": {
                        table: [
                            (col.column_name, round(col.score, 4))
                            for col in merged_columns
                            if col.table_name == table
                        ]
                        for table in {col.table_name for col in merged_columns}
                    },
                },
            )

            # 4. Expand schema (adds related tables and PK/FK columns)
            all_involved_tables, all_involved_columns = self._expand_schema(
                merged_columns
            )
            log.debug(
                "schema_expanded",
                details={
                    "table_count": len(all_involved_tables),
                    "column_count": len(all_involved_columns),
                    "tables": {
                        table.table_name: {
                            "reason": table.reason,
                            "columns": [
                                {
                                    "name": col.column_name,
                                    "score": round(col.score, 4),
                                    "source": col.source,
                                    "type": col.metadata.get("type", "regular"),
                                }
                                for col in all_involved_columns
                                if col.table_name == table.table_name
                            ],
                        }
                        for table in all_involved_tables
                    },
                },
            )

            # 5. Rank and select top k columns
            selected_columns = self._rank_and_select(all_involved_columns, k)
            log.debug(
                "columns_selected",
                details={
                    "count": len(selected_columns),
                    "columns_by_table": {
                        table: [
                            {
                                "name": col.column_name,
                                "score": round(col.score, 4),
                                "source": col.source,
                                "type": col.metadata.get("type", "regular"),
                            }
                            for col in selected_columns
                            if col.table_name == table
                        ]
                        for table in {col.table_name for col in selected_columns}
                    },
                },
            )

            # Rescue structural columns (PKs/FKs) that might have been dropped
            expanded_context_table_names = {
                tbl.table_name for tbl in all_involved_tables
            }

            structural_columns_to_add = []
            current_selected_column_keys = {
                (col.table_name, col.column_name) for col in selected_columns
            }

            # First pass: Rescue PKs and ID columns
            for candidate_col in all_involved_columns:
                candidate_key = (candidate_col.table_name, candidate_col.column_name)
                if candidate_key in current_selected_column_keys:
                    continue

                # Check both explicit PK type and column name patterns
                is_pk = (
                    candidate_col.metadata.get("type") == "PK"
                    or candidate_col.column_name == "id"
                    or candidate_col.column_name.endswith("_id")
                    and candidate_col.column_name == f"{candidate_col.table_name}_id"
                )

                if is_pk and candidate_col.table_name in expanded_context_table_names:
                    structural_columns_to_add.append(candidate_col)
                    current_selected_column_keys.add(candidate_key)
                    log.debug(
                        "rescuing_pk",
                        details={
                            "table": candidate_col.table_name,
                            "column": candidate_col.column_name,
                            "reason": (
                                "explicit_pk"
                                if candidate_col.metadata.get("type") == "PK"
                                else "implicit_pk"
                            ),
                        },
                    )

            # Second pass: Rescue FKs and potential join columns
            for table_name in expanded_context_table_names:
                # Get all FKs that connect tables within our context
                fk_columns = self.schema_graph.get_table_fks_involved(
                    table_name, expanded_context_table_names
                )

                for fk_column in fk_columns:
                    candidate_key = (table_name, fk_column)
                    if candidate_key in current_selected_column_keys:
                        continue

                    # Get metadata about this FK
                    referenced_table = None
                    if fk_column.endswith("_id"):
                        # Try to derive referenced table from column name
                        potential_table = fk_column[:-3]  # Remove "_id"
                        if potential_table in expanded_context_table_names:
                            referenced_table = potential_table

                    # Create a new RetrievedColumn for this FK
                    fk_column_obj = RetrievedColumn(
                        table_name=table_name,
                        column_name=fk_column,
                        score=0.0,  # Structural columns get base score
                        source="schema_expansion",
                        metadata={"type": "FK", "references_table": referenced_table},
                    )

                    structural_columns_to_add.append(fk_column_obj)
                    current_selected_column_keys.add(candidate_key)
                    log.debug(
                        "rescuing_fk",
                        details={
                            "table": table_name,
                            "column": fk_column,
                            "references_table": referenced_table,
                            "reason": "explicit_fk",
                        },
                    )

            if structural_columns_to_add:
                selected_columns.extend(structural_columns_to_add)
                log.info(
                    "structural_columns_rescued",
                    details={
                        "count": len(structural_columns_to_add),
                        "rescued_by_table": {
                            table: [
                                {
                                    "column": col.column_name,
                                    "type": col.metadata.get("type"),
                                    "references_table": col.metadata.get(
                                        "references_table"
                                    ),
                                }
                                for col in structural_columns_to_add
                                if col.table_name == table
                            ]
                            for table in {
                                col.table_name for col in structural_columns_to_add
                            }
                        },
                    },
                )

            # 6. Determine final tables based on the selected columns and expansion results
            final_table_names = {col.table_name for col in selected_columns}
            final_tables = [
                tbl
                for tbl in all_involved_tables
                if tbl.table_name in final_table_names
            ]

            # 7. Construct RetrievedContext
            final_context = RetrievedContext(
                query=question,
                tables=final_tables,
                columns=selected_columns,
            )

            # 8. Structured Logging (AC5)
            def format_cols(cols):
                return [
                    {
                        "table": c.table_name,
                        "column": c.column_name,
                        "score": round(c.score, 4),
                        "source": c.source,
                        "type": c.metadata.get("type", "regular"),
                        "references": c.metadata.get("references_table"),
                    }
                    for c in cols
                ]

            results = {
                "retrieval_inputs": {
                    "token_hits": format_cols(token_hits),
                    "embedding_hits": format_cols(embedding_hits),
                },
                "intermediate_results": {
                    "merged_columns": {
                        table: [
                            {
                                "column": c.column_name,
                                "score": round(c.score, 4),
                                "source": c.source,
                            }
                            for c in merged_columns
                            if c.table_name == table
                        ]
                        for table in {c.table_name for c in merged_columns}
                    },
                    "expanded_schema": {
                        table.table_name: {
                            "reason": table.reason,
                            "columns": [
                                {
                                    "name": c.column_name,
                                    "score": round(c.score, 4),
                                    "source": c.source,
                                    "type": c.metadata.get("type", "regular"),
                                    "references": c.metadata.get("references_table"),
                                }
                                for c in all_involved_columns
                                if c.table_name == table.table_name
                            ],
                        }
                        for table in all_involved_tables
                    },
                },
                "final_context": {
                    "tables": {
                        table.table_name: {
                            "reason": table.reason,
                            "columns": [
                                {
                                    "name": c.column_name,
                                    "score": round(c.score, 4),
                                    "source": c.source,
                                    "type": c.metadata.get("type", "regular"),
                                    "references": c.metadata.get("references_table"),
                                }
                                for c in selected_columns
                                if c.table_name == table.table_name
                            ],
                        }
                        for table in final_tables
                    }
                },
            }

            log.info("retrieval_results", details=results)

            # Validate results
            if not token_hits and not embedding_hits:
                raise RetrievalError(
                    "No schema matches found",
                    details={"question": question, "k_requested": k},
                )

            # After expansion, validate final context
            if not results["final_context"]["tables"]:
                raise RetrievalError(
                    "Schema expansion produced no valid tables",
                    details={
                        "question": question,
                        "initial_hits": len(token_hits) + len(embedding_hits),
                    },
                )

            log.info(
                "schema_retrieval_complete",
                details={
                    "table_count": len(results["final_context"]["tables"]),
                    "column_count": sum(
                        len(table_info["columns"])
                        for table_info in results["final_context"]["tables"].values()
                    ),
                    "tables_summary": {
                        name: {
                            "column_count": len(info["columns"]),
                            "column_types": {col["type"]: 1 for col in info["columns"]},
                        }
                        for name, info in results["final_context"]["tables"].items()
                    },
                },
            )

            return final_context

        except Exception as e:
            log.error(
                "schema_retrieval_failed",
                details={
                    "error": str(e),
                    "question": question,
                    "error_type": e.__class__.__name__,
                },
            )
            if isinstance(e, RetrievalError):
                raise
            raise RetrievalError(
                "Failed to retrieve schema context",
                details={"question": question, "original_error": str(e)},
            )

    def _merge_and_deduplicate(
        self, token_hits: List[RetrievedColumn], embedding_hits: List[RetrievedColumn]
    ) -> List[RetrievedColumn]:
        """Merges hits from token and embedding sources, handling duplicates.

        Keeps the entry with the maximum score if a column is found by both sources.
        """
        merged: Dict[tuple[str, str], RetrievedColumn] = {}

        for hit in token_hits + embedding_hits:
            key = (hit.table_name, hit.column_name)
            if key not in merged or hit.score > merged[key].score:
                merged[key] = hit
            # Optional: Could add logic here to combine metadata if needed
            # elif key in merged:
            #    merged[key].metadata['sources'] = list(set(merged[key].metadata.get('sources', [merged[key].source]) + [hit.source]))

        # Convert back to a list and sort by score
        deduplicated_columns = list(merged.values())
        return sorted(deduplicated_columns, key=lambda x: x.score, reverse=True)

    def _expand_schema(
        self, initial_columns: List[RetrievedColumn]
    ) -> tuple[List[RetrievedTable], List[RetrievedColumn]]:
        """Expands the initial set of columns to include related tables and structural columns.

        Args:
            initial_columns: The initial set of retrieved columns.

        Returns:
            A tuple of (tables, columns) where tables contains all involved tables
            and columns contains all columns (initial + expanded).
        """
        # Track tables we've seen to avoid duplicates
        seen_tables = set()
        # Track columns we've seen to avoid duplicates
        seen_columns = set()

        # Initialize result lists
        all_tables: List[RetrievedTable] = []
        all_columns: List[RetrievedColumn] = []

        # First pass: Process initial columns and their tables
        for col in initial_columns:
            table_name = col.table_name
            if table_name not in seen_tables:
                seen_tables.add(table_name)
                all_tables.append(
                    RetrievedTable(
                        table_name=table_name,
                        reason="direct_hit",
                        metadata={"initial_score": col.score},
                    )
                )

            col_key = (col.table_name, col.column_name)
            if col_key not in seen_columns:
                seen_columns.add(col_key)
                all_columns.append(col)

                # Add sticky columns from the same table
                sticky_columns = self.schema_graph.get_table_sticky_columns(table_name)
                for sticky_col in sticky_columns:
                    sticky_key = (table_name, sticky_col)
                    if sticky_key not in seen_columns:
                        seen_columns.add(sticky_key)
                        all_columns.append(
                            RetrievedColumn(
                                table_name=table_name,
                                column_name=sticky_col,
                                score=0.0,  # No scoring for sticky columns
                                source="sticky",
                                is_sticky=True,
                                metadata={"type": "sticky"},
                            )
                        )

        # Second pass: Add related tables and their columns
        tables_to_process = list(seen_tables)
        for table_name in tables_to_process:
            # Get neighboring tables
            neighbors = self.schema_graph.get_neighbor_tables({table_name})

            for neighbor in neighbors:
                if neighbor not in seen_tables:
                    seen_tables.add(neighbor)
                    all_tables.append(
                        RetrievedTable(
                            table_name=neighbor,
                            reason="join_expansion",
                            metadata={"expanded_from": table_name},
                        )
                    )

                    # Add sticky columns from expanded tables
                    sticky_columns = self.schema_graph.get_table_sticky_columns(
                        neighbor
                    )
                    for sticky_col in sticky_columns:
                        sticky_key = (neighbor, sticky_col)
                        if sticky_key not in seen_columns:
                            seen_columns.add(sticky_key)
                            all_columns.append(
                                RetrievedColumn(
                                    table_name=neighbor,
                                    column_name=sticky_col,
                                    score=0.0,  # No scoring for sticky columns
                                    source="sticky",
                                    is_sticky=True,
                                    metadata={
                                        "type": "sticky",
                                        "expanded_from": table_name,
                                    },
                                )
                            )

        # Add structural columns (PKs/FKs)
        for table_name in seen_tables:
            # Add primary keys
            for pk_col in self.schema_graph.get_table_pks(table_name):
                pk_key = (table_name, pk_col)
                if pk_key not in seen_columns:
                    seen_columns.add(pk_key)
                    all_columns.append(
                        RetrievedColumn(
                            table_name=table_name,
                            column_name=pk_col,
                            score=0.0,  # No scoring for structural columns
                            source="structural",
                            metadata={"type": "PK"},
                        )
                    )

            # Add foreign keys that connect to other tables in our context
            fk_columns = self.schema_graph.get_table_fks_involved(
                table_name, seen_tables
            )
            for fk_col in fk_columns:
                fk_key = (table_name, fk_col)
                if fk_key not in seen_columns:
                    seen_columns.add(fk_key)
                    all_columns.append(
                        RetrievedColumn(
                            table_name=table_name,
                            column_name=fk_col,
                            score=0.0,  # No scoring for structural columns
                            source="structural",
                            metadata={"type": "FK"},
                        )
                    )

        return all_tables, all_columns

    def _rank_and_select(
        self, columns: List[RetrievedColumn], k: int
    ) -> List[RetrievedColumn]:
        """Ranks and selects the top k columns, with special handling for sticky columns.

        Args:
            columns: List of columns to rank and select from.
            k: Maximum number of non-sticky columns to return.

        Returns:
            List of selected columns, including all sticky columns plus top k non-sticky columns.
        """
        if not columns:
            return []

        # Separate sticky and non-sticky columns
        sticky_columns = [col for col in columns if col.is_sticky]
        non_sticky_columns = [col for col in columns if not col.is_sticky]
        
        # Sort non-sticky columns by score
        sorted_non_sticky = sorted(non_sticky_columns, key=lambda x: x.score, reverse=True)
        
        # Take top k non-sticky columns
        selected_non_sticky = sorted_non_sticky[:k]
        
        # Remove duplicates (prefer sticky over non-sticky if same column)
        seen_columns = set()
        final_columns = []
        
        # Add sticky columns first
        for col in sticky_columns:
            col_key = (col.table_name, col.column_name)
            if col_key not in seen_columns:
                seen_columns.add(col_key)
                final_columns.append(col)
        
        # Add non-sticky columns if not already included
        for col in selected_non_sticky:
            col_key = (col.table_name, col.column_name)
            if col_key not in seen_columns:
                seen_columns.add(col_key)
                final_columns.append(col)
        
        return final_columns
