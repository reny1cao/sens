"""Configurable tool registry for different database types and evaluation contexts."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

import structlog

from sens.agents.sqlite_tools import SQLiteAgentTools
from sens.agents.tools import AgentTools

log = structlog.get_logger()


class DatabaseType(str, Enum):
    """Supported database types."""

    POSTGRESQL = "postgresql"
    SQLITE = "sqlite"


class EvaluationContext(str, Enum):
    """Evaluation context types."""

    BIRD_CRITIC = "bird_critic"
    BIRD_SQL_DEV = "bird_sql_dev"
    GENERAL = "general"


class ToolRegistry:
    """Registry for managing different tool sets based on context."""

    def __init__(self):
        """Initialize the tool registry."""
        self.tool_sets = {}
        self._setup_default_configurations()

    def _setup_default_configurations(self):
        """Set up default tool configurations for different contexts."""
        # BIRD-CRITIC configuration (PostgreSQL)
        self.tool_sets[EvaluationContext.BIRD_CRITIC] = {
            "database_type": DatabaseType.POSTGRESQL,
            "tools": [
                "get_current_database",
                "switch_database",
                "discover_databases",
                "explore_database",
                "execute_sql",
            ],
            "disabled_tools": [
                "search_schema",  # Disabled in original implementation
                "search_values",  # Disabled in original implementation
                "diagnose_empty_results",  # Disabled in original implementation
            ],
            "instructions": """
You are working with PostgreSQL databases. You have the following tools available:

1. get_current_database() - Check which PostgreSQL database you're currently connected to
2. switch_database(db_name) - Switch to a different PostgreSQL database by name
3. discover_databases(prefix) - Find PostgreSQL databases with a specific prefix
4. explore_database(table_name=None) - Explore PostgreSQL database schema and tables
5. execute_sql(sql) - Execute SQL queries on the current PostgreSQL database

For BIRD-CRITIC tasks:
- Always start by checking the current database
- Switch to the target database using the provided database prefix
- Explore the schema to understand available tables and columns
- Generate and execute SQL queries to solve the problem
""",
        }

        # BIRD-SQL-DEV configuration (SQLite)
        self.tool_sets[EvaluationContext.BIRD_SQL_DEV] = {
            "database_type": DatabaseType.SQLITE,
            "tools": [
                "get_current_database",
                "switch_database",
                "discover_databases",
                "explore_database",
                "execute_sql",
            ],
            "disabled_tools": [],
            "instructions": """
You are working with SQLite database files. You have the following tools available:

1. get_current_database() - Check which SQLite database file you're currently connected to
2. switch_database(db_path) - Switch to a different SQLite database file by path
3. discover_databases(search_path) - Find SQLite database files in a directory
4. explore_database(table_name=None) - Explore SQLite database schema and tables
5. execute_sql(sql) - Execute SQL queries on the current SQLite database

For BIRD-SQL-DEV tasks:
- Start by switching to the correct SQLite database file
- Explore the schema to understand available tables and columns
- Generate and execute SQL queries using SQLite syntax
- Focus on accurate SQL generation for the given question
""",
        }

        # General configuration (default PostgreSQL)
        self.tool_sets[EvaluationContext.GENERAL] = {
            "database_type": DatabaseType.POSTGRESQL,
            "tools": [
                "get_current_database",
                "switch_database",
                "discover_databases",
                "explore_database",
                "execute_sql",
                "search_schema",
                "search_values",
                "diagnose_empty_results",
            ],
            "disabled_tools": [],
            "instructions": """
You are a SQL expert with access to database exploration and query tools.
Use the available tools to understand the database schema and generate accurate SQL queries.
""",
        }

    def get_tools_for_context(
        self, context: EvaluationContext, db_path: Optional[str] = None, **kwargs
    ) -> Dict[str, Any]:
        """Get the appropriate tool set for the given context.

        Args:
            context: The evaluation context
            db_path: Optional database path (for SQLite)
            **kwargs: Additional configuration options

        Returns:
            Dict containing tools instance and configuration
        """
        if context not in self.tool_sets:
            log.warning("unknown_context", context=context)
            context = EvaluationContext.GENERAL

        config = self.tool_sets[context]
        database_type = config["database_type"]

        # Create appropriate tools instance
        if database_type == DatabaseType.SQLITE:
            tools_instance = SQLiteAgentTools(db_path=db_path)
        else:
            tools_instance = AgentTools()

        # Disable specified tools
        for tool_name in config.get("disabled_tools", []):
            if hasattr(tools_instance, tool_name):
                # Replace with disabled version
                setattr(
                    tools_instance, tool_name, self._create_disabled_tool(tool_name)
                )

        return {
            "tools": tools_instance,
            "database_type": database_type,
            "available_tools": config["tools"],
            "instructions": config["instructions"],
            "context": context,
        }

    def _create_disabled_tool(self, tool_name: str):
        """Create a disabled version of a tool."""

        async def disabled_tool(*args, **kwargs):
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is disabled in this evaluation context",
            }

        return disabled_tool

    def register_custom_context(
        self,
        context: str,
        database_type: DatabaseType,
        tools: List[str],
        instructions: str,
        disabled_tools: Optional[List[str]] = None,
    ):
        """Register a custom evaluation context.

        Args:
            context: Name of the custom context
            database_type: Type of database
            tools: List of available tool names
            instructions: Instructions for the agent
            disabled_tools: List of tools to disable
        """
        self.tool_sets[context] = {
            "database_type": database_type,
            "tools": tools,
            "instructions": instructions,
            "disabled_tools": disabled_tools or [],
        }

        log.info(
            "custom_context_registered",
            context=context,
            database_type=database_type,
            tool_count=len(tools),
        )

    def get_instructions_for_context(self, context: EvaluationContext) -> str:
        """Get the instructions string for a specific context."""
        config = self.tool_sets.get(context, self.tool_sets[EvaluationContext.GENERAL])
        return config["instructions"]

    def list_available_contexts(self) -> List[str]:
        """List all available evaluation contexts."""
        return list(self.tool_sets.keys())


# Global tool registry instance
tool_registry = ToolRegistry()
