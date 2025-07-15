"""
Evaluation module for SENS.

This module provides evaluation utilities for testing SENS against
various benchmarks and datasets.
"""

from sens.evaluation.bird_critic import (
    BirdCriticEvaluator,
    BirdCriticTask,
    EvaluationResult,
)
from sens.evaluation.bird_db_setup import BirdDatabaseSetup

__all__ = [
    "BirdCriticEvaluator",
    "BirdCriticTask",
    "EvaluationResult",
    "BirdDatabaseSetup",
]
