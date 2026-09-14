from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.research_workbench.dynamic_state_runner import _code_fingerprint
from tennis_genome.research_workbench.dynamic_state_search_admission import (
    DEFAULT_ADMISSION_BINDINGS,
    DynamicStateSearchAdmissionBindings,
    _parse_evidence_bytes,
    admit_search_evidence_bytes,
    verify_frozen_search_report,
)
from tennis_genome.research_workbench.dynamic_state_search_family import (
    DynamicStateLessAggressiveFamilySpec,
)
from tennis_genome.research_workbench.dynamic_state_search_runner import (
    DynamicStateCandidateAggregate,
    DynamicStateCandidateTourResult,
    DynamicStateLessAggressiveSearchEvidence,
    DynamicStateLessAggressiveSearchReport,
    _search_code_fingerprint,
)
from tennis_genome.research_workbench.lineage import (
    ChronologySemantics,
    fingerprint_match_population,
)


def _valid_report() -> DynamicStateLessAggressiveSearchReport:
    spec = DynamicStateLessAggressiveFamilySpec()
    results: list[DynamicStateCandidateTourResult] = []
    aggregates: list[DynamicStateCandidateAggregate] = []

    for index, candidate in enumerate(spec.candidates, start=1):
        brier_improvement = 0.0001 * index
        log_improvement = 0.0002 * index
        for tour in spec.tours:
            fixed_brier = 0.22 if tour == "ATP" else 0.23
            fixed_log = 0.63 if tour == "ATP" else 0.65
            development = spec.development_spec(candidate=candidate, tour=tour)
            results.append(
                DynamicStateCandidateTourResult(
                    candidate_id=candidate.candidate_id,
                    tour=tour,
                    development_spec_sha256=development.semantic_sha256,
                    development_report_sha256=(f"{index:02x}" * 32)[:64],
                    n_predictions=100 if tour == "ATP" else 120,
                    fixed_brier=fixed_brier,
                    candidate_brier=fixed_brier - brier_improvement,
                    brier_improvement=brier_improvement,
                    brier_p_value=0.001,
                    brier_familywise_supported=True,
                    fixed_log_loss=fixed_log,
                    candidate_log_loss=fixed_log - log_improvement,
                    log_loss_improvement=log_improvement,
                    log_loss_p_value=0.001,
                    log_loss_familywise_supported=True,
                )
            )
        aggregates.append(
            DynamicStateCandidateAggregate(
                candidate_id=candidate.candidate_id,
                four_cell_positive=True,
                all_four_familywise_supported=True,
                pooled_brier_improvement=brier_improvement,
                pooled_log_loss_improvement=log_improvement,
            )
        )

    selected = spec.candidates[-1].candidate_id
    return DynamicStateLessAggressiveSearchReport(
        family_id=spec.family_id,
        family_spec_sha256=spec.semantic_sha256,
        search_family_sha256=spec.search_family().semantic_sha256,
        primary_claim_count=spec.primary_claim_count,
        bonferroni_alpha=spec.bonferroni_alpha,
        candidate_tour_results=tuple(results),
        candidate_aggregates=tuple(aggregates),
        eligible_candidate_ids=tuple(sorted(candidate.candidate_id for candidate in spec.candidates)),
        selected_candidate_id=selected,
        selection_status="SELECTED",
        selection_rule=spec.selection_rule,
    )


def _synthetic_dataset(*, tour: str, source_sha256: str):
    return fingerprint_match_population(
        dataset_id=f"DYNAMIC-STATE-DEVELOPMENT-001-{tour}",
        ordered_rows=(
            {
                "match_id": f"{tour}-synthetic-1",
                "event_date": "2025-01-01",
                "player_a_id": "A",
                "player_b_id": "B",
                "tour": tour,
            },
        ),
        source_manifest_sha256=source_sha256,
        availability_contract_sha256="3" * 64,
        schema_version="synthetic-v1",
        chronology_semantics=ChronologySemantics.EVENT_DATE_MATCH_ID,
    )


def _synthetic_evidence(repo_root: Path):
    atp_source = "1" * 64
    wta_source = "2" * 64
    atp_dataset = _synthetic_dataset(tour="ATP", source_sha256=atp_source)
    wta_dataset = _synthetic_dataset(tour="WTA", source_sha256=wta_source)
    parent_code = _code_fingerprint(repo_root)
    search_code = _search_code_fingerprint(repo_root)
    evidence = DynamicStateLessAggressiveSearchEvidence(
        atp_source_manifest_sha256=atp_source,
        wta_source_manifest_sha256=wta_source,
        atp_dataset_fingerprint=atp_dataset,
        wta_dataset_fingerprint=wta_dataset,
        parent_code_fingerprint=parent_code,
        search_code_fingerprint=search_code,
        report=_valid_report(),
    )
    bindings = DynamicStateSearchAdmissionBindings(
        atp_source_manifest_sha256=atp_source,
        wta_source_manifest_sha256=wta_source,
        atp_dataset_fingerprint_sha256=atp_dataset.sha256,
        wta_dataset_fingerprint_sha256=wta_dataset.sha256,
        parent_code_fingerprint_sha256=parent_code.sha256,
    )
    return evidence, bindings


def test_valid_frozen_report_rederives_selector() -> None:
    report = _valid_report()

    selected = verify_frozen_search_report(report)

    assert selected == report.selected_candidate_id


def test_missing_candidate_tour_cell_is_rejected() -> None:
    report = _valid_report()
    tampered = report.model_copy(
        update={"candidate_tour_results": report.candidate_tour_results[:-1]}
    )

    with pytest.raises(ValueError, match="incomplete, duplicated or reordered"):
        verify_frozen_search_report(tampered)


def test_tampered_familywise_flag_is_rejected() -> None:
    report = _valid_report()
    rows = list(report.candidate_tour_results)
    rows[0] = rows[0].model_copy(update={"brier_familywise_supported": False})
    tampered = report.model_copy(update={"candidate_tour_results": tuple(rows)})

    with pytest.raises(ValueError, match="familywise-support flag"):
        verify_frozen_search_report(tampered)


def test_tampered_selector_is_rejected() -> None:
    report = _valid_report()
    tampered = report.model_copy(
        update={"selected_candidate_id": report.candidate_aggregates[0].candidate_id}
    )

    with pytest.raises(ValueError, match="selected candidate"):
        verify_frozen_search_report(tampered)


def test_tampered_aggregate_is_rejected() -> None:
    report = _valid_report()
    rows = list(report.candidate_aggregates)
    rows[0] = rows[0].model_copy(
        update={"pooled_log_loss_improvement": rows[0].pooled_log_loss_improvement + 0.01}
    )
    tampered = report.model_copy(update={"candidate_aggregates": tuple(rows)})

    with pytest.raises(ValueError, match="pooled log-loss improvement"):
        verify_frozen_search_report(tampered)


def test_nonfinite_json_is_rejected_before_model_validation() -> None:
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        _parse_evidence_bytes(b'{"evidence_id": NaN}')


def test_full_synthetic_evidence_admission_recomputes_code_and_selector() -> None:
    repo_root = Path.cwd()
    evidence, bindings = _synthetic_evidence(repo_root)
    content = (
        json.dumps(evidence.canonical_payload(), sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")

    receipt = admit_search_evidence_bytes(
        content,
        repo_root=repo_root,
        bindings=bindings,
    )

    assert receipt.admission_status == "ADMITTED_FROZEN_DEVELOPMENT_SEARCH"
    assert receipt.selected_candidate_id == evidence.report.selected_candidate_id
    assert receipt.evidence_semantic_sha256 == evidence.semantic_sha256
    assert receipt.search_code_fingerprint_sha256 == evidence.search_code_fingerprint.sha256


def test_full_admission_rejects_source_binding_drift() -> None:
    repo_root = Path.cwd()
    evidence, bindings = _synthetic_evidence(repo_root)
    content = json.dumps(evidence.canonical_payload(), sort_keys=True).encode("utf-8")
    wrong = bindings.model_copy(update={"atp_source_manifest_sha256": "f" * 64})

    with pytest.raises(ValueError, match="ATP source-manifest identity"):
        admit_search_evidence_bytes(content, repo_root=repo_root, bindings=wrong)


def test_default_parent_code_binding_remains_frozen() -> None:
    observed = _code_fingerprint(Path.cwd())

    assert observed.sha256 == DEFAULT_ADMISSION_BINDINGS.parent_code_fingerprint_sha256
