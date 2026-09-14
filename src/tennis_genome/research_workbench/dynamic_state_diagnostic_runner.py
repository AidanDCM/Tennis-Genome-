from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from tennis_genome.data.canonical import Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet

from .contracts import WorkbenchRecord
from .dynamic_state_development import DynamicStateDevelopmentSpec
from .dynamic_state_diagnostic import (
    DynamicStateFailureDiagnosticReport,
    DynamicStateFailureDiagnosticSpec,
    run_dynamic_state_failure_diagnostic,
)
from .dynamic_state_runner import (
    _code_fingerprint,
    _dataset_fingerprint,
    _eligible_population,
    stable_source_manifest_sha256,
)
from .lineage import CodeFingerprint, DatasetFingerprint
from .sackmann_availability import sackmann_research_availability_registry


class DynamicStateFailureDiagnosticEvidence(WorkbenchRecord):
    """Provenance-bound descriptive diagnostic for the frozen dynamic-state candidate."""

    evidence_id: str = "DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001-EVIDENCE"
    source_manifest_sha256: str
    availability_registry_sha256: str
    dataset_fingerprint: DatasetFingerprint
    code_fingerprint: CodeFingerprint
    report: DynamicStateFailureDiagnosticReport


def run_diagnostic_from_canonical_files(
    *,
    manifest_path: Path,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path,
    spec: DynamicStateFailureDiagnosticSpec,
    repo_root: Path,
) -> DynamicStateFailureDiagnosticEvidence:
    manifest = verify_canonical_manifest(
        manifest_path=manifest_path,
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
        require_research_permission=True,
    )
    development_spec = spec.development_spec
    manifest_tour = str(manifest["tour"])
    if manifest_tour != development_spec.tour:
        raise ValueError(
            f"manifest tour {manifest_tour!r} does not match diagnostic tour "
            f"{development_spec.tour!r}"
        )

    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    eligible = _eligible_population(matches, spec=development_spec)
    if not eligible:
        raise ValueError("diagnostic runner has no eligible matches")

    source_manifest_sha256 = stable_source_manifest_sha256(manifest)
    coverage_start = min(match.pre_match.event_date for match in eligible)
    coverage_end = max(match.pre_match.event_date for match in eligible)
    registry = sackmann_research_availability_registry(
        source_manifest_sha256=source_manifest_sha256,
        coverage_start=coverage_start,
        coverage_end=coverage_end,
    )
    registry.assert_canonical_eligible(("elo_state", "serve_return_state"))

    dataset = _dataset_fingerprint(
        eligible,
        tour=development_spec.tour,
        schema_version=str(manifest["schema_version"]),
        source_manifest_sha256=source_manifest_sha256,
        availability_registry_sha256=registry.semantic_sha256,
    )
    code = _code_fingerprint(repo_root)
    report = run_dynamic_state_failure_diagnostic(eligible, spec)
    return DynamicStateFailureDiagnosticEvidence(
        source_manifest_sha256=source_manifest_sha256,
        availability_registry_sha256=registry.semantic_sha256,
        dataset_fingerprint=dataset,
        code_fingerprint=code,
        report=report,
    )


def _parse_years(value: str) -> tuple[int, ...]:
    years = tuple(int(part) for part in value.split(",") if part.strip())
    if not years:
        raise argparse.ArgumentTypeError("test-years must contain at least one year")
    return years


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001 with provenance binding"
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
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    development_spec = DynamicStateDevelopmentSpec(
        tour=cast(Tour, args.tour),
        test_years=args.test_years,
        min_train_rows=args.min_train_rows,
    )
    diagnostic_spec = DynamicStateFailureDiagnosticSpec(
        development_spec=development_spec,
    )
    evidence = run_diagnostic_from_canonical_files(
        manifest_path=args.manifest,
        pre_match_path=args.pre_match,
        outcome_path=args.outcomes,
        stats_path=args.stats,
        spec=diagnostic_spec,
        repo_root=args.repo_root.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(evidence.canonical_payload(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
