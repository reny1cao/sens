"""Pydantic models for Sens project settings.

This module contains all the Pydantic models used for configuration validation
and type safety across the Sens project.
"""

from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, HttpUrl, field_validator

# Valid environments
EnvironmentType = Literal["development", "staging", "production"]


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
