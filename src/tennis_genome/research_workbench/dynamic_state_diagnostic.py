from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import groupby
from typing import Literal

from pydantic import model_validator

from tennis_genome.data.canonical import HistoricalMatch
from tennis_genome.ratings.dynamic_serve_return import (
    walk_forward_dynamic_serve_return,
)

from .contracts import WorkbenchRecord
from .dynamic_state_development import (
    DynamicStateDevelopmentSpec,
    DynamicStatePredictionRow,
    run_dynamic_state_development_comparison,
)

DiagnosticDimension = Literal[
    "PAIR_MAX_LAYOFF_DAYS",
    "PAIR_MIN_PRIOR_POINT_DEPTH",
    "PAIR_MAX_SERVE_LOGIT_SD",
]

LAYOFF_BUCKETS = (
    "DEBUT_OR_NO_PRIOR",
    "0_7",
    "8_30",
    "31_90",
    "91_180",
    "181_PLUS",
)
PRIOR_POINT_BUCKETS = (
    "0",
    "1_499",
    "500_1999",
    "2000_4999",
    "5000_PLUS",
)
UNCERTAINTY_BUCKETS = (
    "LE_0_35",
    "GT_0_35_LE_0_50",
    "GT_0_50_LE_0_75",
    "GT_0_75",
)


class DynamicStateFailureDiagnosticSpec(WorkbenchRecord):
    """Predeclared descriptive decomposition of an existing development result."""

    diagnostic_id: str = "DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001"
    development_spec: DynamicStateDevelopmentSpec

    @model_validator(mode="after")
    def _fixed_scope(self) -> DynamicStateFailureDiagnosticSpec:
        if self.development_spec.experiment_id != "DYNAMIC-STATE-DEVELOPMENT-001":
            raise ValueError("diagnostic must reference DYNAMIC-STATE-DEVELOPMENT-001")
        return self


class DynamicStateDiagnosticStratum(WorkbenchRecord):
    dimension: DiagnosticDimension
    bucket: str
    n: int
    fixed_brier: float
    dynamic_brier: float
    brier_improvement: float
    fixed_log_loss: float
    dynamic_log_loss: float
    log_loss_improvement: float


class DynamicStateFailureDiagnosticReport(WorkbenchRecord):
    diagnostic_id: str
    diagnostic_spec_sha256: str
    development_report_sha256: str
    tour: str
    n_predictions: int
    layoff_buckets: tuple[str, ...] = LAYOFF_BUCKETS
    prior_point_buckets: tuple[str, ...] = PRIOR_POINT_BUCKETS
    uncertainty_buckets: tuple[str, ...] = UNCERTAINTY_BUCKETS
    strata: tuple[DynamicStateDiagnosticStratum, ...]
    interpretation_boundary: Literal["DESCRIPTIVE_ONLY_NO_PARAMETER_SELECTION"] = (
        "DESCRIPTIVE_ONLY_NO_PARAMETER_SELECTION"
    )


@dataclass(frozen=True)
class _DiagnosticFeatures:
    max_layoff_days: int | None
    min_prior_point_depth: int
    max_serve_logit_sd: float


def _eligible(
    matches: list[HistoricalMatch],
    *,
    spec: DynamicStateDevelopmentSpec,
) -> list[HistoricalMatch]:
    return sorted(
        (
            match
            for match in matches
            if match.pre_match.tour == spec.tour
            and not match.outcome.walkover
            and (not spec.exclude_retirements or not match.outcome.retirement)
        ),
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )


def _pair_layoffs(matches: list[HistoricalMatch]) -> dict[str, int | None]:
    """Return pair maximum layoff using prior dates only.

    If either player has no prior eligible source date, the pair receives None so debut
    rows cannot be mixed into a finite layoff bucket. Same-day matches all see the same
    last prior date.
    """

    last_date: dict[str, date] = {}
    result: dict[str, int | None] = {}

    for event_date, grouped in groupby(
        matches,
        key=lambda match: match.pre_match.event_date,
    ):
        day_matches = list(grouped)
        for match in day_matches:
            state = match.pre_match
            previous_a = last_date.get(state.player_a_id)
            previous_b = last_date.get(state.player_b_id)
            if previous_a is None or previous_b is None:
                result[match.match_id] = None
            else:
                result[match.match_id] = max(
                    (event_date - previous_a).days,
                    (event_date - previous_b).days,
                )
        for match in day_matches:
            last_date[match.pre_match.player_a_id] = event_date
            last_date[match.pre_match.player_b_id] = event_date

    return result


def _snapshot_features(
    matches: list[HistoricalMatch],
    *,
    spec: DynamicStateDevelopmentSpec,
) -> dict[str, _DiagnosticFeatures]:
    snapshots = walk_forward_dynamic_serve_return(
        matches,
        config=spec.dynamic_config(),
        exclude_retirements=False,
    )
    layoffs = _pair_layoffs(matches)
    result: dict[str, _DiagnosticFeatures] = {}
    for snapshot in snapshots:
        depth_a = snapshot.prior_serve_points_a + snapshot.prior_return_points_a
        depth_b = snapshot.prior_serve_points_b + snapshot.prior_return_points_b
        result[snapshot.match_id] = _DiagnosticFeatures(
            max_layoff_days=layoffs[snapshot.match_id],
            min_prior_point_depth=min(depth_a, depth_b),
            max_serve_logit_sd=max(
                snapshot.a_serve_logit_sd,
                snapshot.b_serve_logit_sd,
            ),
        )
    return result


def _layoff_bucket(value: int | None) -> str:
    if value is None:
        return "DEBUT_OR_NO_PRIOR"
    if value <= 7:
        return "0_7"
    if value <= 30:
        return "8_30"
    if value <= 90:
        return "31_90"
    if value <= 180:
        return "91_180"
    return "181_PLUS"


def _prior_point_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value < 500:
        return "1_499"
    if value < 2000:
        return "500_1999"
    if value < 5000:
        return "2000_4999"
    return "5000_PLUS"


def _uncertainty_bucket(value: float) -> str:
    if value <= 0.35:
        return "LE_0_35"
    if value <= 0.50:
        return "GT_0_35_LE_0_50"
    if value <= 0.75:
        return "GT_0_50_LE_0_75"
    return "GT_0_75"


def _mean(values: list[float]) -> float:
    if not values:
        raise ValueError("cannot summarize an empty diagnostic stratum")
    return sum(values) / len(values)


def _summarize(
    *,
    dimension: DiagnosticDimension,
    bucket_order: tuple[str, ...],
    predictions: tuple[DynamicStatePredictionRow, ...],
    features: dict[str, _DiagnosticFeatures],
    bucket_for_match,
) -> list[DynamicStateDiagnosticStratum]:
    grouped: dict[str, list[DynamicStatePredictionRow]] = {
        bucket: [] for bucket in bucket_order
    }
    for row in predictions:
        feature = features.get(row.match_id)
        if feature is None:
            raise ValueError(f"diagnostic feature missing for prediction {row.match_id}")
        bucket = bucket_for_match(feature)
        if bucket not in grouped:
            raise AssertionError(f"unexpected diagnostic bucket: {bucket}")
        grouped[bucket].append(row)

    summaries: list[DynamicStateDiagnosticStratum] = []
    for bucket in bucket_order:
        rows = grouped[bucket]
        if not rows:
            continue
        fixed_brier = _mean([row.fixed_brier_loss for row in rows])
        dynamic_brier = _mean([row.dynamic_brier_loss for row in rows])
        fixed_log = _mean([row.fixed_log_loss for row in rows])
        dynamic_log = _mean([row.dynamic_log_loss for row in rows])
        summaries.append(
            DynamicStateDiagnosticStratum(
                dimension=dimension,
                bucket=bucket,
                n=len(rows),
                fixed_brier=fixed_brier,
                dynamic_brier=dynamic_brier,
                brier_improvement=fixed_brier - dynamic_brier,
                fixed_log_loss=fixed_log,
                dynamic_log_loss=dynamic_log,
                log_loss_improvement=fixed_log - dynamic_log,
            )
        )
    return summaries


def run_dynamic_state_failure_diagnostic(
    matches: list[HistoricalMatch],
    spec: DynamicStateFailureDiagnosticSpec,
) -> DynamicStateFailureDiagnosticReport:
    """Describe where the registered dynamic candidate gains or loses.

    This function deliberately does not fit, tune, rank, or promote any new dynamic
    parameterization. The bins are fixed in code before the diagnostic result.
    """

    development = run_dynamic_state_development_comparison(
        matches,
        spec.development_spec,
    )
    eligible = _eligible(matches, spec=spec.development_spec)
    features = _snapshot_features(eligible, spec=spec.development_spec)

    strata: list[DynamicStateDiagnosticStratum] = []
    strata.extend(
        _summarize(
            dimension="PAIR_MAX_LAYOFF_DAYS",
            bucket_order=LAYOFF_BUCKETS,
            predictions=development.predictions,
            features=features,
            bucket_for_match=lambda feature: _layoff_bucket(feature.max_layoff_days),
        )
    )
    strata.extend(
        _summarize(
            dimension="PAIR_MIN_PRIOR_POINT_DEPTH",
            bucket_order=PRIOR_POINT_BUCKETS,
            predictions=development.predictions,
            features=features,
            bucket_for_match=lambda feature: _prior_point_bucket(
                feature.min_prior_point_depth
            ),
        )
    )
    strata.extend(
        _summarize(
            dimension="PAIR_MAX_SERVE_LOGIT_SD",
            bucket_order=UNCERTAINTY_BUCKETS,
            predictions=development.predictions,
            features=features,
            bucket_for_match=lambda feature: _uncertainty_bucket(
                feature.max_serve_logit_sd
            ),
        )
    )

    return DynamicStateFailureDiagnosticReport(
        diagnostic_id=spec.diagnostic_id,
        diagnostic_spec_sha256=spec.semantic_sha256,
        development_report_sha256=development.semantic_sha256,
        tour=spec.development_spec.tour,
        n_predictions=development.n_predictions,
        strata=tuple(strata),
    )
