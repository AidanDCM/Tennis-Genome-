"""Bounded forecasting research workbench.

This package is intentionally separate from the frozen production predictor. It provides
contracts and research utilities for comparing complete forecasting procedures without
mutating TGE-Independent-v1.
"""

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .evaluation import EvaluationResult, evaluate_probabilities
from .exposure import ExposureGraph, ExposureKind, ExposureRecord
from .registry import ImmutableResearchRegistry
from .synthetic import SyntheticWorld, interaction_world, miscalibration_world, null_world
from .synthetic_benchmark import SyntheticBenchmarkReport, run_synthetic_benchmark

__all__ = [
    "EvaluationResult",
    "EvaluationSpec",
    "ExposureGraph",
    "ExposureKind",
    "ExposureRecord",
    "ForecastingProcedureSpec",
    "ImmutableResearchRegistry",
    "SyntheticBenchmarkReport",
    "SyntheticWorld",
    "WorkbenchRecord",
    "evaluate_probabilities",
    "interaction_world",
    "miscalibration_world",
    "null_world",
    "run_synthetic_benchmark",
]
