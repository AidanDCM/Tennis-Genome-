from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet
from tennis_genome.experiments.family_lab import (
    CORE_FEATURES,
    FAMILY_FEATURES,
    _all_family_features,
    _fit_predict,
    _rows,
    _score,
)


@dataclass(frozen=True)
class YearDelta:
    year: int
    n: int
    add_one_brier_improvement: float
    add_one_log_loss_improvement: float
    ablation_brier_contribution: float
    ablation_log_loss_contribution: float


@dataclass(frozen=True)
class RecentFamilyResult:
    family: str
    recent_years: tuple[int, ...]
    n: int
    add_one_brier_improvement: float
    add_one_log_loss_improvement: float
    ablation_brier_contribution: float
    ablation_log_loss_contribution: float
    brier_winning_years: int
    log_loss_winning_years: int
    yearly: tuple[YearDelta, ...]


@dataclass(frozen=True)
class RecentFamilyDiagnostic:
    experiment_id: str
    recent_year_count: int
    recent_years: tuple[int, ...]
    min_train_matches: int
    families: tuple[RecentFamilyResult, ...]
    note: str


def run_recent_family_diagnostic(
    matches,
    *,
    min_train_matches: int = 1000,
    recent_year_count: int = 5,
    exclude_retirements: bool = True,
) -> RecentFamilyDiagnostic:
    """Report recent-block behavior without changing registered family definitions."""
    if min_train_matches <= 0:
        raise ValueError("min_train_matches must be positive")
    if recent_year_count <= 0:
        raise ValueError("recent_year_count must be positive")

    rows = _rows(matches, exclude_retirements=exclude_retirements)
    years = sorted({row.year for row in rows})
    eligible_years = [
        year
        for year in years
        if len([row for row in rows if row.year < year]) >= min_train_matches
        and any(row.year == year for row in rows)
    ]
    recent_years = tuple(eligible_years[-recent_year_count:])
    if not recent_years:
        raise ValueError("no chronological years are available for recent diagnostics")

    full_features = CORE_FEATURES + _all_family_features()
    family_yearly: dict[str, list[YearDelta]] = {
        family: [] for family in FAMILY_FEATURES
    }
    family_y: dict[str, list[bool]] = {family: [] for family in FAMILY_FEATURES}
    family_core_probs: dict[str, list[float]] = {
        family: [] for family in FAMILY_FEATURES
    }
    family_add_probs: dict[str, list[float]] = {
        family: [] for family in FAMILY_FEATURES
    }
    family_full_probs: dict[str, list[float]] = {
        family: [] for family in FAMILY_FEATURES
    }
    family_without_probs: dict[str, list[float]] = {
        family: [] for family in FAMILY_FEATURES
    }

    for test_year in recent_years:
        train = [row for row in rows if row.year < test_year]
        test = [row for row in rows if row.year == test_year]
        if len({row.outcome_a for row in train}) < 2:
            continue

        y_year = [row.outcome_a for row in test]
        core_probs = _fit_predict(train, test, CORE_FEATURES)
        full_probs = _fit_predict(train, test, full_features)
        core_score = _score(y_year, core_probs)
        full_score = _score(y_year, full_probs)

        for family, names in FAMILY_FEATURES.items():
            add_probs = _fit_predict(train, test, CORE_FEATURES + names)
            excluded = set(names)
            without_features = tuple(
                feature for feature in full_features if feature not in excluded
            )
            without_probs = _fit_predict(train, test, without_features)
            add_score = _score(y_year, add_probs)
            without_score = _score(y_year, without_probs)

            family_yearly[family].append(
                YearDelta(
                    year=test_year,
                    n=len(test),
                    add_one_brier_improvement=core_score.brier - add_score.brier,
                    add_one_log_loss_improvement=(
                        core_score.log_loss - add_score.log_loss
                    ),
                    ablation_brier_contribution=(
                        without_score.brier - full_score.brier
                    ),
                    ablation_log_loss_contribution=(
                        without_score.log_loss - full_score.log_loss
                    ),
                )
            )
            family_y[family].extend(y_year)
            family_core_probs[family].extend(core_probs)
            family_add_probs[family].extend(add_probs)
            family_full_probs[family].extend(full_probs)
            family_without_probs[family].extend(without_probs)

    results: list[RecentFamilyResult] = []
    for family in FAMILY_FEATURES:
        yearly = tuple(family_yearly[family])
        y_all = family_y[family]
        core = _score(y_all, family_core_probs[family])
        add = _score(y_all, family_add_probs[family])
        full = _score(y_all, family_full_probs[family])
        without = _score(y_all, family_without_probs[family])
        results.append(
            RecentFamilyResult(
                family=family,
                recent_years=recent_years,
                n=len(y_all),
                add_one_brier_improvement=core.brier - add.brier,
                add_one_log_loss_improvement=core.log_loss - add.log_loss,
                ablation_brier_contribution=without.brier - full.brier,
                ablation_log_loss_contribution=(
                    without.log_loss - full.log_loss
                ),
                brier_winning_years=sum(
                    item.add_one_brier_improvement > 0.0 for item in yearly
                ),
                log_loss_winning_years=sum(
                    item.add_one_log_loss_improvement > 0.0 for item in yearly
                ),
                yearly=yearly,
            )
        )

    return RecentFamilyDiagnostic(
        experiment_id="FOUNDATIONAL-FAMILY-LAB-001-RECENT-DIAGNOSTIC",
        recent_year_count=recent_year_count,
        recent_years=recent_years,
        min_train_matches=min_train_matches,
        families=tuple(results),
        note=(
            "Reporting-only diagnostic. It reuses the frozen FOUNDATIONAL-FAMILY-LAB-001 "
            "features/model and exists only to make the preregistered recent-block collapse "
            "check explicit. It must not be used to tune feature definitions."
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report recent-block stability for frozen foundational families"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--min-train-matches", type=int, default=1000)
    parser.add_argument("--recent-years", type=int, default=5)
    parser.add_argument("--include-retirements", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    verify_canonical_manifest(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
        require_research_permission=True,
    )
    matches = load_canonical_parquet(
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
    )
    report = run_recent_family_diagnostic(
        matches,
        min_train_matches=args.min_train_matches,
        recent_year_count=args.recent_years,
        exclude_retirements=not args.include_retirements,
    )
    print(json.dumps(asdict(report), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
