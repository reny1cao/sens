"""Session-aware NL2SQL pipeline for multi-datasource support."""

import time
from typing import Dict, Optional, Any
import structlog

from sens.llm.intent_extractor import IntentExtractor
from sens.llm.sql_generator import SQLGenerator
from sens.postprocessing.response_builder import ResponseBuilder
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.schema.context import SchemaContext, LLMSchemaContext
from sens.schema.graph import SchemaGraph
from sens.schema.unified_schema import UnifiedSchema
from sens.schema.format_adapter import SchemaFormatAdapter
from sens.validation.sql_validator import SQLValidator
from sens.datasource.executor import MultiSourceExecutor
from sens.caching.factory import get_cache_manager
from sens.chat.adapters import ChatEmbeddingAdapter, ChatTokenIndexAdapter

logger = structlog.get_logger(__name__)


class SessionAwarePipeline:
    """Pipeline that supports session-specific data sources and schema contexts."""
    
    def __init__(
        self,
        unified_schema: UnifiedSchema,
        sql_executor: MultiSourceExecutor,
        use_optimized_retriever: bool = True
    ):
        """Initialize the session-aware pipeline.
        
        Args:
            unified_schema: The unified schema for this session's data source
            sql_executor: The multi-source executor for running queries
            use_optimized_retriever: Whether to use optimized retrieval
        """
        self.unified_schema = unified_schema
        self.sql_executor = sql_executor
        
        # Initialize components
        self.intent_extractor = IntentExtractor()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.response_builder = ResponseBuilder()
        
        # Initialize retrieval with session-specific schema
        if use_optimized_retriever:
            cache_manager = get_cache_manager()
            
            # For now, skip retrieval optimization for session-specific schemas
            self.schema_graph = None
            self.retriever = None
        else:
            raise NotImplementedError("Standard retriever not supported yet")
    
    async def process(
        self,
        question: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process a natural language question into SQL and execute it.
        
        Args:
            question: The natural language question
            session_id: The session ID for data source lookup
            
        Returns:
            Dict containing SQL, results, and metadata
        """
        start_time = time.time()
        pipeline_steps = []
        
        try:
            # Step 1: Extract intent
            logger.info("extracting_intent", question=question)
            
            # Use format adapter to get schema in intent extractor format
            schema_snippet = SchemaFormatAdapter.for_intent_extractor(self.unified_schema)
            
            intent = await self.intent_extractor.extract(question, schema_snippet)
            pipeline_steps.append({
                "step": "intent_extraction",
                "duration": time.time() - start_time,
                "result": {
                    "query_type": intent.query_type,
                    "tables": intent.tables,
                    "operations": intent.operations,
                    "conditions": intent.conditions,
                    "confidence": intent.confidence
                }
            })
            
            # Step 2: Retrieve relevant schema
            step_start = time.time()
            logger.info("retrieving_schema", intent=intent.query_type)
            
            # For session-specific data, we use the full schema
            # since the data source is limited in scope
            relevant_tables = [table.name for table in self.unified_schema.tables]
            
            schema_context_dict = {
                "intent": {
                    "query_type": intent.query_type,
                    "tables": intent.tables,
                    "operations": intent.operations,
                    "conditions": intent.conditions
                },
                "tables": relevant_tables[:10],  # Limit to prevent context overflow
                "columns": [],
                "relationships": []
            }
            
            pipeline_steps.append({
                "step": "schema_retrieval",
                "duration": time.time() - step_start,
                "result": {
                    "tables_found": len(relevant_tables),
                    "tables": relevant_tables
                }
            })
            
            # Step 3: Generate SQL
            step_start = time.time()
            logger.info("generating_sql")
            
            # Convert schema to LLM format for SQL generation
            llm_schema_context = SchemaFormatAdapter.for_sql_generator(
                self.unified_schema, intent
            )
            
            # Need to create ValidIntent wrapper for SQL generator
            from sens.llm.intent_validator import ValidIntent
            valid_intent = ValidIntent(
                original_intent=intent,
                enhanced_metadata={}
            )
            
            generated_sql = await self.sql_generator.generate(
                question=question,
                intent=valid_intent,
                schema_context=llm_schema_context
            )
            
            # Extract the SQL string
            sql = generated_sql.sql
            
            pipeline_steps.append({
                "step": "sql_generation",
                "duration": time.time() - step_start,
                "result": {"sql": sql}
            })
            
            # Step 4: Validate SQL
            step_start = time.time()
            logger.info("validating_sql", sql=sql)
            
            # Convert schema to validator format
            validator_schema = SchemaFormatAdapter.for_validator(self.unified_schema)
            
            validation_result = self.sql_validator.validate(
                sql=sql,
                full_schema=validator_schema,
                prompted_schema=validator_schema
            )
            
            if not validation_result.is_valid:
                raise ValueError(f"SQL validation failed: {validation_result.error}")
            
            pipeline_steps.append({
                "step": "sql_validation",
                "duration": time.time() - step_start,
                "result": {"is_valid": True}
            })
            
            # Step 5: Execute SQL
            step_start = time.time()
            logger.info("executing_sql", session_id=session_id)
            
            query_result = await self.sql_executor.execute(
                sql=sql,
                session_id=session_id
            )
            
            pipeline_steps.append({
                "step": "sql_execution",
                "duration": time.time() - step_start,
                "result": {
                    "rows_returned": query_result.row_count,
                    "execution_time": query_result.execution_time
                }
            })
            
            # Step 6: Build response summary
            step_start = time.time()
            logger.info("building_response")
            
            # Build complete response
            final_response = self.response_builder.build(
                question=question,
                intent=intent,
                result=query_result,
                sql=sql,
                execution_time_ms=query_result.execution_time * 1000 if query_result else None
            )
            
            # Extract summary from response
            summary = final_response.summary
            
            pipeline_steps.append({
                "step": "response_building",
                "duration": time.time() - step_start,
                "result": {"summary_generated": bool(summary)}
            })
            
            return {
                "sql": sql,
                "query_result": query_result,
                "summary": summary,
                "intent": intent.model_dump(),
                "schema_context": schema_context_dict,
                "pipeline_steps": pipeline_steps,
                "total_duration": time.time() - start_time
            }
            
        except Exception as e:
            logger.error("pipeline_error", 
                        error=str(e),
                        step=pipeline_steps[-1]["step"] if pipeline_steps else "unknown")
            
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "pipeline_steps": pipeline_steps,
                "total_duration": time.time() - start_time
            }