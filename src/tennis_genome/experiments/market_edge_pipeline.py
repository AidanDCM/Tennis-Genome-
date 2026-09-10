from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from tennis_genome.experiments.market_edge import MarketSignalRow, SignalName, Tour
from tennis_genome.experiments.market_edge_family import run_market_edge_family
from tennis_genome.experiments.market_edge_inputs import (
    build_market_signal_rows,
    load_closing_market_rows,
    load_genome_values,
    load_match_years,
    load_profile_gap_values,
    load_settled_outcomes,
)

_DEVELOPMENT_END_YEAR = 2025


@dataclass(frozen=True)
class ClaimCoverage:
    tour: Tour
    signal_name: SignalName
    executable_close_rows: int
    signal_rows: int
    settled_outcome_rows: int
    matched_claim_rows: int


@dataclass(frozen=True)
class MarketEdgeArtifact:
    experiment_id: str
    market_probability_method: str
    coverage: tuple[ClaimCoverage, ...]
    family_report: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _build_claim(
    *,
    close_rows,
    outcomes,
    years_by_match,
    signals,
    tour: Tour,
    signal_name: SignalName,
) -> tuple[list[MarketSignalRow], ClaimCoverage]:
    rows = build_market_signal_rows(
        close_rows=close_rows,
        outcomes=outcomes,
        signals=signals,
        years_by_match=years_by_match,
        tour=tour,
        signal_name=signal_name,
    )
    forbidden = [row.match_id for row in rows if row.year > _DEVELOPMENT_END_YEAR]
    if forbidden:
        raise ValueError(
            "MARKET-EDGE-001 is frozen through 2025; post-2025 rows are forbidden"
        )
    return rows, ClaimCoverage(
        tour=tour,
        signal_name=signal_name,
        executable_close_rows=sum(row.tour == tour for row in close_rows.values()),
        signal_rows=len(signals),
        settled_outcome_rows=len(outcomes),
        matched_claim_rows=len(rows),
    )


def build_market_edge_artifact(
    *,
    market_hist_records: str | Path,
    pre_match: str | Path,
    outcomes_path: str | Path,
    profile_gap_atp: str | Path,
    profile_gap_wta: str | Path,
    genome_atp: str | Path,
    genome_wta: str | Path,
    min_prior_rows: int = 1000,
) -> MarketEdgeArtifact:
    close_rows = load_closing_market_rows(market_hist_records)
    outcomes = load_settled_outcomes(outcomes_path)
    years_by_match = load_match_years(pre_match)

    signal_sets: dict[tuple[Tour, SignalName], dict] = {
        ("ATP", "profile_gap"): load_profile_gap_values(profile_gap_atp, tour="ATP"),
        ("WTA", "profile_gap"): load_profile_gap_values(profile_gap_wta, tour="WTA"),
        ("ATP", "genome"): load_genome_values(genome_atp, tour="ATP"),
        ("WTA", "genome"): load_genome_values(genome_wta, tour="WTA"),
    }
    claim_rows: dict[tuple[Tour, SignalName], list[MarketSignalRow]] = {}
    coverage: list[ClaimCoverage] = []
    for key in (
        ("ATP", "profile_gap"),
        ("WTA", "profile_gap"),
        ("ATP", "genome"),
        ("WTA", "genome"),
    ):
        tour, signal_name = key
        rows, claim_coverage = _build_claim(
            close_rows=close_rows,
            outcomes=outcomes,
            years_by_match=years_by_match,
            signals=signal_sets[key],
            tour=tour,
            signal_name=signal_name,
        )
        claim_rows[key] = rows
        coverage.append(claim_coverage)

    family = run_market_edge_family(
        claim_rows,
        min_prior_rows=min_prior_rows,
    )
    return MarketEdgeArtifact(
        experiment_id="MARKET-EDGE-001",
        market_probability_method="exchange_mid_implied_proportional_v1",
        coverage=tuple(coverage),
        family_report=family.to_dict(),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run MARKET-EDGE-001 from immutable market/signal artifacts"
    )
    parser.add_argument("--market-hist-records", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--profile-gap-atp", required=True, type=Path)
    parser.add_argument("--profile-gap-wta", required=True, type=Path)
    parser.add_argument("--genome-atp", required=True, type=Path)
    parser.add_argument("--genome-wta", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--min-prior-rows", type=int, default=1000)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    artifact = build_market_edge_artifact(
        market_hist_records=args.market_hist_records,
        pre_match=args.pre_match,
        outcomes_path=args.outcomes,
        profile_gap_atp=args.profile_gap_atp,
        profile_gap_wta=args.profile_gap_wta,
        genome_atp=args.genome_atp,
        genome_wta=args.genome_wta,
        min_prior_rows=args.min_prior_rows,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
