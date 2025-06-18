"""Answer generation module for creating natural language responses from query results."""

from typing import Any, Dict, List, Optional

import structlog
from openai import AsyncOpenAI

from sens.settings import get_settings

log = structlog.get_logger()


class AnswerGenerator:
    """Generates natural language answers from SQL query results."""

    def __init__(self, model: Optional[str] = None):
        """Initialize the answer generator.

        Args:
            model: Optional model override for answer generation
        """
        self.settings = get_settings()
        self.config = self.settings.agent_reasoning

        # Use provided model or fall back to configured model
        self.model = model or self.config.primary_model

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

        log.info("answer_generator_initialized", model=self.model)

    async def generate_answer(
        self,
        user_query: str,
        query_results: Dict[str, Any],
        sql_query: Optional[str] = None,
        discovered_mappings: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate a natural language answer based on query results.

        Args:
            user_query: Original user question
            query_results: Dictionary containing query results and metadata
            sql_query: The SQL query that was executed (optional)
            discovered_mappings: Any value mappings discovered during query (optional)

        Returns:
            Natural language answer to the user's question
        """
        # Extract result details
        row_count = query_results.get("row_count", 0)
        columns = query_results.get("columns", [])
        rows = query_results.get("rows", [])

        # Build context for answer generation
        prompt = self._build_answer_prompt(
            user_query=user_query,
            sql_query=sql_query or query_results.get("sql", "No SQL generated"),
            row_count=row_count,
            columns=columns,
            rows=rows,
            discovered_mappings=discovered_mappings,
        )

        try:
            log.info("generating_answer_with_llm", model=self.model)

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=500,
            )

            answer = response.choices[0].message.content.strip()
            log.info("answer_generated", preview=answer[:100])
            return answer

        except Exception as e:
            log.error("generate_answer_error", error=str(e), model=self.model)
            # Return a basic fallback answer
            if row_count > 0:
                return f"I found {row_count} results for your query. The data has been displayed in the table below."
            else:
                return "No results were found for your query."

    def _build_answer_prompt(
        self,
        user_query: str,
        sql_query: str,
        row_count: int,
        columns: List[str],
        rows: List[List[Any]],
        discovered_mappings: Optional[Dict[str, str]] = None,
    ) -> str:
        """Build the prompt for answer generation.

        Args:
            user_query: Original user question
            sql_query: Executed SQL query
            row_count: Number of rows returned
            columns: Column names
            rows: Result rows (sample)
            discovered_mappings: Value mappings discovered

        Returns:
            Formatted prompt for the LLM
        """
        # Build a concise data summary
        data_summary = self._build_data_summary(row_count, columns, rows)

        # Add mapping context if available
        mapping_context = ""
        if discovered_mappings:
            mapping_context = f"\nValue mappings used: {discovered_mappings}"

        prompt = f"""You are a helpful data analyst assistant. A user asked the following question:

"{user_query}"

The SQL query executed was:
{sql_query}

Results summary:
{data_summary}{mapping_context}

Please provide a clear, concise natural language answer to the user's question based on these results.
Focus on directly answering what they asked for. If there are no results, explain that no data was found.
Keep your response brief and to the point.

Answer:"""

        return prompt

    def _build_data_summary(
        self, row_count: int, columns: List[str], rows: List[List[Any]]
    ) -> str:
        """Build a summary of the query results.

        Args:
            row_count: Total number of rows
            columns: Column names
            rows: Sample rows to include

        Returns:
            Formatted data summary string
        """
        data_summary = f"Found {row_count} results with columns: {', '.join(columns)}"

        if rows:
            # Include sample data (up to 5 rows)
            sample_rows = rows[:5]
            data_summary += f"\n\nSample data (first {len(sample_rows)} rows):\n"

            for i, row in enumerate(sample_rows):
                if isinstance(row, list):
                    # Convert list to dict using columns
                    row_dict = dict(zip(columns, row))
                    data_summary += f"Row {i+1}: {row_dict}\n"
                elif isinstance(row, dict):
                    data_summary += f"Row {i+1}: {row}\n"
                else:
                    data_summary += f"Row {i+1}: {row}\n"

        return data_summary

    async def generate_error_answer(
        self, user_query: str, error: str, context: Optional[Dict[str, Any]] = None
    ) -> str:
        """Generate a helpful answer when an error occurs.

        Args:
            user_query: Original user question
            error: Error message
            context: Optional context about what was attempted

        Returns:
            Natural language explanation of the error
        """
        prompt = f"""You are a helpful data analyst assistant. A user asked:

"{user_query}"

Unfortunately, an error occurred: {error}

Context: {context or 'No additional context available'}

Please provide a brief, helpful explanation of what went wrong and suggest what the user might try instead.
Keep your response concise and constructive.

Response:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            log.error("generate_error_answer_failed", error=str(e))
            return f"I encountered an error while processing your query: {error}"

    async def generate_empty_result_answer(
        self,
        user_query: str,
        sql_query: str,
        discovered_mappings: Optional[Dict[str, str]] = None,
    ) -> str:
        """Generate a helpful answer when query returns no results.

        Args:
            user_query: Original user question
            sql_query: The SQL query that was executed
            discovered_mappings: Any mappings that were discovered

        Returns:
            Natural language explanation for empty results
        """
        mapping_info = ""
        if discovered_mappings:
            mapping_info = f"\nNote: I used these mappings: {discovered_mappings}"

        prompt = f"""You are a helpful data analyst assistant. A user asked:

"{user_query}"

I executed this SQL query:
{sql_query}

But it returned no results.{mapping_info}

Please provide a brief, helpful explanation of why there might be no results and suggest what the user could check or try differently.
Keep your response concise and constructive.

Response:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            log.error("generate_empty_result_answer_failed", error=str(e))
            return "No results were found for your query. This could be due to the specific filters or time period requested."
