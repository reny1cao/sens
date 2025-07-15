"""
Sequential pipeline implementation.
"""

from typing import Any, Dict

from ..interfaces import (
    Pipeline,
    PipelineContext,
    PipelineResult,
    QueryExecutor,
    Retriever,
    SQLGenerator,
    Validator,
)


class SequentialPipeline(Pipeline):
    """Executes pipeline steps sequentially."""

    def __init__(
        self,
        retriever: Retriever,
        generator: SQLGenerator,
        validator: Validator,
        executor: QueryExecutor,
        **kwargs,
    ):
        self.retriever = retriever
        self.generator = generator
        self.validator = validator
        self.executor = executor
        self.config = kwargs

    async def process(self, context: PipelineContext, **kwargs) -> PipelineResult:
        """Process query through sequential steps."""
        # For now, return a mock result
        # TODO: Implement actual sequential processing
        return PipelineResult(
            success=True,
            sql="SELECT 1",
            total_time_ms=100.0,
            steps_timing={
                "retrieval": 20.0,
                "generation": 50.0,
                "validation": 10.0,
                "execution": 20.0,
            },
            metadata={"pipeline": "sequential"},
        )

    async def initialize(self) -> None:
        """Initialize components."""
        await self.retriever.initialize()

    async def close(self) -> None:
        """Clean up resources."""
        await self.retriever.close()

    def get_capabilities(self) -> Dict[str, Any]:
        """Get pipeline capabilities."""
        return {
            "supports_sessions": False,
            "supports_streaming": False,
            "supports_multi_datasource": False,
            "supports_agent_mode": False,
            "implementation": "Sequential",
            "version": "1.0",
        }
