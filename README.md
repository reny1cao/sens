# Sens Project

## OpenRouter Setup

1. Sign up for an OpenRouter account at https://openrouter.ai/
2. Create an API key from your account dashboard
3. Set the API key as an environment variable:
   ```bash
   export OPENROUTER_API_KEY=your-api-key-here
   ```

## Model Configuration

The project supports configurable models for different tasks through environment variables:

### Required Variables
- `OPENROUTER_API_KEY`: Your OpenRouter API key

### Optional Model Configuration
You can override the default models for specific tasks:

```bash
# Intent extraction
export OPENROUTER_MODEL_INTENT=openai/gpt-4o

# SQL generation
export OPENROUTER_MODEL_SQL=openai/gpt-4o
```

### Fallback Models
Optionally configure fallback models for each task:

```bash
# Intent extraction fallback
export OPENROUTER_FALLBACK_MODEL_INTENT=openai/gpt-3.5-turbo

# SQL generation fallback
export OPENROUTER_FALLBACK_MODEL_SQL=openai/gpt-3.5-turbo
```

## Usage Example

```python
from sens.llm.intent_extractor import IntentExtractor

# Initialize with default model
extractor = IntentExtractor()

# Or specify a custom model
extractor = IntentExtractor(model="openai/gpt-3.5-turbo")

# Extract intent from a question
intent = extractor.extract(
    "How many movies were released in 2023?",
    """
    TABLE movie(
        id INTEGER PRIMARY KEY,
        title TEXT,
        release_year INTEGER
    )
    """
)
```
