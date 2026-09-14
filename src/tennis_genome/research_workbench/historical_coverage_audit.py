from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Literal, cast

from tennis_genome.data.canonical import HistoricalMatch, MatchStats, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet

from .contracts import WorkbenchRecord


class HistoricalCoverageYear(WorkbenchRecord):
    tour: Tour
    year: int
    n_matches: int
    n_strict_eligible: int
    n_stats_present: int
    n_service_observation_a: int
    n_service_observation_b: int
    n_service_observation_both: int
    n_duration_present: int
    stats_present_rate: float
    service_both_rate: float
    duration_present_rate: float


class HistoricalCoverageAudit(WorkbenchRecord):
    audit_id: str = "HISTORICAL-AVAILABILITY-COVERAGE-001"
    source_manifest_sha256: str
    tour: Tour
    rows: tuple[HistoricalCoverageYear, ...]
    evidence_role: Literal["DESCRIPTIVE_ONLY"] = "DESCRIPTIVE_ONLY"


def _manifest_sha256(manifest_path: Path) -> str:
    return hashlib.sha256(manifest_path.read_bytes()).hexdigest()


def _service_observation_available(stats: MatchStats, side: str) -> bool:
    if side == "a":
        total = stats.service_points_a
        first_won = stats.first_serve_points_won_a
        second_won = stats.second_serve_points_won_a
    elif side == "b":
        total = stats.service_points_b
        first_won = stats.first_serve_points_won_b
        second_won = stats.second_serve_points_won_b
    else:
        raise ValueError(f"invalid side: {side!r}")
    if total is None or first_won is None or second_won is None or total <= 0:
        return False
    won = first_won + second_won
    return 0 <= won <= total


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def audit_historical_coverage(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    source_manifest_sha256: str,
) -> HistoricalCoverageAudit:
    observed_tours = {match.pre_match.tour for match in matches}
    if observed_tours and observed_tours != {tour}:
        raise ValueError(
            f"coverage audit requires only {tour} matches; got {sorted(observed_tours)}"
        )

    grouped: dict[int, list[HistoricalMatch]] = defaultdict(list)
    for match in matches:
        grouped[match.pre_match.event_date.year].append(match)

    rows: list[HistoricalCoverageYear] = []
    for year in sorted(grouped):
        year_matches = grouped[year]
        strict = [
            match
            for match in year_matches
            if not match.outcome.walkover and not match.outcome.retirement
        ]
        stats_present = sum(match.stats is not None for match in strict)
        service_a = sum(
            match.stats is not None
            and _service_observation_available(match.stats, "a")
            for match in strict
        )
        service_b = sum(
            match.stats is not None
            and _service_observation_available(match.stats, "b")
            for match in strict
        )
        service_both = sum(
            match.stats is not None
            and _service_observation_available(match.stats, "a")
            and _service_observation_available(match.stats, "b")
            for match in strict
        )
        duration_present = sum(
            match.stats is not None and match.stats.duration_minutes is not None
            for match in strict
        )
        denominator = len(strict)
        rows.append(
            HistoricalCoverageYear(
                tour=tour,
                year=year,
                n_matches=len(year_matches),
                n_strict_eligible=denominator,
                n_stats_present=stats_present,
                n_service_observation_a=service_a,
                n_service_observation_b=service_b,
                n_service_observation_both=service_both,
                n_duration_present=duration_present,
                stats_present_rate=_rate(stats_present, denominator),
                service_both_rate=_rate(service_both, denominator),
                duration_present_rate=_rate(duration_present, denominator),
            )
        )

    return HistoricalCoverageAudit(
        source_manifest_sha256=source_manifest_sha256,
        tour=tour,
        rows=tuple(rows),
    )


def run_from_canonical_files(
    *,
    manifest_path: Path,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path,
    tour: Tour,
) -> HistoricalCoverageAudit:
    manifest = verify_canonical_manifest(
        manifest_path=manifest_path,
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
        require_research_permission=True,
    )
    manifest_tour = str(manifest["tour"])
    if manifest_tour != tour:
        raise ValueError(
            f"manifest tour {manifest_tour!r} does not match requested tour {tour!r}"
        )
    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    return audit_historical_coverage(
        matches,
        tour=tour,
        source_manifest_sha256=_manifest_sha256(manifest_path),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit historical stats/duration availability by tour and year"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    report = run_from_canonical_files(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
        tour=cast(Tour, args.tour),
    )
    rendered = json.dumps(
        report.canonical_payload(), indent=2, sort_keys=True, ensure_ascii=False
    ) + "\n"
    if args.output is None:
        print(rendered, end="")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
