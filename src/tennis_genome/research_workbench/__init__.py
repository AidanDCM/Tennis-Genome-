"""Bounded forecasting research workbench.

This package is intentionally separate from the frozen production predictor. It provides
contracts and research utilities for comparing complete forecasting procedures without
mutating TGE-Independent-v1.
"""

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .evaluation import EvaluationResult, evaluate_probabilities
from .exposure import ExposureGraph, ExposureKind, ExposureRecord
from .lineage import (
    CanonicalEvaluationBinding,
    CodeFingerprint,
    DatasetFingerprint,
    ProcedureSearchFamily,
    build_canonical_evaluation_binding,
    fingerprint_code_components,
    fingerprint_match_population,
)
from .registry import ImmutableResearchRegistry
from .protected import (
    ProtectedDataVault,
    ProtectedDatasetReference,
    ProtectedOpenAuthorization,
    ProtectedOpenReceipt,
    write_protected_dataset,
)
from .synthetic import SyntheticWorld, interaction_world, miscalibration_world, null_world
from .synthetic_benchmark import SyntheticBenchmarkReport, run_synthetic_benchmark

__all__ = [
    "CanonicalEvaluationBinding",
    "CodeFingerprint",
    "DatasetFingerprint",
    "EvaluationResult",
    "EvaluationSpec",
    "ExposureGraph",
    "ExposureKind",
    "ExposureRecord",
    "ForecastingProcedureSpec",
    "ImmutableResearchRegistry",
    "ProcedureSearchFamily",
    "ProtectedDataVault",
    "ProtectedDatasetReference",
    "ProtectedOpenAuthorization",
    "ProtectedOpenReceipt",
    "SyntheticBenchmarkReport",
    "SyntheticWorld",
    "WorkbenchRecord",
    "build_canonical_evaluation_binding",
    "evaluate_probabilities",
    "fingerprint_code_components",
    "fingerprint_match_population",
    "interaction_world",
    "miscalibration_world",
    "null_world",
    "run_synthetic_benchmark",
    "write_protected_dataset",
]
