"""SQL query generation from natural language using LLMs."""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import structlog
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from sens.schema.graph import SchemaGraph
from sens.settings import get_llm_settings, get_settings

from .intent_validator import ValidIntent
from .models import GeneratedSQL, SchemaContext, SQLGenerationError

log = structlog.get_logger()

# Constants
DEFAULT_PROMPT_DIR = Path(__file__).parent / "prompts"
DEFAULT_PROMPT_NAME = "sql_generation.prompt.txt"
DEFAULT_MAX_TOKENS = 500
DEFAULT_TEMPERATURE = 0.1  # Low temperature for more deterministic SQL generation


class SQLGenerator:
    """
    Generates SQL queries from natural language questions using LLM-based generation.
    Uses validated intents and schema context to ensure accurate and safe query generation.
    """

    def __init__(
        self,
        prompt_dir: Path = DEFAULT_PROMPT_DIR,
        prompt_filename: str = DEFAULT_PROMPT_NAME,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
    ):
        """
        Initialize the SQL Generator with prompt template and configuration.

        Args:
            prompt_dir: Directory containing prompt templates
            prompt_filename: Name of the SQL generation prompt template
            max_tokens: Maximum tokens for LLM completion
            temperature: LLM temperature (0.0-1.0, lower = more deterministic)
        """
        self.prompt_path = prompt_dir / prompt_filename
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Prompt template not found: {self.prompt_path}")

        self.jinja_env = Environment(
            loader=FileSystemLoader(str(prompt_dir)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Load LLM configuration
        settings = get_settings()
        llm_config = get_llm_settings()

        # Get SQL generator specific settings
        sql_config = llm_config["sql_generator"]
        self.primary_model = sql_config.get("primary_model", "gpt-4")
        self.fallback_model = sql_config.get("fallback_model")
        self.max_tokens = max_tokens
        self.temperature = temperature

        # Initialize OpenRouter client with configuration from settings
        openrouter_config = settings.get_openrouter_config()
        self.client = OpenAI(
            base_url=openrouter_config["base_url"],
            api_key=openrouter_config["api_key"],
            default_headers=openrouter_config["headers"],
        )

        # Initialize schema graph for metadata lookups
        self.schema = SchemaGraph.get_instance()

        log.info(
            "sql_generator_initialized",
            prompt_path=str(self.prompt_path),
            primary_model=self.primary_model,
            fallback_model=self.fallback_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _build_schema_context(self, intent: ValidIntent) -> SchemaContext:
        """
        Build a focused SchemaContext for the tables involved in the query.

        Args:
            intent: The validated intent containing target tables

        Returns:
            SchemaContext with relevant schema information
        """
        # Start with explicitly mentioned tables
        relevant_tables = set(intent.original_intent.tables)

        # Add any tables needed for joins based on relationships
        for table in list(
            relevant_tables
        ):  # Convert to list to avoid modification during iteration
            referenced = self.schema.get_referenced_tables(table)
            referencing = self.schema.get_referencing_tables(table)
            relevant_tables.update(referenced)
            relevant_tables.update(referencing)

        # Build the schema context
        tables_dict = {}
        pk_dict = {}
        column_descriptions = {}

        # Collect table and column information
        for table in relevant_tables:
            # Get actual columns from schema
            columns = self.schema.get_table_columns(table)
            tables_dict[table] = columns

            # Get primary keys
            pk_dict[table] = self.schema.get_table_pks(table)

            # Get column descriptions
            table_descriptions = {}
            for column in columns:
                description = self.schema.get_column_comment(table, column)
                if description:
                    table_descriptions[column] = description
            if table_descriptions:
                column_descriptions[table] = table_descriptions

        # Build foreign key information
        fk_list = []
        for table in relevant_tables:
            # Get foreign keys for each table
            for ref_table in self.schema.get_referenced_tables(table):
                if ref_table in relevant_tables:
                    fk_cols = self.schema.get_table_fks_involved(table, {ref_table})
                    if fk_cols:
                        fk_list.append(
                            {
                                "from_table": table,
                                "to_table": ref_table,
                                "columns": fk_cols,
                            }
                        )

        return SchemaContext(
            tables=tables_dict,
            primary_keys=pk_dict,
            foreign_keys=fk_list,
            column_descriptions=column_descriptions,
        )

    def _render_prompt(
        self, question: str, intent: ValidIntent, schema: SchemaContext
    ) -> str:
        """
        Render the SQL generation prompt template with the provided context.

        Args:
            question: The original user question
            intent: The validated intent
            schema: The relevant schema context

        Returns:
            The rendered prompt string
        """
        template = self.jinja_env.get_template(DEFAULT_PROMPT_NAME)

        # Prepare the template context
        context = {
            "question": question,
            "intent": intent.original_intent,
            "schema": schema,
        }

        try:
            rendered = template.render(context)
            log.debug(
                "prompt_rendered",
                question=question,
                intent_type=intent.original_intent.query_type,
                schema_tables=list(schema.tables.keys()),
            )
            return rendered
        except Exception as e:
            log.error("prompt_render_failed", error=str(e), context=context)
            raise SQLGenerationError(
                f"Failed to render SQL generation prompt: {e}",
                details={"context": context},
            )

    async def _call_llm(self, prompt: str) -> str:
        """
        Call the LLM to generate SQL.

        Args:
            prompt: The rendered prompt with question and schema context

        Returns:
            The LLM completion text

        Raises:
            SQLGenerationError: If the LLM call fails
        """
        try:
            response = self.client.chat.completions.create(
                model=self.primary_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a SQL expert that generates safe and efficient SQL queries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "text"},  # Ensure we get raw text back
            )

            completion = response.choices[0].message.content

            # Log token usage
            usage = response.usage
            log.info(
                "llm_call_success",
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )

            return completion

        except Exception as e:
            log.error(
                "llm_call_failed",
                error=str(e),
                model=self.primary_model,
            )

            # Try fallback model if configured
            if self.fallback_model:
                try:
                    response = self.client.chat.completions.create(
                        model=self.fallback_model,
                        messages=[
                            {
                                "role": "system",
                                "content": "You are a SQL expert that generates safe and efficient SQL queries.",
                            },
                            {"role": "user", "content": prompt},
                        ],
                        temperature=self.temperature,
                        max_tokens=self.max_tokens,
                        response_format={"type": "text"},
                    )
                    return response.choices[0].message.content
                except Exception as fallback_error:
                    log.error(
                        "fallback_llm_call_failed",
                        error=str(fallback_error),
                        model=self.fallback_model,
                    )

            raise SQLGenerationError(
                f"Failed to generate SQL using LLM: {e}",
                details={"model": self.primary_model},
            )

    def _extract_sql_from_completion(self, completion: str) -> str:
        """
        Extract the SQL query from the LLM completion text.

        Args:
            completion: The raw completion text from the LLM

        Returns:
            The extracted SQL query string

        Raises:
            SQLGenerationError: If no valid SQL could be extracted
        """
        # Check for error response
        if "ERROR:" in completion:
            error_msg = completion.split("ERROR:")[1].strip()
            raise SQLGenerationError(f"LLM indicated generation error: {error_msg}")

        # Try to extract SQL from markdown code block
        if "```sql" in completion:
            sql_parts = completion.split("```sql")
            if len(sql_parts) > 1:
                sql = sql_parts[1].split("```")[0].strip()
                return sql

        # Try to extract just the SQL if it starts with SELECT
        if completion.strip().upper().startswith("SELECT"):
            return completion.strip()

        raise SQLGenerationError(
            "Could not extract valid SQL from LLM completion",
            details={"completion": completion},
        )

    def _validate_generated_sql(
        self, sql: str, schema: SchemaContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform basic validation of the generated SQL.

        Args:
            sql: The SQL query to validate
            schema: The schema context for validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        # This is a placeholder for the actual SQLValidator integration
        # Basic checks that could be done here:
        # 1. Verify it's a SELECT statement
        # 2. Check that all referenced tables exist in schema
        # 3. Check that all referenced columns exist in their tables
        # 4. Verify basic SQL syntax
        return True, None

    def _extract_query_metadata(
        self, sql: str, schema: SchemaContext
    ) -> Tuple[List[str], Dict[str, List[str]]]:
        """
        Extract metadata about tables and columns used in the query.

        Args:
            sql: The generated SQL query
            schema: The schema context

        Returns:
            Tuple of (tables_used, columns_used)
        """
        # This is a placeholder implementation
        # In practice, you'd want to properly parse the SQL
        # and extract exact tables and columns used
        tables_used = list(schema.tables.keys())
        columns_used = {table: columns for table, columns in schema.tables.items()}
        return tables_used, columns_used

    async def generate(self, question: str, intent: ValidIntent) -> GeneratedSQL:
        """
        Generate a SQL query from a natural language question and validated intent.

        Args:
            question: The original user question
            intent: The validated intent with schema metadata

        Returns:
            GeneratedSQL object containing the query and metadata

        Raises:
            SQLGenerationError: If generation fails
        """
        start_time = time.time()

        try:
            # Build schema context
            schema_context = self._build_schema_context(intent)

            # Render the prompt
            rendered_prompt = self._render_prompt(question, intent, schema_context)

            # Call LLM
            completion = await self._call_llm(rendered_prompt)

            # Extract SQL from completion
            sql = self._extract_sql_from_completion(completion)

            # Validate the generated SQL
            is_valid, error = self._validate_generated_sql(sql, schema_context)
            if not is_valid:
                raise SQLGenerationError(
                    f"Generated SQL failed validation: {error}",
                    details={"sql": sql, "error": error},
                )

            # Extract query metadata
            tables_used, columns_used = self._extract_query_metadata(
                sql, schema_context
            )

            # Calculate generation time
            generation_ms = int((time.time() - start_time) * 1000)

            # Create and return GeneratedSQL object
            generated = GeneratedSQL(
                sql=sql,
                tables_used=tables_used,
                columns_used=columns_used,
                prompt_tokens=0,  # Will be updated from LLM response
                completion_tokens=0,  # Will be updated from LLM response
                model_used=self.primary_model,
                generation_ms=generation_ms,
            )

            log.info(
                "sql_generated",
                question=question,
                tables=tables_used,
                model=self.primary_model,
                generation_ms=generation_ms,
            )

            return generated

        except Exception as e:
            log.exception(
                "sql_generation_failed",
                error=str(e),
                question=question,
                intent_type=intent.original_intent.query_type,
            )
            if isinstance(e, SQLGenerationError):
                raise
            raise SQLGenerationError(
                f"Unexpected error during SQL generation: {e}",
                details={"question": question},
            ) from e
