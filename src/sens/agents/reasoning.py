"""Reasoning engine for the SENS agent using LLMs."""

from typing import Any, Dict, List, Optional

import structlog
from openai import AsyncOpenAI

from sens.settings import get_settings

log = structlog.get_logger()


class ReasoningEngine:
    """Uses LLMs to reason about the current situation and plan next actions."""

    def __init__(self, model: Optional[str] = None, models: Optional[List[str]] = None):
        """Initialize the reasoning engine.

        Args:
            model: Optional model override
            models: Optional list of models to try in order
        """
        self.settings = get_settings()
        self.config = self.settings.agent_reasoning

        # Determine models to use
        if models:
            self.models = models
        elif model:
            self.models = [model]
        else:
            # Use configured models
            self.models = [self.config.primary_model]
            if self.config.fallback_model:
                self.models.append(self.config.fallback_model)

        # Initialize OpenAI client with OpenRouter config

        cfg = self.settings.get_openrouter_config()
        self.client = AsyncOpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            default_headers={
                "HTTP-Referer": str(cfg["headers"]["HTTP-Referer"]),
                "X-Title": cfg["headers"]["X-Title"],
            },
        )

        log.info("reasoning_engine_initialized", models=self.models)

    async def decide_action(
        self,
        user_query: str,
        full_context: str,
        iteration: int,
    ) -> Dict[str, Any]:
        """Decide what action to take based on full context.

        Args:
            user_query: Original user query
            full_context: Complete context including all history
            iteration: Current iteration number

        Returns:
            Dict with action_type, parameters, reasoning, and notes
        """
        prompt = f"""You are an intelligent PostgreSQL database agent helping to answer user queries.

DATABASE TYPE: PostgreSQL (use PostgreSQL-specific syntax and functions)

User Query: {user_query}
Current Iteration: {iteration}

========================================
CURRENT CONTEXT (What I know so far):
========================================
{full_context}
========================================

🔍 **IMPORTANT**: Before choosing any action, check if you have CONVERSATION HISTORY above.
If previous queries in this conversation have already explored the database or gathered information that's relevant to the current query, USE THAT KNOWLEDGE instead of repeating the same exploration.

🎯 **FOLLOW-UP QUESTIONS**: If the user's query references previous work (e.g., "those tables", "that analysis", "following", "suggest questions"), use the conversation history to understand what they're referring to and provide relevant suggestions.

Available Actions:
1. EXPLORE_DATABASE - Execute PostgreSQL SELECT queries to understand database structure and discover data
2. GENERATE_SQL - Generate SQL to answer the user's query (only after sufficient schema exploration)
3. EXECUTE_SQL - Execute the generated SQL (ONLY after GENERATE_SQL has been called)
4. DISCOVER_DATABASES - Find available databases with a given prefix
5. SWITCH_DATABASE - Switch to a different database
6. GET_CURRENT_DATABASE - Get the current database name
7. RESPOND_TO_USER - Provide answer, ask for clarification, or suggest options to the user

WORKFLOW RULES:
- EXECUTE_SQL can only be called after GENERATE_SQL has been successfully called
- If you need to execute SQL but haven't generated it yet, call GENERATE_SQL first
- Never call EXECUTE_SQL unless you've already called GENERATE_SQL in a previous step

DECISION STRATEGY:
1. **CHECK CONVERSATION HISTORY FIRST**: If previous queries have already discovered relevant tables/columns, use that knowledge
2. **FOR FOLLOW-UP QUESTIONS**: If user asks for "suggestions", "follow-up questions", or references previous analysis, use RESPOND_TO_USER to provide relevant suggestions based on conversation history
3. Only EXPLORE_DATABASE if you need NEW information not available from conversation history
4. Then GENERATE_SQL based on what you discovered (or already know from conversation)
5. Finally EXECUTE_SQL to get the user's requested data
6. If results are empty or wrong, use EXPLORE_DATABASE again to investigate

IMPORTANT: Consider these scenarios for RESPOND_TO_USER:
- If the user asks about available data, schema, or capabilities → RESPOND_TO_USER
- If the query references previous analysis and asks for suggestions/follow-ups → RESPOND_TO_USER with suggestions
- If the query is ambiguous (e.g., "recent", unclear timeframe) → RESPOND_TO_USER (request clarification)
- If you need user guidance on multiple valid interpretations → RESPOND_TO_USER (suggest options)
- If the database schema doesn't seem relevant to the query → RESPOND_TO_USER explaining the mismatch
- Only proceed with SQL if the query is clear and requires data retrieval

Based on the context above, decide which action to take and provide the necessary parameters.

Respond in this JSON format:
{{
    "action_type": "EXPLORE_DATABASE|GENERATE_SQL|EXECUTE_SQL|DISCOVER_DATABASES|SWITCH_DATABASE|GET_CURRENT_DATABASE|RESPOND_TO_USER",
    "parameters": {{...}},
    "reasoning": "Why you chose this action",
    "notes": "Any important discoveries to remember (optional)"
}}

Parameter examples:
For EXPLORE_DATABASE: {{"query": "SELECT ..."}}
For GENERATE_SQL: {{}}
For EXECUTE_SQL: {{}}
For DISCOVER_DATABASES: {{"prefix": "bird_"}}
For SWITCH_DATABASE: {{"db_name": "bird_financial"}} or {{"db_path": "/path/to/database.db"}} for SQLite
For GET_CURRENT_DATABASE: {{}}
For RESPOND_TO_USER:
  - To provide answer: {{"response_type": "answer", "message": "Based on our previous analysis... Here are some suggestions: 1) ... 2) ... 3) ..."}}
  - To request clarification: {{"response_type": "clarification", "message": "I need clarification about...", "options": ["Option 1", "Option 2"]}}
  - To suggest follow-up questions: {{"response_type": "suggestions", "message": "Based on your correlation analysis...", "suggestions": ["What factors influence loan amounts most?", "Which districts have the highest a10 values?", "Are there seasonal patterns in loan data?"]}}

PostgreSQL Exploration Examples:
- List tables: {{"query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"}}
- Examine table structure: {{"query": "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'your_table' AND table_schema = 'public' ORDER BY ordinal_position"}}
- Sample data: {{"query": "SELECT * FROM your_table LIMIT 5"}}
- Search for entities: {{"query": "SELECT * FROM your_table WHERE column_name ILIKE '%search_term%' LIMIT 10"}}
- Count records: {{"query": "SELECT COUNT(*) as total_records FROM your_table"}}
"""

        # Use LLM to decide
        response = await self._call_llm(prompt)

        # Parse JSON response
        return self._parse_json_response(response)

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON response from LLM."""
        try:
            # Try to extract JSON from the response
            import json
            import re

            # Look for JSON block
            json_match = re.search(r"\{.*\}", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                result = json.loads(json_str)

                # Ensure required fields
                if "action_type" not in result:
                    log.error(
                        "missing_action_type_in_response", response=response[:200]
                    )
                    result["action_type"] = "EXPLORE_DATABASE"
                    result["parameters"] = {
                        "query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                    }

                if "parameters" not in result:
                    result["parameters"] = {}

                if "reasoning" not in result:
                    result["reasoning"] = "Proceeding with exploration"

                return result
            else:
                log.error("no_json_in_response", response=response[:200])
                # Fallback
                return {
                    "action_type": "EXPLORE_DATABASE",
                    "parameters": {
                        "query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                    },
                    "reasoning": "Starting with database exploration",
                }

        except Exception as e:
            log.error("json_parse_error", error=str(e), response=response[:200])
            # Fallback
            return {
                "action_type": "EXPLORE_DATABASE",
                "parameters": {
                    "query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
                },
                "reasoning": "Starting with database exploration",
            }

    async def _call_llm(self, prompt: str) -> str:
        """Call LLM with the prompt."""
        # Try each model in order
        for model in self.models:
            try:
                # Call OpenRouter API
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    timeout=self.config.timeout_seconds,
                )

                # Extract content from response
                content = response.choices[0].message.content
                log.info("reasoning_llm_success", model=model)
                return content

            except Exception as e:
                log.error("reasoning_llm_failed", error=str(e), model=model)
                # Try next model
                continue

        # All models failed, fallback to simple heuristics
        log.warning("all_reasoning_models_failed", models=self.models)
        return self._fallback_reasoning(prompt)

    def _fallback_reasoning(self, prompt: str) -> str:
        """Smart heuristic-based reasoning when LLM fails."""
        prompt_lower = prompt.lower()

        # Count different types of actions to detect loops
        table_count = prompt_lower.count("information_schema.tables")
        column_count = prompt_lower.count("information_schema.columns")
        discover_count = prompt_lower.count("discover_databases")

        # Check context for SQL status
        current_sql_exists = "=== current sql ===" in prompt_lower
        sql_generated_status = "✅ sql generated" in prompt_lower

        # If SQL exists, execute it
        if current_sql_exists or sql_generated_status:
            return """{"action_type": "EXECUTE_SQL", "parameters": {}, "reasoning": "SQL is available and ready to execute to get the requested results.", "notes": "Fallback: Executing existing SQL"}"""

        # Check for DISCOVER_DATABASES loops (critical fix)
        if discover_count >= 2:
            # Agent keeps discovering databases but never switches to one
            # Look for financial/transaction-related databases in the context
            if "bird_financial" in prompt_lower:
                return """{"action_type": "SWITCH_DATABASE", "parameters": {"db_name": "bird_financial"}, "reasoning": "Found bird_financial database which likely contains transaction and payment data - switching to it instead of discovering again"}"""
            elif "bird_debit_card" in prompt_lower:
                return """{"action_type": "SWITCH_DATABASE", "parameters": {"db_name": "bird_debit_card_specializing"}, "reasoning": "Found bird_debit_card_specializing database which likely contains payment type data - switching to it"}"""
            elif "discovered_databases" in prompt_lower and "count=" in prompt_lower:
                # Generic fallback when databases were discovered but no specific match
                return """{"action_type": "RESPOND_TO_USER", "parameters": {"response_type": "answer", "message": "I discovered multiple databases but need your guidance on which one to explore. Available options include financial, card games, debit card, and other specialized datasets. Which type of data are you most interested in?"}, "reasoning": "Breaking discover loop - asking user to choose from available databases"}"""

        # Check for stuck table exploration loops
        if table_count >= 3 and column_count == 0:
            # Agent keeps listing tables but never examines structure
            return """{"action_type": "RESPOND_TO_USER", "parameters": {"response_type": "answer", "message": "I've explored the database structure multiple times but cannot find data relevant to your query. The current database appears to contain different types of data. Would you like me to discover other available databases or clarify what specific information you need?"}, "reasoning": "Breaking repetitive table exploration loop - offering alternatives to user"}"""

        if table_count >= 2 and column_count == 0:
            # Found tables, should examine their structure next
            if (
                "found 8 results" in prompt_lower
                or "found" in prompt_lower
                and "results" in prompt_lower
            ):
                # Agent found tables but hasn't examined their structure
                return """{"action_type": "EXPLORE_DATABASE", "parameters": {"query": "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_schema = 'public' ORDER BY table_name, ordinal_position LIMIT 50"}, "reasoning": "Found tables, now examining their column structures to understand what data is available"}"""

        # Check for database connectivity issues
        if "empty_database" in prompt_lower or (
            "no results" in prompt_lower and "information_schema.tables" in prompt_lower
        ):
            return """{"action_type": "DISCOVER_DATABASES", "parameters": {"prefix": "bird_"}, "reasoning": "Current database is empty, discovering other available databases with data"}"""

        # Check for basic errors
        if "not exist" in prompt_lower:
            return """{"action_type": "EXPLORE_DATABASE", "parameters": {"query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"}, "reasoning": "Table/column doesn't exist, finding correct schema"}"""

        # Check for action completion patterns
        # If we have sufficient exploration and no SQL yet, generate it
        if (
            table_count >= 1
            and column_count >= 1
            and "found" in prompt_lower
            and "results" in prompt_lower
        ):
            return """{"action_type": "GENERATE_SQL", "parameters": {}, "reasoning": "Found tables and examined their structure. Have sufficient schema knowledge to generate SQL query.", "notes": "Progression: Moving from exploration to SQL generation"}"""

        # Fallback to exploration if all else fails
        return """{"action_type": "EXPLORE_DATABASE", "parameters": {"query": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' LIMIT 10"}, "reasoning": "Fallback action: exploring database structure to understand available data", "notes": "Fallback reasoning applied"}"""

    async def diagnose_error(
        self,
        error: str,
        sql: str,
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Diagnose an error and suggest fixes.

        Args:
            error: Error message
            sql: SQL that caused the error
            schema: Schema context

        Returns:
            Diagnosis and suggestions
        """
        prompt = f"""Diagnose this SQL error and suggest how to fix it:

Error: {error}

SQL:
{sql}

Available Schema:
Tables: {', '.join(schema.get('tables', []))}

What is the likely cause and how can we fix it? Be specific and actionable.
"""

        response = await self._call_llm(prompt)

        return {
            "diagnosis": response,
            "error_type": self._classify_error(error),
        }

    def _classify_error(self, error: str) -> str:
        """Classify the type of error."""
        error_lower = error.lower()

        if "does not exist" in error_lower:
            return "missing_object"
        elif "syntax error" in error_lower:
            return "syntax_error"
        elif "permission denied" in error_lower:
            return "permission_error"
        elif "no results" in error_lower or "empty" in error_lower:
            return "empty_results"
        else:
            return "unknown"
