"""Module for transforming SQL query results into structured, user-facing responses."""

import json
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI

from sens.execution.types import QueryResult
from sens.llm.models import Intent, TokenUsage
from sens.settings import get_settings
from sens.settings.models import ResponseBuilderConfig

# Configure structured logging
log = structlog.get_logger()

# Constants
DEFAULT_PROMPT_DIR = Path(__file__).parent.parent / "llm" / "prompts"
DEFAULT_PROMPT_NAME = "summary.prompt.txt"


@dataclass
class FinalResponse:
    """Structured response containing the query results and metadata."""

    summary: str
    table_preview: List[Dict[str, Any]]
    row_count: int
    sql: str
    execution_time_ms: float
    generated_at: str
    metadata: Dict[str, Any]

    def to_json(self) -> str:
        """Convert the response to a JSON string."""
        return json.dumps(asdict(self), default=str)

    @classmethod
    def create_empty_response(cls, sql: str) -> "FinalResponse":
        """Create a response for when no results are found."""
        return cls(
            summary="No matching records were found.",
            table_preview=[],
            row_count=0,
            sql=sql,
            execution_time_ms=0.0,
            generated_at=datetime.utcnow().isoformat(),
            metadata={"status": "empty"},
        )


class ResponseBuilder:
    """Builds structured responses from SQL query results."""

    def __init__(
        self,
        prompt_dir: Path = DEFAULT_PROMPT_DIR,
        prompt_filename: str = DEFAULT_PROMPT_NAME,
        config: Optional[ResponseBuilderConfig] = None,
    ):
        """
        Initialize the ResponseBuilder with prompt template and configuration.

        Args:
            prompt_dir: Directory containing prompt templates
            prompt_filename: Name of the summary generation prompt template
            config: Optional ResponseBuilderConfig instance
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

        # Add json filter to environment with datetime handling
        def json_filter(value, **kwargs):
            def datetime_handler(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return str(obj)

            return json.dumps(value, default=datetime_handler, **kwargs)

        self.jinja_env.filters["json"] = json_filter

        # Load configuration
        settings = get_settings()

        # Use provided config or get from settings
        self.config = config or settings.response_builder

        # Initialize OpenRouter client with configuration from settings
        openrouter_config = settings.get_openrouter_config()
        self.client = OpenAI(
            base_url=openrouter_config["base_url"],
            api_key=openrouter_config["api_key"],
            default_headers=openrouter_config["headers"],
        )

        log.info(
            "response_builder_initialized",
            prompt_path=str(self.prompt_path),
            primary_model=self.config.primary_model,
            fallback_model=self.config.fallback_model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
        )

    def build(
        self,
        question: str,
        intent: Intent,
        result: QueryResult,
        sql: str,
        execution_time_ms: Optional[float] = None,
    ) -> FinalResponse:
        """
        Build a structured response from the query results.

        Args:
            question: Original natural language question
            intent: Structured query intent
            result: SQL query result
            sql: Executed SQL query
            execution_time_ms: Query execution time in milliseconds

        Returns:
            FinalResponse object containing the structured response
        """
        log.info("building_response", question=question)

        if not result.rows:
            log.info("no_results_found")
            return FinalResponse.create_empty_response(sql)

        # Generate summary based on intent type
        prompt = self._build_summary_prompt(
            question=question, sql=sql, result=result, intent=intent
        )

        try:
            summary = self._call_llm(prompt)
        except Exception as e:
            log.error("summary_generation_failed", error=str(e))
            summary = self._generate_fallback_summary(result)

        metadata = {
            "intent_type": intent.query_type,
            "columns": result.columns,
            "total_rows": result.row_count,
            "truncated": result.row_count > 5,
        }

        return FinalResponse(
            summary=summary.strip(),
            table_preview=result.rows[:5],
            row_count=result.row_count,
            sql=sql,
            execution_time_ms=execution_time_ms or 0.0,
            generated_at=datetime.utcnow().isoformat(),
            metadata=metadata,
        )

    def _build_summary_prompt(
        self, question: str, sql: str, result: QueryResult, intent: Intent
    ) -> str:
        """Build a context-aware prompt based on the intent type."""
        template = self.jinja_env.get_template(DEFAULT_PROMPT_NAME)

        # Prepare the template context
        context = {
            "question": question,
            "sql": sql,
            "result": result,
            "intent": intent,
        }

        try:
            rendered = template.render(context)
            log.debug(
                "prompt_rendered",
                question=question,
                intent_type=intent.query_type,
                row_count=result.row_count,
            )
            return rendered
        except Exception as e:
            log.error("prompt_render_failed", error=str(e), context=context)
            raise ValueError(f"Failed to render summary prompt: {e}")

    def _call_llm(self, prompt: str) -> str:
        """Call the LLM to generate a summary, with fallback handling."""
        models_to_try = [self.config.primary_model]
        if self.config.fallback_model:
            models_to_try.append(self.config.fallback_model)

        last_error = None
        for model in models_to_try:
            try:
                start_time = time.time()
                response = self.client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a data analyst that summarizes SQL query results clearly and concisely.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=self.config.temperature,
                    max_tokens=self.config.max_tokens,
                    response_format={"type": "text"},
                )

                summary = response.choices[0].message.content
                duration_ms = (time.time() - start_time) * 1000

                # Create TokenUsage object for logging
                usage = TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens,
                    completion_tokens=response.usage.completion_tokens,
                )

                log.info(
                    "llm_call_success",
                    model=model,
                    duration_ms=duration_ms,
                    prompt_tokens=usage.prompt_tokens,
                    completion_tokens=usage.completion_tokens,
                    total_tokens=usage.total_tokens,
                )

                return summary

            except Exception as e:
                last_error = e
                log.warning(
                    "llm_call_failed",
                    error=str(e),
                    model=model,
                    will_retry=model != models_to_try[-1],
                )
                continue

        # If we get here, all models failed
        log.error(
            "all_llm_models_failed", models=models_to_try, final_error=str(last_error)
        )
        raise RuntimeError(f"Failed to generate summary with any model: {last_error}")

    def _generate_fallback_summary(self, result: QueryResult) -> str:
        """Generate a basic summary when LLM calls fail."""
        return (
            f"Found {result.row_count} records matching your query. "
            "Please see the data preview for details."
        )
