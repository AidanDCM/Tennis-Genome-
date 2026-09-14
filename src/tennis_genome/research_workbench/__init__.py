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
from .constitution import (
    DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    REQUIRED_TENNIS_RESEARCH_INVARIANTS,
    ResearchAuthority,
    ResearchConstitution,
)
from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .dynamic_state_benchmark import (
    DynamicStateSeedResult,
    DynamicStateShiftReport,
    DynamicStateShiftSpec,
    run_dynamic_state_shift_benchmark,
)
from .dynamic_state_development import (
    DynamicStateDevelopmentReport,
    DynamicStateDevelopmentSpec,
    DynamicStatePredictionRow,
    DynamicStateYearScore,
    run_dynamic_state_development_comparison,
)
from .dynamic_state_runner import (
    DynamicStateDevelopmentEvidence,
    build_dynamic_state_development_evidence,
    run_from_canonical_files,
)
from .evaluation import EvaluationResult, evaluate_probabilities
from .exposure import ExposureGraph, ExposureKind, ExposureRecord
from .history import (
    ResearchHistoryEvent,
    ResearchLifecycleAudit,
    ResearchLifecycleLedger,
)
from .lineage import (
    CanonicalEvaluationBinding,
    ChronologySemantics,
    CodeFingerprint,
    DatasetFingerprint,
    ProcedureSearchFamily,
    build_canonical_evaluation_binding,
    fingerprint_code_components,
    fingerprint_match_population,
)
from .null_calibration import (
    NullCalibrationReport,
    NullCalibrationSpec,
    NullSeedResult,
    run_null_calibration_campaign,
)
from .protected import (
    ProtectedDatasetReference,
    ProtectedDataVault,
    ProtectedOpenAuthorization,
    ProtectedOpenReceipt,
    write_protected_dataset,
)
from .registry import ImmutableResearchRegistry
from .sackmann_availability import sackmann_research_availability_registry
from .synthetic import SyntheticWorld, interaction_world, miscalibration_world, null_world
from .synthetic_benchmark import SyntheticBenchmarkReport, run_synthetic_benchmark

__all__ = [
    "AvailabilityDecision",
    "CanonicalEvaluationBinding",
    "ChronologySemantics",
    "CodeFingerprint",
    "DEFAULT_TENNIS_RESEARCH_CONSTITUTION",
    "DatasetFingerprint",
    "DynamicStateDevelopmentEvidence",
    "DynamicStateDevelopmentReport",
    "DynamicStateDevelopmentSpec",
    "DynamicStatePredictionRow",
    "DynamicStateSeedResult",
    "DynamicStateShiftReport",
    "DynamicStateShiftSpec",
    "DynamicStateYearScore",
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
    "NullCalibrationReport",
    "NullCalibrationSpec",
    "NullSeedResult",
    "ProcedureSearchFamily",
    "ProtectedDataVault",
    "ProtectedDatasetReference",
    "ProtectedOpenAuthorization",
    "ProtectedOpenReceipt",
    "REQUIRED_TENNIS_RESEARCH_INVARIANTS",
    "ReliabilityGrade",
    "ResearchAuthority",
    "ResearchConstitution",
    "ResearchHistoryEvent",
    "ResearchLifecycleAudit",
    "ResearchLifecycleLedger",
    "RevisionSemantics",
    "SyntheticBenchmarkReport",
    "SyntheticWorld",
    "T0Policy",
    "TargetBoundary",
    "TimestampSemantics",
    "WorkbenchRecord",
    "assert_features_available",
    "build_canonical_evaluation_binding",
    "build_dynamic_state_development_evidence",
    "evaluate_feature_availability",
    "evaluate_probabilities",
    "fingerprint_code_components",
    "fingerprint_match_population",
    "interaction_world",
    "miscalibration_world",
    "null_world",
    "run_dynamic_state_development_comparison",
    "run_dynamic_state_shift_benchmark",
    "run_from_canonical_files",
    "run_null_calibration_campaign",
    "run_synthetic_benchmark",
    "sackmann_research_availability_registry",
    "write_protected_dataset",
]
