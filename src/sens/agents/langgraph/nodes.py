"""Node implementations for LangGraph SENS agent."""

import asyncio
import time
from typing import Dict, Any, List

from .state import SensAgentState

# Import structlog if available, otherwise create a simple logger
try:
    import structlog
    log = structlog.get_logger()
except ImportError:
    import logging
    log = logging.getLogger(__name__)

# Fallback imports for when LangGraph dependencies are not available
try:
    from langchain_core.runnables import RunnableConfig
    from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
except ImportError:
    # Create fallback classes
    RunnableConfig = Dict[str, Any]
    
    class BaseMessage:
        def __init__(self, content: str, type: str = "human"):
            self.content = content
            self.type = type
    
    class HumanMessage(BaseMessage):
        def __init__(self, content: str):
            super().__init__(content, "human")
    
    class AIMessage(BaseMessage):
        def __init__(self, content: str):
            super().__init__(content, "ai")


async def analyze_intent(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Analyze user intent and extract query requirements."""
    
    start_time = time.time()
    log.info("langgraph_node_start", node="analyze_intent", query=state["user_query"])
    
    try:
        # Import here to avoid circular imports and handle missing dependencies
        try:
            from ...llm.intent_extractor import IntentExtractor
            intent_extractor = IntentExtractor()
            intent_result = await intent_extractor.extract_intent(state["user_query"])
            
            return {
                "intent": intent_result.intent,
                "query_context": getattr(intent_result, 'context', {}),
                "thoughts": [f"Identified intent: {intent_result.intent}"],
                "actions_taken": ["analyze_intent"],
                "observations": [f"Intent extracted with confidence: {getattr(intent_result, 'confidence', 'unknown')}"],
                "current_node": "analyze_intent"
            }
        except ImportError as e:
            log.warning("intent_extractor_not_available", error=str(e))
            # Fallback to simple intent analysis
            return {
                "intent": "data_query",  # Default intent
                "query_context": {"fallback": True},
                "thoughts": ["Using fallback intent analysis"],
                "actions_taken": ["analyze_intent"],
                "observations": ["Intent extractor not available, using fallback"],
                "current_node": "analyze_intent"
            }
    except Exception as e:
        log.error("langgraph_node_error", node="analyze_intent", error=str(e))
        return {
            "thoughts": [f"Intent analysis failed: {str(e)}"],
            "actions_taken": ["analyze_intent"],
            "observations": [f"Error in intent analysis: {str(e)}"],
            "current_node": "analyze_intent"
        }


async def retrieve_schema(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Retrieve relevant schema information using existing retrieval system."""
    
    log.info("langgraph_node_start", node="retrieve_schema", intent=state.get("intent"))
    
    try:
        # Import here to avoid circular imports and handle missing dependencies
        try:
            from ...retrieval.hybrid_retriever import HybridRetriever
            retriever = HybridRetriever()
            
            # Retrieve schema based on query and intent
            schema_results = await retriever.retrieve_relevant_schema(
                query=state["user_query"],
                intent=state.get("intent"),
                top_k=10
            )
            
            # Extract different types of schema information
            tables = []
            columns = []
            relationships = []
            
            for result in schema_results:
                if result.get("type") == "table":
                    tables.append(result["name"])
                elif result.get("type") == "column":
                    columns.append(result)
                elif result.get("type") == "relationship":
                    relationships.append(result)
            
            return {
                "retrieved_schema": schema_results,
                "relevant_tables": tables,
                "relevant_columns": columns,
                "table_relationships": relationships,
                "thoughts": [f"Retrieved schema for {len(schema_results)} elements"],
                "actions_taken": ["retrieve_schema"],
                "observations": [f"Found {len(tables)} tables, {len(columns)} columns"],
                "current_node": "retrieve_schema"
            }
        except ImportError as e:
            log.warning("retrieval_system_not_available", error=str(e))
            # Fallback schema retrieval
            return {
                "retrieved_schema": [],
                "relevant_tables": ["fallback_table"],
                "relevant_columns": [],
                "table_relationships": [],
                "thoughts": ["Using fallback schema retrieval"],
                "actions_taken": ["retrieve_schema"],
                "observations": ["Retrieval system not available, using fallback"],
                "current_node": "retrieve_schema"
            }
    except Exception as e:
        log.error("langgraph_node_error", node="retrieve_schema", error=str(e))
        return {
            "thoughts": [f"Schema retrieval failed: {str(e)}"],
            "actions_taken": ["retrieve_schema"],
            "observations": [f"Error in schema retrieval: {str(e)}"],
            "current_node": "retrieve_schema"
        }


async def generate_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Generate SQL query based on intent and schema using existing generator."""
    
    log.info("langgraph_node_start", node="generate_sql", 
             tables=len(state.get("relevant_tables", [])))
    
    try:
        # Import here to avoid circular imports and handle missing dependencies
        try:
            from ...generation.openrouter_generator import OpenRouterGenerator
            generator = OpenRouterGenerator()
            
            # Prepare context for SQL generation
            context = {
                "query": state["user_query"],
                "intent": state.get("intent"),
                "schema": state.get("retrieved_schema", []),
                "tables": state.get("relevant_tables", []),
                "columns": state.get("relevant_columns", []),
                "relationships": state.get("table_relationships", [])
            }
            
            # Generate SQL
            sql_result = await generator.generate_sql(context)
            
            return {
                "generated_sql": sql_result.sql,
                "sql_explanation": sql_result.explanation,
                "sql_confidence": getattr(sql_result, 'confidence', 0.8),
                "sql_assumptions": getattr(sql_result, 'assumptions', []) if hasattr(sql_result, 'assumptions') else [],
                "thoughts": [f"Generated SQL: {sql_result.sql[:100]}..."],
                "actions_taken": ["generate_sql"],
                "observations": [f"SQL generated with confidence: {getattr(sql_result, 'confidence', 'unknown')}"],
                "current_node": "generate_sql"
            }
        except ImportError as e:
            log.warning("sql_generator_not_available", error=str(e))
            # Fallback SQL generation
            fallback_sql = f"SELECT * FROM {state.get('relevant_tables', ['table'])[0]} LIMIT 10;"
            return {
                "generated_sql": fallback_sql,
                "sql_explanation": "Fallback SQL query generated",
                "sql_confidence": 0.5,
                "sql_assumptions": ["Using fallback generator"],
                "thoughts": ["Using fallback SQL generation"],
                "actions_taken": ["generate_sql"],
                "observations": ["SQL generator not available, using fallback"],
                "current_node": "generate_sql"
            }
    except Exception as e:
        log.error("langgraph_node_error", node="generate_sql", error=str(e))
        return {
            "thoughts": [f"SQL generation failed: {str(e)}"],
            "actions_taken": ["generate_sql"],
            "observations": [f"Error in SQL generation: {str(e)}"],
            "current_node": "generate_sql"
        }


async def validate_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Validate the generated SQL before execution."""
    
    log.info("langgraph_node_start", node="validate_sql")
    
    try:
        # Import here to avoid circular imports and handle missing dependencies
        try:
            from ...validation.sql_validator import SQLValidator
            validator = SQLValidator()
            
            validation_result = await validator.validate(
                sql=state["generated_sql"],
                schema=state.get("retrieved_schema", [])
            )
            
            if validation_result.is_valid:
                return {
                    "thoughts": ["SQL validation passed"],
                    "actions_taken": ["validate_sql"],
                    "observations": [f"SQL is valid: {validation_result.message}"],
                    "current_node": "validate_sql"
                }
            else:
                return {
                    "needs_refinement": True,
                    "refinement_reason": f"SQL validation failed: {validation_result.message}",
                    "thoughts": [f"SQL validation failed: {validation_result.message}"],
                    "actions_taken": ["validate_sql"],
                    "observations": [f"SQL validation errors: {getattr(validation_result, 'errors', [])}"],
                    "current_node": "validate_sql"
                }
        except ImportError as e:
            log.warning("sql_validator_not_available", error=str(e))
            # Basic SQL validation fallback
            sql = state.get("generated_sql", "")
            if sql and "SELECT" in sql.upper():
                return {
                    "thoughts": ["Using fallback SQL validation"],
                    "actions_taken": ["validate_sql"],
                    "observations": ["SQL validator not available, basic validation passed"],
                    "current_node": "validate_sql"
                }
            else:
                return {
                    "needs_refinement": True,
                    "refinement_reason": "Basic validation failed: Invalid SQL format",
                    "thoughts": ["Basic SQL validation failed"],
                    "actions_taken": ["validate_sql"],
                    "observations": ["SQL appears invalid"],
                    "current_node": "validate_sql"
                }
    except Exception as e:
        log.error("langgraph_node_error", node="validate_sql", error=str(e))
        return {
            "needs_refinement": True,
            "refinement_reason": f"SQL validation error: {str(e)}",
            "thoughts": [f"SQL validation error: {str(e)}"],
            "actions_taken": ["validate_sql"],
            "observations": [f"Error in SQL validation: {str(e)}"],
            "current_node": "validate_sql"
        }


async def execute_sql(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Execute the generated SQL query using existing executor."""
    
    log.info("langgraph_node_start", node="execute_sql", sql=state["generated_sql"][:100])
    
    try:
        # Import here to avoid circular imports and handle missing dependencies
        try:
            from ...execution.executor import SQLExecutor
            executor = SQLExecutor()
            
            # Execute SQL
            execution_result = await executor.execute(
                sql=state["generated_sql"],
                limit=1000  # Safety limit
            )
            
            return {
                "execution_results": execution_result.data,
                "execution_metadata": {
                    "row_count": len(execution_result.data) if execution_result.data else 0,
                    "columns": getattr(execution_result, 'columns', []) if hasattr(execution_result, 'columns') else [],
                    "execution_time": getattr(execution_result, 'execution_time', None) if hasattr(execution_result, 'execution_time') else None
                },
                "thoughts": [f"Query executed successfully, returned {len(execution_result.data) if execution_result.data else 0} rows"],
                "actions_taken": ["execute_sql"],
                "observations": [f"SQL execution completed successfully"],
                "current_node": "execute_sql"
            }
        except ImportError as e:
            log.warning("sql_executor_not_available", error=str(e))
            # Fallback execution result
            return {
                "execution_results": [{"message": "Executor not available - this is a simulation"}],
                "execution_metadata": {
                    "row_count": 1,
                    "columns": ["message"],
                    "execution_time": 0.1
                },
                "thoughts": ["Using fallback SQL execution"],
                "actions_taken": ["execute_sql"],
                "observations": ["SQL executor not available, using simulation"],
                "current_node": "execute_sql"
            }
    except Exception as e:
        log.error("langgraph_node_error", node="execute_sql", error=str(e))
        return {
            "execution_error": str(e),
            "needs_refinement": True,
            "refinement_reason": f"SQL execution failed: {str(e)}",
            "thoughts": [f"Query failed: {str(e)}"],
            "actions_taken": ["execute_sql"],
            "observations": [f"SQL execution error: {str(e)}"],
            "current_node": "execute_sql"
        }


async def reflect_and_improve(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Reflect on results and determine if refinement is needed."""
    
    log.info("langgraph_node_start", node="reflect_and_improve", 
             has_error=bool(state.get("execution_error")))
    
    try:
        # Check for execution errors
        if state.get("execution_error"):
            return {
                "needs_refinement": True,
                "refinement_reason": f"Execution error: {state['execution_error']}",
                "thoughts": [f"Execution failed, needs refinement: {state['execution_error']}"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Identified execution error, refinement needed"],
                "current_node": "reflect_and_improve"
            }
        
        # Check for empty results
        results = state.get("execution_results")
        if not results or len(results) == 0:
            return {
                "needs_refinement": True,
                "refinement_reason": "Query returned no results",
                "thoughts": ["Query returned no results, may need refinement"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Empty result set detected"],
                "current_node": "reflect_and_improve"
            }
        
        # Check iteration count
        iteration_count = state.get("iteration_count", 0)
        max_iterations = state.get("max_iterations", 3)
        
        if iteration_count >= max_iterations:
            return {
                "needs_refinement": False,
                "thoughts": [f"Maximum iterations ({max_iterations}) reached, finalizing"],
                "actions_taken": ["reflect_and_improve"],
                "observations": ["Maximum iterations reached"],
                "current_node": "reflect_and_improve"
            }
        
        # Results look good
        return {
            "needs_refinement": False,
            "thoughts": ["Query executed successfully with meaningful results"],
            "actions_taken": ["reflect_and_improve"],
            "observations": [f"Successful execution with {len(results)} results"],
            "current_node": "reflect_and_improve"
        }
    
    except Exception as e:
        log.error("langgraph_node_error", node="reflect_and_improve", error=str(e))
        return {
            "needs_refinement": False,  # Stop on reflection error
            "thoughts": [f"Reflection error: {str(e)}"],
            "actions_taken": ["reflect_and_improve"],
            "observations": [f"Error in reflection: {str(e)}"],
            "current_node": "reflect_and_improve"
        }


async def finalize_response(state: SensAgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Finalize the response with results and explanations."""
    
    log.info("langgraph_node_start", node="finalize_response")
    
    try:
        # Prepare final response
        final_message = AIMessage(
            content=f"Query: {state['user_query']}\n\n"
                   f"Generated SQL:\n```sql\n{state.get('generated_sql', '')}\n```\n\n"
                   f"Explanation: {state.get('sql_explanation', '')}\n\n"
                   f"Results: {len(state.get('execution_results', []))} rows returned"
        )
        
        return {
            "messages": [final_message],
            "end_time": time.time(),
            "thoughts": ["Response finalized"],
            "actions_taken": ["finalize_response"],
            "observations": ["Final response prepared"],
            "current_node": "finalize_response"
        }
    
    except Exception as e:
        log.error("langgraph_node_error", node="finalize_response", error=str(e))
        error_message = AIMessage(
            content=f"An error occurred while processing your query: {str(e)}"
        )
        return {
            "messages": [error_message],
            "end_time": time.time(),
            "thoughts": [f"Error in finalization: {str(e)}"],
            "actions_taken": ["finalize_response"],
            "observations": ["Error response prepared"],
            "current_node": "finalize_response"
        }