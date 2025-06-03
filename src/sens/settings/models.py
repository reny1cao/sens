"""Pydantic models for Sens project settings.

This module contains all the Pydantic models used for configuration validation
and type safety across the Sens project.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator
from pydantic_settings import BaseSettings

# Valid environments
EnvironmentType = Literal["development", "staging", "production"]


class LoggingConfig(BaseModel):
    """Logging configuration."""

    format: Literal["json", "pretty"] = Field(
        default="pretty",
        description="Log format (json for production, pretty for development)",
        validation_alias="SENS_LOG_FORMAT",
    )
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        description="Logging level",
        validation_alias="SENS_LOG_LEVEL",
    )
    enable_colors: bool = Field(
        default=True,
        description="Enable colored output in pretty format",
        validation_alias="SENS_LOG_COLORS",
    )
    environment: Optional[EnvironmentType] = Field(
        default=None,
        description="Environment context for logging configuration",
    )
    verbose: bool = Field(
        default=False,
        description="Enable verbose (DEBUG) logging",
    )

    @field_validator("format")
    def validate_format(cls, v: str) -> str:
        """Validate log format."""
        if v not in ("json", "pretty"):
            raise ValueError("Log format must be either 'json' or 'pretty'")
        return v

    @field_validator("level")
    def validate_level(cls, v: str) -> str:
        """Validate log level."""
        valid_levels = ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        if v not in valid_levels:
            raise ValueError(f"Log level must be one of: {', '.join(valid_levels)}")
        return v

    def model_post_init(self, __context):
        """Post-initialization hook to set environment-aware defaults."""
        import os

        # Get environment from instance or environment variable
        environment = self.environment or os.getenv("SENS_ENVIRONMENT", "development")

        # Only change format and colors away from defaults if:
        # 1. We're not in development environment AND
        # 2. The values weren't explicitly set via environment variables
        if environment != "development":
            # If format wasn't explicitly set via env var, use json for non-dev
            if not os.getenv("SENS_LOG_FORMAT"):
                self.format = "json"

            # If colors weren't explicitly set via env var, disable for non-dev
            if not os.getenv("SENS_LOG_COLORS"):
                self.enable_colors = False

        # Override level if verbose mode is enabled
        if self.verbose:
            self.level = "DEBUG"

        # Store environment for future reference
        self.environment = environment

    def with_updates(self, **kwargs) -> "LoggingConfig":
        """Create a new LoggingConfig instance with updated values."""
        current_dict = self.model_dump()
        current_dict.update(kwargs)
        return LoggingConfig(**current_dict)


class OpenRouterConfig(BaseModel):
    """OpenRouter API configuration."""

    api_key: str = Field(
        description="OpenRouter API key for LLM access",
        repr=False,  # Don't expose in logs/repr
    )
    base_url: HttpUrl = Field(
        default="https://openrouter.ai/api/v1", description="OpenRouter API base URL"
    )
    referer: HttpUrl = Field(
        default="https://github.com/your-org/sens",
        description="HTTP referer for OpenRouter API",
    )
    title: str = Field(
        default="Sens Project", description="Title for OpenRouter API", min_length=1
    )

    @field_validator("api_key")
    def validate_api_key(cls, v: str) -> str:
        """Validate that API key is not empty and has valid format."""
        if not v:
            raise ValueError("OpenRouter API key cannot be empty")
        if not v.startswith(("sk-", "key-")):
            raise ValueError("OpenRouter API key must start with 'sk-' or 'key-'")
        return v

    @field_validator("base_url", "referer")
    def validate_urls(cls, v: HttpUrl) -> HttpUrl:
        """Validate URLs are HTTPS."""
        if str(v).startswith("http://"):
            raise ValueError("URLs must use HTTPS")
        return v


class ModelConfig(BaseModel):
    """Base configuration for ML models."""

    primary_model: str = Field(
        description="Primary model name",
        pattern=r"^[a-zA-Z0-9._:/-]+$",  # Enforce valid model ID format
    )
    fallback_model: Optional[str] = Field(
        default=None, description="Fallback model name", pattern=r"^[a-zA-Z0-9._:/-]+$"
    )
    max_tokens: int = Field(description="Maximum tokens for completion", gt=0, le=4096)
    temperature: float = Field(
        description="Temperature for generation (0.0-1.0)", ge=0.0, le=1.0
    )
    timeout_seconds: int = Field(
        description="Timeout in seconds for requests", gt=0, le=300
    )


class SQLGeneratorConfig(ModelConfig):
    """SQL Generator component configuration."""

    primary_model: str = Field(
        default="openai/gpt-4o", description="Primary model for SQL generation"
    )
    fallback_model: Optional[str] = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="Fallback model for SQL generation",
    )
    max_tokens: int = Field(
        default=500, description="Maximum tokens for SQL generation"
    )
    temperature: float = Field(
        default=0.1, description="Temperature for SQL generation"
    )
    timeout_seconds: int = Field(
        default=30, description="Timeout in seconds for SQL generation requests"
    )


class IntentExtractorConfig(ModelConfig):
    """Intent Extractor component configuration."""

    primary_model: str = Field(
        default="openai/gpt-4o",
        description="Primary model for intent extraction",
    )
    fallback_model: Optional[str] = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="Fallback model for intent extraction",
    )
    confidence_threshold: float = Field(
        default=0.75,
        description="Minimum confidence threshold for intent validation",
        ge=0.0,
        le=1.0,
    )
    max_tokens: int = Field(
        default=300, description="Maximum tokens for intent extraction"
    )
    temperature: float = Field(
        default=0.2, description="Temperature for intent extraction"
    )
    timeout_seconds: int = Field(
        default=30, description="Timeout in seconds for intent extraction requests"
    )


class DatabaseConfig(BaseModel):
    """Database connection configuration."""

    host: str = Field(default="localhost", description="Database host")
    port: int = Field(default=5432, description="Database port", gt=0, le=65535)
    name: str = Field(default="postgres", description="Database name")
    user: str = Field(default="postgres", description="Database user")
    password: str = Field(
        default="",
        description="Database password",
        repr=False,  # Don't expose in logs/repr
    )

    model_config = {"extra": "allow"}  # Allow extra fields in database config

    @field_validator("password")
    def validate_password(cls, v: str) -> str:
        """Validate that password is not empty."""
        if not v:
            raise ValueError("Database password cannot be empty")
        return v


class ResponseBuilderConfig(ModelConfig):
    """Response builder component configuration."""

    primary_model: str = Field(
        default="openai/gpt-4o",
        description="Primary model for response generation",
    )
    fallback_model: Optional[str] = Field(
        default="deepseek/deepseek-chat-v3-0324",
        description="Fallback model for response generation",
    )
    max_tokens: int = Field(
        default=300,
        description="Maximum tokens for response generation",
    )
    temperature: float = Field(
        default=0.3,
        description="Temperature for response generation",
    )
    timeout_seconds: int = Field(
        default=30,
        description="Timeout in seconds for response generation requests",
    )


class CacheConfig(BaseModel):
    """Cache configuration."""

    backend: Literal["redis", "memory"] = Field(
        default="memory",
        description="Cache backend to use",
        validation_alias="SENS_CACHE_BACKEND",
    )
    redis_host: str = Field(
        default="localhost",
        description="Redis host",
        validation_alias="SENS_CACHE_REDIS_HOST",
    )
    redis_port: int = Field(
        default=6379,
        description="Redis port",
        gt=0,
        le=65535,
        validation_alias="SENS_CACHE_REDIS_PORT",
    )
    redis_db: int = Field(
        default=0,
        description="Redis database number",
        ge=0,
        validation_alias="SENS_CACHE_REDIS_DB",
    )
    redis_password: Optional[str] = Field(
        default=None,
        description="Redis password",
        repr=False,
        validation_alias="SENS_CACHE_REDIS_PASSWORD",
    )
    ttl_seconds: int = Field(
        default=3600,
        description="Default TTL in seconds (1 hour)",
        gt=0,
        validation_alias="SENS_CACHE_TTL_SECONDS",
    )
    embedding_ttl_hours: int = Field(
        default=24,
        description="TTL for embedding cache in hours",
        gt=0,
        validation_alias="SENS_CACHE_EMBEDDING_TTL_HOURS",
    )
    llm_ttl_hours: int = Field(
        default=12,
        description="TTL for LLM response cache in hours",
        gt=0,
        validation_alias="SENS_CACHE_LLM_TTL_HOURS",
    )
    schema_ttl_hours: int = Field(
        default=1,
        description="TTL for schema cache in hours",
        gt=0,
        validation_alias="SENS_CACHE_SCHEMA_TTL_HOURS",
    )


class FinancialDataConfig(BaseSettings):
    """Financial data API configuration."""

    alpha_vantage_api_key: Optional[str] = Field(
        default=None,
        description="Alpha Vantage API key for stock market data",
        repr=False,
        validation_alias="SENS_ALPHA_VANTAGE_API_KEY",
    )
    fred_api_key: Optional[str] = Field(
        default=None,
        description="FRED API key for economic data",
        repr=False,
        validation_alias="SENS_FRED_API_KEY",
    )
    rate_limit_delay: int = Field(
        default=12,
        description="Rate limit delay in seconds between API calls",
        gt=0,
        validation_alias="SENS_FINANCIAL_RATE_LIMIT_DELAY",
    )
    max_concurrent_requests: int = Field(
        default=5,
        description="Maximum concurrent API requests",
        gt=0,
        le=20,
        validation_alias="SENS_FINANCIAL_MAX_CONCURRENT",
    )
    default_symbols: List[str] = Field(
        default_factory=lambda: ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"],
        description="Default stock symbols to load",
        validation_alias="SENS_FINANCIAL_DEFAULT_SYMBOLS",
    )
    update_frequency_hours: int = Field(
        default=24,
        description="How often to update financial data (hours)",
        gt=0,
        validation_alias="SENS_FINANCIAL_UPDATE_FREQUENCY_HOURS",
    )

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @field_validator("alpha_vantage_api_key", "fred_api_key")
    def validate_api_keys(cls, v: Optional[str]) -> Optional[str]:
        """Validate API key format if provided."""
        if v is not None and len(v.strip()) == 0:
            return None
        return v
