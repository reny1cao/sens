"""
SQLite-specific NL2SQL pipeline for BIRD-SQL-DEV evaluation.

This pipeline adapts the existing NL2SQL generation for SQLite databases.
"""

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import structlog
from openai import OpenAI

from sens.exceptions import PipelineError
from sens.schema.sqlite_schema_extractor import SQLiteSchemaExtractor
from sens.settings import get_settings

logger = structlog.get_logger(__name__)


class SQLiteNL2SQLPipeline:
    """Pipeline for converting natural language to SQL for SQLite databases."""

    def __init__(self, db_path: str):
        """Initialize the SQLite NL2SQL pipeline.
        
        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = Path(db_path)
        self.settings = get_settings()
        
        # Initialize schema extractor
        self.schema_extractor = SQLiteSchemaExtractor(str(db_path))
        self.schema_cache = None
        
        # Initialize OpenAI client using settings (same as BIRD-CRITIC)
        self.openai_client = OpenAI(
            api_key=self.settings.openrouter_api_key,
            base_url=str(self.settings.openrouter_base_url),
        )
        
        # Get model configuration from settings (same as BIRD-CRITIC)
        self.model_name = self.settings.get_model_for("sql_generator")
        self.max_tokens = self.settings.sql_generator.max_tokens
        self.temperature = self.settings.sql_generator.temperature
        self.timeout_seconds = self.settings.sql_generator.timeout_seconds
        
        logger.info(f"Initialized SQLite NL2SQL pipeline for: {db_path}")
        logger.info(f"Using model: {self.model_name}")

    def _get_schema_context(self) -> str:
        """Get schema context with caching.
        
        Returns:
            Formatted schema context string
        """
        if self.schema_cache is None:
            self.schema_cache = self.schema_extractor.get_schema_context()
        return self.schema_cache

    async def generate_sql(self, question: str, evidence: Optional[str] = None) -> Dict[str, Any]:
        """Generate SQL query from natural language question.
        
        Args:
            question: Natural language question
            evidence: Optional evidence/context from the dataset
            
        Returns:
            Dictionary containing SQL and generation metadata
        """
        start_time = time.time()
        
        try:
            # Get schema context
            schema_context = self._get_schema_context()
            
            # Create the prompt for SQL generation
            prompt = self._create_sql_generation_prompt(question, schema_context, evidence)
            
            # Generate SQL using OpenAI with settings-configured model
            response = self.openai_client.chat.completions.create(
                model=self.model_name,  # Use model from settings (same as BIRD-CRITIC)
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert SQL developer specializing in SQLite databases. Generate accurate SQL queries based on the given schema and natural language questions."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,  # Use temperature from settings
                max_tokens=self.max_tokens,  # Use max_tokens from settings
                timeout=self.timeout_seconds,  # Use timeout from settings
            )
            
            # Extract SQL from response
            sql_response = response.choices[0].message.content.strip()
            
            # Parse SQL from response (handle potential markdown formatting)
            sql_query = self._extract_sql_from_response(sql_response)
            
            generation_time = (time.time() - start_time) * 1000
            
            return {
                "sql": sql_query,
                "success": True,
                "generation_time_ms": generation_time,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "model_used": self.model_name,  # Use actual model from settings
                "raw_response": sql_response,
            }
            
        except Exception as e:
            generation_time = (time.time() - start_time) * 1000
            logger.error(f"SQL generation failed: {e}")
            
            return {
                "sql": None,
                "success": False,
                "error": str(e),
                "generation_time_ms": generation_time,
            }

    def _create_sql_generation_prompt(self, question: str, schema_context: str, evidence: Optional[str] = None) -> str:
        """Create a prompt for SQL generation.
        
        Args:
            question: Natural language question
            schema_context: Database schema context
            evidence: Optional evidence/context
            
        Returns:
            Formatted prompt for LLM
        """
        prompt_parts = [
            "You are an expert SQL developer. Generate a SQLite SQL query to answer the given question.",
            "",
            "DATABASE SCHEMA:",
            schema_context,
            "",
            "QUESTION:",
            question,
        ]
        
        if evidence:
            prompt_parts.extend([
                "",
                "ADDITIONAL CONTEXT:",
                evidence,
            ])
        
        prompt_parts.extend([
            "",
            "INSTRUCTIONS:",
            "1. Generate a valid SQLite SQL query that answers the question",
            "2. Use only tables and columns that exist in the schema",
            "3. Follow SQLite syntax conventions",
            "4. Return only the SQL query without any explanation or formatting",
            "5. Do not include markdown code blocks or other formatting",
            "6. Make sure the query is syntactically correct",
            "",
            "SQL QUERY:",
        ])
        
        return "\n".join(prompt_parts)

    def _extract_sql_from_response(self, response: str) -> str:
        """Extract SQL query from LLM response.
        
        Args:
            response: Raw LLM response
            
        Returns:
            Clean SQL query
        """
        # Remove markdown code blocks if present
        if "```sql" in response:
            start_idx = response.find("```sql") + 6
            end_idx = response.find("```", start_idx)
            if end_idx != -1:
                response = response[start_idx:end_idx]
        elif "```" in response:
            start_idx = response.find("```") + 3
            end_idx = response.find("```", start_idx)
            if end_idx != -1:
                response = response[start_idx:end_idx]
        
        # Clean up the response
        sql_query = response.strip()
        
        # Fix common parsing issues where "SQLite" gets partially truncated
        if sql_query.startswith("ite "):
            sql_query = sql_query[4:]  # Remove "ite " prefix
        elif sql_query.startswith("lite "):
            sql_query = sql_query[5:]  # Remove "lite " prefix
        
        # Look for SELECT statement specifically
        select_match = None
        for keyword in ["SELECT", "INSERT", "UPDATE", "DELETE", "WITH", "CREATE"]:
            idx = sql_query.upper().find(keyword)
            if idx != -1:
                if select_match is None or idx < select_match:
                    select_match = idx
        
        if select_match is not None:
            sql_query = sql_query[select_match:]
        
        # Remove any leading/trailing text that's not SQL
        lines = sql_query.split('\n')
        sql_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and not line.startswith('--'):
                sql_lines.append(line)
        
        return ' '.join(sql_lines)

    def execute_sql(self, sql: str) -> Dict[str, Any]:
        """Execute SQL query on the SQLite database.
        
        Args:
            sql: SQL query to execute
            
        Returns:
            Execution result with data and metadata
        """
        start_time = time.time()
        
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(sql)
                
                # Fetch results
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description] if cursor.description else []
                
                # Convert rows to list of dictionaries
                data = []
                for row in rows:
                    data.append(dict(row))
                
                execution_time = (time.time() - start_time) * 1000
                
                return {
                    "success": True,
                    "data": data,
                    "columns": columns,
                    "row_count": len(data),
                    "execution_time_ms": execution_time,
                }
                
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"SQL execution failed: {e}")
            
            return {
                "success": False,
                "error": str(e),
                "execution_time_ms": execution_time,
            }

    async def process_question(self, question: str, evidence: Optional[str] = None) -> Dict[str, Any]:
        """Process a natural language question end-to-end.
        
        Args:
            question: Natural language question
            evidence: Optional evidence/context
            
        Returns:
            Complete processing result
        """
        try:
            # Generate SQL
            sql_result = await self.generate_sql(question, evidence)
            
            if not sql_result["success"]:
                return {
                    "success": False,
                    "error": sql_result.get("error", "SQL generation failed"),
                    "question": question,
                    "sql": None,
                    "execution_result": None,
                }
            
            # Execute SQL
            execution_result = self.execute_sql(sql_result["sql"])
            
            return {
                "success": execution_result["success"],
                "question": question,
                "sql": sql_result["sql"],
                "execution_result": execution_result,
                "generation_metadata": {
                    "generation_time_ms": sql_result.get("generation_time_ms"),
                    "tokens_used": sql_result.get("tokens_used"),
                    "model_used": sql_result.get("model_used"),
                },
                "error": execution_result.get("error") if not execution_result["success"] else None,
            }
            
        except Exception as e:
            logger.error(f"Question processing failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "question": question,
                "sql": None,
                "execution_result": None,
            }

    def validate_sql_syntax(self, sql: str) -> Dict[str, Any]:
        """Validate SQL syntax without executing.
        
        Args:
            sql: SQL query to validate
            
        Returns:
            Validation result
        """
        try:
            with sqlite3.connect(str(self.db_path)) as conn:
                cursor = conn.cursor()
                # Use EXPLAIN to validate syntax without executing
                cursor.execute(f"EXPLAIN {sql}")
                
                return {
                    "valid": True,
                    "error": None,
                }
                
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }

    def get_database_info(self) -> Dict[str, Any]:
        """Get information about the SQLite database.
        
        Returns:
            Database information
        """
        try:
            schema = self.schema_extractor.extract_schema()
            
            return {
                "database_path": str(self.db_path),
                "database_type": "sqlite",
                "table_count": len(schema.tables),
                "tables": list(schema.tables.keys()),
                "total_columns": sum(len(table.columns) for table in schema.tables.values()),
                "total_relationships": len(schema.relationships),
            }
            
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {
                "database_path": str(self.db_path),
                "database_type": "sqlite",
                "error": str(e),
            }