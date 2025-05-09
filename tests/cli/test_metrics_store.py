import tempfile
from pathlib import Path

from sens.cli.metrics_store import MetricsStore


def test_metrics_store_basic(tmp_path):
    metrics_path = tmp_path / "metrics.json"
    store = MetricsStore(path=metrics_path)

    # Initial state
    summary = store.get_summary()
    assert summary["total_commands"] == 0
    assert summary["errors"] == 0
    assert summary["commands"] == {}

    # Record commands
    store.record_command("foo")
    store.record_command("foo")
    store.record_command("bar")
    store.record_error()
    store.record_error()

    summary = store.get_summary()
    assert summary["total_commands"] == 3
    assert summary["errors"] == 2
    assert summary["commands"]["foo"] == 2
    assert summary["commands"]["bar"] == 1
