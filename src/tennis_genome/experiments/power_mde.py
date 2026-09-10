from __future__ import annotations

import argparse
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, cast

import numpy as np
from scipy.special import expit
from scipy.stats import norm

from tennis_genome.experiments.market_edge import SignalName, Tour
from tennis_genome.experiments.market_edge_inputs import (
    ClosingMarketRow,
    SignalValue,
    load_closing_market_rows,
    load_genome_values,
    load_match_years,
    load_profile_gap_values,
)

_EXPERIMENT_ID = "POWER-MDE-001"
_DEVELOPMENT_END_YEAR = 2025
_MIN_PRIOR_ROWS = 1000
_FAMILY_ALPHA = 0.05
_FAMILY_SIZE = 4
_PLANNING_ALPHA = _FAMILY_ALPHA / _FAMILY_SIZE
_LOGIT_CLIP = 1e-6
_CONDITION_NUMBER_LIMIT = 1e12
_POWER_TARGETS = (0.80, 0.90)
_BETA_GRID = (0.02, 0.05, 0.10, 0.15, 0.20)
_REFERENCE_MARKET_PROBABILITIES = (0.50, 0.65, 0.80)


@dataclass(frozen=True)
class PowerMdeRow:
    match_id: str
    tour: Tour
    year: int
    market_probability_a: float
    signal: float

    def __post_init__(self) -> None:
        if not self.match_id:
            raise ValueError("match_id must be non-empty")
        if self.tour not in {"ATP", "WTA"}:
            raise ValueError("tour must be ATP or WTA")
        if self.year < 1900 or self.year > _DEVELOPMENT_END_YEAR:
            raise ValueError("POWER-MDE-001 is frozen through 2025")
        if not math.isfinite(self.market_probability_a):
            raise ValueError("market_probability_a must be finite")
        if not 0.0 < self.market_probability_a < 1.0:
            raise ValueError("market_probability_a must be in (0, 1)")
        if not math.isfinite(self.signal):
            raise ValueError("signal must be finite")


@dataclass(frozen=True)
class PowerGridPoint:
    beta_abs: float
    approximate_two_sided_power: float


@dataclass(frozen=True)
class ProbabilityShift:
    market_probability: float
    shift_at_mde_80: float
    shift_at_mde_90: float


@dataclass(frozen=True)
class YearPowerPlan:
    evaluation_year: int
    training_n: int
    evaluation_n: int
    identifiable: bool
    signal_mean_train: float
    signal_sd_train: float
    market_logit_signal_correlation: float | None
    information_condition_number: float | None
    beta_se_null: float | None
    mde_beta_80: float | None
    mde_beta_90: float | None
    power_grid: tuple[PowerGridPoint, ...]
    probability_shifts: tuple[ProbabilityShift, ...]
    non_identifiable_reason: str | None


@dataclass(frozen=True)
class ClaimPowerReport:
    experiment_id: str
    tour: Tour
    signal_name: SignalName
    matched_rows: int
    min_prior_rows: int
    family_alpha: float
    family_size: int
    conservative_planning_alpha: float
    logit_clip: float
    condition_number_limit: float
    first_planned_evaluation_year: int
    last_planned_evaluation_year: int
    identifiable_year_count: int
    year_plans: tuple[YearPowerPlan, ...]


@dataclass(frozen=True)
class PowerMdeArtifact:
    experiment_id: str
    outcome_blind: bool
    method: str
    family_alpha: float
    family_size: int
    conservative_planning_alpha: float
    beta_grid: tuple[float, ...]
    reference_market_probabilities: tuple[float, ...]
    input_sha256: dict[str, str]
    claims: tuple[ClaimPowerReport, ...]
    artifact_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _logit(probability: float) -> float:
    clipped = min(max(float(probability), _LOGIT_CLIP), 1.0 - _LOGIT_CLIP)
    return math.log(clipped / (1.0 - clipped))


def _sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _two_sided_normal_power(*, beta_abs: float, standard_error: float) -> float:
    if beta_abs < 0.0 or not math.isfinite(beta_abs):
        raise ValueError("beta_abs must be finite and non-negative")
    if standard_error <= 0.0 or not math.isfinite(standard_error):
        raise ValueError("standard_error must be finite and positive")
    critical = float(norm.ppf(1.0 - _PLANNING_ALPHA / 2.0))
    noncentrality = beta_abs / standard_error
    upper = 1.0 - float(norm.cdf(critical - noncentrality))
    lower = float(norm.cdf(-critical - noncentrality))
    return min(max(upper + lower, 0.0), 1.0)


def _mde_beta(*, standard_error: float, target_power: float) -> float:
    if not 0.0 < target_power < 1.0:
        raise ValueError("target_power must be in (0, 1)")
    critical = float(norm.ppf(1.0 - _PLANNING_ALPHA / 2.0))
    power_quantile = float(norm.ppf(target_power))
    return (critical + power_quantile) * standard_error


def _probability_shift(*, probability: float, beta: float) -> float:
    return float(expit(_logit(probability) + beta) - probability)


def _correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    if left.size < 2 or right.size < 2:
        return None
    left_sd = float(np.std(left, ddof=0))
    right_sd = float(np.std(right, ddof=0))
    if left_sd <= 0.0 or right_sd <= 0.0:
        return None
    value = float(np.corrcoef(left, right)[0, 1])
    return value if math.isfinite(value) else None


def _non_identifiable_plan(
    *,
    evaluation_year: int,
    training_n: int,
    evaluation_n: int,
    signal_mean: float,
    signal_sd: float,
    correlation: float | None,
    condition_number: float | None,
    reason: str,
) -> YearPowerPlan:
    return YearPowerPlan(
        evaluation_year=evaluation_year,
        training_n=training_n,
        evaluation_n=evaluation_n,
        identifiable=False,
        signal_mean_train=signal_mean,
        signal_sd_train=signal_sd,
        market_logit_signal_correlation=correlation,
        information_condition_number=condition_number,
        beta_se_null=None,
        mde_beta_80=None,
        mde_beta_90=None,
        power_grid=(),
        probability_shifts=(),
        non_identifiable_reason=reason,
    )


def _year_power_plan(
    *,
    train: list[PowerMdeRow],
    evaluation_n: int,
    evaluation_year: int,
) -> YearPowerPlan:
    signals = np.asarray([row.signal for row in train], dtype=float)
    signal_mean = float(np.mean(signals))
    signal_sd = float(np.std(signals, ddof=0))
    market_logits = np.asarray(
        [_logit(row.market_probability_a) for row in train],
        dtype=float,
    )
    if not math.isfinite(signal_sd) or signal_sd <= 0.0:
        return _non_identifiable_plan(
            evaluation_year=evaluation_year,
            training_n=len(train),
            evaluation_n=evaluation_n,
            signal_mean=signal_mean,
            signal_sd=signal_sd,
            correlation=None,
            condition_number=None,
            reason="training signal has zero or non-finite standard deviation",
        )

    z_signal = (signals - signal_mean) / signal_sd
    correlation = _correlation(market_logits, z_signal)
    design = np.column_stack(
        [
            np.ones(len(train), dtype=float),
            market_logits,
            z_signal,
        ]
    )
    market_probabilities = np.asarray(
        [row.market_probability_a for row in train],
        dtype=float,
    )
    weights = market_probabilities * (1.0 - market_probabilities)
    information = design.T @ (weights[:, None] * design)
    rank = int(np.linalg.matrix_rank(information))
    condition_number = float(np.linalg.cond(information))
    if rank < design.shape[1]:
        return _non_identifiable_plan(
            evaluation_year=evaluation_year,
            training_n=len(train),
            evaluation_n=evaluation_n,
            signal_mean=signal_mean,
            signal_sd=signal_sd,
            correlation=correlation,
            condition_number=condition_number,
            reason="null Fisher information matrix is rank deficient",
        )
    if not math.isfinite(condition_number) or condition_number >= _CONDITION_NUMBER_LIMIT:
        return _non_identifiable_plan(
            evaluation_year=evaluation_year,
            training_n=len(train),
            evaluation_n=evaluation_n,
            signal_mean=signal_mean,
            signal_sd=signal_sd,
            correlation=correlation,
            condition_number=condition_number,
            reason="null Fisher information matrix is ill conditioned",
        )

    covariance = np.linalg.inv(information)
    beta_variance = float(covariance[2, 2])
    if not math.isfinite(beta_variance) or beta_variance <= 0.0:
        return _non_identifiable_plan(
            evaluation_year=evaluation_year,
            training_n=len(train),
            evaluation_n=evaluation_n,
            signal_mean=signal_mean,
            signal_sd=signal_sd,
            correlation=correlation,
            condition_number=condition_number,
            reason="beta variance is non-positive or non-finite",
        )

    beta_se = math.sqrt(beta_variance)
    mde_80 = _mde_beta(standard_error=beta_se, target_power=_POWER_TARGETS[0])
    mde_90 = _mde_beta(standard_error=beta_se, target_power=_POWER_TARGETS[1])
    grid = tuple(
        PowerGridPoint(
            beta_abs=beta,
            approximate_two_sided_power=_two_sided_normal_power(
                beta_abs=beta,
                standard_error=beta_se,
            ),
        )
        for beta in _BETA_GRID
    )
    shifts = tuple(
        ProbabilityShift(
            market_probability=probability,
            shift_at_mde_80=_probability_shift(
                probability=probability,
                beta=mde_80,
            ),
            shift_at_mde_90=_probability_shift(
                probability=probability,
                beta=mde_90,
            ),
        )
        for probability in _REFERENCE_MARKET_PROBABILITIES
    )
    return YearPowerPlan(
        evaluation_year=evaluation_year,
        training_n=len(train),
        evaluation_n=evaluation_n,
        identifiable=True,
        signal_mean_train=signal_mean,
        signal_sd_train=signal_sd,
        market_logit_signal_correlation=correlation,
        information_condition_number=condition_number,
        beta_se_null=beta_se,
        mde_beta_80=mde_80,
        mde_beta_90=mde_90,
        power_grid=grid,
        probability_shifts=shifts,
        non_identifiable_reason=None,
    )


def build_power_rows(
    *,
    close_rows: dict[str, ClosingMarketRow],
    signals: dict[str, SignalValue],
    years_by_match: dict[str, int],
    tour: Tour,
) -> list[PowerMdeRow]:
    shared = sorted(set(close_rows).intersection(signals, years_by_match))
    rows: list[PowerMdeRow] = []
    for match_id in shared:
        market = close_rows[match_id]
        if market.tour != tour:
            continue
        rows.append(
            PowerMdeRow(
                match_id=match_id,
                tour=tour,
                year=int(years_by_match[match_id]),
                market_probability_a=market.market_probability_a,
                signal=signals[match_id].signal,
            )
        )
    return sorted(rows, key=lambda row: (row.year, row.match_id))


def run_power_mde_claim(
    rows: list[PowerMdeRow],
    *,
    signal_name: SignalName,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> ClaimPowerReport:
    if signal_name not in {"profile_gap", "genome"}:
        raise ValueError("unsupported signal_name")
    if min_prior_rows <= 0:
        raise ValueError("min_prior_rows must be positive")
    if not rows:
        raise ValueError("rows must be non-empty")
    tours = {row.tour for row in rows}
    if len(tours) != 1:
        raise ValueError("one POWER-MDE claim must contain exactly one tour")
    match_ids = [row.match_id for row in rows]
    if len(match_ids) != len(set(match_ids)):
        raise ValueError("POWER-MDE rows contain duplicate match_id values")
    if any(row.year > _DEVELOPMENT_END_YEAR for row in rows):
        raise ValueError("POWER-MDE-001 is frozen through 2025")

    ordered = sorted(rows, key=lambda row: (row.year, row.match_id))
    plans: list[YearPowerPlan] = []
    for evaluation_year in sorted({row.year for row in ordered}):
        train = [row for row in ordered if row.year < evaluation_year]
        evaluation_n = sum(row.year == evaluation_year for row in ordered)
        if len(train) < min_prior_rows or evaluation_n <= 0:
            continue
        plans.append(
            _year_power_plan(
                train=train,
                evaluation_n=evaluation_n,
                evaluation_year=evaluation_year,
            )
        )
    if not plans:
        raise ValueError("no prospective evaluation year has enough earlier rows")
    tour = cast(Tour, next(iter(tours)))
    return ClaimPowerReport(
        experiment_id=_EXPERIMENT_ID,
        tour=tour,
        signal_name=signal_name,
        matched_rows=len(rows),
        min_prior_rows=min_prior_rows,
        family_alpha=_FAMILY_ALPHA,
        family_size=_FAMILY_SIZE,
        conservative_planning_alpha=_PLANNING_ALPHA,
        logit_clip=_LOGIT_CLIP,
        condition_number_limit=_CONDITION_NUMBER_LIMIT,
        first_planned_evaluation_year=min(plan.evaluation_year for plan in plans),
        last_planned_evaluation_year=max(plan.evaluation_year for plan in plans),
        identifiable_year_count=sum(plan.identifiable for plan in plans),
        year_plans=tuple(plans),
    )


def _load_signal_values(
    path: str | Path,
    *,
    tour: Tour,
    signal_name: SignalName,
) -> dict[str, SignalValue]:
    if signal_name == "profile_gap":
        return load_profile_gap_values(path, tour=tour)
    return load_genome_values(path, tour=tour)


def _claim_from_files(
    *,
    close_rows: dict[str, ClosingMarketRow],
    years_by_match: dict[str, int],
    signal_path: str | Path,
    tour: Tour,
    signal_name: SignalName,
    min_prior_rows: int,
) -> ClaimPowerReport:
    signals = _load_signal_values(signal_path, tour=tour, signal_name=signal_name)
    rows = build_power_rows(
        close_rows=close_rows,
        signals=signals,
        years_by_match=years_by_match,
        tour=tour,
    )
    return run_power_mde_claim(
        rows,
        signal_name=signal_name,
        min_prior_rows=min_prior_rows,
    )


def build_power_mde_artifact(
    *,
    market_hist_records: str | Path,
    pre_match: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = _MIN_PRIOR_ROWS,
) -> PowerMdeArtifact:
    """Build the four-claim planning artifact without opening real outcomes."""

    paths = {
        "market_hist_records": Path(market_hist_records),
        "pre_match": Path(pre_match),
        "profile_gap_atp": Path(profile_gap_atp),
        "profile_gap_wta": Path(profile_gap_wta),
        "genome_atp": Path(genome_atp),
        "genome_wta": Path(genome_wta),
    }
    close_rows = load_closing_market_rows(paths["market_hist_records"])
    years_by_match = load_match_years(paths["pre_match"])
    claims = (
        _claim_from_files(
            close_rows=close_rows,
            years_by_match=years_by_match,
            signal_path=paths["profile_gap_atp"],
            tour="ATP",
            signal_name="profile_gap",
            min_prior_rows=min_prior_rows,
        ),
        _claim_from_files(
            close_rows=close_rows,
            years_by_match=years_by_match,
            signal_path=paths["profile_gap_wta"],
            tour="WTA",
            signal_name="profile_gap",
            min_prior_rows=min_prior_rows,
        ),
        _claim_from_files(
            close_rows=close_rows,
            years_by_match=years_by_match,
            signal_path=paths["genome_atp"],
            tour="ATP",
            signal_name="genome",
            min_prior_rows=min_prior_rows,
        ),
        _claim_from_files(
            close_rows=close_rows,
            years_by_match=years_by_match,
            signal_path=paths["genome_wta"],
            tour="WTA",
            signal_name="genome",
            min_prior_rows=min_prior_rows,
        ),
    )
    input_hashes = {name: _sha256_file(path) for name, path in sorted(paths.items())}
    unsigned = {
        "experiment_id": _EXPERIMENT_ID,
        "outcome_blind": True,
        "method": "null_fisher_information_wald_planning_v1",
        "family_alpha": _FAMILY_ALPHA,
        "family_size": _FAMILY_SIZE,
        "conservative_planning_alpha": _PLANNING_ALPHA,
        "beta_grid": _BETA_GRID,
        "reference_market_probabilities": _REFERENCE_MARKET_PROBABILITIES,
        "input_sha256": input_hashes,
        "claims": [asdict(claim) for claim in claims],
    }
    artifact_hash = hashlib.sha256(_canonical_json_bytes(unsigned)).hexdigest()
    return PowerMdeArtifact(
        experiment_id=_EXPERIMENT_ID,
        outcome_blind=True,
        method="null_fisher_information_wald_planning_v1",
        family_alpha=_FAMILY_ALPHA,
        family_size=_FAMILY_SIZE,
        conservative_planning_alpha=_PLANNING_ALPHA,
        beta_grid=_BETA_GRID,
        reference_market_probabilities=_REFERENCE_MARKET_PROBABILITIES,
        input_sha256=input_hashes,
        claims=claims,
        artifact_sha256=artifact_hash,
    )


def write_power_mde_artifact(artifact: PowerMdeArtifact, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run outcome-blind POWER-MDE-001 for the four MARKET-EDGE claims"
    )
    parser.add_argument("--market-hist-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--min-prior-rows", type=int, default=_MIN_PRIOR_ROWS)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_power_mde_artifact(
        market_hist_records=args.market_hist_records,
        pre_match=args.pre_match,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
        min_prior_rows=args.min_prior_rows,
    )
    write_power_mde_artifact(artifact, args.output)
    print(json.dumps(artifact.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
