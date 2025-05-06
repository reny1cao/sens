"""Intent extraction from natural language using LLMs."""

import json
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import structlog
from openai import OpenAI

from sens.schema.graph import SchemaGraph
from sens.settings import get_settings

from .models import Intent, IntentExtractionError, QueryType

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
        self.client = OpenAI(
            base_url=cfg["base_url"],
            api_key=cfg["api_key"],
            default_headers={
                "HTTP-Referer": str(cfg["headers"]["HTTP-Referer"]),
                "X-Title": cfg["headers"]["X-Title"],
            },
        )

        # Get primary and fallback models
        if models is not None:
            if not models:
                raise ValueError("At least one model must be specified")
            self.models = models
        else:
            self.models = settings.get_models_for(
                "intent_extractor", [model] if model else None
            )
            if not self.models:
                raise ValueError("No models configured for intent_extractor")

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

    def _validate_inputs(self, question: str, schema_snippet: str) -> None:
        """
        Validate input parameters.

        Args:
            question: The question to validate
            schema_snippet: The schema to validate

        Raises:
            ValueError: If inputs are invalid
        """
        if not question or not question.strip():
            raise ValueError("Question cannot be empty")
        if not schema_snippet or not schema_snippet.strip():
            raise ValueError("Schema cannot be empty")

        # Basic schema validation - must contain at least one TABLE definition
        if not re.search(r"TABLE\s+\w+\s*\(", schema_snippet, re.IGNORECASE):
            raise ValueError(
                "Invalid schema format: must contain at least one TABLE definition"
            )

    def extract(self, question: str, schema_snippet: str) -> Intent:
        """
        Extract intent from a natural language question about a database schema.

        Args:
            question: The natural language question to analyze
            schema_snippet: Relevant portion of the database schema

        Returns:
            Intent object containing the structured understanding of the query

        Raises:
            ValueError: If inputs are invalid or if the LLM response cannot be parsed
        """
        # Validate inputs
        self._validate_inputs(question, schema_snippet)

        prompt = self.template.format(question=question, schema_snippet=schema_snippet)

        # Try primary model first, fall back if needed
        for model in self.models:
            try:
                resp = self.client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    response_format={"type": "json_object"},
                )
                raw_json = resp.choices[0].message.content.strip()
                cleaned_json = self._clean_json_response(raw_json)
                intent = Intent.model_validate_json(cleaned_json)
                log.info("intent_extracted", intent=intent.model_dump(), model=model)
                return intent
            except Exception as e:
                if model == self.models[-1]:  # Last model in the list
                    log.error("intent_extraction_failed", error=str(e), model=model)
                    raise ValueError(f"Failed to extract intent: {str(e)}")
                log.warning(
                    "model_attempt_failed", error=str(e), model=model, will_retry=True
                )
                continue
