"""Session-aware NL2SQL pipeline for multi-datasource support."""

import time
from typing import Dict, Optional, Any
import structlog

from sens.llm.intent_extractor import IntentExtractor
from sens.llm.sql_generator import SQLGenerator
from sens.postprocessing.response_builder import ResponseBuilder
from sens.retrieval.optimized_retriever import OptimizedSchemaRetriever
from sens.schema.context import SchemaContext
from sens.schema.graph import SchemaGraph
from sens.validation.sql_validator import SQLValidator
from sens.datasource.executor import MultiSourceExecutor
from sens.caching.factory import get_cache_manager
from sens.chat.adapters import ChatEmbeddingAdapter, ChatTokenIndexAdapter

logger = structlog.get_logger(__name__)


class SessionAwarePipeline:
    """Pipeline that supports session-specific data sources and schema contexts."""
    
    def __init__(
        self,
        schema_context: SchemaContext,
        sql_executor: MultiSourceExecutor,
        use_optimized_retriever: bool = True
    ):
        """Initialize the session-aware pipeline.
        
        Args:
            schema_context: The schema context for this session's data source
            sql_executor: The multi-source executor for running queries
            use_optimized_retriever: Whether to use optimized retrieval
        """
        self.schema_context = schema_context
        self.sql_executor = sql_executor
        
        # Initialize components
        self.intent_extractor = IntentExtractor()
        self.sql_generator = SQLGenerator()
        self.sql_validator = SQLValidator()
        self.response_builder = ResponseBuilder()
        
        # Initialize retrieval with session-specific schema
        if use_optimized_retriever:
            cache_manager = get_cache_manager()
            
            # Create temporary schema graph for this session
            self.schema_graph = SchemaGraph()
            if hasattr(schema_context, '_schema_dict'):
                self.schema_graph._build_from_dict(schema_context._schema_dict)
            
            self.retriever = OptimizedSchemaRetriever(
                token_index=ChatTokenIndexAdapter(),
                embedding_index=ChatEmbeddingAdapter(),
                schema_graph=self.schema_graph,
                cache_manager=cache_manager,
                enable_caching=False  # Don't cache session-specific schemas
            )
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
            intent = await self.intent_extractor.extract(question)
            pipeline_steps.append({
                "step": "intent_extraction",
                "duration": time.time() - start_time,
                "result": {
                    "query_type": intent.query_type,
                    "entities": intent.entities,
                    "filters": intent.filters
                }
            })
            
            # Step 2: Retrieve relevant schema
            step_start = time.time()
            logger.info("retrieving_schema", intent=intent.query_type)
            
            # For session-specific data, we use the full schema context
            # since the data source is limited in scope
            relevant_tables = list(self.schema_context._schema_dict.get("tables", {}).keys())
            
            schema_context_dict = {
                "intent": {
                    "query_type": intent.query_type,
                    "entities": intent.entities
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
            
            sql = await self.sql_generator.generate(
                intent=intent,
                schema_context=self.schema_context
            )
            
            pipeline_steps.append({
                "step": "sql_generation",
                "duration": time.time() - step_start,
                "result": {"sql": sql}
            })
            
            # Step 4: Validate SQL
            step_start = time.time()
            logger.info("validating_sql", sql=sql)
            
            validation_result = self.sql_validator.validate(
                sql=sql,
                schema=self.schema_context._schema_dict
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
            
            summary = await self.response_builder.build_summary(
                question=question,
                sql_query=sql,
                query_result=query_result
            )
            
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