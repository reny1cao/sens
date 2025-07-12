"""Graph builder for SENS LangGraph agent."""

from typing import Literal, Dict, Any

from .state import SensAgentState
from .nodes import (
    analyze_intent,
    retrieve_schema,
    generate_sql,
    validate_sql,
    execute_sql,
    reflect_and_improve,
    finalize_response
)

# Import structlog if available, otherwise create a simple logger
try:
    import structlog
    log = structlog.get_logger()
except ImportError:
    import logging
    log = logging.getLogger(__name__)

# Fallback imports for when LangGraph dependencies are not available
try:
    from langgraph.graph import StateGraph, START, END
    from langchain_core.runnables import RunnableConfig
    LANGGRAPH_AVAILABLE = True
except ImportError:
    # Create fallback classes
    log.warning("LangGraph not available, using fallback implementation")
    LANGGRAPH_AVAILABLE = False
    
    class StateGraph:
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.edges = {}
            self.conditional_edges = {}
            self.entry_point = None
        
        def add_node(self, name: str, func):
            self.nodes[name] = func
        
        def add_edge(self, from_node: str, to_node: str):
            if from_node not in self.edges:
                self.edges[from_node] = []
            self.edges[from_node].append(to_node)
        
        def add_conditional_edges(self, from_node: str, condition_func, mappings: Dict):
            self.conditional_edges[from_node] = {
                "condition": condition_func,
                "mappings": mappings
            }
        
        def set_entry_point(self, node: str):
            self.entry_point = node
        
        def compile(self):
            return FallbackCompiledGraph(self)
    
    class FallbackCompiledGraph:
        def __init__(self, workflow):
            self.workflow = workflow
        
        async def ainvoke(self, initial_state: SensAgentState, config=None):
            """Fallback graph execution."""
            state = initial_state.copy()
            current_node = self.workflow.entry_point
            
            # Simple sequential execution
            node_sequence = [
                "analyze_intent",
                "retrieve_schema", 
                "generate_sql",
                "validate_sql",
                "execute_sql",
                "reflect_and_improve",
                "finalize_response"
            ]
            
            for node_name in node_sequence:
                if node_name in self.workflow.nodes:
                    try:
                        result = await self.workflow.nodes[node_name](state, config or {})
                        state.update(result)
                        
                        # Check if we need to stop early
                        if node_name == "reflect_and_improve" and not state.get("needs_refinement", False):
                            break
                    except Exception as e:
                        log.error(f"Error in node {node_name}: {e}")
                        break
            
            return state
        
        async def astream(self, initial_state: SensAgentState, config=None):
            """Fallback streaming execution."""
            state = initial_state.copy()
            
            node_sequence = [
                "analyze_intent",
                "retrieve_schema",
                "generate_sql", 
                "validate_sql",
                "execute_sql",
                "reflect_and_improve",
                "finalize_response"
            ]
            
            for node_name in node_sequence:
                if node_name in self.workflow.nodes:
                    try:
                        result = await self.workflow.nodes[node_name](state, config or {})
                        state.update(result)
                        yield state
                        
                        # Check if we need to stop early
                        if node_name == "reflect_and_improve" and not state.get("needs_refinement", False):
                            break
                    except Exception as e:
                        log.error(f"Error in node {node_name}: {e}")
                        break
    
    START = "START"
    END = "END"
    RunnableConfig = Dict[str, Any]


def should_continue_iteration(state: SensAgentState) -> Literal["continue", "finalize"]:
    """Determine if we should continue iterating or finalize."""
    
    # Check if refinement is needed
    if not state.get("needs_refinement", False):
        return "finalize"
    
    # Check iteration count
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if iteration_count >= max_iterations:
        if LANGGRAPH_AVAILABLE:
            log.info("langgraph_max_iterations_reached", 
                    iteration_count=iteration_count, 
                    max_iterations=max_iterations)
        else:
            log.info(f"Maximum iterations reached: {iteration_count}/{max_iterations}")
        return "finalize"
    
    if LANGGRAPH_AVAILABLE:
        log.info("langgraph_continue_iteration", 
                iteration_count=iteration_count, 
                max_iterations=max_iterations)
    else:
        log.info(f"Continuing iteration: {iteration_count}/{max_iterations}")
    return "continue"


def increment_iteration_count(state: SensAgentState) -> Dict[str, Any]:
    """Increment iteration count when continuing."""
    return {
        "iteration_count": state.get("iteration_count", 0) + 1,
        "needs_refinement": False,  # Reset for next iteration
        "thoughts": [f"Starting iteration {state.get('iteration_count', 0) + 1}"],
        "actions_taken": ["increment_iteration_count"]
    }


def create_sens_agent_graph():
    """Create the SENS agent workflow graph."""
    
    if LANGGRAPH_AVAILABLE:
        log.info("langgraph_creating_graph")
    else:
        log.info("Creating SENS agent graph with fallback implementation")
    
    # Create graph with state schema
    workflow = StateGraph(SensAgentState)
    
    # Add all nodes
    workflow.add_node("analyze_intent", analyze_intent)
    workflow.add_node("retrieve_schema", retrieve_schema)
    workflow.add_node("generate_sql", generate_sql)
    workflow.add_node("validate_sql", validate_sql)
    workflow.add_node("execute_sql", execute_sql)
    workflow.add_node("reflect_and_improve", reflect_and_improve)
    workflow.add_node("increment_iteration", increment_iteration_count)
    workflow.add_node("finalize_response", finalize_response)
    
    # Define the workflow
    workflow.set_entry_point("analyze_intent")
    
    # Linear flow for main processing
    workflow.add_edge("analyze_intent", "retrieve_schema")
    workflow.add_edge("retrieve_schema", "generate_sql")
    workflow.add_edge("generate_sql", "validate_sql")
    
    if LANGGRAPH_AVAILABLE:
        # Conditional routing after validation
        workflow.add_conditional_edges(
            "validate_sql",
            lambda state: "execute" if not state.get("needs_refinement") else "reflect",
            {
                "execute": "execute_sql",
                "reflect": "reflect_and_improve"
            }
        )
        
        # After execution, always reflect
        workflow.add_edge("execute_sql", "reflect_and_improve")
        
        # Conditional routing based on reflection
        workflow.add_conditional_edges(
            "reflect_and_improve",
            should_continue_iteration,
            {
                "continue": "increment_iteration",
                "finalize": "finalize_response"
            }
        )
        
        # After incrementing iteration, go back to SQL generation
        workflow.add_edge("increment_iteration", "generate_sql")
        
        # Final response leads to end
        workflow.add_edge("finalize_response", END)
    else:
        # Simplified edges for fallback
        workflow.add_edge("validate_sql", "execute_sql")
        workflow.add_edge("execute_sql", "reflect_and_improve")
        workflow.add_edge("reflect_and_improve", "finalize_response")
    
    # Compile the graph
    graph = workflow.compile()
    
    if LANGGRAPH_AVAILABLE:
        log.info("langgraph_graph_created")
    else:
        log.info("SENS agent graph created with fallback implementation")
    
    return graph