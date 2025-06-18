"""Format agent messages for user-friendly display."""

from typing import Any, Dict, Optional


class AgentMessageFormatter:
    """Format agent messages into clear, user-friendly text."""

    # Action type mappings to user-friendly descriptions
    ACTION_DESCRIPTIONS = {
        "EXPLORE_DATABASE": "Exploring database structure",
        "GENERATE_SQL": "Generating SQL query",
        "EXECUTE_SQL": "Executing SQL query",
        "VALIDATE_SQL": "Validating SQL syntax",
        "REFLECT": "Analyzing results",
    }

    # Reasoning templates for clearer messages
    REASONING_TEMPLATES = {
        "start": "I'll help you find {}. Let me analyze your request...",
        "explore": "I need to understand your database structure first. Let me check the available tables and columns...",
        "schema": "I found the {} table. Now let me examine its structure to understand what data is available...",
        "generate": "Based on your database schema, I'm creating a SQL query to get the information you need...",
        "execute": "I've prepared the query. Now let me run it to get your results...",
        "complete": "I've successfully retrieved the data you requested.",
    }

    @classmethod
    def format_reasoning(cls, event_data: Dict[str, Any]) -> str:
        """Format reasoning event into user-friendly message."""
        iteration = event_data.get("iteration", 0)
        action_type = event_data.get("action_type", "")
        reasoning = event_data.get("reasoning", "")

        # First iteration - understand the request
        if iteration == 1:
            query = event_data.get("query", "the information")
            return f"I'll help you find {query[:100]}{'...' if len(query) > 100 else ''}. Let me analyze your request..."

        # Format based on action type
        if action_type == "EXPLORE_DATABASE":
            if "table_name" in reasoning.lower() or "tables" in reasoning.lower():
                return "I need to check which tables contain the data you're looking for..."
            elif "column" in reasoning.lower() or "schema" in reasoning.lower():
                return "Let me examine the table structure to understand what information is available..."
            else:
                return "Exploring your database to find the relevant data..."

        elif action_type == "GENERATE_SQL":
            return "Now I'll create a SQL query to retrieve the specific information you requested..."

        elif action_type == "EXECUTE_SQL":
            return "I've prepared the query. Let me run it to get your results..."

        # Default: use the original reasoning but make it cleaner
        return cls._clean_reasoning(reasoning)

    @classmethod
    def format_action(cls, event_data: Dict[str, Any]) -> str:
        """Format action event into user-friendly message."""
        action_type = event_data.get("action_type", "")
        parameters = event_data.get("parameters", {})

        # Get friendly action description
        action_desc = cls.ACTION_DESCRIPTIONS.get(action_type, action_type)

        # Add specific details based on action type
        if action_type == "EXPLORE_DATABASE" and parameters.get("query"):
            query = parameters["query"]
            if "table_name" in query:
                return f"{action_desc}: Looking for available tables..."
            elif "column_name" in query:
                table = parameters.get("table_name", "the relevant table")
                return f"{action_desc}: Examining structure of {table}..."

        elif action_type == "GENERATE_SQL":
            return f"{action_desc} based on your requirements..."

        elif action_type == "EXECUTE_SQL":
            return f"{action_desc} to retrieve your data..."

        return f"{action_desc}..."

    @classmethod
    def format_observation(cls, event_data: Dict[str, Any]) -> str:
        """Format observation event into user-friendly message."""
        success = event_data.get("success", False)
        action_type = event_data.get("action_type", "")
        content_preview = event_data.get("content_preview", "")

        if not success:
            return "❌ Encountered an issue. Let me try a different approach..."

        # Format based on what was observed
        if action_type == "explore_database":
            if isinstance(content_preview, dict):
                row_count = content_preview.get("row_count", 0)
                if row_count > 0:
                    return f"✓ Found {row_count} relevant items in the database"
                else:
                    return "✓ Database exploration completed"
            return "✓ Database structure analyzed"

        elif action_type == "generate_sql":
            return "✓ SQL query created successfully"

        elif action_type == "execute_sql":
            if isinstance(content_preview, dict):
                row_count = content_preview.get("row_count", 0)
                if row_count > 0:
                    return f"✓ Query executed successfully - found {row_count} results"
                else:
                    return "✓ Query executed but no matching data found"
            return "✓ Query executed successfully"

        return "✓ Step completed successfully"

    @classmethod
    def _clean_reasoning(cls, reasoning: str) -> str:
        """Clean up technical reasoning for user display."""
        if not reasoning:
            return "Analyzing your request..."

        # Remove technical jargon
        replacements = {
            "I need to": "Let me",
            "I will": "I'll",
            "SQL query": "query",
            "execute": "run",
            "formulate": "create",
            "retrieve": "get",
        }

        cleaned = reasoning
        for old, new in replacements.items():
            cleaned = cleaned.replace(old, new)

        # Ensure it ends with proper punctuation
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "..."

        return cleaned

    @classmethod
    def format_sql_for_display(cls, sql: str, parameters: Optional[Dict] = None) -> str:
        """Format SQL for user-friendly display in action steps."""
        if not sql:
            return ""

        # Clean up SQL formatting
        sql_lines = sql.strip().split("\n")
        cleaned_lines = []

        for line in sql_lines:
            line = line.strip()
            if line:
                # Indent subqueries and conditions
                if line.upper().startswith(
                    ("SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING")
                ):
                    cleaned_lines.append(line)
                else:
                    cleaned_lines.append(f"  {line}")

        formatted_sql = "\n".join(cleaned_lines)

        # If we have parameters (for exploring queries), show them
        if parameters and parameters.get("query"):
            return parameters["query"]

        return formatted_sql
