"""Intent extraction from natural language using LLMs."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import structlog
from openai import AsyncOpenAI

from sens.retrieval.models import RetrievedColumn, RetrievedContext, RetrievedTable
from sens.schema.context import SchemaContext, TableContext
from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

from .models import Intent, IntentExtractionError, QueryType, RetrievedSchemaContext

log = structlog.get_logger()


class IntentExtractor:
    """
    Extracts structured intent from natural language questions about database schemas.
    Uses OpenRouter's API to parse questions and return validated Intent objects.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        models: Optional[List[str]] = None,
        prompt_path: Optional[Path] = None,
    ):
        """
        Initialize the IntentExtractor.

        Args:
            model: Optional override for the primary model to use
            models: Optional list of models to use in sequence (overrides model parameter)
            prompt_path: Optional path to custom prompt template (as Path object)

        Raises:
            ValueError: If required settings are missing or if models list is empty
            FileNotFoundError: If prompt template cannot be found
        """
        # Check for API key before initializing settings
        api_key = os.getenv("SENS_OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("SENS_OPENROUTER_API_KEY must be set")

        # Get settings instance
        settings = get_settings()

        # Initialize OpenAI client with OpenRouter config
        cfg = settings.get_openrouter_config()
        self.client = AsyncOpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            default_headers={
                "HTTP-Referer": str(cfg["headers"]["HTTP-Referer"]),
                "X-Title": cfg["headers"]["X-Title"],
            },
        )

        # Get primary and fallback models from settings
        if models is not None:
            if not models:
                raise ValueError("At least one model must be specified")
            self.models = models
        elif model is not None:
            self.models = [model]
        else:
            # Use configured models from settings
            intent_config = settings.intent_extractor
            self.models = [intent_config.primary_model]
            if intent_config.fallback_model:
                self.models.append(intent_config.fallback_model)

        # Store primary model for test access
        self.model = self.models[0] if self.models else None
        self._load_prompt(prompt_path)

    def _load_prompt(self, path: Optional[Path] = None) -> None:
        """
        Load the prompt template from file or use default.

        Args:
            path: Optional Path to custom prompt template

        Raises:
            FileNotFoundError: If prompt template cannot be found
        """
        if path:
            if not path.exists():
                raise FileNotFoundError(f"Custom prompt not found at {path}")
            self.template = path.read_text()
        else:
            # Look for the prompt file in the llm/prompts directory
            default_path = Path(__file__).parent / "prompts" / "intent.txt"
            if not default_path.exists():
                raise FileNotFoundError(
                    f"Default prompt template not found at {default_path}"
                )
            self.template = default_path.read_text()

    def _clean_json_response(self, raw_response: str) -> str:
        """
        Clean the JSON response from markdown code blocks and other formatting.

        Args:
            raw_response: The raw response from the API

        Returns:
            Clean JSON string
        """
        # Remove markdown code blocks if present
        json_match = re.search(r"```(?:json)?\n(.*?)\n```", raw_response, re.DOTALL)
        if json_match:
            return json_match.group(1).strip()
        return raw_response.strip()

    def _validate_inputs(
        self,
        question: str,
        schema_snippet: Union[str, Dict, RetrievedSchemaContext, RetrievedContext],
    ) -> None:
        """
        Validate input parameters.

        Args:
            question: The question to validate
            schema_snippet: The schema to validate (string or structured format)

        Raises:
            ValueError: If inputs are invalid or schema is malformed
            IntentExtractionError: If schema context is invalid for intent extraction
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")

        # Handle different schema input types
        if isinstance(schema_snippet, str):
            if not SchemaContext.validate_snippet(schema_snippet):
                raise IntentExtractionError(
                    "Invalid or empty schema context",
                    details={
                        "schema_snippet": schema_snippet,
                        "reason": "schema_validation_failed",
                    },
                )
        elif isinstance(schema_snippet, dict):
            # Check if it's a RetrievedContext-like dictionary (from retrieval module)
            if all(key in schema_snippet for key in ["query", "tables", "columns"]):
                # Simple validation for RetrievedContext dictionary
                if not schema_snippet["tables"]:
                    raise IntentExtractionError(
                        "Empty schema context", details={"reason": "no_tables_found"}
                    )
                # Check table structure - RetrievedContext uses "name" for tables
                if not all(
                    "name" in table or "table_name" in table
                    for table in schema_snippet["tables"]
                ):
                    raise IntentExtractionError(
                        "Invalid table structure in schema context",
                        details={"reason": "invalid_table_structure"},
                    )
                # Check column structure - RetrievedContext uses "table" and "column" for columns
                if not all(
                    (
                        ("table" in col and "column" in col)
                        or ("table_name" in col and "column_name" in col)
                    )
                    for col in schema_snippet["columns"]
                ):
                    raise IntentExtractionError(
                        "Invalid column structure in schema context",
                        details={"reason": "invalid_column_structure"},
                    )
            else:
                # Try validation as RetrievedSchemaContext
                try:
                    RetrievedSchemaContext.model_validate(schema_snippet)
                except Exception as e:
                    raise IntentExtractionError(
                        "Invalid schema context structure",
                        details={"error": str(e), "reason": "schema_validation_failed"},
                    )
        elif isinstance(schema_snippet, (RetrievedSchemaContext, RetrievedContext)):
            if (
                isinstance(schema_snippet, RetrievedContext)
                and not schema_snippet.tables
            ):
                raise IntentExtractionError(
                    "Empty schema context", details={"reason": "no_tables_found"}
                )
        else:
            raise ValueError(f"Unsupported schema_snippet type: {type(schema_snippet)}")

    async def extract(
        self,
        question: str,
        schema_snippet: Union[str, Dict, RetrievedSchemaContext, RetrievedContext],
    ) -> Intent:
        """
        Extract intent from a natural language question about a database schema.

        Args:
            question: The natural language question to analyze
            schema_snippet: Schema context in string or structured format

        Returns:
            Intent object containing the structured understanding of the query

        Raises:
            IntentExtractionError: If intent extraction fails
            ValueError: If inputs are invalid
        """
        # Validate inputs
        self._validate_inputs(question, schema_snippet)

        # Convert schema_snippet to string format if needed
        if isinstance(schema_snippet, dict):
            # Handle RetrievedContext-like dictionary
            if all(key in schema_snippet for key in ["query", "tables", "columns"]):
                # Group columns by table
                table_columns = {}
                for col in schema_snippet["columns"]:
                    # Handle both field name formats
                    table_name = col.get("table") or col.get("table_name")
                    column_name = col.get("column") or col.get("column_name")
                    if table_name not in table_columns:
                        table_columns[table_name] = []
                    table_columns[table_name].append(column_name)

                # Format for LLM
                parts = []
                for table in schema_snippet["tables"]:
                    # Handle both field name formats
                    table_name = table.get("name") or table.get("table_name")
                    columns_str = ", ".join(sorted(table_columns.get(table_name, [])))
                    table_def = f"TABLE {table_name} ({columns_str})"
                    if table.get("metadata", {}).get("description"):
                        table_def += f"\n-- {table['metadata']['description']}"
                    parts.append(table_def)
                schema_snippet = "\n\n".join(parts)
            else:
                # Try as RetrievedSchemaContext
                schema_snippet = RetrievedSchemaContext.model_validate(schema_snippet)
                schema_snippet = schema_snippet.format_for_llm()
        elif isinstance(schema_snippet, RetrievedContext):
            # Convert RetrievedContext to string format using model_dump()
            context_dict = schema_snippet.model_dump()
            table_columns = {}
            for col in context_dict["columns"]:
                table_name = col["table_name"]
                if table_name not in table_columns:
                    table_columns[table_name] = []
                table_columns[table_name].append(col["column_name"])

            parts = []
            for table in context_dict["tables"]:
                columns_str = ", ".join(
                    sorted(table_columns.get(table["table_name"], []))
                )
                table_def = f"TABLE {table['table_name']} ({columns_str})"
                if table.get("metadata", {}).get("description"):
                    table_def += f"\n-- {table['metadata']['description']}"
                parts.append(table_def)
            schema_snippet = "\n\n".join(parts)
        elif isinstance(schema_snippet, RetrievedSchemaContext):
            schema_snippet = schema_snippet.format_for_llm()

        log.info("extracting_intent", question=question, schema_snippet=schema_snippet)

        prompt = self.template.format(question=question, schema_snippet=schema_snippet)

        # Get settings for LLM parameters
        settings = get_settings()
        intent_config = settings.intent_extractor

        # Try primary model first, fall back if needed
        for model in self.models:
            try:
                resp = await self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=intent_config.temperature,
                    max_tokens=intent_config.max_tokens,
                    response_format={"type": "json_object"},
                )

                # Expect string content due to json_object response format
                content = resp.choices[0].message.content
                intent_obj = None

                if isinstance(content, dict):
                    log.info(
                        "llm_response_is_dict",
                        details={
                            "message": "LLM response content is a dict. Validating directly."
                        },
                        model=model,
                        raw_content=content,
                    )
                    try:
                        intent_obj = Intent.model_validate(content)
                    except Exception as e:
                        log.error(
                            "pydantic_validation_failed_for_dict",
                            details={
                                "message": "Pydantic validation failed for LLM dictionary response."
                            },
                            error=str(e),
                            raw_content=content,
                            model=model,
                        )
                        raise IntentExtractionError(
                            f"Failed to validate structured dictionary from LLM: {str(e)}",
                            details={
                                "error_message": str(e),
                                "original_data": content,
                                "model": model,
                            },
                        )

                elif isinstance(content, str):
                    log.info(
                        "llm_response_is_string",
                        details={
                            "message": "LLM response content is a string. Cleaning and validating as JSON string."
                        },
                        model=model,
                        raw_content=content,
                    )
                    try:
                        cleaned_json_string = self._clean_json_response(content)
                        intent_obj = Intent.model_validate_json(cleaned_json_string)
                    except json.JSONDecodeError as e_json:
                        log.error(
                            "json_decode_failed_for_string",
                            details={
                                "message": "JSON decoding failed for LLM string response after cleaning."
                            },
                            error=str(e_json),
                            cleaned_content=cleaned_json_string,
                            original_content=content,
                            model=model,
                        )
                        raise IntentExtractionError(
                            f"Failed to decode JSON string from LLM: {str(e_json)}",
                            details={
                                "error_message": str(e_json),
                                "original_data": content,
                                "model": model,
                            },
                        )
                    except Exception as e_pydantic:
                        log.error(
                            "pydantic_validation_failed_for_string",
                            details={
                                "message": "Pydantic validation failed for LLM JSON string response."
                            },
                            error=str(e_pydantic),
                            cleaned_content=cleaned_json_string,
                            original_content=content,
                            model=model,
                        )
                        raise IntentExtractionError(
                            f"Failed to validate JSON string from LLM: {str(e_pydantic)}",
                            details={
                                "error_message": str(e_pydantic),
                                "original_data": content,
                                "model": model,
                            },
                        )
                else:
                    log.error(
                        "unexpected_llm_response_content_type",
                        details={
                            "message": "LLM response content has an unexpected data type."
                        },
                        content_actual_type=type(content).__name__,
                        model=model,
                        raw_content=str(content),
                    )
                    raise IntentExtractionError(
                        f"LLM returned unexpected content type: {type(content).__name__}",
                        details={
                            "content_actual_type": type(content).__name__,
                            "model": model,
                        },
                    )

                log.info(
                    "intent_extracted", intent=intent_obj.model_dump(), model=model
                )
                return intent_obj

            except Exception as e:
                if model == self.models[-1]:  # Last model in the list
                    log.error("intent_extraction_failed", error=str(e), model=model)
                    raise IntentExtractionError(
                        f"Failed to extract intent: {str(e)}",
                        details={"error": str(e), "model": model, "question": question},
                    )
                log.warning(
                    "model_attempt_failed", error=str(e), model=model, will_retry=True
                )
                continue
