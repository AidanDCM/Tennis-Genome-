from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Literal

from .contracts import WorkbenchRecord
from .dynamic_state_runner import _code_fingerprint
from .dynamic_state_search_family import DynamicStateLessAggressiveFamilySpec
from .dynamic_state_search_runner import (
    DynamicStateCandidateAggregate,
    DynamicStateCandidateTourResult,
    DynamicStateLessAggressiveSearchEvidence,
    DynamicStateLessAggressiveSearchReport,
    _search_code_fingerprint,
)


class DynamicStateSearchAdmissionBindings(WorkbenchRecord):
    """Previously exposed identities that a real family-search result must preserve."""

    atp_source_manifest_sha256: str
    wta_source_manifest_sha256: str
    atp_dataset_fingerprint_sha256: str
    wta_dataset_fingerprint_sha256: str
    parent_code_fingerprint_sha256: str


DEFAULT_ADMISSION_BINDINGS = DynamicStateSearchAdmissionBindings(
    atp_source_manifest_sha256=(
        "742283031b9a89f703ae852511ef207e16dde7b70f961d02db102e785aa060a8"
    ),
    wta_source_manifest_sha256=(
        "9d43d556933947879d61c51a83865a8ee48a885df45b141e588136dd5c6d42d2"
    ),
    atp_dataset_fingerprint_sha256=(
        "df3822aa1129ba825de9300cf74f5b948171309e02bbaa3e6fabf8d813fe58cf"
    ),
    wta_dataset_fingerprint_sha256=(
        "b97a5d9fef5916e836d3ef4722d26c5c43c829d24c17d5d0d701106d150bd2ea"
    ),
    parent_code_fingerprint_sha256=(
        "bc31f1d7f2831adc007732a4ff4cf6343b309138ece3165dd1420fad53020449"
    ),
)


class DynamicStateSearchAdmissionReceipt(WorkbenchRecord):
    """Deterministic receipt proving that one result passed the frozen admission gate."""

    receipt_id: str = "DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001-ADMISSION"
    evidence_file_sha256: str
    evidence_semantic_sha256: str
    report_sha256: str
    family_spec_sha256: str
    search_family_sha256: str
    atp_source_manifest_sha256: str
    wta_source_manifest_sha256: str
    atp_dataset_fingerprint_sha256: str
    wta_dataset_fingerprint_sha256: str
    parent_code_fingerprint_sha256: str
    search_code_fingerprint_sha256: str
    selection_status: Literal["SELECTED", "NO_CANDIDATE"]
    selected_candidate_id: str | None
    admission_status: Literal["ADMITTED_FROZEN_DEVELOPMENT_SEARCH"] = (
        "ADMITTED_FROZEN_DEVELOPMENT_SEARCH"
    )


def _assert_close(label: str, observed: float, expected: float) -> None:
    if not math.isfinite(observed) or not math.isfinite(expected):
        raise ValueError(f"{label} must be finite")
    if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"{label} does not reproduce")


def _verify_result_cell(
    *,
    row: DynamicStateCandidateTourResult,
    expected_spec_sha256: str,
    bonferroni_alpha: float,
) -> None:
    if row.development_spec_sha256 != expected_spec_sha256:
        raise ValueError(
            f"development spec identity drift for {row.candidate_id}/{row.tour}"
        )
    if row.n_predictions <= 0:
        raise ValueError("candidate-tour result must contain prediction rows")
    for label, value in (
        ("fixed_brier", row.fixed_brier),
        ("candidate_brier", row.candidate_brier),
        ("brier_improvement", row.brier_improvement),
        ("brier_p_value", row.brier_p_value),
        ("fixed_log_loss", row.fixed_log_loss),
        ("candidate_log_loss", row.candidate_log_loss),
        ("log_loss_improvement", row.log_loss_improvement),
        ("log_loss_p_value", row.log_loss_p_value),
    ):
        if not math.isfinite(value):
            raise ValueError(f"{label} must be finite")
    if not 0.0 <= row.fixed_brier <= 1.0 or not 0.0 <= row.candidate_brier <= 1.0:
        raise ValueError("Brier scores must be in [0, 1]")
    if row.fixed_log_loss < 0.0 or row.candidate_log_loss < 0.0:
        raise ValueError("log loss must be non-negative")
    if not 0.0 <= row.brier_p_value <= 1.0:
        raise ValueError("Brier p-value must be in [0, 1]")
    if not 0.0 <= row.log_loss_p_value <= 1.0:
        raise ValueError("log-loss p-value must be in [0, 1]")

    _assert_close(
        "Brier improvement",
        row.brier_improvement,
        row.fixed_brier - row.candidate_brier,
    )
    _assert_close(
        "log-loss improvement",
        row.log_loss_improvement,
        row.fixed_log_loss - row.candidate_log_loss,
    )
    expected_brier_support = (
        row.brier_improvement > 0.0 and row.brier_p_value <= bonferroni_alpha
    )
    expected_log_support = (
        row.log_loss_improvement > 0.0 and row.log_loss_p_value <= bonferroni_alpha
    )
    if row.brier_familywise_supported != expected_brier_support:
        raise ValueError("Brier familywise-support flag does not reproduce")
    if row.log_loss_familywise_supported != expected_log_support:
        raise ValueError("log-loss familywise-support flag does not reproduce")


def verify_frozen_search_report(
    report: DynamicStateLessAggressiveSearchReport,
    *,
    spec: DynamicStateLessAggressiveFamilySpec | None = None,
) -> str | None:
    """Independently rederive family completeness, aggregation and frozen selection."""

    spec = spec or DynamicStateLessAggressiveFamilySpec()
    search_family = spec.search_family()
    if report.family_id != spec.family_id:
        raise ValueError("search result family_id does not match frozen family")
    if report.family_spec_sha256 != spec.semantic_sha256:
        raise ValueError("search result family-spec identity does not reproduce")
    if report.search_family_sha256 != search_family.semantic_sha256:
        raise ValueError("search result ProcedureSearchFamily identity does not reproduce")
    if report.primary_claim_count != spec.primary_claim_count:
        raise ValueError("search result primary-claim count does not reproduce")
    _assert_close("Bonferroni alpha", report.bonferroni_alpha, spec.bonferroni_alpha)
    if report.selection_rule != spec.selection_rule:
        raise ValueError("search result selection rule does not match preregistration")

    expected_order = tuple(
        (candidate.candidate_id, tour)
        for candidate in spec.candidates
        for tour in spec.tours
    )
    observed_order = tuple(
        (row.candidate_id, row.tour) for row in report.candidate_tour_results
    )
    if observed_order != expected_order:
        raise ValueError("candidate-tour result cells are incomplete, duplicated or reordered")

    candidate_lookup = {candidate.candidate_id: candidate for candidate in spec.candidates}
    by_candidate: dict[str, list[DynamicStateCandidateTourResult]] = {
        candidate.candidate_id: [] for candidate in spec.candidates
    }
    by_tour: dict[str, list[DynamicStateCandidateTourResult]] = {
        tour: [] for tour in spec.tours
    }
    for row in report.candidate_tour_results:
        candidate = candidate_lookup[row.candidate_id]
        expected_development = spec.development_spec(candidate=candidate, tour=row.tour)
        _verify_result_cell(
            row=row,
            expected_spec_sha256=expected_development.semantic_sha256,
            bonferroni_alpha=spec.bonferroni_alpha,
        )
        by_candidate[row.candidate_id].append(row)
        by_tour[row.tour].append(row)

    for tour, rows in by_tour.items():
        prediction_counts = {row.n_predictions for row in rows}
        fixed_brier = {row.fixed_brier for row in rows}
        fixed_log_loss = {row.fixed_log_loss for row in rows}
        if len(prediction_counts) != 1:
            raise ValueError(f"{tour} candidate runs changed the evaluation population")
        if len(fixed_brier) != 1 or len(fixed_log_loss) != 1:
            raise ValueError(f"{tour} candidate runs changed the fixed comparator")

    expected_aggregates: list[DynamicStateCandidateAggregate] = []
    eligible: list[str] = []
    for candidate in spec.candidates:
        rows = by_candidate[candidate.candidate_id]
        total_n = sum(row.n_predictions for row in rows)
        pooled_brier = sum(
            row.n_predictions * row.brier_improvement for row in rows
        ) / total_n
        pooled_log = sum(
            row.n_predictions * row.log_loss_improvement for row in rows
        ) / total_n
        four_positive = all(
            row.brier_improvement > 0.0 and row.log_loss_improvement > 0.0
            for row in rows
        )
        all_supported = all(
            row.brier_familywise_supported and row.log_loss_familywise_supported
            for row in rows
        )
        expected_aggregates.append(
            DynamicStateCandidateAggregate(
                candidate_id=candidate.candidate_id,
                four_cell_positive=four_positive,
                all_four_familywise_supported=all_supported,
                pooled_brier_improvement=pooled_brier,
                pooled_log_loss_improvement=pooled_log,
            )
        )
        if four_positive:
            eligible.append(candidate.candidate_id)

    if tuple(row.candidate_id for row in report.candidate_aggregates) != tuple(
        candidate.candidate_id for candidate in spec.candidates
    ):
        raise ValueError("candidate aggregate rows do not match frozen family order")
    for observed, expected in zip(
        report.candidate_aggregates,
        expected_aggregates,
        strict=True,
    ):
        if observed.candidate_id != expected.candidate_id:
            raise ValueError("candidate aggregate identity does not reproduce")
        if observed.four_cell_positive != expected.four_cell_positive:
            raise ValueError("four-cell-positive flag does not reproduce")
        if observed.all_four_familywise_supported != expected.all_four_familywise_supported:
            raise ValueError("familywise-support aggregate flag does not reproduce")
        _assert_close(
            "pooled Brier improvement",
            observed.pooled_brier_improvement,
            expected.pooled_brier_improvement,
        )
        _assert_close(
            "pooled log-loss improvement",
            observed.pooled_log_loss_improvement,
            expected.pooled_log_loss_improvement,
        )

    expected_eligible = tuple(sorted(eligible))
    if report.eligible_candidate_ids != expected_eligible:
        raise ValueError("eligible candidate set does not reproduce")

    selected: str | None = None
    if eligible:
        sortable = [
            row for row in expected_aggregates if row.candidate_id in set(eligible)
        ]
        sortable.sort(
            key=lambda row: (
                -row.pooled_log_loss_improvement,
                -row.pooled_brier_improvement,
                row.candidate_id,
            )
        )
        selected = sortable[0].candidate_id
    expected_status = "SELECTED" if selected is not None else "NO_CANDIDATE"
    if report.selected_candidate_id != selected:
        raise ValueError("selected candidate does not reproduce frozen selector")
    if report.selection_status != expected_status:
        raise ValueError("selection status does not reproduce frozen selector")
    return selected


def _parse_evidence_bytes(content: bytes) -> DynamicStateLessAggressiveSearchEvidence:
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("search evidence must be UTF-8 JSON") from exc

    def reject_nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON constant is forbidden: {value}")

    try:
        payload = json.loads(text, parse_constant=reject_nonfinite)
    except json.JSONDecodeError as exc:
        raise ValueError("search evidence is not valid JSON") from exc
    return DynamicStateLessAggressiveSearchEvidence.model_validate(payload)


def admit_search_evidence_bytes(
    content: bytes,
    *,
    repo_root: Path,
    bindings: DynamicStateSearchAdmissionBindings = DEFAULT_ADMISSION_BINDINGS,
) -> DynamicStateSearchAdmissionReceipt:
    """Admit one evidence file only after every frozen identity and selector rederives."""

    evidence = _parse_evidence_bytes(content)
    verify_frozen_search_report(evidence.report)

    if evidence.atp_source_manifest_sha256 != bindings.atp_source_manifest_sha256:
        raise ValueError("ATP source-manifest identity does not match frozen history")
    if evidence.wta_source_manifest_sha256 != bindings.wta_source_manifest_sha256:
        raise ValueError("WTA source-manifest identity does not match frozen history")
    if evidence.atp_dataset_fingerprint.sha256 != bindings.atp_dataset_fingerprint_sha256:
        raise ValueError("ATP dataset fingerprint does not match frozen history")
    if evidence.wta_dataset_fingerprint.sha256 != bindings.wta_dataset_fingerprint_sha256:
        raise ValueError("WTA dataset fingerprint does not match frozen history")
    if evidence.atp_dataset_fingerprint.dataset_id != "DYNAMIC-STATE-DEVELOPMENT-001-ATP":
        raise ValueError("ATP dataset ID does not match frozen development population")
    if evidence.wta_dataset_fingerprint.dataset_id != "DYNAMIC-STATE-DEVELOPMENT-001-WTA":
        raise ValueError("WTA dataset ID does not match frozen development population")
    if (
        evidence.atp_dataset_fingerprint.source_manifest_sha256
        != evidence.atp_source_manifest_sha256
    ):
        raise ValueError("ATP dataset fingerprint is detached from source identity")
    if (
        evidence.wta_dataset_fingerprint.source_manifest_sha256
        != evidence.wta_source_manifest_sha256
    ):
        raise ValueError("WTA dataset fingerprint is detached from source identity")

    current_parent_code = _code_fingerprint(repo_root)
    if current_parent_code.sha256 != bindings.parent_code_fingerprint_sha256:
        raise ValueError("current parent-model code drifted from exposed frozen identity")
    if evidence.parent_code_fingerprint.sha256 != current_parent_code.sha256:
        raise ValueError("evidence parent-model code fingerprint does not reproduce")

    current_search_code = _search_code_fingerprint(repo_root)
    if evidence.search_code_fingerprint.sha256 != current_search_code.sha256:
        raise ValueError("evidence search-code fingerprint does not reproduce")

    family = DynamicStateLessAggressiveFamilySpec()
    search_family = family.search_family()
    return DynamicStateSearchAdmissionReceipt(
        evidence_file_sha256=hashlib.sha256(content).hexdigest(),
        evidence_semantic_sha256=evidence.semantic_sha256,
        report_sha256=evidence.report.semantic_sha256,
        family_spec_sha256=family.semantic_sha256,
        search_family_sha256=search_family.semantic_sha256,
        atp_source_manifest_sha256=evidence.atp_source_manifest_sha256,
        wta_source_manifest_sha256=evidence.wta_source_manifest_sha256,
        atp_dataset_fingerprint_sha256=evidence.atp_dataset_fingerprint.sha256,
        wta_dataset_fingerprint_sha256=evidence.wta_dataset_fingerprint.sha256,
        parent_code_fingerprint_sha256=evidence.parent_code_fingerprint.sha256,
        search_code_fingerprint_sha256=evidence.search_code_fingerprint.sha256,
        selection_status=evidence.report.selection_status,
        selected_candidate_id=evidence.report.selected_candidate_id,
    )


def admit_search_evidence_file(
    evidence_path: Path,
    *,
    repo_root: Path,
) -> DynamicStateSearchAdmissionReceipt:
    return admit_search_evidence_bytes(
        evidence_path.read_bytes(),
        repo_root=repo_root,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify and admit frozen dynamic-state family-search evidence"
    )
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--receipt", type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    receipt = admit_search_evidence_file(
        args.evidence,
        repo_root=args.repo_root.resolve(),
    )
    rendered = json.dumps(receipt.canonical_payload(), indent=2, sort_keys=True) + "\n"
    if args.receipt is None:
        print(rendered, end="")
        return
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(rendered, encoding="utf-8")


if __name__ == "__main__":
    main()
