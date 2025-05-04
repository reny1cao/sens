from pathlib import Path
from typing import Optional

import structlog
from openai import OpenAI

from .models import Intent

log = structlog.get_logger()


class IntentExtractor:
    """
    Extracts structured intent from natural language questions about database schemas.
    Uses OpenAI's API to parse questions and return validated Intent objects.
    """

    def __init__(self, model: str = "gpt-4o-mini", prompt_path: Optional[str] = None):
        """
        Initialize the IntentExtractor.

        Args:
            model: OpenAI model to use for extraction
            prompt_path: Optional path to custom prompt template
        """
        self.client = OpenAI()
        self.model = model
        self._load_prompt(prompt_path)

    def _load_prompt(self, path: Optional[str] = None) -> None:
        """
        Load the prompt template from file.

        Args:
            path: Optional custom path to prompt template
        """
        if not path:
            path = Path(__file__).parent.parent.parent / "prompts/llm/intent.txt"
        self.template = Path(path).read_text()
        log.info("prompt_loaded", path=str(path))

    def extract(self, question: str, schema_snippet: str) -> Intent:
        """
        Extract structured intent from a natural language question.

        Args:
            question: User's natural language question
            schema_snippet: Relevant database schema context

        Returns:
            Intent: Structured intent with confidence score

        Raises:
            ValidationError: If LLM output doesn't match Intent schema
            OpenAIError: For API-related issues
        """
        log.info("extracting_intent", phase="intent_extraction", question=question)

        prompt = self.template.format(question=question, schema_snippet=schema_snippet)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,  # Deterministic
                response_format={"type": "json_object"},
            )

            raw_json = response.choices[0].message.content
            intent = Intent.model_validate_json(raw_json)

            log.info(
                "intent_extracted",
                phase="intent_extraction",
                intent=intent.model_dump(),
                confidence=intent.confidence,
            )

            return intent

        except Exception as e:
            log.error(
                "intent_extraction_failed",
                phase="intent_extraction",
                error=str(e),
                question=question,
            )
            raise
