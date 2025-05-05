import os
from typing import Dict, List, Optional

# Default per-task model config
DEFAULT_MODELS: Dict[str, str] = {
    "intent_extractor": os.getenv("OPENROUTER_MODEL_INTENT", "openai/gpt-3.5-turbo"),
    "sql_generator": os.getenv("OPENROUTER_MODEL_SQL", "openai/gpt-4o"),
}

# Optional fallback models for OpenRouter's multi-model support
FALLBACK_MODELS: Dict[str, str] = {
    "intent_extractor": os.getenv(
        "OPENROUTER_MODEL_INTENT_FALLBACK", "openai/gpt-3.5-turbo:free"
    ),
    "sql_generator": os.getenv("OPENROUTER_MODEL_SQL_FALLBACK", "openai/gpt-4o:free"),
}


def get_model_for(task: str, override: Optional[str] = None) -> str:
    """
    Get the model for a given task, with optional override.

    Args:
        task: The task identifier (e.g., "intent_extractor")
        override: Optional model override

    Returns:
        The model identifier to use
    """
    if override:
        return override
    return DEFAULT_MODELS.get(task)


def get_models_for(task: str, override: Optional[List[str]] = None) -> List[str]:
    """
    Get a list of models for a given task (for fallback), with optional override.

    Args:
        task: The task identifier (e.g., "intent_extractor")
        override: Optional list of model overrides

    Returns:
        List of model identifiers to use
    """
    if override:
        return override
    return [DEFAULT_MODELS.get(task), FALLBACK_MODELS.get(task)]


def get_openrouter_config() -> Dict:
    """
    Get OpenRouter API config from environment.

    Returns:
        Dict containing OpenRouter configuration

    Raises:
        ValueError: If OPENROUTER_API_KEY is not set
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY must be set")

    return {
        "api_key": api_key,
        "base_url": "https://openrouter.ai/api/v1",
        "headers": {
            "HTTP-Referer": os.getenv(
                "OPENROUTER_REFERER", "https://github.com/your-org/sens"
            ),
            "X-Title": os.getenv("OPENROUTER_TITLE", "Sens Project"),
        },
    }
