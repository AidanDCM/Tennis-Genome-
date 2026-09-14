from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path
from typing import cast

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import sha256_file, verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet

from .contracts import WorkbenchRecord
from .dynamic_state_development import (
    DynamicStateDevelopmentReport,
    DynamicStateDevelopmentSpec,
    run_dynamic_state_development_comparison,
)
from .lineage import (
    ChronologySemantics,
    CodeFingerprint,
    DatasetFingerprint,
    fingerprint_code_components,
    fingerprint_match_population,
)
from .sackmann_availability import sackmann_research_availability_registry

_CODE_COMPONENTS = (
    "src/tennis_genome/research_workbench/dynamic_state_development.py",
    "src/tennis_genome/ratings/dynamic_serve_return.py",
    "src/tennis_genome/ratings/serve_return.py",
    "src/tennis_genome/evaluation/walkforward.py",
    "src/tennis_genome/models/feature_probability.py",
    "src/tennis_genome/evaluation/block_inference.py",
    "src/tennis_genome/evaluation/metrics.py",
)


class DynamicStateDevelopmentEvidence(WorkbenchRecord):
    """Provenance-bound output for one development-only dynamic-state run."""

    evidence_id: str = "DYNAMIC-STATE-DEVELOPMENT-001-EVIDENCE"
    source_manifest_sha256: str
    availability_registry_sha256: str
    dataset_fingerprint: DatasetFingerprint
    code_fingerprint: CodeFingerprint
    report: DynamicStateDevelopmentReport


def _eligible_population(
    matches: list[HistoricalMatch],
    *,
    spec: DynamicStateDevelopmentSpec,
) -> list[HistoricalMatch]:
    observed_tours = {match.pre_match.tour for match in matches}
    if observed_tours and observed_tours != {spec.tour}:
        raise ValueError(
            f"development runner requires only {spec.tour} matches; got {sorted(observed_tours)}"
        )
    return sorted(
        (
            match
            for match in matches
            if not match.outcome.walkover
            and (not spec.exclude_retirements or not match.outcome.retirement)
        ),
        key=lambda match: (match.pre_match.event_date, match.match_id),
    )


def _coverage(matches: list[HistoricalMatch]) -> tuple[date, date]:
    if not matches:
        raise ValueError("development runner has no eligible matches")
    dates = [match.pre_match.event_date for match in matches]
    return min(dates), max(dates)


def _dataset_fingerprint(
    matches: list[HistoricalMatch],
    *,
    tour: Tour,
    schema_version: str,
    source_manifest_sha256: str,
    availability_registry_sha256: str,
) -> DatasetFingerprint:
    rows = [
        {
            "match_id": match.match_id,
            "event_date": match.pre_match.event_date.isoformat(),
            "player_a_id": match.pre_match.player_a_id,
            "player_b_id": match.pre_match.player_b_id,
            "tour": match.pre_match.tour,
        }
        for match in matches
    ]
    return fingerprint_match_population(
        dataset_id=f"DYNAMIC-STATE-DEVELOPMENT-001-{tour}",
        ordered_rows=rows,
        source_manifest_sha256=source_manifest_sha256,
        availability_contract_sha256=availability_registry_sha256,
        schema_version=schema_version,
        chronology_semantics=ChronologySemantics.EVENT_DATE_MATCH_ID,
    )


def _code_fingerprint(repo_root: Path) -> CodeFingerprint:
    components: dict[str, bytes] = {}
    for relative in _CODE_COMPONENTS:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"required code component is missing: {relative}")
        components[relative] = path.read_bytes()
    return fingerprint_code_components(components)


def build_dynamic_state_development_evidence(
    *,
    matches: list[HistoricalMatch],
    spec: DynamicStateDevelopmentSpec,
    source_manifest_sha256: str,
    schema_version: str,
    repo_root: Path,
) -> DynamicStateDevelopmentEvidence:
    """Run the registered development comparison with reproducible provenance bindings."""

    eligible = _eligible_population(matches, spec=spec)
    coverage_start, coverage_end = _coverage(eligible)
    registry = sackmann_research_availability_registry(
        source_manifest_sha256=source_manifest_sha256,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
    )
    registry.assert_canonical_eligible(("elo_state", "serve_return_state"))

    dataset = _dataset_fingerprint(
        eligible,
        tour=spec.tour,
        schema_version=schema_version,
        source_manifest_sha256=source_manifest_sha256,
        availability_registry_sha256=registry.semantic_sha256,
    )
    code = _code_fingerprint(repo_root)
    report = run_dynamic_state_development_comparison(eligible, spec)
    return DynamicStateDevelopmentEvidence(
        source_manifest_sha256=source_manifest_sha256,
        availability_registry_sha256=registry.semantic_sha256,
        dataset_fingerprint=dataset,
        code_fingerprint=code,
        report=report,
    )


def run_from_canonical_files(
    *,
    manifest_path: Path,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path,
    spec: DynamicStateDevelopmentSpec,
    repo_root: Path,
) -> DynamicStateDevelopmentEvidence:
    manifest = verify_canonical_manifest(
        manifest_path=manifest_path,
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
        require_research_permission=True,
    )
    manifest_tour = str(manifest["tour"])
    if manifest_tour != spec.tour:
        raise ValueError(
            f"manifest tour {manifest_tour!r} does not match registered tour {spec.tour!r}"
        )

    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    return build_dynamic_state_development_evidence(
        matches=matches,
        spec=spec,
        source_manifest_sha256=sha256_file(manifest_path),
        schema_version=str(manifest["schema_version"]),
        repo_root=repo_root,
    )


def _parse_years(value: str) -> tuple[int, ...]:
    years = tuple(int(part) for part in value.split(",") if part.strip())
    if not years:
        raise argparse.ArgumentTypeError("test-years must contain at least one year")
    return years


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DYNAMIC-STATE-DEVELOPMENT-001 with provenance binding"
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument("--outcomes", required=True, type=Path)
    parser.add_argument("--stats", required=True, type=Path)
    parser.add_argument("--tour", required=True, choices=("ATP", "WTA"))
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--test-years",
        type=_parse_years,
        default=tuple(range(2015, 2026)),
    )
    parser.add_argument("--min-train-rows", type=int, default=5_000)
    parser.add_argument("--include-retirements", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    spec = DynamicStateDevelopmentSpec(
        tour=cast(Tour, args.tour),
        test_years=args.test_years,
        min_train_rows=args.min_train_rows,
        exclude_retirements=not args.include_retirements,
    )
    evidence = run_from_canonical_files(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
        spec=spec,
        repo_root=args.repo_root.resolve(),
    )
    rendered = json.dumps(evidence.canonical_payload(), indent=2, sort_keys=True) + "\n"
    if args.output is None:
        print(rendered, end="")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
