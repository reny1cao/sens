"""SQLite-specific tools for the SENS agent."""

import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog

from sens.settings import get_settings

log = structlog.get_logger()


class SQLiteAgentTools:
    """Collection of SQLite-specific tools for the agent."""

    def __init__(self, db_path: Optional[str] = None):
        """Initialize SQLite agent tools.

        Args:
            db_path: Path to the SQLite database file
        """
        self.current_db_path = db_path
        self.settings = get_settings()
        log.info("sqlite_tools_initialized", db_path=db_path)

    async def get_current_database(self) -> Dict[str, Any]:
        """Get information about the currently connected SQLite database.

        Returns:
            Dict with current database information
        """
        log.info("tool_get_current_database_sqlite")

        if not self.current_db_path:
            return {
                "success": True,
                "current_database": None,
                "database_type": "sqlite",
                "message": "No SQLite database currently connected",
            }

        try:
            db_path = Path(self.current_db_path)
            if not db_path.exists():
                return {
                    "success": False,
                    "current_database": None,
                    "database_type": "sqlite",
                    "error": f"SQLite database file does not exist: {self.current_db_path}",
                }

            # Get database info
            with sqlite3.connect(self.current_db_path) as conn:
                cursor = conn.cursor()

                # Get database file size
                file_size = db_path.stat().st_size

                # Get table count
                cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
                table_count = cursor.fetchone()[0]

                return {
                    "success": True,
                    "current_database": str(db_path.name),
                    "database_type": "sqlite",
                    "database_path": self.current_db_path,
                    "file_size_bytes": file_size,
                    "table_count": table_count,
                }

        except Exception as e:
            log.error("get_current_database_failed", error=str(e))
            return {
                "success": False,
                "current_database": None,
                "database_type": "sqlite",
                "error": str(e),
            }

    async def switch_database(self, db_path: str) -> Dict[str, Any]:
        """Switch to a different SQLite database.

        Args:
            db_path: Path to the SQLite database file

        Returns:
            Dict with success status and connection information
        """
        log.info("tool_switch_database_sqlite", db_path=db_path)

        try:
            # Check if file exists
            db_file = Path(db_path)
            if not db_file.exists():
                return {
                    "success": False,
                    "error": f"SQLite database file not found: {db_path}",
                    "current_database": self.current_db_path,
                }

            # Test connection
            with sqlite3.connect(db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT sqlite_version()")
                version = cursor.fetchone()[0]

            # Update current database
            old_db = self.current_db_path
            self.current_db_path = db_path

            return {
                "success": True,
                "message": f"Successfully switched to SQLite database: {db_file.name}",
                "previous_database": old_db,
                "current_database": db_path,
                "sqlite_version": version,
            }

        except Exception as e:
            log.error("switch_database_failed", error=str(e), db_path=db_path)
            return {
                "success": False,
                "error": f"Failed to switch to SQLite database: {str(e)}",
                "current_database": self.current_db_path,
            }

    async def explore_database(
        self, table_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Explore SQLite database schema and structure.

        Args:
            table_name: Optional specific table to explore

        Returns:
            Dict with schema information
        """
        log.info("tool_explore_database_sqlite", table_name=table_name)

        if not self.current_db_path:
            return {"success": False, "error": "No SQLite database connected"}

        try:
            with sqlite3.connect(self.current_db_path) as conn:
                cursor = conn.cursor()

                if table_name:
                    # Get specific table info
                    cursor.execute(
                        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
                        (table_name,),
                    )
                    result = cursor.fetchone()

                    if not result:
                        return {
                            "success": False,
                            "error": f"Table '{table_name}' not found",
                        }

                    # Get table schema
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = cursor.fetchall()

                    # Get sample data
                    cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                    sample_data = cursor.fetchall()

                    return {
                        "success": True,
                        "table_name": table_name,
                        "create_sql": result[0],
                        "columns": [
                            {
                                "name": col[1],
                                "type": col[2],
                                "not_null": bool(col[3]),
                                "default": col[4],
                                "primary_key": bool(col[5]),
                            }
                            for col in columns
                        ],
                        "sample_data": sample_data[:3],  # Limit for agent processing
                        "row_count": len(sample_data),
                    }
                else:
                    # Get all tables
                    cursor.execute(
                        "SELECT name, type, sql FROM sqlite_master WHERE type IN ('table', 'view') ORDER BY name"
                    )
                    tables_info = cursor.fetchall()

                    tables = []
                    for table_info in tables_info:
                        table_name = table_info[0]
                        table_type = table_info[1]

                        # Get row count for tables
                        if table_type == "table":
                            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                            row_count = cursor.fetchone()[0]
                        else:
                            row_count = None

                        tables.append(
                            {
                                "name": table_name,
                                "type": table_type,
                                "row_count": row_count,
                                "create_sql": table_info[2],
                            }
                        )

                    return {
                        "success": True,
                        "database_path": self.current_db_path,
                        "table_count": len([t for t in tables if t["type"] == "table"]),
                        "view_count": len([t for t in tables if t["type"] == "view"]),
                        "tables": tables,
                    }

        except Exception as e:
            log.error("explore_database_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query on SQLite database.

        Args:
            sql: SQL query to execute

        Returns:
            Dict with execution results
        """
        log.info("tool_execute_sql_sqlite", sql_preview=sql[:100])

        if not self.current_db_path:
            return {"success": False, "error": "No SQLite database connected"}

        try:
            start_time = time.time()

            with sqlite3.connect(self.current_db_path) as conn:
                conn.row_factory = sqlite3.Row  # Enable column access by name
                cursor = conn.cursor()

                cursor.execute(sql)

                # Handle different query types
                if sql.strip().upper().startswith(("SELECT", "WITH")):
                    # For SELECT queries, fetch results
                    rows = cursor.fetchall()

                    # Convert to list of dicts for JSON serialization
                    results = []
                    for row in rows:
                        results.append(dict(row))

                    execution_time = (time.time() - start_time) * 1000

                    return {
                        "success": True,
                        "row_count": len(results),
                        "columns": list(rows[0].keys()) if rows else [],
                        "rows": results[:100],  # Limit for agent processing
                        "execution_time_ms": execution_time,
                        "query_type": "SELECT",
                    }
                else:
                    # For other queries (INSERT, UPDATE, DELETE), get affected rows
                    affected_rows = cursor.rowcount
                    execution_time = (time.time() - start_time) * 1000

                    return {
                        "success": True,
                        "affected_rows": affected_rows,
                        "execution_time_ms": execution_time,
                        "query_type": "MODIFICATION",
                    }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            log.error("execute_sql_failed", error=str(e), sql=sql[:100])
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time,
            }

    async def discover_databases(self, search_path: str = ".") -> Dict[str, Any]:
        """Discover SQLite database files in the specified path.

        Args:
            search_path: Directory path to search for SQLite files

        Returns:
            Dict with discovered database files
        """
        log.info("tool_discover_databases_sqlite", search_path=search_path)

        try:
            search_dir = Path(search_path)
            if not search_dir.exists():
                return {
                    "success": False,
                    "error": f"Search path does not exist: {search_path}",
                }

            # Find SQLite files
            sqlite_files = []
            for ext in [".sqlite", ".db", ".sqlite3"]:
                sqlite_files.extend(search_dir.rglob(f"*{ext}"))

            databases = []
            for db_file in sqlite_files:
                try:
                    # Test if it's a valid SQLite database
                    with sqlite3.connect(str(db_file)) as conn:
                        cursor = conn.cursor()
                        cursor.execute(
                            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
                        )
                        table_count = cursor.fetchone()[0]

                    databases.append(
                        {
                            "path": str(db_file),
                            "name": db_file.name,
                            "size_bytes": db_file.stat().st_size,
                            "table_count": table_count,
                        }
                    )
                except Exception:
                    # Skip files that aren't valid SQLite databases
                    continue

            return {
                "success": True,
                "search_path": search_path,
                "databases_found": len(databases),
                "databases": databases,
            }

        except Exception as e:
            log.error("discover_databases_failed", error=str(e))
            return {"success": False, "error": str(e)}

    async def generate_sql(
        self,
        query: str,
        exploration_results: Dict[str, Any],
        mappings: Optional[Dict[str, str]] = None,
        agent_notes: str = "",
    ) -> str:
        """Generate SQL using SQLite-specific syntax and exploration results.

        Args:
            query: User's natural language query
            exploration_results: Results from database exploration
            mappings: Discovered value mappings
            agent_notes: Agent's notes from exploration

        Returns:
            Generated SQLite SQL query
        """
        log.info("tool_generate_sql_sqlite", query=query, mappings=mappings)

        # Apply value mappings discovered during exploration
        modified_query = query
        if mappings:
            for user_term, db_value in mappings.items():
                # Replace user terms with database values
                modified_query = modified_query.replace(user_term, db_value)
                log.info("applying_mapping", from_term=user_term, to_value=db_value)

        # Build schema context from exploration results
        schema_context = self._build_sqlite_schema_context(exploration_results)

        # Log the schema context for debugging
        log.info(
            "schema_context_for_sql_generation",
            context=schema_context,
            exploration_keys=list(exploration_results.keys()),
        )

        # Generate SQL using direct LLM call with SQLite-specific context
        try:
            sql = await self._generate_sql_from_exploration(
                modified_query, schema_context, agent_notes
            )
            return sql
        except Exception as e:
            log.error(
                "sqlite_sql_generation_failed", error=str(e), query=modified_query
            )
            # Fallback to basic SQLite SQL generation
            return await self._fallback_sqlite_sql_generation(modified_query)

    def _build_sqlite_schema_context(self, exploration_results: Dict[str, Any]) -> str:
        """Build focused schema context from SQLite exploration results."""
        context_parts = []

        # Extract table information
        if "discovered_tables" in exploration_results:
            tables = exploration_results["discovered_tables"]
            if tables:
                context_parts.append(f"Available Tables: {', '.join(tables)}")

        # Add detailed schema for important tables
        if "table_schemas" in exploration_results:
            for table_name, table_info in exploration_results["table_schemas"].items():
                # Handle both dict format and list format
                if isinstance(table_info, dict) and "columns" in table_info:
                    columns = table_info["columns"]
                elif isinstance(table_info, list):
                    columns = table_info
                else:
                    continue

                if columns:
                    context_parts.append(f"\nTable '{table_name}':")
                    context_parts.append(f"  Columns: {', '.join(columns)}")

        # Add sample data insights
        if "sample_data" in exploration_results:
            for table_name, sample_data in exploration_results["sample_data"].items():
                if sample_data and len(sample_data) > 0:
                    context_parts.append(f"\nSample from '{table_name}':")
                    sample = (
                        sample_data[0] if isinstance(sample_data, list) else sample_data
                    )
                    if isinstance(sample, dict):
                        sample_str = ", ".join(
                            f"{k}: {v}" for k, v in list(sample.items())[:3]
                        )
                        context_parts.append(f"  Example: {sample_str}")

        # Add value mappings
        if "value_mappings" in exploration_results:
            mappings = exploration_results["value_mappings"]
            if mappings:
                context_parts.append("\nValue Mappings:")
                for key, value in list(mappings.items())[:5]:  # Limit to 5 mappings
                    context_parts.append(f"  {key} = {value}")

        return (
            "\n".join(context_parts)
            if context_parts
            else "No schema information discovered yet."
        )

    async def _generate_sql_from_exploration(
        self, query: str, schema_context: str, agent_notes: str = ""
    ) -> str:
        """Generate SQLite SQL using direct LLM call with exploration context."""
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

        prompt = f"""You are a SQLite SQL expert. Generate a COMPLETE SQL query for the user's request based only on the database schema discovered through exploration.

DATABASE: SQLite (use SQLite-specific syntax and functions)

User Request: {query}

Agent's Discovery Notes:
{agent_notes if agent_notes else "No notes available."}

Database Schema (discovered through exploration):
{schema_context}

SQLITE-SPECIFIC RULES:
1. Use ONLY the tables and columns mentioned in the schema above
2. Return ONLY the COMPLETE SQL query with SELECT, FROM, WHERE clauses
3. Use SQLite syntax and functions (strftime, datetime, etc.)
4. Use SQLite date/time functions: strftime('%Y-%m-%d', date_column)
5. Use SQLite string functions (LIKE for pattern matching, || for concatenation)
6. Use SQLite LIMIT syntax (not TOP)
7. Use single quotes for string literals
8. For case-insensitive matching, use UPPER() or LOWER() functions
9. SQLite column names are case-sensitive by default
10. MUST include FROM clause and appropriate WHERE clauses for filtering

SQLite Examples:
- Date filtering: WHERE date_column >= date('now', '-30 days')
- Case-insensitive search: WHERE UPPER(column_name) LIKE UPPER('%pattern%')
- String concatenation: SELECT column1 || ' ' || column2 as full_name
- Date formatting: SELECT strftime('%Y-%m', date_column) as month

SQL Query:"""

        try:
            response = await self._llm_client.chat.completions.create(
                model="google/gemini-2.0-flash-001",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=500,
            )

            sql = response.choices[0].message.content.strip()

            # Log the raw response for debugging
            log.info("sqlite_sql_generation_raw_response", response=sql[:500])

            # Clean up the response - extract just the SQL
            sql = self._extract_sql_from_response(sql)

            log.info("sqlite_sql_generated_from_exploration", sql=sql)
            return sql

        except Exception as e:
            log.error("llm_sqlite_sql_generation_failed", error=str(e))
            raise e

    async def _fallback_sqlite_sql_generation(self, query: str) -> str:
        """Simple fallback SQLite SQL generation when exploration fails."""
        log.warning("using_fallback_sqlite_sql_generation")

        # Very basic SQL generation based on common patterns
        query_lower = query.lower()

        if "zip" in query_lower and "code" in query_lower:
            return "SELECT zip FROM table_name LIMIT 10"
        elif "count" in query_lower:
            return "SELECT COUNT(*) FROM table_name"
        elif "list" in query_lower or "all" in query_lower:
            return "SELECT * FROM table_name LIMIT 10"
        else:
            return "SELECT name FROM sqlite_master WHERE type='table'"

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
