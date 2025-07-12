"""CLI command to test LangGraph agent."""

import asyncio
import json
import time
from typing import Any, Dict

import click

from ...agents.langgraph.graph import create_sens_agent_graph
from ...agents.langgraph.state import SensAgentState

# Import message classes with fallback
try:
    from langchain_core.messages import HumanMessage
except ImportError:
    class HumanMessage:
        def __init__(self, content: str):
            self.content = content
            self.type = "human"


@click.command()
@click.option(
    "--query",
    "-q",
    required=True,
    help="Natural language query to test"
)
@click.option(
    "--max-iterations",
    "-m",
    default=3,
    type=int,
    help="Maximum number of refinement iterations"
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output"
)
@click.option(
    "--stream",
    "-s",
    is_flag=True,
    help="Enable streaming output"
)
async def test_langgraph_agent(query: str, max_iterations: int, verbose: bool, stream: bool):
    """Test the LangGraph agent with a natural language query."""
    
    click.echo(f"Testing LangGraph agent with query: {query}")
    click.echo(f"Max iterations: {max_iterations}")
    click.echo("=" * 50)
    
    try:
        # Create graph
        graph = create_sens_agent_graph()
        click.echo("✓ Graph created successfully")
        
        # Create initial state
        initial_state = SensAgentState(
            messages=[HumanMessage(content=query)],
            user_query=query,
            iteration_count=0,
            max_iterations=max_iterations,
            needs_refinement=False,
            sql_confidence=0.0,
            thoughts=[],
            actions_taken=[],
            observations=[],
            retrieved_schema=[],
            relevant_tables=[],
            relevant_columns=[],
            table_relationships=[],
            sql_assumptions=[],
            discovered_mappings=[],
            success_patterns=[],
            start_time=time.time(),
            # Optional fields
            intent=None,
            query_context=None,
            generated_sql=None,
            sql_explanation=None,
            execution_results=None,
            execution_error=None,
            execution_metadata=None,
            refinement_reason=None,
            model_config=None,
            retrieval_config=None,
            current_node=None,
            end_time=None
        )
        
        if stream:
            # Stream execution
            click.echo("Streaming agent execution...")
            click.echo("-" * 30)
            
            async for event in graph.astream(initial_state):
                current_node = event.get("current_node", "unknown")
                actions = event.get("actions_taken", [])
                thoughts = event.get("thoughts", [])
                
                click.echo(f"Node: {current_node}")
                if actions:
                    click.echo(f"Actions: {actions[-1] if actions else 'None'}")
                if thoughts:
                    click.echo(f"Thought: {thoughts[-1] if thoughts else 'None'}")
                
                if verbose:
                    click.echo(f"Full state: {json.dumps(event, indent=2, default=str)}")
                
                click.echo("-" * 30)
        else:
            # Synchronous execution
            click.echo("Executing agent...")
            
            result = await graph.ainvoke(initial_state)
            
            # Display results
            click.echo("\n" + "=" * 50)
            click.echo("EXECUTION RESULTS")
            click.echo("=" * 50)
            
            click.echo(f"Query: {result.get('user_query', 'N/A')}")
            click.echo(f"Intent: {result.get('intent', 'N/A')}")
            click.echo(f"Generated SQL: {result.get('generated_sql', 'N/A')}")
            click.echo(f"SQL Explanation: {result.get('sql_explanation', 'N/A')}")
            click.echo(f"Execution Error: {result.get('execution_error', 'None')}")
            click.echo(f"Iterations: {result.get('iteration_count', 0)}")
            click.echo(f"SQL Confidence: {result.get('sql_confidence', 0.0)}")
            
            if result.get("execution_results"):
                click.echo(f"Results: {len(result.get('execution_results', []))} rows")
                
                if verbose:
                    click.echo("\nFirst few results:")
                    for i, row in enumerate(result.get('execution_results', [])[:5]):
                        click.echo(f"  Row {i+1}: {row}")
            
            if verbose:
                click.echo("\n" + "=" * 50)
                click.echo("DETAILED AGENT TRACE")
                click.echo("=" * 50)
                
                thoughts = result.get("thoughts", [])
                actions = result.get("actions_taken", [])
                observations = result.get("observations", [])
                
                click.echo(f"Thoughts ({len(thoughts)}):")
                for i, thought in enumerate(thoughts):
                    click.echo(f"  {i+1}. {thought}")
                
                click.echo(f"\nActions ({len(actions)}):")
                for i, action in enumerate(actions):
                    click.echo(f"  {i+1}. {action}")
                
                click.echo(f"\nObservations ({len(observations)}):")
                for i, observation in enumerate(observations):
                    click.echo(f"  {i+1}. {observation}")
                
                click.echo(f"\nSchema Retrieved: {len(result.get('retrieved_schema', []))}")
                click.echo(f"Tables: {result.get('relevant_tables', [])}")
                click.echo(f"Columns: {len(result.get('relevant_columns', []))}")
                click.echo(f"Relationships: {len(result.get('table_relationships', []))}")
                
                if result.get("start_time") and result.get("end_time"):
                    duration = result.get("end_time") - result.get("start_time")
                    click.echo(f"Total execution time: {duration:.2f} seconds")
        
        click.echo("\n✓ Agent test completed successfully")
        
    except Exception as e:
        click.echo(f"✗ Error during agent test: {str(e)}")
        if verbose:
            import traceback
            click.echo(traceback.format_exc())


@click.command()
@click.option(
    "--format",
    "-f",
    default="text",
    type=click.Choice(["text", "json", "mermaid"]),
    help="Output format"
)
def visualize_graph(format: str):
    """Visualize the LangGraph agent structure."""
    
    try:
        graph = create_sens_agent_graph()
        
        if format == "text":
            click.echo("LangGraph Agent Structure:")
            click.echo("=" * 30)
            
            nodes = [
                "analyze_intent",
                "retrieve_schema",
                "generate_sql",
                "validate_sql",
                "execute_sql",
                "reflect_and_improve",
                "increment_iteration",
                "finalize_response"
            ]
            
            edges = [
                ("analyze_intent", "retrieve_schema"),
                ("retrieve_schema", "generate_sql"),
                ("generate_sql", "validate_sql"),
                ("validate_sql", "execute_sql"),
                ("execute_sql", "reflect_and_improve"),
                ("reflect_and_improve", "increment_iteration"),
                ("reflect_and_improve", "finalize_response"),
                ("increment_iteration", "generate_sql")
            ]
            
            click.echo("Nodes:")
            for node in nodes:
                click.echo(f"  - {node}")
            
            click.echo("\nEdges:")
            for from_node, to_node in edges:
                click.echo(f"  {from_node} -> {to_node}")
        
        elif format == "json":
            structure = {
                "nodes": [
                    {"id": "analyze_intent", "label": "Analyze Intent"},
                    {"id": "retrieve_schema", "label": "Retrieve Schema"},
                    {"id": "generate_sql", "label": "Generate SQL"},
                    {"id": "validate_sql", "label": "Validate SQL"},
                    {"id": "execute_sql", "label": "Execute SQL"},
                    {"id": "reflect_and_improve", "label": "Reflect & Improve"},
                    {"id": "increment_iteration", "label": "Increment Iteration"},
                    {"id": "finalize_response", "label": "Finalize Response"}
                ],
                "edges": [
                    {"from": "analyze_intent", "to": "retrieve_schema"},
                    {"from": "retrieve_schema", "to": "generate_sql"},
                    {"from": "generate_sql", "to": "validate_sql"},
                    {"from": "validate_sql", "to": "execute_sql", "condition": "valid"},
                    {"from": "validate_sql", "to": "reflect_and_improve", "condition": "invalid"},
                    {"from": "execute_sql", "to": "reflect_and_improve"},
                    {"from": "reflect_and_improve", "to": "increment_iteration", "condition": "needs_refinement"},
                    {"from": "reflect_and_improve", "to": "finalize_response", "condition": "done"},
                    {"from": "increment_iteration", "to": "generate_sql"}
                ]
            }
            
            click.echo(json.dumps(structure, indent=2))
        
        elif format == "mermaid":
            click.echo("```mermaid")
            click.echo("graph TD")
            click.echo("    A[Analyze Intent] --> B[Retrieve Schema]")
            click.echo("    B --> C[Generate SQL]")
            click.echo("    C --> D[Validate SQL]")
            click.echo("    D -->|Valid| E[Execute SQL]")
            click.echo("    D -->|Invalid| F[Reflect & Improve]")
            click.echo("    E --> F")
            click.echo("    F -->|Needs Refinement| G[Increment Iteration]")
            click.echo("    F -->|Done| H[Finalize Response]")
            click.echo("    G --> C")
            click.echo("```")
        
        click.echo("\n✓ Graph visualization completed")
        
    except Exception as e:
        click.echo(f"✗ Error visualizing graph: {str(e)}")


# Click needs sync functions, so wrap the async function
def sync_test_langgraph_agent(query: str, max_iterations: int, verbose: bool, stream: bool):
    """Synchronous wrapper for the async test function."""
    asyncio.run(test_langgraph_agent(query, max_iterations, verbose, stream))

# Create the sync version of the command
test_langgraph_agent.callback = sync_test_langgraph_agent