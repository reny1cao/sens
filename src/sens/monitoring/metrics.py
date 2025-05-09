"""Performance monitoring and metrics tracking."""

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Dict, List, Optional

import structlog

log = structlog.get_logger()


@dataclass
class StepMetrics:
    """Metrics for a single pipeline step."""

    step_name: str
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    success: bool = False
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)


@dataclass
class PipelineMetrics:
    """Metrics for a complete pipeline execution."""

    conversation_id: str
    start_time: datetime = field(default_factory=lambda: datetime.now(UTC))
    end_time: Optional[datetime] = None
    total_duration_ms: Optional[float] = None
    steps: List[StepMetrics] = field(default_factory=list)
    success: bool = False
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def add_step(self, step: StepMetrics) -> None:
        """Add a step to the pipeline metrics."""
        self.steps.append(step)

    def complete(self, success: bool = True, error: Optional[str] = None) -> None:
        """Mark the pipeline as complete."""
        self.end_time = datetime.now(UTC)
        self.total_duration_ms = (
            self.end_time - self.start_time
        ).total_seconds() * 1000
        self.success = success
        self.error = error

        # Log completion metrics
        log.info(
            "pipeline_metrics",
            conversation_id=self.conversation_id,
            total_duration_ms=self.total_duration_ms,
            success=self.success,
            error=self.error,
            step_count=len(self.steps),
            steps=[
                {
                    "name": step.step_name,
                    "duration_ms": step.duration_ms,
                    "success": step.success,
                }
                for step in self.steps
            ],
            metadata=self.metadata,
        )

    def model_dump(self) -> Dict:
        """Convert the metrics to a dictionary representation."""
        return {
            "conversation_id": self.conversation_id,
            "total_duration_ms": self.total_duration_ms or 0.0,
            "success": self.success,
            "error": self.error,
            "step_count": len(self.steps),
            "steps": [
                {
                    "name": step.step_name,
                    "duration_ms": step.duration_ms or 0.0,
                    "success": step.success,
                    "error": step.error,
                    "metadata": step.metadata,
                }
                for step in self.steps
            ],
            "metadata": self.metadata,
        }


@contextmanager
def track_step(pipeline_metrics: PipelineMetrics, step_name: str):
    """Context manager for tracking a pipeline step.

    Args:
        pipeline_metrics: The pipeline metrics to add the step to
        step_name: Name of the step being tracked

    Example:
        ```python
        metrics = PipelineMetrics(conversation_id="123")
        with track_step(metrics, "schema_retrieval") as step:
            # Do work
            step.metadata["table_count"] = 5
        ```
    """
    step = StepMetrics(step_name=step_name)
    start_time = time.perf_counter()

    try:
        yield step
        step.success = True
    except Exception as e:
        step.success = False
        step.error = str(e)
        raise
    finally:
        end_time = time.perf_counter()
        step.end_time = datetime.now(UTC)
        step.duration_ms = (end_time - start_time) * 1000
        pipeline_metrics.add_step(step)

        # Log step completion
        log.info(
            "step_metrics",
            conversation_id=pipeline_metrics.conversation_id,
            step_name=step.step_name,
            duration_ms=step.duration_ms,
            success=step.success,
            error=step.error,
            metadata=step.metadata,
        )
