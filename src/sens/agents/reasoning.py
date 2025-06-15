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

    async def analyze_situation(
        self,
        user_query: str,
        context: str,
        iteration: int,
        discovered_mappings: Dict[str, str],
    ) -> Dict[str, Any]:
        """Analyze the current situation and suggest next action.

        Args:
            user_query: Original user query
            context: Recent thoughts, actions, and observations
            iteration: Current iteration number
            discovered_mappings: Value mappings discovered so far

        Returns:
            Dict with thought and suggested action
        """
        # Build prompt for reasoning
        prompt = self._build_reasoning_prompt(
            user_query,
            context,
            iteration,
            discovered_mappings,
        )

        # Use LLM to reason
        response = await self._call_llm(prompt)

        # Parse response
        return self._parse_reasoning_response(response)

    def _build_reasoning_prompt(
        self,
        user_query: str,
        context: str,
        iteration: int,
        discovered_mappings: Dict[str, str],
    ) -> str:
        """Build prompt for reasoning about next action."""
        return f"""You are an intelligent PostgreSQL database agent helping to answer user queries.

DATABASE TYPE: PostgreSQL (use PostgreSQL-specific syntax and functions)
DATA DOMAIN: Financial/Stock Market Data

User Query: {user_query}
Current Iteration: {iteration}/5

Recent Context:
{context}

Discovered Value Mappings:
{discovered_mappings if discovered_mappings else "None yet"}

Based on the above context, reason about what to do next. Consider:
1. Have we successfully retrieved schema? If not, we should search for it.
2. Have we generated SQL? If not and we have schema, generate it.
3. Did the SQL execution fail or return empty results? Diagnose why.
4. Are there value mismatches? Search for correct database values.
5. Should we try a different approach?

IMPORTANT: If you've already searched for schema multiple times successfully, move on to generating SQL. Don't get stuck repeating the same action.

DATABASE CONTEXT: You are working with a PostgreSQL database containing financial data.
Use PostgreSQL-specific syntax when exploring and generating SQL.

LIMITED TOOLS MODE - Only 3 tools available:
- EXPLORE_DATABASE: Execute PostgreSQL SELECT queries to understand database structure and discover data
- GENERATE_SQL: Generates PostgreSQL SQL query based on discovered schema and user query
- EXECUTE_SQL: Executes the generated PostgreSQL SQL query against the database

ALL OTHER TOOLS ARE DISABLED. You must work with only these three tools.

Strategy:
1. First EXPLORE_DATABASE to understand table structures, column names, and sample data
2. Then GENERATE_SQL based on what you discovered
3. Finally EXECUTE_SQL to get the user's requested data
4. If results are empty or wrong, use EXPLORE_DATABASE again to investigate

DECISION RULES:
- If you have NO schema knowledge: use EXPLORE_DATABASE to find tables
- If you found tables but need column info: use EXPLORE_DATABASE to examine table structure
- If you found company mappings (e.g., Apple→AAPL): you have enough info to GENERATE_SQL
- If you have SQL but haven't executed it: use EXECUTE_SQL
- If you've explored 3+ times: move to GENERATE_SQL even with limited info

Respond in this format:
THOUGHT: <Your reasoning about current situation and next action>
CONFIDENCE: <0.0 to 1.0>
ACTION: <One of: EXPLORE_DATABASE, GENERATE_SQL, EXECUTE_SQL>
PARAMETERS: <JSON parameters for the action>

PostgreSQL Examples:
THOUGHT: I need to understand the PostgreSQL database structure first. Let me find what tables exist.
CONFIDENCE: 0.9
ACTION: EXPLORE_DATABASE
PARAMETERS: {{"query": "SELECT table_name, table_type FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"}}

THOUGHT: I found a securities table. Let me check if Apple is stored as "Apple" or "AAPL" using PostgreSQL ILIKE.
CONFIDENCE: 0.8
ACTION: EXPLORE_DATABASE
PARAMETERS: {{"query": "SELECT symbol, company_name FROM securities WHERE company_name ILIKE '%apple%' OR symbol ILIKE '%aapl%' LIMIT 10"}}

THOUGHT: I need to see the structure of the daily_prices table using PostgreSQL information_schema.
CONFIDENCE: 0.8
ACTION: EXPLORE_DATABASE
PARAMETERS: {{"query": "SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'daily_prices' AND table_schema = 'public' ORDER BY ordinal_position"}}

THOUGHT: Now I know Apple is "AAPL" and I found the daily_prices table structure. I can generate PostgreSQL-specific SQL for the user's request.
CONFIDENCE: 0.9
ACTION: GENERATE_SQL
PARAMETERS: {{}}

IMPORTANT Instructions:
- EXPLORE_DATABASE: Use {{"query": "SELECT ..."}} with your SQL exploration query
- GENERATE_SQL: Use empty {{}} - parameters will be filled automatically
- EXECUTE_SQL: Use empty {{}} - SQL will be taken from state
"""

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

    def _parse_reasoning_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM reasoning response."""
        result = {
            "thought": "",
            "confidence": 1.0,
            "suggested_action": None,
        }

        lines = response.strip().split("\n")

        for line in lines:
            if line.startswith("THOUGHT:"):
                result["thought"] = line.replace("THOUGHT:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(
                        line.replace("CONFIDENCE:", "").strip()
                    )
                except ValueError:
                    result["confidence"] = 0.5
            elif line.startswith("ACTION:"):
                action_type = line.replace("ACTION:", "").strip()
                result["suggested_action"] = {"type": action_type}
            elif line.startswith("PARAMETERS:"):
                if result["suggested_action"]:
                    try:
                        import json

                        params_str = line.replace("PARAMETERS:", "").strip()
                        result["suggested_action"]["parameters"] = json.loads(
                            params_str
                        )
                    except (ValueError, json.JSONDecodeError):
                        result["suggested_action"]["parameters"] = {}

        # Validate we have a thought
        if not result["thought"]:
            result["thought"] = "Analyzing the situation to determine next steps."

        return result

    def _fallback_reasoning(self, prompt: str) -> str:
        """Simple heuristic-based reasoning when LLM fails."""
        # Extract key information from prompt
        if "no results" in prompt.lower() or "empty" in prompt.lower():
            return """THOUGHT: The query returned no results. I should diagnose why and search for correct values.
CONFIDENCE: 0.7
ACTION: DIAGNOSE_EMPTY_RESULTS
PARAMETERS: {}"""

        elif "not exist" in prompt.lower():
            return """THOUGHT: A table or column doesn't exist. I should search for the correct schema.
CONFIDENCE: 0.8
ACTION: SEARCH_SCHEMA
PARAMETERS: {}"""

        elif "iteration: 1" in prompt.lower() and "schema" not in prompt.lower():
            return """THOUGHT: This is the first iteration. I should start by searching for relevant schema.
CONFIDENCE: 0.9
ACTION: SEARCH_SCHEMA
PARAMETERS: {}"""

        else:
            return """THOUGHT: I should proceed with the standard flow.
CONFIDENCE: 0.5
ACTION: GENERATE_SQL
PARAMETERS: {}"""

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
