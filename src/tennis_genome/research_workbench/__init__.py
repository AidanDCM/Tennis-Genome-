"""Bounded forecasting research workbench.

This package is intentionally separate from the frozen production predictor. It provides
contracts and research utilities for comparing complete forecasting procedures without
mutating TGE-Independent-v1.
"""

from .availability import (
    AvailabilityDecision,
    FeatureAvailabilityContract,
    FeatureAvailabilityRegistry,
    FeatureObservation,
    ReliabilityGrade,
    RevisionSemantics,
    T0Policy,
    TargetBoundary,
    TimestampSemantics,
    assert_features_available,
    evaluate_feature_availability,
)
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
from .protected import (
    ProtectedDatasetReference,
    ProtectedDataVault,
    ProtectedOpenAuthorization,
    ProtectedOpenReceipt,
    write_protected_dataset,
)
from .registry import ImmutableResearchRegistry
from .synthetic import SyntheticWorld, interaction_world, miscalibration_world, null_world
from .synthetic_benchmark import SyntheticBenchmarkReport, run_synthetic_benchmark

__all__ = [
    "AvailabilityDecision",
    "CanonicalEvaluationBinding",
    "CodeFingerprint",
    "DatasetFingerprint",
    "EvaluationResult",
    "EvaluationSpec",
    "ExposureGraph",
    "ExposureKind",
    "ExposureRecord",
    "FeatureAvailabilityContract",
    "FeatureAvailabilityRegistry",
    "FeatureObservation",
    "ForecastingProcedureSpec",
    "ImmutableResearchRegistry",
    "ProcedureSearchFamily",
    "ProtectedDataVault",
    "ProtectedDatasetReference",
    "ProtectedOpenAuthorization",
    "ProtectedOpenReceipt",
    "ReliabilityGrade",
    "RevisionSemantics",
    "SyntheticBenchmarkReport",
    "SyntheticWorld",
    "T0Policy",
    "TargetBoundary",
    "TimestampSemantics",
    "WorkbenchRecord",
    "assert_features_available",
    "build_canonical_evaluation_binding",
    "evaluate_feature_availability",
    "evaluate_probabilities",
    "fingerprint_code_components",
    "fingerprint_match_population",
    "interaction_world",
    "miscalibration_world",
    "null_world",
    "run_synthetic_benchmark",
    "write_protected_dataset",
]
