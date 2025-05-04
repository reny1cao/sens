import logging
from typing import Dict, List  # Assuming List and Dict will be needed

# Import the context model
from .models import RetrievedColumn, RetrievedContext, RetrievedTable

# Placeholder for actual index implementations (to be imported later)
# from .token_index import TokenIndex # Assuming location
# from .embedding_index import EmbeddingIndex # Assuming location
# from ..schema.graph import SchemaGraph # Assuming location for schema info

logger = logging.getLogger(__name__)


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
        logger.info("RetrievalOrchestrator initialized.")

    def get_relevant_context(self, question: str, k: int = 5) -> RetrievedContext:
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
        logger.debug(f"Orchestrating retrieval for question: '{question}' with k={k}")

        # 1. Call token index
        try:
            # Fetch more initially to allow for merging/ranking (e.g., 2*k or more)
            token_hits = self.token_index.search(question, k=k * 2)
        except AttributeError:
            logger.error("token_index.search method not found or failed.")
            token_hits: List[RetrievedColumn] = []
        except Exception as e:
            logger.error(f"Error calling token index: {e}")
            token_hits: List[RetrievedColumn] = []
        logger.debug(f"Token index returned {len(token_hits)} hits.")

        # 2. Call embedding index
        try:
            embedding_hits = self.embedding_index.search(question, k=k * 2)
        except AttributeError:
            logger.error("embedding_index.search method not found or failed.")
            embedding_hits: List[RetrievedColumn] = []
        except Exception as e:
            logger.error(f"Error calling embedding index: {e}")
            embedding_hits: List[RetrievedColumn] = []
        logger.debug(f"Embedding index returned {len(embedding_hits)} hits.")

        # 3. Merge scores and deduplicate columns (sorted by score)
        merged_columns = self._merge_and_deduplicate(token_hits, embedding_hits)
        logger.debug(f"Merged and deduplicated to {len(merged_columns)} columns.")

        # 4. Expand schema (adds related tables and PK/FK columns)
        # Returns all involved tables and columns (original + schema), sorted by score
        all_involved_tables, all_involved_columns = self._expand_schema(merged_columns)
        logger.debug(
            f"Schema expanded to {len(all_involved_tables)} tables and {len(all_involved_columns)} columns."
        )

        # 5. Rank and select top k columns based on score
        # Note: This selects the top *columns*. The tables included are those
        # associated with these columns plus any added during expansion.
        selected_columns = self._rank_and_select(all_involved_columns, k)
        logger.debug(f"Ranked and selected top {len(selected_columns)} columns.")

        # 6. Determine final tables based *only* on the selected columns and expansion results
        final_table_names = {col.table_name for col in selected_columns}
        # Ensure all tables from the expansion step that contained a selected column are included
        final_tables = [
            tbl for tbl in all_involved_tables if tbl.table_name in final_table_names
        ]

        # 7. Construct RetrievedContext
        final_context = RetrievedContext(
            query=question,
            tables=final_tables,
            columns=selected_columns,  # Already sorted and capped
        )

        # 8. Structured Logging (AC5)
        # Helper to format column lists for logging
        def format_cols(cols):
            return [
                (c.table_name, c.column_name, round(c.score, 4), c.source) for c in cols
            ]

        log_data = {
            "phase": "retrieval_orchestration",
            "question": question,
            "k_requested": k,
            "retrieval_inputs": {
                "token_hits": format_cols(token_hits),
                "embedding_hits": format_cols(embedding_hits),
            },
            "intermediate_results": {
                "merged_deduplicated_columns": format_cols(merged_columns),
                "schema_expanded_columns": format_cols(all_involved_columns),
                "schema_expanded_tables": [
                    (t.table_name, t.reason) for t in all_involved_tables
                ],
            },
            "final_context": {
                "selected_columns": format_cols(selected_columns),
                "included_tables": [(t.table_name, t.reason) for t in final_tables],
            },
        }
        # Consider using json.dumps for more robust serialization if logging complex metadata
        logger.info(log_data)

        return final_context

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
        """Expands the schema based on initial hits and schema graph (FKs).

        Includes tables directly hit and those joinable via FKs within the hit set.
        Adds necessary PK and FK columns for the included tables.
        """
        if not initial_columns:
            return [], []

        # Use a dictionary to easily add/update columns and ensure uniqueness
        final_columns_dict: Dict[tuple[str, str], RetrievedColumn] = {
            (col.table_name, col.column_name): col for col in initial_columns
        }

        direct_hit_tables = {col.table_name for col in initial_columns}

        # Assume schema_graph has a method to find directly connected neighbors
        # This method should ideally consider only joins *between* potential tables
        try:
            # Placeholder: Get all tables involved in direct hits and their immediate neighbors
            expanded_table_names = self.schema_graph.get_neighbor_tables(
                direct_hit_tables
            )
        except AttributeError:
            # Fallback if schema_graph or method doesn't exist
            logger.warning(
                "schema_graph.get_neighbor_tables not found. Using direct hits only."
            )
            expanded_table_names = direct_hit_tables
        except Exception as e:
            logger.error(f"Error during schema expansion: {e}")
            expanded_table_names = direct_hit_tables  # Fallback on error

        final_tables: List[RetrievedTable] = []
        for table_name in expanded_table_names:
            reason = (
                "direct_hit" if table_name in direct_hit_tables else "join_expansion"
            )
            final_tables.append(RetrievedTable(table_name=table_name, reason=reason))

        # Add PKs and FKs for all tables in the final set
        # Use a placeholder score and source for schema-added columns
        SCHEMA_SCORE = 0.0
        SCHEMA_SOURCE = "schema_expansion"

        for table_name in expanded_table_names:
            try:
                # Add Primary Keys
                pk_columns = self.schema_graph.get_table_pks(table_name)
                for pk_col in pk_columns:
                    key = (table_name, pk_col)
                    if key not in final_columns_dict:
                        final_columns_dict[key] = RetrievedColumn(
                            table_name=table_name,
                            column_name=pk_col,
                            score=SCHEMA_SCORE,
                            source=SCHEMA_SOURCE,
                            metadata={"type": "PK"},
                        )

                # Add Foreign Keys that connect *within* the expanded set
                fk_columns = self.schema_graph.get_table_fks_involved(
                    table_name, expanded_table_names
                )
                for fk_col in fk_columns:
                    key = (table_name, fk_col)
                    if key not in final_columns_dict:
                        final_columns_dict[key] = RetrievedColumn(
                            table_name=table_name,
                            column_name=fk_col,
                            score=SCHEMA_SCORE,
                            source=SCHEMA_SOURCE,
                            metadata={"type": "FK"},
                        )
            except AttributeError:
                logger.warning(
                    f"schema_graph methods (get_table_pks/get_table_fks_involved) not found for table {table_name}."
                )
                # Continue without adding PK/FK if methods are missing
                pass
            except Exception as e:
                logger.error(f"Error adding PK/FK for table {table_name}: {e}")
                pass  # Continue on error

        # Return the list of tables and the unique columns (original + schema)
        # Keep the original sorting based on score for ranking later
        final_columns_list = sorted(
            final_columns_dict.values(), key=lambda x: x.score, reverse=True
        )

        return final_tables, final_columns_list

    def _rank_and_select(
        self, columns: List[RetrievedColumn], k: int
    ) -> List[RetrievedColumn]:
        """Ranks the final set of columns and selects the top k."""
        # TODO: Implement potentially more sophisticated ranking
        # For now, assume already sorted by score (from merge step) and take top k
        return columns[:k]
