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
        """DISABLED: Search for relevant schema elements."""
        log.info("tool_search_schema_disabled", query=query)
        return {
            "error": "Schema search disabled - agent must work without schema discovery",
            "tables": [],
            "columns": [],
        }

    async def search_values(
        self,
        table: str,
        column: str,
        pattern: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """DISABLED: Search for actual values in a database column."""
        log.info(
            "tool_search_values_disabled", table=table, column=column, pattern=pattern
        )
        return [
            {"error": "Value search disabled - agent must work without value discovery"}
        ]

    async def find_similar_values(
        self,
        user_term: str,
        table: str,
        column: str,
        threshold: float = 0.6,
    ) -> Dict[str, Any]:
        """DISABLED: Find values similar to user term using fuzzy matching and embeddings."""
        log.info(
            "tool_find_similar_values_disabled",
            term=user_term,
            table=table,
            column=column,
        )
        return {
            "found": False,
            "error": "Similar values search disabled - agent must work without value discovery",
            "values": [],
        }

    async def get_value_distribution(
        self,
        table: str,
        column: str,
    ) -> Dict[str, Any]:
        """DISABLED: Get distribution statistics for a column."""
        log.info("tool_get_value_distribution_disabled", table=table, column=column)
        return {
            "error": "Value distribution disabled - agent must work without data exploration"
        }

    async def generate_sql(
        self,
        query: str,
        exploration_results: Dict[str, Any],
        mappings: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate SQL using only what we discovered through database exploration."""
        log.info("tool_generate_sql_exploration", query=query, mappings=mappings)

        # Apply value mappings discovered during exploration
        modified_query = query
        if mappings:
            for user_term, db_value in mappings.items():
                # Replace user terms with database values
                modified_query = modified_query.replace(user_term, db_value)
                log.info("applying_mapping", from_term=user_term, to_value=db_value)

        # Build schema context from exploration results
        schema_context = self._build_exploration_schema_context(exploration_results)

        # Log the schema context for debugging
        log.info(
            "schema_context_for_sql_generation",
            context=schema_context,
            exploration_keys=list(exploration_results.keys()),
        )

        # Generate SQL using direct LLM call with exploration context
        try:
            sql = await self._generate_sql_from_exploration(
                modified_query, schema_context
            )
            return sql
        except Exception as e:
            log.error(
                "exploration_sql_generation_failed", error=str(e), query=modified_query
            )
            # Fallback to basic SQL generation
            return await self._fallback_sql_generation(modified_query)

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
        """DISABLED: Diagnose why a query returned no results."""
        log.info("tool_diagnose_empty_results_disabled")
        return {
            "error": "Diagnosis disabled - agent must work without result analysis",
            "issues": [],
            "suggestions": [],
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

    async def explore_database(self, query: str) -> Dict[str, Any]:
        """Execute exploratory SQL queries to understand the PostgreSQL database.

        This tool allows direct SQL execution for exploration purposes:
        - Check table structures in PostgreSQL
        - Sample data from tables using PostgreSQL syntax
        - Understand value formats and data types
        - Discover relationships and constraints
        - Use PostgreSQL-specific information_schema queries

        CONTEXT: You are exploring a PostgreSQL database with financial/stock market data.
        Use PostgreSQL-specific syntax and functions when needed.

        Args:
            query: PostgreSQL SQL query to execute (read-only SELECT only)

        Returns:
            Dict with query results and metadata
        """
        log.info("tool_explore_database_postgresql", query=query)

        try:
            # Safety check - only allow SELECT queries
            normalized_query = query.strip().upper()
            if not normalized_query.startswith("SELECT"):
                return {
                    "success": False,
                    "error": "Only SELECT queries allowed for exploration",
                    "hint": "Use SELECT statements to explore data",
                }

            # Execute query
            result = self.executor.execute(query)

            if result.error:
                return {
                    "success": False,
                    "error": result.error,
                    "hint": self._suggest_exploration_fix(result.error),
                }

            # Format results for agent understanding
            return {
                "success": True,
                "columns": result.columns,
                "row_count": result.row_count,
                "data": result.rows[:20],  # Limit to 20 rows for exploration
                "truncated": result.row_count > 20,
                "insights": self._extract_insights(result),
            }

        except Exception as e:
            log.error("explore_database_failed", error=str(e))
            return {"success": False, "error": str(e)}

    def _suggest_exploration_fix(self, error: str) -> str:
        """Suggest how to fix common exploration errors."""
        error_lower = error.lower()

        if "does not exist" in error_lower:
            return "Try: SELECT table_name FROM information_schema.tables"
        elif "column" in error_lower and "does not exist" in error_lower:
            return "Try: SELECT column_name FROM information_schema.columns WHERE table_name = 'your_table'"
        elif "syntax error" in error_lower:
            return "Check SQL syntax. Example: SELECT * FROM table_name LIMIT 5"
        else:
            return "Try a simpler query first"

    def _extract_insights(self, result) -> Dict[str, Any]:
        """Extract useful insights from query results."""
        insights = {}

        if result.row_count == 0:
            insights["empty_result"] = True
            insights["suggestion"] = "No data found. Check table name or conditions."

        # Analyze data types and patterns
        if result.rows:
            sample_row = result.rows[0]
            insights["data_types"] = {}

            for i, col in enumerate(result.columns):
                value = sample_row[i] if i < len(sample_row) else None
                insights["data_types"][col] = (
                    type(value).__name__ if value is not None else "null"
                )

        return insights

    def _build_exploration_schema_context(
        self, exploration_results: Dict[str, Any]
    ) -> str:
        """Build focused schema context from exploration results."""
        context_parts = []

        # Focus on main data tables (skip system tables)
        if "discovered_tables" in exploration_results:
            tables = exploration_results["discovered_tables"]
            # Filter out PostgreSQL system tables
            data_tables = [
                t
                for t in tables
                if not t.startswith("pg_") and t != "information_schema"
            ]
            # Prioritize main tables
            primary_tables = [
                t for t in data_tables if t in ["securities", "daily_prices", "trades"]
            ]
            other_tables = [t for t in data_tables if t not in primary_tables]

            if primary_tables:
                context_parts.append(f"Primary Tables: {', '.join(primary_tables)}")
            if other_tables[:5]:  # Limit to first 5 other tables
                context_parts.append(f"Other Tables: {', '.join(other_tables[:5])}")

        # Add detailed schema for important tables
        if "table_schemas" in exploration_results:
            # Prioritize schema info for key tables
            for table in ["daily_prices", "securities", "trades"]:
                if table in exploration_results["table_schemas"]:
                    columns = exploration_results["table_schemas"][table]
                    if columns:
                        # Group columns by type for better understanding
                        key_cols = [
                            c
                            for c in columns
                            if c in ["id", "symbol", "trade_date", "created_at"]
                        ]
                        price_cols = [
                            c
                            for c in columns
                            if "price" in c.lower()
                            or c in ["open", "high", "low", "close"]
                        ]
                        volume_cols = [c for c in columns if "volume" in c.lower()]
                        metric_cols = [
                            c
                            for c in columns
                            if c not in key_cols + price_cols + volume_cols
                        ]

                        context_parts.append(f"\nTable '{table}':")
                        if key_cols:
                            context_parts.append(
                                f"  Key columns: {', '.join(key_cols)}"
                            )
                        if price_cols:
                            context_parts.append(
                                f"  Price columns: {', '.join(price_cols)}"
                            )
                        if volume_cols:
                            context_parts.append(
                                f"  Volume columns: {', '.join(volume_cols)}"
                            )
                        if metric_cols[:5]:  # Limit metrics shown
                            context_parts.append(
                                f"  Other metrics: {', '.join(metric_cols[:5])}"
                            )

        # Add curated sample data
        if "sample_data" in exploration_results:
            for table in ["daily_prices", "securities"]:
                if table in exploration_results["sample_data"]:
                    data = exploration_results["sample_data"][table]
                    if data and len(data) > 0:
                        sample = data[0] if isinstance(data, list) else data
                        # Extract key fields from sample
                        if table == "daily_prices" and len(sample) > 6:
                            context_parts.append(f"\nSample from '{table}':")
                            context_parts.append(
                                f"  Symbol: {sample[1]}, Date: {sample[2]}, Close: {sample[6]}"
                            )
                        elif table == "securities" and len(sample) > 1:
                            context_parts.append(f"\nSample from '{table}':")
                            context_parts.append(
                                f"  Symbol: {sample[0]}, Company: {sample[1]}"
                            )

        # Add value mappings in a clear format
        if "value_mappings" in exploration_results:
            mappings = exploration_results["value_mappings"]
            if mappings:
                context_parts.append("\nStock Symbol Mappings:")
                # Group by first letter for organization
                for key, value in sorted(mappings.items())[:10]:  # Limit to 10 mappings
                    if len(key) > 20:  # Truncate long company names
                        key = key[:20] + "..."
                    context_parts.append(f"  {key} = {value}")

        # Add discovered patterns or insights
        if "insights" in exploration_results:
            insights = exploration_results["insights"]
            context_parts.append(f"\nData Insights: {insights}")

        return (
            "\n".join(context_parts)
            if context_parts
            else "No schema information discovered yet."
        )

    async def _generate_sql_from_exploration(
        self, query: str, schema_context: str
    ) -> str:
        """Generate SQL using direct LLM call with exploration context."""
        # Initialize OpenAI client if needed
        if not hasattr(self, "_llm_client"):
            from openai import AsyncOpenAI

            cfg = self.settings.get_openrouter_config()
            self._llm_client = AsyncOpenAI(
                base_url=cfg["base_url"],
                api_key=cfg["api_key"],
                default_headers={
                    "HTTP-Referer": str(cfg["headers"]["HTTP-Referer"]),
                    "X-Title": cfg["headers"]["X-Title"],
                },
            )

        prompt = f"""You are a PostgreSQL SQL expert. Generate a COMPLETE SQL query for the user's request based only on the database schema discovered through exploration.

DATABASE: PostgreSQL (use PostgreSQL-specific syntax and functions)

User Request: {query}

Database Schema (discovered through exploration):
{schema_context}

POSTGRESQL-SPECIFIC RULES:
1. Use ONLY the tables and columns mentioned in the schema above
2. Return ONLY the COMPLETE SQL query with SELECT, FROM, WHERE clauses
3. Use PostgreSQL syntax and functions (DATE_TRUNC, EXTRACT, AGE, etc.)
4. Use proper PostgreSQL date/timestamp handling with INTERVAL syntax
5. Use PostgreSQL string functions (ILIKE for case-insensitive matching)
6. For aggregations, use PostgreSQL window functions when appropriate
7. Use PostgreSQL LIMIT syntax (not TOP)
8. Use double quotes for case-sensitive identifiers if needed
9. If you need to filter by company names, check if there's a mapping in the schema
10. For stock data, common columns are: symbol, trade_date, open, high, low, close, volume
11. MUST include FROM clause and appropriate WHERE clauses for filtering

PostgreSQL Examples:
- Time filtering: WHERE trade_date >= CURRENT_DATE - INTERVAL '30 days'
- Case-insensitive search: WHERE company_name ILIKE '%apple%'
- Date truncation: SELECT DATE_TRUNC('month', trade_date) as month
- Window functions: ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY trade_date DESC)

SQL Query:"""

        try:
            response = await self._llm_client.chat.completions.create(
                model="openai/gpt-4",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )

            sql = response.choices[0].message.content.strip()

            # Log the raw response for debugging
            log.info("sql_generation_raw_response", response=sql[:500])

            # Clean up the response - extract just the SQL
            sql = self._extract_sql_from_response(sql)

            log.info("sql_generated_from_exploration", sql=sql)
            return sql

        except Exception as e:
            log.error("llm_sql_generation_failed", error=str(e))
            raise e

    async def _fallback_sql_generation(self, query: str) -> str:
        """Simple fallback SQL generation when exploration fails."""
        log.warning("using_fallback_sql_generation")

        # Very basic SQL generation based on common patterns
        query_lower = query.lower()

        if "apple" in query_lower or "aapl" in query_lower:
            return "SELECT * FROM daily_prices WHERE symbol = 'AAPL' ORDER BY trade_date DESC LIMIT 10"
        elif "stock" in query_lower and "price" in query_lower:
            return "SELECT * FROM daily_prices ORDER BY trade_date DESC LIMIT 10"
        elif "companies" in query_lower or "securities" in query_lower:
            return "SELECT * FROM securities LIMIT 10"
        else:
            return "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"

    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from LLM response."""
        if not response:
            log.error("empty_sql_response")
            return "SELECT 1"  # Fallback query

        # Remove markdown code blocks if present
        if "```sql" in response.lower():
            # Case-insensitive search for sql block
            import re

            pattern = r"```sql\s*(.*?)```"
            match = re.search(pattern, response, re.DOTALL | re.IGNORECASE)
            if match:
                response = match.group(1).strip()
        elif "```" in response:
            # Generic code block
            start = response.find("```") + 3
            end = response.find("```", start)
            if end != -1:
                response = response[start:end].strip()

        # Remove common prefixes and labels
        prefixes_to_remove = [
            "SQL Query:",
            "Query:",
            "sql:",
            "SQL:",
            "Here is the SQL query:",
            "Here's the SQL:",
        ]
        for prefix in prefixes_to_remove:
            if response.startswith(prefix):
                response = response[len(prefix) :].strip()

        # Find the actual SQL query (looks for SELECT/WITH/DELETE/UPDATE/INSERT)
        sql_keywords = ["SELECT", "WITH", "DELETE", "UPDATE", "INSERT"]
        lines = response.split("\n")

        # Find first line that starts with SQL keyword
        sql_start_idx = -1
        for i, line in enumerate(lines):
            line_upper = line.strip().upper()
            if any(line_upper.startswith(keyword) for keyword in sql_keywords):
                sql_start_idx = i
                break

        if sql_start_idx >= 0:
            # Extract from SQL start to end, looking for a terminating semicolon or end of text
            sql_lines = []
            for i in range(sql_start_idx, len(lines)):
                sql_lines.append(lines[i])
                if lines[i].strip().endswith(";"):
                    break
            response = "\n".join(sql_lines)

        # Final cleanup
        response = response.strip()

        # If we still don't have valid SQL, log error
        if not response or not any(
            response.upper().startswith(kw) for kw in sql_keywords
        ):
            log.error("invalid_sql_extraction", extracted=response[:100])
            return "SELECT 1"  # Fallback

        return response
