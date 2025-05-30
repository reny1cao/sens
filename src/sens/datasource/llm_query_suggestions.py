"""LLM-powered query suggestion generation for uploaded data."""

import asyncio
import json
from typing import List, Dict, Any, Optional
import structlog
from openai import AsyncOpenAI

from sens.settings import get_settings
from sens.schema.unified_schema import UnifiedSchema

logger = structlog.get_logger(__name__)


class LLMQuerySuggestionGenerator:
    """Generates insightful query suggestions using LLM based on data schema and content."""
    
    def __init__(self):
        settings = get_settings()
        openrouter_config = settings.get_openrouter_config()
        
        self.client = AsyncOpenAI(
            base_url=openrouter_config["base_url"],
            api_key=openrouter_config["api_key"],
            default_headers=openrouter_config["headers"],
        )
        # Use SQL generator model for suggestions
        self.model = settings.sql_generator.primary_model
    
    async def generate_suggestions(
        self, 
        unified_schema: UnifiedSchema, 
        sample_data: Optional[List[Dict[str, Any]]] = None,
        num_suggestions: int = 10
    ) -> List[str]:
        """Generate insightful query suggestions using LLM.
        
        Args:
            unified_schema: UnifiedSchema object containing schema information
            sample_data: Optional sample rows for better context
            num_suggestions: Number of suggestions to generate
            
        Returns:
            List of insightful natural language queries
        """
        try:
            # Build context for LLM
            context = self._build_context(unified_schema, sample_data)
            
            prompt = f"""You are a data analyst helping users explore their dataset. Based on the following schema and sample data, generate {num_suggestions} insightful and diverse natural language questions that would help users understand and analyze their data.

Schema and Sample Data:
{context}

Guidelines:
1. Ask questions that reveal insights, patterns, and trends
2. Include various types of queries: aggregations, comparisons, filtering, grouping, time-based analysis
3. Focus on business value and actionable insights
4. Use natural, conversational language
5. Consider relationships between columns
6. Suggest both simple and complex analytical questions
7. If there are dates, include time-based analysis
8. If there are categories, include distribution and comparison questions
9. If there are numeric values, include statistical and trend questions
10. Make questions specific to the actual data, not generic

Generate exactly {num_suggestions} questions, one per line, without numbering or bullet points."""

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a data analyst expert who helps users explore their data by suggesting insightful questions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            suggestions_text = response.choices[0].message.content.strip()
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip()]
            
            # Ensure we have the requested number
            suggestions = suggestions[:num_suggestions]
            
            logger.info("llm_suggestions_generated", 
                       count=len(suggestions),
                       model=self.model)
            
            return suggestions
            
        except Exception as e:
            logger.error("llm_suggestion_generation_failed", error=str(e))
            # Fall back to pattern-based suggestions
            from sens.datasource.query_suggestions import QuerySuggestionGenerator
            generator = QuerySuggestionGenerator()
            return generator.generate_suggestions(unified_schema, sample_data)[:num_suggestions]
    
    def _build_context(self, unified_schema: UnifiedSchema, sample_data: Optional[List[Dict[str, Any]]]) -> str:
        """Build context string for LLM with schema and sample data."""
        context_parts = []
        
        for table in unified_schema.tables:
            table_info = f"Table: {table.name}"
            if table.row_count:
                table_info += f" ({table.row_count:,} rows)"
            context_parts.append(table_info)
            
            # Add column information
            context_parts.append("Columns:")
            for col in table.columns:
                col_info = f"  - {col.name}: {col.data_type.value}"
                if col.is_primary_key:
                    col_info += " (Primary Key)"
                if col.description:
                    col_info += f" - {col.description}"
                context_parts.append(col_info)
            
            # Add sample data if available
            if table.sample_data:
                context_parts.append("\nSample data:")
                # Show first 3 rows
                for i, row in enumerate(table.sample_data[:3]):
                    context_parts.append(f"  Row {i+1}: {json.dumps(row, default=str)}")
                
                # Add value statistics for better context
                if len(table.sample_data) > 1:
                    context_parts.append("\nValue insights:")
                    for col in table.columns:
                        col_name = col.name
                        values = [row.get(col_name) for row in table.sample_data if row.get(col_name) is not None]
                        
                        if values:
                            if col.data_type.value in ['integer', 'bigint', 'numeric', 'float', 'double']:
                                if all(isinstance(v, (int, float)) for v in values):
                                    min_val = min(values)
                                    max_val = max(values)
                                    context_parts.append(f"  - {col_name}: ranges from {min_val} to {max_val}")
                            elif col.data_type.value in ['varchar', 'text']:
                                unique_values = list(set(str(v) for v in values))[:5]
                                context_parts.append(f"  - {col_name}: sample values: {', '.join(unique_values)}")
            
            context_parts.append("")  # Empty line between tables
        
        return '\n'.join(context_parts)


async def generate_llm_query_suggestions(
    unified_schema: UnifiedSchema,
    sample_data: Optional[List[Dict[str, Any]]] = None,
    num_suggestions: int = 10
) -> List[str]:
    """Convenience function to generate LLM-powered query suggestions."""
    generator = LLMQuerySuggestionGenerator()
    return await generator.generate_suggestions(unified_schema, sample_data, num_suggestions)