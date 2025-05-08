"""Core settings management for the Sens project.

This module provides the main Settings class and utility functions for managing
project-wide configuration through environment variables with validation.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import structlog
from pydantic import Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .models import (
    DatabaseConfig,
    EnvironmentType,
    IntentExtractorConfig,
    OpenRouterConfig,
    ResponseBuilderConfig,
    SQLGeneratorConfig,
)

log = structlog.get_logger()

# Get project root for default paths
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Project-wide settings using environment variables."""

    # Core Settings
    # --------------------
    environment: EnvironmentType = Field(
        default="development",
        description="Current environment (development/staging/production)",
        validation_alias="SENS_ENVIRONMENT",
    )

    # Data Paths
    # --------------------
    schema_path: Path = Field(
        default=PROJECT_ROOT / "src/sens/data/schemas/metadata/schema_metadata.json",
        description="Path to the schema metadata JSON file",
        validation_alias="SENS_SCHEMA_PATH",
    )

    llm_schema_path: Path = Field(
        default=PROJECT_ROOT / "src/sens/data/schemas/prompts/schema_for_llm.txt",
        description="Path to the LLM-friendly schema format file",
        validation_alias="SENS_LLM_SCHEMA_PATH",
    )

    index_dir: Path = Field(
        default=PROJECT_ROOT / "src/sens/data/indices",
        description="Directory for storing FAISS indices",
        validation_alias="SENS_INDEX_DIR",
    )

    # Database Configuration
    # --------------------
    db_host: str = Field(
        default="localhost",
        description="Database host",
        validation_alias="SENS_DB_HOST",
    )
    db_port: int = Field(
        default=5432, description="Database port", validation_alias="SENS_DB_PORT"
    )
    db_name: str = Field(
        default="postgres", description="Database name", validation_alias="SENS_DB_NAME"
    )
    db_user: str = Field(
        default="postgres", description="Database user", validation_alias="SENS_DB_USER"
    )
    db_password: str = Field(
        default="", description="Database password", validation_alias="SENS_DB_PASSWORD"
    )

    @property
    def db_url(self) -> str:
        """Get the database URL constructed from components."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # OpenRouter Configuration
    # -----------------------
    openrouter: Optional[OpenRouterConfig] = Field(
        default=None, description="OpenRouter configuration object"
    )
    openrouter_api_key: str = Field(
        description="OpenRouter API key", validation_alias="SENS_OPENROUTER_API_KEY"
    )
    openrouter_base_url: HttpUrl = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter base URL"
    )
    openrouter_referer: HttpUrl = Field(
        default="https://github.com/your-org/sens", description="OpenRouter referer"
    )
    openrouter_title: str = Field(
        default="Sens Project", description="OpenRouter title", min_length=1
    )

    # Component Configurations
    # ----------------------
    sql_generator: SQLGeneratorConfig = Field(
        default_factory=SQLGeneratorConfig,
        description="SQL Generator component configuration",
    )
    intent_extractor: IntentExtractorConfig = Field(
        default_factory=IntentExtractorConfig,
        description="Intent Extractor component configuration",
    )

    # Add ResponseBuilder configuration
    response_builder: ResponseBuilderConfig = Field(
        default_factory=ResponseBuilderConfig,
        description="Response builder component configuration",
    )

    # API Security Settings
    # -------------------
    cors_origins: Union[str, List[str]] = Field(
        default=["*"],
        description="Allowed CORS origins (comma-separated string or JSON array)",
    )
    cors_methods: Union[str, List[str]] = Field(
        default=["*"],
        description="Allowed CORS methods (comma-separated string or JSON array)",
    )
    cors_headers: Union[str, List[str]] = Field(
        default=["*"],
        description="Allowed CORS headers (comma-separated string or JSON array)",
    )
    rate_limit_requests: int = Field(
        default=100, description="Maximum requests per window", gt=0
    )
    rate_limit_window: int = Field(
        default=60, description="Rate limit window in seconds", gt=0
    )

    # Environment Settings
    # ------------------
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(
        default="INFO",
        description="Logging level",
        pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$",
    )

    model_config = SettingsConfigDict(
        env_prefix="SENS_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_default=True,
        frozen=True,
        extra="allow",  # Allow extra fields
    )

    @field_validator("schema_path")
    def validate_schema_path(cls, v: Path) -> Path:
        """Ensure schema path exists and is a file."""
        # Convert to absolute path if relative
        if not v.is_absolute():
            v = PROJECT_ROOT / v
        return v

    @field_validator("index_dir")
    def validate_index_dir(cls, v: Path) -> Path:
        """Ensure index directory exists and is accessible."""
        # Convert to absolute path if relative
        if not v.is_absolute():
            v = PROJECT_ROOT / v
        # Create directory if it doesn't exist
        if not v.exists():
            v.mkdir(parents=True, exist_ok=True)
        return v

    def __init__(self, **kwargs):
        """Initialize settings with OpenRouter config and database config."""
        super().__init__(**kwargs)
        # Initialize OpenRouter config
        if not self.openrouter and self.openrouter_api_key:
            object.__setattr__(
                self,
                "openrouter",
                OpenRouterConfig(
                    api_key=self.openrouter_api_key,
                    base_url=self.openrouter_base_url,
                    referer=self.openrouter_referer,
                    title=self.openrouter_title,
                ),
            )

        # Initialize database config
        object.__setattr__(
            self,
            "database",
            DatabaseConfig(
                host=self.db_host,
                port=self.db_port,
                name=self.db_name,
                user=self.db_user,
                password=self.db_password,
            ),
        )

    @field_validator("cors_origins", "cors_methods", "cors_headers", mode="before")
    @classmethod
    def parse_cors_settings(cls, v: Union[str, List[str]]) -> List[str]:
        """Parse CORS settings from string or list."""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",")]
        return v

    def get_model_for(self, task: str, override: Optional[str] = None) -> str:
        """Get the primary model for a specific task."""
        if override:
            return override

        config = getattr(self, task, None)
        if not config:
            raise ValueError(f"No configuration found for task: {task}")

        return config.primary_model

    def get_models_for(
        self, task: str, override: Optional[List[str]] = None
    ) -> List[str]:
        """Get all available models for a specific task."""
        if override:
            return override

        config = getattr(self, task, None)
        if not config:
            raise ValueError(f"No configuration found for task: {task}")

        models = [config.primary_model]
        if config.fallback_model:
            models.append(config.fallback_model)

        return models

    def get_openrouter_config(self) -> Dict[str, Any]:
        """Get OpenRouter configuration as a dictionary."""
        if not self.openrouter:
            raise ValueError("OpenRouter configuration not available")
        return {
            "api_key": self.openrouter.api_key,
            "base_url": str(self.openrouter.base_url),
            "headers": {
                "HTTP-Referer": str(self.openrouter.referer),
                "X-Title": self.openrouter.title,
            },
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration as a dictionary."""
        return self.database.model_dump()

    def with_updates(self, **kwargs) -> "Settings":
        """Create a new Settings instance with updated values."""
        current_dict = self.model_dump()
        current_dict.update(kwargs)
        return Settings(**current_dict)


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the global settings instance."""
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
        except Exception as e:
            log.error("Failed to load settings", error=str(e))
            raise
    return _settings


def get_llm_settings() -> Dict[str, Any]:
    """Get LLM-specific settings."""
    settings = get_settings()
    return {
        "openrouter": settings.get_openrouter_config(),
        "sql_generator": settings.sql_generator.model_dump(),
        "intent_extractor": settings.intent_extractor.model_dump(),
        "response_builder": settings.response_builder.model_dump(),
    }


def reload_settings() -> None:
    """Reload settings from environment."""
    global _settings
    _settings = None
    get_settings()
