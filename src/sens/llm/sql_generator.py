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
from .models import GeneratedSQL, SchemaContext, SQLGenerationError, TokenUsage

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
            if not columns:  # Skip tables with no columns
                continue
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
                    # Get the full constraint info
                    fk_cols = self.schema.get_table_fks_involved(table, {ref_table})
                    if fk_cols:
                        # For each FK relationship
                        fk_list.append(
                            {
                                "from_table": table,
                                "to_table": ref_table,
                                "from_columns": fk_cols,
                                "to_columns": self.schema.get_table_pks(ref_table),
                            }
                        )

        # Filter out any tables that don't have columns
        tables_dict = {k: v for k, v in tables_dict.items() if v}
        pk_dict = {k: v for k, v in pk_dict.items() if k in tables_dict}

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

    async def _call_llm(self, prompt: str) -> Tuple[str, str, Optional[TokenUsage]]:
        """
        Call the LLM to generate SQL, with fallback handling.

        Args:
            prompt: The rendered prompt with question and schema context

        Returns:
            Tuple of (completion text, model used, token usage)

        Raises:
            SQLGenerationError: If both primary and fallback models fail
        """
        models_to_try = [self.primary_model]
        if self.fallback_model:
            models_to_try.append(self.fallback_model)

        last_error = None
        for model in models_to_try:
            try:
                response = self.client.chat.completions.create(
                    model=model,
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

                # Create TokenUsage object
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )

                log.info(
                    "llm_call_success",
                    model=model,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )

                return completion, model, usage

            except Exception as e:
                log.error(
                    "llm_call_failed",
                    error=str(e),
                    model=model,
                )
                last_error = e
                continue  # Try next model if available

        # If we get here, all models failed
        raise SQLGenerationError(
            "Failed to generate SQL with all available models",
            details={"last_error": str(last_error)},
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
            schema: The schema context used for generation

        Returns:
            Tuple of (list of tables used, dict of table -> list of columns used)
        """
        tables_used = []
        columns_used = {}

        # Extract tables from schema context
        for table in schema.tables:
            if table.lower() in sql.lower():
                tables_used.append(table)
                # Extract columns for this table
                columns = []
                for col in schema.tables[table]:
                    if col.lower() in sql.lower():
                        columns.append(col)
                if columns:
                    columns_used[table] = columns

        return tables_used, columns_used

    async def generate(self, question: str, intent: ValidIntent) -> GeneratedSQL:
        """
        Generate a SQL query from a natural language question and validated intent.

        Args:
            question: The original user question
            intent: The validated intent with metadata

        Returns:
            GeneratedSQL object containing the query and metadata

        Raises:
            SQLGenerationError: If query generation fails
        """
        try:
            start_time = time.time()

            # Build schema context for relevant tables
            schema = self._build_schema_context(intent)

            # Render prompt with question, intent, and schema
            prompt = self._render_prompt(question, intent, schema)

            # Generate SQL using LLM
            completion, model_used, token_usage = await self._call_llm(prompt)

            # Extract SQL from completion
            sql = self._extract_sql_from_completion(completion)

            # Validate the generated SQL
            is_valid, error = self._validate_generated_sql(sql, schema)
            if not is_valid:
                raise SQLGenerationError(
                    "Generated SQL failed validation",
                    details={"sql": sql, "error": error},
                )

            # Extract tables and columns used in the query
            tables_used, columns_used = self._extract_query_metadata(sql, schema)

            # Calculate generation time
            generation_ms = int((time.time() - start_time) * 1000)

            result = GeneratedSQL(
                sql=sql,
                tables_used=tables_used,
                columns_used=columns_used,
                token_usage=token_usage,
                model_used=model_used,
                generation_ms=generation_ms,
            )

            log.info(
                "sql_generated",
                question=question,
                tables=tables_used,
                model=model_used,
                generation_ms=generation_ms,
            )

            return result

        except Exception as e:
            log.error(
                "sql_generation_failed",
                error=str(e),
                question=question,
                intent=intent.model_dump(),
            )
            raise SQLGenerationError(str(e), details={"question": question})
