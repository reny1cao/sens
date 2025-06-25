"""
Centralized metrics collection utilities.
"""

import logging
import time
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Context variable for request-scoped metrics
_metrics_context: ContextVar[Optional["MetricsCollector"]] = ContextVar(
    "metrics_context", default=None
)


@dataclass
class MetricEvent:
    """Single metric event."""

    name: str
    value: Any
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects metrics for a single request/operation."""

    def __init__(self, operation_name: str):
        self.operation_name = operation_name
        self.start_time = time.time()
        self.events: List[MetricEvent] = []
        self.timings: Dict[str, float] = {}
        self.counters: Dict[str, int] = {}
        self.tags: Dict[str, str] = {}

    def add_tag(self, key: str, value: str) -> None:
        """Add a tag to all metrics."""
        self.tags[key] = value

    def record_timing(self, name: str, duration_ms: float) -> None:
        """Record a timing metric."""
        self.timings[name] = duration_ms
        self.events.append(
            MetricEvent(
                name=f"{self.operation_name}.{name}",
                value=duration_ms,
                timestamp=time.time(),
                tags={**self.tags, "metric_type": "timing"},
            )
        )

    def increment_counter(self, name: str, value: int = 1) -> None:
        """Increment a counter metric."""
        self.counters[name] = self.counters.get(name, 0) + value
        self.events.append(
            MetricEvent(
                name=f"{self.operation_name}.{name}",
                value=value,
                timestamp=time.time(),
                tags={**self.tags, "metric_type": "counter"},
            )
        )

    def record_event(
        self, name: str, value: Any, tags: Optional[Dict[str, str]] = None
    ) -> None:
        """Record a generic event."""
        event_tags = {**self.tags, "metric_type": "event"}
        if tags:
            event_tags.update(tags)

        self.events.append(
            MetricEvent(
                name=f"{self.operation_name}.{name}",
                value=value,
                timestamp=time.time(),
                tags=event_tags,
            )
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        total_time = time.time() - self.start_time

        return {
            "operation": self.operation_name,
            "total_time_ms": total_time * 1000,
            "timings": self.timings,
            "counters": self.counters,
            "tags": self.tags,
            "event_count": len(self.events),
        }

    @staticmethod
    def current() -> Optional["MetricsCollector"]:
        """Get the current metrics collector from context."""
        return _metrics_context.get()

    def __enter__(self):
        """Enter context manager."""
        self._token = _metrics_context.set(self)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        _metrics_context.reset(self._token)

        # Log summary on exit
        if logger.isEnabledFor(logging.INFO):
            summary = self.get_summary()
            logger.info(f"Metrics summary: {summary}")


def track_timing(name: str):
    """
    Decorator to track function execution time.

    Args:
        name: Metric name for the timing
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            collector = MetricsCollector.current()
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                if collector:
                    collector.record_timing(name, duration_ms)
                else:
                    logger.debug(f"{name} took {duration_ms:.2f}ms")

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            collector = MetricsCollector.current()
            start_time = time.time()

            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                if collector:
                    collector.record_timing(name, duration_ms)
                else:
                    logger.debug(f"{name} took {duration_ms:.2f}ms")

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def track_event(name: str, value_func: Optional[Callable] = None):
    """
    Decorator to track custom events.

    Args:
        name: Event name
        value_func: Optional function to extract value from result
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            collector = MetricsCollector.current()
            if collector:
                value = value_func(result) if value_func else 1
                collector.record_event(name, value)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            result = func(*args, **kwargs)

            collector = MetricsCollector.current()
            if collector:
                value = value_func(result) if value_func else 1
                collector.record_event(name, value)

            return result

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


class TimingContext:
    """Context manager for timing code blocks."""

    def __init__(self, name: str, collector: Optional[MetricsCollector] = None):
        self.name = name
        self.collector = collector or MetricsCollector.current()
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time and self.collector:
            duration_ms = (time.time() - self.start_time) * 1000
            self.collector.record_timing(self.name, duration_ms)
