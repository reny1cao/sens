"""Configuration management for LangGraph SENS agent."""

import os
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

# Fallback imports for when LangGraph dependencies are not available
try:
    from langchain_core.runnables import RunnableConfig
except ImportError:
    # Create a simple RunnableConfig type for compatibility
    RunnableConfig = Optional[Dict[str, Any]]


class SensAgentConfig(BaseModel):
    """Configuration for SENS LangGraph agent."""
    
    # Model configuration
    intent_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for intent extraction"
    )
    
    sql_generation_model: str = Field(
        default="openai/gpt-4o",
        description="Model for SQL generation"
    )
    
    reflection_model: str = Field(
        default="openai/gpt-4o-mini",
        description="Model for reflection and improvement"
    )
    
    # Execution configuration
    max_iterations: int = Field(
        default=3,
        description="Maximum number of refinement iterations"
    )
    
    result_limit: int = Field(
        default=1000,
        description="Maximum number of result rows"
    )
    
    # Retrieval configuration
    retrieval_top_k: int = Field(
        default=10,
        description="Number of schema elements to retrieve"
    )
    
    # Temperature settings
    generation_temperature: float = Field(
        default=0.1,
        description="Temperature for SQL generation"
    )
    
    reflection_temperature: float = Field(
        default=0.3,
        description="Temperature for reflection"
    )
    
    @classmethod
    def from_runnable_config(cls, config: Optional[RunnableConfig] = None) -> "SensAgentConfig":
        """Create configuration from RunnableConfig."""
        
        configurable = config.get("configurable", {}) if config else {}
        
        # Get values from environment or config
        raw_values: Dict[str, Any] = {}
        
        for field_name in cls.model_fields.keys():
            # Check config first, then environment
            value = configurable.get(field_name)
            if value is None:
                env_var = field_name.upper()
                value = os.environ.get(env_var)
            
            if value is not None:
                raw_values[field_name] = value
        
        return cls(**raw_values)