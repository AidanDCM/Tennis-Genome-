from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from tennis_genome.data.canonical import HistoricalMatch, Tour
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
    DynamicStateDevelopmentEvidence,
    build_dynamic_state_development_evidence,
    stable_source_manifest_sha256,
)
from .lineage import CodeFingerprint, fingerprint_code_components

_DIAGNOSTIC_CODE_COMPONENTS = (
    "src/tennis_genome/research_workbench/dynamic_state_diagnostic_runner.py",
    "src/tennis_genome/research_workbench/dynamic_state_diagnostic.py",
    "src/tennis_genome/research_workbench/dynamic_state_development.py",
    "src/tennis_genome/ratings/dynamic_serve_return.py",
    "src/tennis_genome/ratings/serve_return.py",
    "src/tennis_genome/evaluation/walkforward.py",
    "src/tennis_genome/models/feature_probability.py",
    "src/tennis_genome/evaluation/block_inference.py",
    "src/tennis_genome/evaluation/metrics.py",
)


class DynamicStateFailureDiagnosticEvidence(WorkbenchRecord):
    """Provenance-bound descriptive evidence for the frozen failure diagnostic."""

    evidence_id: str = "DYNAMIC-STATE-FAILURE-DIAGNOSTIC-001-EVIDENCE"
    parent_evidence: DynamicStateDevelopmentEvidence
    diagnostic_code_fingerprint: CodeFingerprint
    report: DynamicStateFailureDiagnosticReport


def _diagnostic_code_fingerprint(repo_root: Path) -> CodeFingerprint:
    components: dict[str, bytes] = {}
    for relative in _DIAGNOSTIC_CODE_COMPONENTS:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"required diagnostic code component is missing: {relative}")
        components[relative] = path.read_bytes()
    return fingerprint_code_components(components)


def build_dynamic_state_failure_diagnostic_evidence(
    *,
    matches: list[HistoricalMatch],
    spec: DynamicStateFailureDiagnosticSpec,
    source_manifest_sha256: str,
    schema_version: str,
    repo_root: Path,
) -> DynamicStateFailureDiagnosticEvidence:
    """Run the frozen descriptive diagnostic and bind it to its exact parent evidence."""

    parent = build_dynamic_state_development_evidence(
        matches=matches,
        spec=spec.development_spec,
        source_manifest_sha256=source_manifest_sha256,
        schema_version=schema_version,
        repo_root=repo_root,
    )
    report = run_dynamic_state_failure_diagnostic(matches, spec)
    if report.development_report_sha256 != parent.report.semantic_sha256:
        raise ValueError("diagnostic parent report does not match bound development evidence")

    return DynamicStateFailureDiagnosticEvidence(
        parent_evidence=parent,
        diagnostic_code_fingerprint=_diagnostic_code_fingerprint(repo_root),
        report=report,
    )


def run_from_canonical_files(
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
    manifest_tour = str(manifest["tour"])
    if manifest_tour != spec.development_spec.tour:
        raise ValueError(
            f"manifest tour {manifest_tour!r} does not match registered tour "
            f"{spec.development_spec.tour!r}"
        )

    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    return build_dynamic_state_failure_diagnostic_evidence(
        matches=matches,
        spec=spec,
        source_manifest_sha256=stable_source_manifest_sha256(manifest),
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
    parser.add_argument("--include-retirements", action="store_true")
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    development_spec = DynamicStateDevelopmentSpec(
        tour=cast(Tour, args.tour),
        test_years=args.test_years,
        min_train_rows=args.min_train_rows,
        exclude_retirements=not args.include_retirements,
    )
    spec = DynamicStateFailureDiagnosticSpec(development_spec=development_spec)
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
