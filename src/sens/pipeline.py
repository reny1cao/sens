"""Enhanced NL2SQL pipeline with proper error handling."""

import time
from typing import Any, Dict, Optional, Set

import structlog

from sens.exceptions import (
    ExecutionError,
    IntentExtractionError,
    PipelineError,
    RetrievalError,
    SensError,
    ValidationError,
)
from sens.schema.context import ValidatorSchemaContext
from sens.schema.graph import SchemaGraph
from sens.validation.sql_validator import SQLValidator, ValidatedSQL, ValidationLevel

log = structlog.get_logger()


class EnhancedNL2SQLPipeline:
    """Pipeline for converting natural language to SQL with enhanced error handling."""

    def __init__(self):
        """Initialize pipeline components."""
        self.schema_graph = SchemaGraph.get_instance()
        self.sql_validator = SQLValidator()

        # Initialize schema context for validation
        tables = self.schema_graph.list_all_tables()
        self.schema_context = ValidatorSchemaContext(
            tables=set(tables),
            columns_per_table={
                table: set(self.schema_graph.get_table_columns(table))
                for table in tables
            },
        )

    async def process_query(self, query: str) -> Dict[str, Any]:
        """
        Process a natural language query to SQL.

        Args:
            query: The natural language query to process

        Returns:
            Dictionary containing the results and metadata

        Raises:
            PipelineError: If any step in the pipeline fails
        """
        try:
            # Track pipeline metrics
            metrics = {
                "steps": [],
                "step_count": 0,
                "success": False,
                "error": None,
                "metadata": {"user_input": query},
            }

            # Step 1: Schema Retrieval
            start_time = time.time()
            try:
                schema_context = await self._retrieve_schema_context(query)
                self._add_step_metrics(metrics, "schema_retrieval", start_time)
            except Exception as e:
                self._add_step_metrics(
                    metrics, "schema_retrieval", start_time, error=str(e)
                )
                raise RetrievalError(f"Schema retrieval failed: {e}")

            # Step 2: Intent Extraction
            start_time = time.time()
            try:
                intent = await self._extract_intent(query, schema_context)
                self._add_step_metrics(metrics, "intent_extraction", start_time)
            except Exception as e:
                self._add_step_metrics(
                    metrics, "intent_extraction", start_time, error=str(e)
                )
                raise IntentExtractionError(f"Intent extraction failed: {e}")

            # Step 3: Intent Validation
            start_time = time.time()
            try:
                validated_intent = self._validate_intent(intent)
                self._add_step_metrics(metrics, "intent_validation", start_time)
            except Exception as e:
                self._add_step_metrics(
                    metrics, "intent_validation", start_time, error=str(e)
                )
                raise ValidationError(f"Intent validation failed: {e}")

            # Step 4: SQL Generation
            start_time = time.time()
            try:
                sql_result = await self._generate_sql(query, validated_intent)
                self._add_step_metrics(metrics, "sql_generation", start_time)
            except Exception as e:
                self._add_step_metrics(
                    metrics, "sql_generation", start_time, error=str(e)
                )
                raise ExecutionError(f"SQL generation failed: {e}")

            # Step 5: SQL Validation
            start_time = time.time()
            try:
                validation_result = self._validate_sql(sql_result.sql)
                if not validation_result.is_valid:
                    raise ValidationError(str(validation_result.errors[0]))
                self._add_step_metrics(metrics, "sql_validation", start_time)
            except Exception as e:
                self._add_step_metrics(
                    metrics, "sql_validation", start_time, error=str(e)
                )
                raise ValidationError(f"SQL validation failed: {e}")

            # Calculate total duration
            total_duration = sum(step["duration_ms"] for step in metrics["steps"])
            metrics["total_duration_ms"] = total_duration
            metrics["success"] = True

            return {
                "sql": sql_result.sql,
                "tables_used": sql_result.tables_used,
                "columns_used": sql_result.columns_used,
                "metrics": metrics,
            }

        except SensError as e:
            # Log the error with metrics
            metrics["error"] = str(e)
            log.error("pipeline_error", error=str(e), metrics=metrics)
            raise PipelineError(str(e))

        except Exception as e:
            # Log unexpected errors
            metrics["error"] = str(e)
            log.error("unexpected_error", error=str(e), metrics=metrics)
            raise PipelineError(f"An unexpected error occurred: {e}")

        finally:
            # Always log pipeline metrics
            log.info(
                "pipeline_metrics",
                conversation_id=metrics.get("conversation_id"),
                success=metrics["success"],
                error=metrics.get("error"),
                step_count=metrics["step_count"],
                steps=metrics["steps"],
                total_duration_ms=metrics.get("total_duration_ms", 0),
                metadata=metrics["metadata"],
            )

    def _validate_sql(self, sql: str) -> ValidatedSQL:
        """
        Validate generated SQL.

        Args:
            sql: SQL query to validate

        Returns:
            ValidatedSQL result
        """
        return self.sql_validator.validate(
            sql=sql,
            schema=self.schema_context,
            levels={
                ValidationLevel.SYNTAX,
                ValidationLevel.SCHEMA,
                ValidationLevel.SAFETY,
            },
        )

    @staticmethod
    def _add_step_metrics(
        metrics: Dict[str, Any],
        step_name: str,
        start_time: float,
        error: Optional[str] = None,
    ) -> None:
        """Add metrics for a pipeline step."""
        duration_ms = (time.time() - start_time) * 1000
        metrics["steps"].append(
            {"name": step_name, "duration_ms": duration_ms, "success": error is None}
        )
        if error:
            metrics["steps"][-1]["error"] = error
        metrics["step_count"] += 1

        # Log step metrics
        log.info(
            "step_metrics",
            conversation_id=metrics.get("conversation_id"),
            step_name=step_name,
            duration_ms=duration_ms,
            success=error is None,
            error=error,
            metadata=metrics.get("metadata", {}),
        )
