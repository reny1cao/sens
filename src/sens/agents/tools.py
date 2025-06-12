"""Tools available to the SENS agent for database exploration and query fixing."""

import re
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlglot import exp, parse_one

from sens.chat.orchestrator import ChatOrchestrator
from sens.execution.executor import SQLExecutor
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

log = structlog.get_logger()


class AgentTools:
    """Collection of tools the agent can use."""

    def __init__(self):
        """Initialize agent tools."""
        self.settings = get_settings()
        self.executor = SQLExecutor(self.settings.db_url)
        self.schema_graph = SchemaGraph.get_instance()
        self.embedding_search = EmbeddingSearch()
        self.chat_orchestrator = None  # Lazy init to avoid circular imports

    async def search_schema(self, query: str) -> Dict[str, Any]:
        """Search for relevant schema elements."""
        log.info("tool_search_schema", query=query)

        # Use existing retrieval system
        if not self.chat_orchestrator:
            self.chat_orchestrator = ChatOrchestrator()

        context = await self.chat_orchestrator.retrieval.get_relevant_context(
            question=query,
            k=10,
        )

        return {
            "tables": [
                t.model_dump() if hasattr(t, "model_dump") else t.__dict__
                for t in context.tables
            ],
            "columns": [
                c.model_dump() if hasattr(c, "model_dump") else c.__dict__
                for c in context.columns
            ],
        }

    async def search_values(
        self,
        table: str,
        column: str,
        pattern: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Search for actual values in a database column."""
        log.info("tool_search_values", table=table, column=column, pattern=pattern)

        # Handle wildcard column
        if column == "*":
            log.warning("wildcard_column_not_supported", table=table)
            return []

        try:
            # Build query
            if pattern:
                sql = f"""
                SELECT DISTINCT {column}, COUNT(*) as count
                FROM {table}
                WHERE CAST({column} AS TEXT) ILIKE %s
                GROUP BY {column}
                ORDER BY count DESC
                LIMIT %s
                """
                params = (f"%{pattern}%", limit)
            else:
                sql = f"""
                SELECT DISTINCT {column}, COUNT(*) as count
                FROM {table}
                WHERE {column} IS NOT NULL
                GROUP BY {column}
                ORDER BY count DESC
                LIMIT %s
                """
                params = (limit,)

            # Execute with parameters
            result = self.executor.execute_with_params(sql, params)

            return [{"value": row[0], "count": row[1]} for row in result.rows]

        except Exception as e:
            log.error("search_values_failed", error=str(e))
            return []

    async def find_similar_values(
        self,
        user_term: str,
        table: str,
        column: str,
        threshold: float = 0.6,
    ) -> Dict[str, Any]:
        """Find values similar to user term using fuzzy matching and embeddings."""
        log.info("tool_find_similar_values", term=user_term, table=table, column=column)

        # First try exact match
        exact_values = await self.search_values(
            table=table,
            column=column,
            pattern=user_term,
            limit=5,
        )

        if exact_values:
            return {
                "found": True,
                "exact_match": True,
                "values": exact_values,
                "mapping": {user_term: exact_values[0]["value"]},
            }

        # Try semantic search
        all_values = await self.search_values(
            table=table,
            column=column,
            limit=100,
        )

        if not all_values:
            return {"found": False, "values": []}

        # Use embeddings to find similar values
        # value_texts = [str(v["value"]) for v in all_values]  # Future: use embeddings

        # Simple similarity scoring (in production, use proper embeddings)
        similar_values = []
        user_term_lower = user_term.lower()

        for value_dict in all_values:
            value = str(value_dict["value"])
            value_lower = value.lower()

            # Calculate similarity score
            score = 0.0

            # Exact substring match
            if user_term_lower in value_lower:
                score = 0.8
            # Partial word match
            elif any(word in value_lower for word in user_term_lower.split()):
                score = 0.6
            # First letter match (e.g., "Apple" -> "AAPL")
            elif user_term_lower[0] == value_lower[0]:
                score = 0.4

            if score >= threshold:
                similar_values.append(
                    {
                        "value": value,
                        "count": value_dict["count"],
                        "similarity": score,
                    }
                )

        # Sort by similarity
        similar_values.sort(key=lambda x: x["similarity"], reverse=True)

        if similar_values:
            best_match = similar_values[0]["value"]
            return {
                "found": True,
                "exact_match": False,
                "values": similar_values[:5],
                "mapping": {user_term: best_match},
                "confidence": similar_values[0]["similarity"],
            }

        return {"found": False, "values": []}

    async def get_value_distribution(
        self,
        table: str,
        column: str,
    ) -> Dict[str, Any]:
        """Get distribution statistics for a column."""
        log.info("tool_get_value_distribution", table=table, column=column)

        try:
            # Get basic statistics
            sql = f"""
            SELECT
                COUNT(*) as total_count,
                COUNT(DISTINCT {column}) as distinct_count,
                COUNT({column}) as non_null_count,
                MIN({column}::text) as min_value,
                MAX({column}::text) as max_value
            FROM {table}
            """

            result = self.executor.execute(sql)
            stats = result.rows[0] if result.rows else {}

            # Get top values
            top_values = await self.search_values(
                table=table,
                column=column,
                limit=10,
            )

            return {
                "statistics": {
                    "total_rows": stats[0] if stats else 0,
                    "distinct_values": stats[1] if stats else 0,
                    "non_null_count": stats[2] if stats else 0,
                    "null_count": (stats[0] - stats[2]) if stats else 0,
                    "min_value": stats[3] if stats else None,
                    "max_value": stats[4] if stats else None,
                },
                "top_values": top_values,
            }

        except Exception as e:
            log.error("get_distribution_failed", error=str(e))
            return {"error": str(e)}

    async def generate_sql(
        self,
        query: str,
        schema: Dict[str, Any],
        mappings: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate SQL with value mappings applied."""
        log.info("tool_generate_sql", query=query, mappings=mappings)

        # Apply mappings to query
        modified_query = query
        if mappings:
            for user_term, db_value in mappings.items():
                # Replace user terms with database values
                modified_query = modified_query.replace(user_term, db_value)
                log.info("applying_mapping", from_term=user_term, to_value=db_value)

        # Use existing SQL generator with proper intent extraction
        if not self.chat_orchestrator:
            self.chat_orchestrator = ChatOrchestrator()

        try:
            # Use the proper intent extraction pipeline instead of mocking
            # This extracts real intent, validates it, and creates proper schema context
            intent = await self.chat_orchestrator.intent_extractor.extract(
                modified_query
            )

            # Validate the intent using the proper validator
            validated_intent = await self.chat_orchestrator.intent_validator.validate(
                intent=intent, question=modified_query
            )

            result = await self.chat_orchestrator.sql_generator.generate(
                question=modified_query,
                intent=validated_intent,
                schema_context=None,  # Let the generator build the proper schema context
            )
        except Exception as e:
            log.error("intent_extraction_failed", error=str(e), query=modified_query)
            # Fallback: use direct SQL generation without intent
            result = await self.chat_orchestrator.sql_generator.generate(
                question=modified_query,
                intent=None,  # Let the generator handle the lack of intent
                schema_context=None,
            )

        return result.sql

    async def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL and return results."""
        log.info("tool_execute_sql", sql=sql[:100])

        try:
            result = self.executor.execute(sql)

            return {
                "success": True,
                "row_count": result.row_count,
                "columns": result.columns,
                "rows": result.rows[:100],  # Limit for agent processing
                "error": result.error,
            }

        except Exception as e:
            return {
                "success": False,
                "row_count": 0,
                "error": str(e),
            }

    async def diagnose_empty_results(
        self,
        sql: str,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Diagnose why a query returned no results."""
        log.info("tool_diagnose_empty_results")

        diagnosis = {
            "issues": [],
            "suggestions": [],
        }

        try:
            # Parse SQL
            parsed = parse_one(sql, read="postgres")

            # Extract WHERE conditions
            where_conditions = []
            for node in parsed.find_all(exp.Where):
                where_conditions.extend(self._extract_conditions(node))

            # Test each condition individually
            for condition in where_conditions:
                test_sql = f"""
                SELECT COUNT(*)
                FROM {self._get_main_table(parsed)}
                WHERE {condition}
                """

                result = self.executor.execute(test_sql)
                count = result.rows[0][0] if result.rows else 0

                if count == 0:
                    diagnosis["issues"].append(
                        {
                            "type": "empty_filter",
                            "condition": condition,
                            "message": f"Condition '{condition}' returns no rows",
                        }
                    )

                    # Try to find what values exist
                    column = self._extract_column_from_condition(condition)
                    if column:
                        values = await self.search_values(
                            table=self._get_main_table(parsed),
                            column=column,
                            limit=5,
                        )
                        diagnosis["suggestions"].append(
                            {
                                "type": "alternative_values",
                                "column": column,
                                "current_condition": condition,
                                "available_values": values,
                            }
                        )

            # Check if tables exist
            tables = self._extract_tables(parsed)
            for table in tables:
                if not self._table_exists(table):
                    diagnosis["issues"].append(
                        {
                            "type": "missing_table",
                            "table": table,
                            "message": f"Table '{table}' does not exist",
                        }
                    )

            return diagnosis

        except Exception as e:
            log.error("diagnose_failed", error=str(e))
            return {
                "error": str(e),
                "issues": [{"type": "parse_error", "message": str(e)}],
            }

    def _extract_conditions(self, where_node) -> List[str]:
        """Extract individual conditions from WHERE clause."""
        conditions = []

        # Simple extraction - in production use proper AST traversal
        if where_node.this:
            conditions.append(str(where_node.this))

        return conditions

    def _get_main_table(self, parsed) -> str:
        """Extract main table from parsed SQL."""
        for table in parsed.find_all(exp.Table):
            return str(table.this)
        return ""

    def _extract_column_from_condition(self, condition: str) -> Optional[str]:
        """Extract column name from a condition string."""
        # Simple regex - in production use proper parsing
        match = re.match(r"(\w+)\s*=", condition)
        if match:
            return match.group(1)
        return None

    def _extract_tables(self, parsed) -> List[str]:
        """Extract all table names from parsed SQL."""
        tables = []
        for table in parsed.find_all(exp.Table):
            tables.append(str(table.this))
        return tables

    def _table_exists(self, table: str) -> bool:
        """Check if a table exists."""
        try:
            sql = f"SELECT 1 FROM {table} LIMIT 0"
            self.executor.execute(sql)
            return True
        except Exception:
            return False
