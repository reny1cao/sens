"""SQL query generation from natural language using LLMs."""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import structlog
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from sens.schema.context import LLMSchemaContext
from sens.schema.graph import SchemaGraph
from sens.settings import get_llm_settings, get_settings
from sens.validation.sql_validator import SQLValidator, ValidationLevel

from .intent_validator import ValidIntent
from .models import GeneratedSQL, SQLGenerationError, TokenUsage

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

        Raises:
            FileNotFoundError: If prompt template cannot be found
            SQLGenerationError: If template loading fails
        """
        self.prompt_dir = prompt_dir
        self.prompt_filename = prompt_filename
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.schema = SchemaGraph.get_instance()

        # Verify template exists before initializing Jinja
        template_path = prompt_dir / prompt_filename
        if not template_path.exists():
            raise FileNotFoundError(
                f"SQL generation template not found at: {template_path}"
            )

        try:
            # Initialize Jinja environment
            self.env = Environment(
                loader=FileSystemLoader(str(prompt_dir)),
                trim_blocks=True,
                lstrip_blocks=True,
            )

            # Verify template can be loaded
            self.env.get_template(prompt_filename)
        except Exception as e:
            raise SQLGenerationError(
                f"Failed to load SQL generation template: {e}",
                details={"template_path": str(template_path)},
            )

        # Load LLM configuration
        settings = get_settings()
        llm_config = get_llm_settings()

        # Get SQL generator specific settings
        sql_config = llm_config["sql_generator"]
        self.primary_model = sql_config.get("primary_model", "openai/gpt-4")
        self.fallback_model = sql_config.get("fallback_model")

        # Initialize OpenRouter client with configuration from settings
        openrouter_config = settings.get_openrouter_config()
        self.client = OpenAI(
            base_url=openrouter_config["base_url"],
            api_key=openrouter_config["api_key"],
            default_headers=openrouter_config["headers"],
        )

        log.info(
            "sql_generator_initialized",
            prompt_dir=str(self.prompt_dir),
            prompt_filename=self.prompt_filename,
            template_exists=template_path.exists(),
            primary_model=self.primary_model,
            fallback_model=self.fallback_model,
            max_tokens=max_tokens,
            temperature=temperature,
        )

    def _build_schema_context(self, intent: ValidIntent) -> LLMSchemaContext:
        """
        Build a focused SchemaContext for the tables involved in the query.

        Args:
            intent: The validated intent containing target tables

        Returns:
            LLMSchemaContext with relevant schema information
        """
        # Start with explicitly mentioned tables
        relevant_tables = set(intent.original_intent.tables)

        # Add any tables needed for joins based on relationships
        for table in list(relevant_tables):
            referenced = self.schema.get_referenced_tables(table)
            referencing = self.schema.get_referencing_tables(table)
            relevant_tables.update(referenced)
            relevant_tables.update(referencing)

        # Build the schema context
        tables_columns = {}
        pk_dict = {}
        column_descriptions = {}

        # Collect table and column information
        for table in relevant_tables:
            # Get actual columns from schema
            columns = self.schema.get_table_columns(table)
            if not columns:  # Skip tables with no columns
                continue
            tables_columns[table] = columns

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
            for ref_table in relevant_tables:
                fk_cols = self.schema.get_table_fks_involved(table, {ref_table})
                if fk_cols:
                    fk_list.append(
                        {
                            "from_table": table,
                            "from_columns": fk_cols,
                            "to_table": ref_table,
                            "to_columns": self.schema.get_table_pks(ref_table),
                        }
                    )

        return LLMSchemaContext(
            tables=relevant_tables,
            tables_columns=tables_columns,
            primary_keys=pk_dict,
            foreign_keys=fk_list,
            column_descriptions=column_descriptions,
        )

    def _render_prompt(
        self, question: str, intent: ValidIntent, schema: LLMSchemaContext
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
        template = self.env.get_template(self.prompt_filename)

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
                schema_tables=list(schema.tables_columns.keys()),
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
            error_type="LLM_API_ERROR",  # Add specific error type
        )

    def _extract_sql_from_completion(self, completion: str) -> str:
        """
        Extract the SQL query or detect a structured error from the LLM completion text.

        Args:
            completion: The raw completion text from the LLM

        Returns:
            The extracted SQL query string

        Raises:
            SQLGenerationError: If no valid SQL could be extracted or if the LLM
                              returned a structured INSUFFICIENT_SCHEMA error.
        """
        if not isinstance(completion, str):
            completion = str(completion)

        completion = completion.strip()

        # Function to try parsing JSON and check for INSUFFICIENT_SCHEMA error
        def try_parse_json_error(text: str) -> Optional[Dict]:
            try:
                # Remove any "json" prefix that might come from markdown
                if text.lower().startswith("json"):
                    text = text[4:].lstrip()

                parsed = json.loads(text)
                if parsed.get("error_type") == "INSUFFICIENT_SCHEMA":
                    return parsed
                return None
            except json.JSONDecodeError:
                return None

        # First check if the entire completion is a JSON error
        json_error = try_parse_json_error(completion)
        if json_error:
            log.warning(
                "llm_returned_insufficient_schema_error",
                error_details=json_error,
                raw_completion=completion,
            )
            raise SQLGenerationError(
                "LLM indicated insufficient schema",
                error_type="INSUFFICIENT_SCHEMA",
                details=json_error,
            )

        # If markdown blocks are present, extract and check each block
        if "```" in completion:
            parts = completion.split("```")
            for i, part in enumerate(parts):
                if i % 2 == 1:  # Only look at content between ``` markers
                    part = part.strip()

                    # Check if this block is a JSON error
                    json_error = try_parse_json_error(part)
                    if json_error:
                        log.warning(
                            "llm_returned_insufficient_schema_error_in_markdown",
                            error_details=json_error,
                            raw_completion=completion,
                        )
                        raise SQLGenerationError(
                            "LLM indicated insufficient schema",
                            error_type="INSUFFICIENT_SCHEMA",
                            details=json_error,
                        )

                    # If not JSON error, try to extract SQL
                    if part.lower().startswith("sql"):
                        sql = part[3:].strip()
                    else:
                        sql = part.strip()

                    if sql and "select" in sql.lower():
                        return sql.strip()

            # If we get here, no valid SQL block was found
            raise SQLGenerationError(
                "Could not extract valid SQL from markdown blocks",
                error_type="SQL_EXTRACTION_FAILURE",
                details={"raw_completion": completion},
            )

        # If no markdown and no JSON error, treat as raw SQL
        sql = completion
        if not sql or "select" not in sql.lower():
            raise SQLGenerationError(
                "Could not extract valid SQL query from completion",
                error_type="SQL_EXTRACTION_FAILURE",
                details={"raw_completion": completion},
            )

        return sql.strip()

    def _validate_generated_sql(
        self, sql: str, schema: LLMSchemaContext
    ) -> Tuple[bool, Optional[str]]:
        """
        Perform basic validation of the generated SQL.

        Args:
            sql: The SQL query to validate
            schema: The schema context for validation

        Returns:
            Tuple of (is_valid, error_message)
        """
        validator = SQLValidator()
        validation_result = validator.validate(
            sql=sql,
            schema=schema.to_validator_schema(),
            levels={ValidationLevel.SYNTAX, ValidationLevel.SCHEMA},
        )

        if not validation_result.is_valid:
            error_msg = (
                str(validation_result.errors[0])
                if validation_result.errors
                else "Unknown validation error"
            )
            log.error(
                "sql_validation_failed",
                sql=sql,
                error=error_msg,
                validation_errors=[str(e) for e in validation_result.errors],
                validation_warnings=validation_result.warnings,
            )
            return False, error_msg

        return True, None

    def _extract_query_metadata(
        self, sql: str, schema: LLMSchemaContext
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
        for table in schema.tables_columns:
            if table.lower() in sql.lower():
                tables_used.append(table)
                # Extract columns for this table
                columns = []
                for col in schema.tables_columns[table]:
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
            SQLGenerationError: If query generation fails, with specific error_type
                              and details for INSUFFICIENT_SCHEMA errors
        """
        try:
            start_time = time.time()

            # Build schema context for relevant tables
            schema = self._build_schema_context(intent)

            # Render prompt with question, intent, and schema
            prompt = self._render_prompt(question, intent, schema)

            # Generate SQL using LLM
            completion, model_used, token_usage = await self._call_llm(prompt)

            try:
                # Extract SQL from completion (this may raise INSUFFICIENT_SCHEMA)
                sql = self._extract_sql_from_completion(completion)

                # Validate the generated SQL
                is_valid, error_msg = self._validate_generated_sql(sql, schema)
                if not is_valid:
                    raise SQLGenerationError(
                        f"Generated SQL failed validation: {error_msg}",
                        error_type="SQL_VALIDATION_ERROR",
                        details={"sql": sql, "error": error_msg},
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

            except SQLGenerationError as gen_error:
                if gen_error.error_type == "INSUFFICIENT_SCHEMA":
                    # Log structured error details and metric flag
                    missing_elements = gen_error.details.get("missing_elements", [])
                    reason = gen_error.details.get("reason", "No reason provided")

                    log.warning(
                        "sql_generation_failed_insufficient_schema",
                        error_type=gen_error.error_type,
                        missing_elements=missing_elements,
                        reason=reason,
                        question=question,
                        model_used=model_used,
                        token_usage=token_usage.model_dump() if token_usage else None,
                        step_metrics={"schema_insufficient": True},
                    )
                else:
                    log.error(
                        "sql_generation_failed",
                        error_type=gen_error.error_type,
                        message=gen_error.message,
                        details=gen_error.details,
                        question=question,
                    )
                raise gen_error

        except Exception as e:
            if isinstance(e, SQLGenerationError):
                raise e
            log.exception(
                "unexpected_error_during_sql_generation",
                error=str(e),
                question=question,
            )
            raise SQLGenerationError(
                f"Unexpected error during SQL generation: {str(e)}",
                error_type="UNEXPECTED_ERROR",
            ) from e
