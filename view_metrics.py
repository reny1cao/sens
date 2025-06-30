#!/usr/bin/env python3
"""Simple script to view BIRD-CRITIC test metrics in a formatted way."""

import glob
import json
from pathlib import Path


def view_metrics():
    """Display all available metrics files."""
    # Find all metrics files
    metrics_files = glob.glob("*metrics*.json") + glob.glob("test_env_validation")

    print("🔍 BIRD-CRITIC Test Metrics Summary")
    print("=" * 50)

    for file_path in sorted(metrics_files):
        print(f"\n📊 {file_path}")
        print("-" * 30)

        try:
            with open(file_path, "r") as f:
                data = json.load(f)

            if "total_tasks" in data:
                print(f"Tasks: {data['total_tasks']}")
                print(f"Success Rate: {data['success_rate']:.1%}")
                print(f"SQL Generation: {data['sql_generation_rate']:.1%}")
                print(f"Avg Time: {data['avg_execution_time_ms']:.1f}ms")

                if data.get("error_breakdown"):
                    print("Errors:", data["error_breakdown"])

                # Submission-ready metrics
                if "submission_ready" in data:
                    sub = data["submission_ready"]
                    print("🚀 Submission Ready:")
                    print(f"  - Execution Accuracy: {sub['execution_accuracy']:.3f}")
                    print(f"  - SQL Coverage: {sub['sql_generation_coverage']:.3f}")
                    print(f"  - Performance: {sub['performance_ms']:.1f}ms")
            else:
                print("Non-standard metrics format")

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

    print(f"\n📁 Available files: {len(metrics_files)}")
    print("\nTo analyze detailed results:")
    print("poetry run sens bird-critic analyze <results_file.json>")


if __name__ == "__main__":
    view_metrics()
