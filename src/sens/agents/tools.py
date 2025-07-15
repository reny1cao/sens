"""Tools available to the SENS agent for database exploration and query fixing."""

import re
from typing import Any, Dict, List, Optional, Tuple

import structlog
from sqlglot import exp, parse_one

from sens.agents.note_taker import LLMDatabaseNoteTaker
from sens.chat.orchestrator import ChatOrchestrator
from sens.execution.executor import SQLExecutor
from sens.execution.safe_executor import SafeSQLExecutor
from sens.retrieval.embedding.search import EmbeddingSearch
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

log = structlog.get_logger()


class AgentTools:
    """Tools available to the unified agent."""

    def __init__(self, executor=None, generator=None, memory_manager=None):
        # Initialize executor if not provided
        if executor is None:
            from sens.execution.safe_executor import SafeSQLExecutor

            executor = SafeSQLExecutor()

        self.executor = executor
        self.generator = generator
        self.memory_manager = memory_manager
        self.discovered_mappings = {}
        self.current_sql = None
        self.current_database = None

        # Initialize settings for LLM configuration access
        self.settings = get_settings()

        # Initialize LLM-powered note taker
        self.note_taker = LLMDatabaseNoteTaker()

        log.info(
            "agent_tools_initialized",
            has_memory=memory_manager is not None,
            has_note_taker=True,
            has_executor=executor is not None,
        )

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
        agent_notes: str = "",
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

        # Build comprehensive context from exploration results AND accumulated memory
        schema_context = self._build_exploration_schema_context(exploration_results)
        memory_context = self.get_knowledge_context(query)

        # Combine contexts for comprehensive decision making
        full_context = f"""=== SCHEMA DISCOVERY ===
{schema_context}

=== ACCUMULATED KNOWLEDGE ===
{memory_context}"""

        # Log the full context for debugging
        log.info(
            "comprehensive_context_for_sql_generation",
            schema_context_length=len(schema_context),
            memory_context_length=len(memory_context),
            exploration_keys=list(exploration_results.keys()),
        )

        # Generate SQL using direct LLM call with comprehensive context
        try:
            sql = await self._generate_sql_from_exploration(
                modified_query, full_context, agent_notes
            )
            return sql
        except Exception as e:
            log.error(
                "exploration_sql_generation_failed", error=str(e), query=modified_query
            )
            # Fallback to basic SQL generation
            return await self._fallback_sql_generation(modified_query)

    async def execute_sql(self, sql: Optional[str] = None) -> Dict[str, Any]:
        """Execute the current SQL query or provided SQL."""
        # Use provided SQL or fall back to current_sql
        query_to_execute = sql or self.current_sql

        if not query_to_execute:
            return {"error": "No SQL query available to execute", "data": []}

        try:
            log.info("tool_execute_sql", sql=query_to_execute)
            result = self.executor.execute(query_to_execute)

            # Convert QueryResult to dict format expected by the system
            result_dict = result.to_dict() if hasattr(result, "to_dict") else result

            # Let LLM note taker intelligently observe the execution
            await self.note_taker.observe_database_interaction(
                interaction_type="query_execution",
                query=query_to_execute,
                results=result_dict,
                context="User query execution",
            )

            return result_dict

        except Exception as e:
            log.error("execute_sql_error", error=str(e), sql=self.current_sql)
            return {"error": str(e), "data": []}

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

    async def discover_databases(self, prefix: str = "bird_") -> Dict[str, Any]:
        """Discover available databases with given prefix.

        Args:
            prefix: Database name prefix to search for (default: "bird_")

        Returns:
            Dict with success status and list of discovered databases
        """
        log.info("tool_discover_databases", prefix=prefix)

        try:
            # Query to find databases with the specified prefix
            sql = """
            SELECT datname
            FROM pg_database
            WHERE datname LIKE %s
            AND datistemplate = false
            ORDER BY datname
            """

            # Use a parameterized query to prevent SQL injection
            result = self.executor.execute_with_params(sql, (f"{prefix}%",))

            if result.error:
                return {"success": False, "error": result.error, "databases": []}

            databases = [row[0] for row in result.rows]
            log.info(
                "discovered_databases", count=len(databases), databases=databases[:10]
            )

            return {
                "success": True,
                "databases": databases,
                "count": len(databases),
                "prefix": prefix,
            }

        except Exception as e:
            log.error("database_discovery_failed", error=str(e))
            return {"success": False, "error": str(e), "databases": []}

    async def switch_database(self, db_name: str) -> Dict[str, Any]:
        """Switch to a different database for subsequent operations.

        Args:
            db_name: Name of the database to switch to

        Returns:
            Dict with success status and connection information
        """
        log.info("tool_switch_database", db_name=db_name)

        try:
            # Create new database URL
            settings = get_settings()
            current_url = settings.db_url

            # Parse current URL and replace database name
            if current_url.endswith("/"):
                current_url = current_url[:-1]

            # Split URL to get base and current database
            url_parts = current_url.rsplit("/", 1)
            if len(url_parts) == 2:
                base_url = url_parts[0]
                new_db_url = f"{base_url}/{db_name}"
            else:
                # If no database in URL, append it
                new_db_url = f"{current_url}/{db_name}"

            # Test connection to new database
            test_executor = SafeSQLExecutor(new_db_url)
            test_result = test_executor.execute("SELECT current_database()")

            if test_result.error:
                return {
                    "success": False,
                    "error": f"Cannot connect to database {db_name}: {test_result.error}",
                    "current_database": None,
                }

            # Close old connection and replace executor
            self.executor.close()
            self.executor = test_executor

            # Refresh schema graph for new database
            self.schema_graph = SchemaGraph.get_instance()

            # Get actual database name from connection
            actual_db = test_result.rows[0][0] if test_result.rows else db_name

            log.info(
                "database_switched_successfully",
                new_database=actual_db,
                target_database=db_name,
            )

            return {
                "success": True,
                "current_database": actual_db,
                "target_database": db_name,
                "message": f"Successfully switched to database: {actual_db}",
            }

        except Exception as e:
            log.error("database_switch_failed", error=str(e), db_name=db_name)
            return {"success": False, "error": str(e), "current_database": None}

    async def get_current_database(self) -> Dict[str, Any]:
        """Get the name of the currently connected database.

        Returns:
            Dict with current database name and connection status
        """
        try:
            result = self.executor.execute("SELECT current_database()")
            if result.error:
                return {
                    "success": False,
                    "error": result.error,
                    "current_database": None,
                }

            current_db = result.rows[0][0] if result.rows else "unknown"

            return {"success": True, "current_database": current_db}

        except Exception as e:
            log.error("get_current_database_failed", error=str(e))
            return {"success": False, "error": str(e), "current_database": None}

    async def explore_database(self, query: str) -> Dict[str, Any]:
        """Execute a database exploration query."""
        try:
            log.info("tool_explore_database_postgresql", query=query)
            result = self.executor.execute(query)

            # Convert QueryResult to dict format expected by the system
            result_dict = result.to_dict() if hasattr(result, "to_dict") else result

            # Let LLM note taker intelligently observe the exploration
            await self.note_taker.observe_database_interaction(
                interaction_type="exploration",
                query=query,
                results=result_dict,
                context="Database schema exploration",
            )

            return result_dict

        except Exception as e:
            log.error("explore_database_error", error=str(e), query=query)
            return {"error": str(e), "data": []}

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
        """Build comprehensive schema context from all exploration results."""
        context_parts = []

        # If no exploration results, say so clearly
        if not exploration_results:
            return "No database exploration has been performed yet."

        # Document all discovered information without filtering
        context_parts.append("=== DATABASE EXPLORATION FINDINGS ===")

        # 1. Document any discovered tables
        if "discovered_tables" in exploration_results:
            tables = exploration_results["discovered_tables"]
            if tables:
                context_parts.append(
                    f"\nTables found in database ({len(tables)} total):"
                )
                for table in tables:
                    context_parts.append(f"  • {table}")
            else:
                context_parts.append("\nNo tables discovered in recent exploration.")

        # 2. Document any table schemas discovered
        if "table_schemas" in exploration_results:
            schemas = exploration_results["table_schemas"]
            if schemas:
                context_parts.append(
                    f"\nTable schemas discovered ({len(schemas)} tables):"
                )
                for table_name, schema_info in schemas.items():
                    context_parts.append(f"\n  Table: {table_name}")
                    if isinstance(schema_info, dict) and "columns" in schema_info:
                        columns = schema_info["columns"]
                        context_parts.append(
                            f"    Columns ({len(columns)}): {', '.join(columns)}"
                        )
                    elif isinstance(schema_info, list):
                        context_parts.append(
                            f"    Columns ({len(schema_info)}): {', '.join(schema_info)}"
                        )
                    else:
                        context_parts.append(f"    Schema info: {schema_info}")

        # 3. Document raw exploration query results
        raw_results = []
        for key, value in exploration_results.items():
            if key not in [
                "discovered_tables",
                "table_schemas",
                "sample_data",
                "value_mappings",
                "insights",
            ]:
                raw_results.append((key, value))

        if raw_results:
            context_parts.append(
                f"\nRaw exploration results ({len(raw_results)} queries):"
            )
            for result_key, result_data in raw_results:
                if isinstance(result_data, dict):
                    if "rows" in result_data and "columns" in result_data:
                        rows = result_data["rows"]
                        columns = result_data["columns"]
                        context_parts.append(f"\n  Query result '{result_key}':")
                        context_parts.append(f"    Columns: {columns}")
                        if rows:
                            context_parts.append(f"    Found {len(rows)} row(s):")
                            # Show first few rows to give context
                            for i, row in enumerate(rows[:5]):  # Limit to first 5 rows
                                context_parts.append(f"      Row {i+1}: {row}")
                            if len(rows) > 5:
                                context_parts.append(
                                    f"      ... and {len(rows) - 5} more rows"
                                )
                        else:
                            context_parts.append("    No rows found.")
                    elif "error" in result_data:
                        context_parts.append(
                            f"\n  Query '{result_key}' failed: {result_data['error']}"
                        )
                    else:
                        context_parts.append(
                            f"\n  Result '{result_key}': {result_data}"
                        )
                else:
                    context_parts.append(f"\n  Result '{result_key}': {result_data}")

        # 4. Document any sample data
        if "sample_data" in exploration_results:
            sample_data = exploration_results["sample_data"]
            if sample_data:
                context_parts.append(
                    f"\nSample data from tables ({len(sample_data)} tables):"
                )
                for table_name, data in sample_data.items():
                    context_parts.append(f"\n  Sample from '{table_name}':")
                    if isinstance(data, list) and data:
                        context_parts.append(f"    First row: {data[0]}")
                        if len(data) > 1:
                            context_parts.append(f"    Total samples: {len(data)}")
                    else:
                        context_parts.append(f"    Data: {data}")

        # 5. Document any value mappings discovered
        if "value_mappings" in exploration_results:
            mappings = exploration_results["value_mappings"]
            if mappings:
                context_parts.append(
                    f"\nValue mappings discovered ({len(mappings)} mappings):"
                )
                for user_term, db_value in mappings.items():
                    context_parts.append(f"  '{user_term}' maps to '{db_value}'")

        # 6. Document any insights or patterns discovered
        if "insights" in exploration_results:
            insights = exploration_results["insights"]
            if insights:
                context_parts.append(f"\nInsights from exploration:")
                if isinstance(insights, dict):
                    for insight_key, insight_value in insights.items():
                        context_parts.append(f"  {insight_key}: {insight_value}")
                else:
                    context_parts.append(f"  {insights}")

        # 7. Summary statement
        if len(context_parts) == 1:  # Only the header was added
            return "No meaningful database schema information has been discovered yet through exploration."

        context_parts.append(f"\n=== END OF EXPLORATION FINDINGS ===")

        return "\n".join(context_parts)

    async def _generate_sql_from_exploration(
        self, query: str, schema_context: str, agent_notes: str = ""
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

        prompt = f"""You are a PostgreSQL SQL expert with access to comprehensive database exploration findings and accumulated knowledge.

Your task: Generate a COMPLETE SQL query for the user's request, but ONLY if the database actually contains the relevant data.

DATABASE: PostgreSQL (use PostgreSQL-specific syntax and functions)

User Request: {query}

Agent's Current Notes:
{agent_notes if agent_notes else "No current session notes."}

Comprehensive Database Context:
{schema_context}

CRITICAL DECISION RULES:
1. EXAMINE THE EVIDENCE: Look at all exploration findings and accumulated knowledge above
2. IF NO RELEVANT TABLES/COLUMNS EXIST: Do not generate SQL. Instead respond with: "INSUFFICIENT_DATA: The database does not contain tables or columns related to [describe what's missing]"
3. IF RELEVANT DATA EXISTS: Generate a complete PostgreSQL query using only discovered tables and columns
4. NEVER HALLUCINATE: Do not assume tables or columns exist unless explicitly shown in the context above

POSTGRESQL RULES (only if generating SQL):
- Use ONLY tables and columns explicitly mentioned in the context above
- Use PostgreSQL syntax (ILIKE, DATE_TRUNC, INTERVAL, etc.)
- Include proper FROM clause and WHERE conditions
- Use appropriate aggregations and GROUP BY clauses
- Return only the complete SQL query

RESPONSE FORMAT:
- If insufficient data: "INSUFFICIENT_DATA: [explanation]"
- If sufficient data: Return the complete SQL query only

Generate your response:"""

        try:
            response = await self._llm_client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
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
        """Extract SQL query from LLM response, handling INSUFFICIENT_DATA cases."""
        if not response:
            log.error("empty_sql_response")
            return "SELECT 1"  # Fallback query

        response = response.strip()

        # Check if the LLM determined there's insufficient data
        if response.startswith("INSUFFICIENT_DATA:"):
            log.warning("llm_determined_insufficient_data", reason=response)
            # Return a descriptive error instead of generating SQL
            reason = response[len("INSUFFICIENT_DATA:") :].strip()
            return f"-- ERROR: {reason}\nSELECT 'Insufficient data: {reason}' as error_message"

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
            "Generate your response:",
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

    def _extract_table_name_from_query(self, query: str) -> Optional[str]:
        """Extract table name from a query."""
        query_upper = query.upper()

        # For information_schema.columns queries
        if "TABLE_NAME = '" in query_upper:
            start = query_upper.find("TABLE_NAME = '") + len("TABLE_NAME = '")
            end = query_upper.find("'", start)
            return query[start:end] if end > start else None

        # For SELECT FROM queries
        if "FROM " in query_upper:
            parts = query_upper.split("FROM ")
            if len(parts) > 1:
                table_part = parts[1].split()[0]
                return table_part.strip("'\"")

        return None

    def _extract_tables_from_sql(self, sql: str) -> List[str]:
        """Extract table names from SQL query."""
        tables = []
        sql_upper = sql.upper()

        # Simple extraction - can be improved
        if "FROM " in sql_upper:
            parts = sql_upper.split("FROM ")
            for part in parts[1:]:
                table_name = part.split()[0].strip("'\"")
                if table_name and table_name not in tables:
                    tables.append(table_name)

        return tables

    def get_knowledge_context(self, query: str) -> str:
        """Get relevant knowledge context for a query."""
        # Get relevant notes using LLM-powered search
        relevant_notes = self.note_taker.search_notes(query)

        if not relevant_notes:
            return "No specific database knowledge available for this query."

        context_parts = ["=== RELEVANT DATABASE KNOWLEDGE ==="]

        # Add top relevant notes
        for note in relevant_notes[:5]:  # Top 5 most relevant
            context_parts.append(f"• {note.title} (confidence: {note.confidence:.2f})")
            context_parts.append(f"  {note.content}")
            if note.insights:
                context_parts.append(f"  Key insights: {', '.join(note.insights[:2])}")
            if note.tables_involved:
                context_parts.append(f"  Tables: {', '.join(note.tables_involved)}")

        # Add table summaries for any mentioned tables
        query_lower = query.lower()
        for table_name in self.note_taker.table_knowledge.keys():
            if table_name.lower() in query_lower:
                summary = self.note_taker.get_table_summary(table_name)
                if "error" not in summary:
                    context_parts.append(
                        f"\n=== {table_name.upper()} TABLE SUMMARY ==="
                    )
                    if summary.get("description"):
                        context_parts.append(f"Description: {summary['description']}")
                    if summary.get("purpose"):
                        context_parts.append(f"Purpose: {summary['purpose']}")
                    if summary.get("key_insights"):
                        context_parts.append(
                            f"Key insights: {', '.join(summary['key_insights'][:3])}"
                        )

        return "\n".join(context_parts)

    def get_knowledge_summary(self) -> Dict[str, Any]:
        """Get summary of accumulated knowledge."""
        return self.note_taker.get_knowledge_summary()
