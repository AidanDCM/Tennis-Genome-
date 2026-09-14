from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Literal, cast

from tennis_genome.data.canonical import HistoricalMatch, Tour
from tennis_genome.data.manifest import verify_canonical_manifest
from tennis_genome.data.parquet import load_canonical_parquet

from .contracts import WorkbenchRecord
from .dynamic_state_runner import (
    build_dynamic_state_development_evidence,
    stable_source_manifest_sha256,
)
from .dynamic_state_search_family import (
    DynamicStateLessAggressiveFamilySpec,
    LessAggressiveDynamicCandidate,
)
from .lineage import CodeFingerprint, DatasetFingerprint, fingerprint_code_components

_SEARCH_CODE_COMPONENTS = (
    "src/tennis_genome/research_workbench/dynamic_state_search_runner.py",
    "src/tennis_genome/research_workbench/dynamic_state_search_family.py",
    "src/tennis_genome/research_workbench/dynamic_state_development.py",
    "src/tennis_genome/research_workbench/dynamic_state_runner.py",
    "src/tennis_genome/ratings/dynamic_serve_return.py",
    "src/tennis_genome/ratings/serve_return.py",
    "src/tennis_genome/evaluation/walkforward.py",
    "src/tennis_genome/models/feature_probability.py",
    "src/tennis_genome/evaluation/block_inference.py",
    "src/tennis_genome/evaluation/metrics.py",
)


class DynamicStateCandidateTourResult(WorkbenchRecord):
    candidate_id: str
    tour: Tour
    development_spec_sha256: str
    development_report_sha256: str
    n_predictions: int
    fixed_brier: float
    candidate_brier: float
    brier_improvement: float
    brier_p_value: float
    brier_familywise_supported: bool
    fixed_log_loss: float
    candidate_log_loss: float
    log_loss_improvement: float
    log_loss_p_value: float
    log_loss_familywise_supported: bool


class DynamicStateCandidateAggregate(WorkbenchRecord):
    candidate_id: str
    four_cell_positive: bool
    all_four_familywise_supported: bool
    pooled_brier_improvement: float
    pooled_log_loss_improvement: float


class DynamicStateLessAggressiveSearchReport(WorkbenchRecord):
    family_id: str
    family_spec_sha256: str
    search_family_sha256: str
    primary_claim_count: int
    bonferroni_alpha: float
    candidate_tour_results: tuple[DynamicStateCandidateTourResult, ...]
    candidate_aggregates: tuple[DynamicStateCandidateAggregate, ...]
    eligible_candidate_ids: tuple[str, ...]
    selected_candidate_id: str | None
    selection_status: Literal["SELECTED", "NO_CANDIDATE"]
    selection_rule: str
    evidence_role: Literal["DEVELOPMENT_SEARCH_ONLY"] = "DEVELOPMENT_SEARCH_ONLY"


class DynamicStateLessAggressiveSearchEvidence(WorkbenchRecord):
    evidence_id: str = "DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001-EVIDENCE"
    atp_source_manifest_sha256: str
    wta_source_manifest_sha256: str
    atp_dataset_fingerprint: DatasetFingerprint
    wta_dataset_fingerprint: DatasetFingerprint
    parent_code_fingerprint: CodeFingerprint
    search_code_fingerprint: CodeFingerprint
    report: DynamicStateLessAggressiveSearchReport


def _search_code_fingerprint(repo_root: Path) -> CodeFingerprint:
    components: dict[str, bytes] = {}
    for relative in _SEARCH_CODE_COMPONENTS:
        path = repo_root / relative
        if not path.is_file():
            raise ValueError(f"required search code component is missing: {relative}")
        components[relative] = path.read_bytes()
    return fingerprint_code_components(components)


def _candidate_result(
    *,
    candidate: LessAggressiveDynamicCandidate,
    tour: Tour,
    evidence,
    bonferroni_alpha: float,
) -> DynamicStateCandidateTourResult:
    report = evidence.report
    brier_p = float(report.brier_sign_flip["p_value"])
    log_p = float(report.log_loss_sign_flip["p_value"])
    return DynamicStateCandidateTourResult(
        candidate_id=candidate.candidate_id,
        tour=tour,
        development_spec_sha256=report.experiment_spec_sha256,
        development_report_sha256=report.semantic_sha256,
        n_predictions=report.n_predictions,
        fixed_brier=report.overall_fixed_brier,
        candidate_brier=report.overall_dynamic_brier,
        brier_improvement=report.overall_brier_improvement,
        brier_p_value=brier_p,
        brier_familywise_supported=(
            report.overall_brier_improvement > 0.0 and brier_p <= bonferroni_alpha
        ),
        fixed_log_loss=report.overall_fixed_log_loss,
        candidate_log_loss=report.overall_dynamic_log_loss,
        log_loss_improvement=report.overall_log_loss_improvement,
        log_loss_p_value=log_p,
        log_loss_familywise_supported=(
            report.overall_log_loss_improvement > 0.0 and log_p <= bonferroni_alpha
        ),
    )


def _aggregate_candidates(
    *,
    spec: DynamicStateLessAggressiveFamilySpec,
    results: tuple[DynamicStateCandidateTourResult, ...],
) -> tuple[tuple[DynamicStateCandidateAggregate, ...], tuple[str, ...], str | None]:
    by_candidate: dict[str, list[DynamicStateCandidateTourResult]] = {
        candidate.candidate_id: [] for candidate in spec.candidates
    }
    for result in results:
        if result.candidate_id not in by_candidate:
            raise ValueError(f"unregistered candidate result: {result.candidate_id}")
        by_candidate[result.candidate_id].append(result)

    aggregates: list[DynamicStateCandidateAggregate] = []
    eligible: list[str] = []
    for candidate in spec.candidates:
        cells = sorted(by_candidate[candidate.candidate_id], key=lambda row: row.tour)
        if tuple(row.tour for row in cells) != tuple(sorted(spec.tours)):
            raise ValueError(
                f"candidate {candidate.candidate_id} does not contain exactly both tour results"
            )
        total_n = sum(row.n_predictions for row in cells)
        if total_n <= 0:
            raise ValueError("search candidate has no prediction rows")
        pooled_brier = sum(
            row.n_predictions * row.brier_improvement for row in cells
        ) / total_n
        pooled_log = sum(
            row.n_predictions * row.log_loss_improvement for row in cells
        ) / total_n
        four_positive = all(
            row.brier_improvement > 0.0 and row.log_loss_improvement > 0.0
            for row in cells
        )
        all_familywise = all(
            row.brier_familywise_supported and row.log_loss_familywise_supported
            for row in cells
        )
        aggregates.append(
            DynamicStateCandidateAggregate(
                candidate_id=candidate.candidate_id,
                four_cell_positive=four_positive,
                all_four_familywise_supported=all_familywise,
                pooled_brier_improvement=pooled_brier,
                pooled_log_loss_improvement=pooled_log,
            )
        )
        if four_positive:
            eligible.append(candidate.candidate_id)

    selected: str | None = None
    if eligible:
        eligible_rows = [row for row in aggregates if row.candidate_id in eligible]
        eligible_rows.sort(
            key=lambda row: (
                -row.pooled_log_loss_improvement,
                -row.pooled_brier_improvement,
                row.candidate_id,
            )
        )
        selected = eligible_rows[0].candidate_id
    return tuple(aggregates), tuple(sorted(eligible)), selected


def run_dynamic_state_less_aggressive_search(
    *,
    atp_matches: list[HistoricalMatch],
    wta_matches: list[HistoricalMatch],
    atp_source_manifest_sha256: str,
    wta_source_manifest_sha256: str,
    atp_schema_version: str,
    wta_schema_version: str,
    repo_root: Path,
    spec: DynamicStateLessAggressiveFamilySpec | None = None,
) -> DynamicStateLessAggressiveSearchEvidence:
    """Evaluate every frozen family member on both tours and apply the frozen selector."""

    spec = spec or DynamicStateLessAggressiveFamilySpec()
    search_family = spec.search_family()
    search_family.assert_canonical_claim_allowed(
        [candidate.candidate_id for candidate in spec.candidates]
    )
    matches_by_tour: dict[Tour, list[HistoricalMatch]] = {
        "ATP": atp_matches,
        "WTA": wta_matches,
    }
    source_by_tour: dict[Tour, str] = {
        "ATP": atp_source_manifest_sha256,
        "WTA": wta_source_manifest_sha256,
    }
    schema_by_tour: dict[Tour, str] = {
        "ATP": atp_schema_version,
        "WTA": wta_schema_version,
    }

    results: list[DynamicStateCandidateTourResult] = []
    dataset_by_tour: dict[Tour, DatasetFingerprint] = {}
    parent_code: CodeFingerprint | None = None

    for candidate in spec.candidates:
        for tour in spec.tours:
            development_spec = spec.development_spec(candidate=candidate, tour=tour)
            evidence = build_dynamic_state_development_evidence(
                matches=matches_by_tour[tour],
                spec=development_spec,
                source_manifest_sha256=source_by_tour[tour],
                schema_version=schema_by_tour[tour],
                repo_root=repo_root,
            )
            previous_dataset = dataset_by_tour.get(tour)
            if previous_dataset is None:
                dataset_by_tour[tour] = evidence.dataset_fingerprint
            elif previous_dataset.sha256 != evidence.dataset_fingerprint.sha256:
                raise ValueError("candidate runs did not preserve a common dataset fingerprint")
            if parent_code is None:
                parent_code = evidence.code_fingerprint
            elif parent_code.sha256 != evidence.code_fingerprint.sha256:
                raise ValueError("candidate runs did not preserve a common parent code fingerprint")
            results.append(
                _candidate_result(
                    candidate=candidate,
                    tour=tour,
                    evidence=evidence,
                    bonferroni_alpha=spec.bonferroni_alpha,
                )
            )

    expected_cells = len(spec.candidates) * len(spec.tours)
    if len(results) != expected_cells:
        raise ValueError("search did not evaluate every registered candidate-tour cell")
    if parent_code is None or set(dataset_by_tour) != {"ATP", "WTA"}:
        raise ValueError("search did not establish complete provenance")

    aggregates, eligible, selected = _aggregate_candidates(
        spec=spec,
        results=tuple(results),
    )
    report = DynamicStateLessAggressiveSearchReport(
        family_id=spec.family_id,
        family_spec_sha256=spec.semantic_sha256,
        search_family_sha256=search_family.semantic_sha256,
        primary_claim_count=spec.primary_claim_count,
        bonferroni_alpha=spec.bonferroni_alpha,
        candidate_tour_results=tuple(results),
        candidate_aggregates=aggregates,
        eligible_candidate_ids=eligible,
        selected_candidate_id=selected,
        selection_status="SELECTED" if selected is not None else "NO_CANDIDATE",
        selection_rule=spec.selection_rule,
    )
    return DynamicStateLessAggressiveSearchEvidence(
        atp_source_manifest_sha256=atp_source_manifest_sha256,
        wta_source_manifest_sha256=wta_source_manifest_sha256,
        atp_dataset_fingerprint=dataset_by_tour["ATP"],
        wta_dataset_fingerprint=dataset_by_tour["WTA"],
        parent_code_fingerprint=parent_code,
        search_code_fingerprint=_search_code_fingerprint(repo_root),
        report=report,
    )


def _load_verified_tour(
    *,
    tour: Tour,
    manifest_path: Path,
    pre_match_path: Path,
    outcome_path: Path,
    stats_path: Path,
) -> tuple[list[HistoricalMatch], str, str]:
    manifest = verify_canonical_manifest(
        manifest_path=manifest_path,
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
        require_research_permission=True,
    )
    if str(manifest["tour"]) != tour:
        raise ValueError(f"manifest tour does not match registered {tour} search input")
    matches = load_canonical_parquet(
        pre_match_path=pre_match_path,
        outcome_path=outcome_path,
        stats_path=stats_path,
    )
    return (
        matches,
        stable_source_manifest_sha256(manifest),
        str(manifest["schema_version"]),
    )


def run_from_canonical_files(
    *,
    atp_manifest_path: Path,
    atp_pre_match_path: Path,
    atp_outcome_path: Path,
    atp_stats_path: Path,
    wta_manifest_path: Path,
    wta_pre_match_path: Path,
    wta_outcome_path: Path,
    wta_stats_path: Path,
    repo_root: Path,
) -> DynamicStateLessAggressiveSearchEvidence:
    atp_matches, atp_source, atp_schema = _load_verified_tour(
        tour="ATP",
        manifest_path=atp_manifest_path,
        pre_match_path=atp_pre_match_path,
        outcome_path=atp_outcome_path,
        stats_path=atp_stats_path,
    )
    wta_matches, wta_source, wta_schema = _load_verified_tour(
        tour="WTA",
        manifest_path=wta_manifest_path,
        pre_match_path=wta_pre_match_path,
        outcome_path=wta_outcome_path,
        stats_path=wta_stats_path,
    )
    return run_dynamic_state_less_aggressive_search(
        atp_matches=atp_matches,
        wta_matches=wta_matches,
        atp_source_manifest_sha256=atp_source,
        wta_source_manifest_sha256=wta_source,
        atp_schema_version=atp_schema,
        wta_schema_version=wta_schema,
        repo_root=repo_root,
        spec=DynamicStateLessAggressiveFamilySpec(),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the frozen DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001 family"
    )
    for tour in ("atp", "wta"):
        parser.add_argument(f"--{tour}-manifest", required=True, type=Path)
        parser.add_argument(f"--{tour}-pre-match", required=True, type=Path)
        parser.add_argument(f"--{tour}-outcomes", required=True, type=Path)
        parser.add_argument(f"--{tour}-stats", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    evidence = run_from_canonical_files(
        atp_manifest_path=args.atp_manifest,
        atp_pre_match_path=args.atp_pre_match,
        atp_outcome_path=args.atp_outcomes,
        atp_stats_path=args.atp_stats,
        wta_manifest_path=args.wta_manifest,
        wta_pre_match_path=args.wta_pre_match,
        wta_outcome_path=args.wta_outcomes,
        wta_stats_path=args.wta_stats,
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
