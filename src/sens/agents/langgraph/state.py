"""State management for LangGraph SENS agents."""

from typing import TypedDict, Annotated, List, Optional, Dict, Any
import operator

# Fallback imports for when LangGraph dependencies are not available
try:
    from langchain_core.messages import BaseMessage
except ImportError:
    # Create a simple BaseMessage class for compatibility
    class BaseMessage:
        def __init__(self, content: str, type: str = "human"):
            self.content = content
            self.type = type

try:
    from langgraph.graph.message import add_messages
except ImportError:
    # Fallback for when LangGraph is not available
    def add_messages(existing: List, new: List) -> List:
        """Fallback message adding function."""
        return existing + new


class SensAgentState(TypedDict):
    """Central state for SENS agent workflow."""
    
    # Message history (compatible with existing chat system)
    messages: Annotated[List[BaseMessage], add_messages]
    
    # Query processing
    user_query: str
    intent: Optional[str]
    query_context: Optional[Dict[str, Any]]
    
    # Schema retrieval (accumulates results from parallel searches)
    retrieved_schema: Annotated[List[Dict], operator.add]
    relevant_tables: Annotated[List[str], operator.add]
    relevant_columns: Annotated[List[Dict], operator.add]
    table_relationships: Annotated[List[Dict], operator.add]
    
    # SQL generation
    generated_sql: Optional[str]
    sql_explanation: Optional[str]
    sql_confidence: float
    sql_assumptions: Annotated[List[str], operator.add]
    
    # Execution results
    execution_results: Optional[Any]
    execution_error: Optional[str]
    execution_metadata: Optional[Dict[str, Any]]
    
    # Agent reasoning (for transparency)
    thoughts: Annotated[List[str], operator.add]
    actions_taken: Annotated[List[str], operator.add]
    observations: Annotated[List[str], operator.add]
    
    # Iteration control
    iteration_count: int
    max_iterations: int
    needs_refinement: bool
    refinement_reason: Optional[str]
    
    # Memory and learning
    discovered_mappings: Annotated[List[Dict], operator.add]
    success_patterns: Annotated[List[Dict], operator.add]
    
    # Configuration
    model_config: Optional[Dict[str, Any]]
    retrieval_config: Optional[Dict[str, Any]]
    
    # Status tracking
    current_node: Optional[str]
    start_time: Optional[float]
    end_time: Optional[float]