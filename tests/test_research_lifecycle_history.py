from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from tennis_genome.research_workbench import (
    DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    EvaluationResult,
    EvaluationSpec,
    ExposureGraph,
    ExposureKind,
    ExposureRecord,
    ForecastingProcedureSpec,
    ProcedureSearchFamily,
    ProtectedOpenReceipt,
    ResearchLifecycleLedger,
    build_canonical_evaluation_binding,
    fingerprint_code_components,
    fingerprint_match_population,
)


def _procedure() -> ForecastingProcedureSpec:
    return ForecastingProcedureSpec(
        procedure_id="proc-a",
        name="Lifecycle challenger",
        version="1",
        input_contract="chronological-tennis-v2",
        feature_set=("core_probability",),
        training_method="logistic",
        calibration="identity",
        prediction_method="predict_proba",
        required_data=("core_probability",),
        development_exposure_ids=("exp-development",),
        source_code_sha="a" * 40,
        runtime_id="python-3.11-pinned",
        random_seed=7,
    )


def _evaluation(procedure: ForecastingProcedureSpec) -> EvaluationSpec:
    dataset = _dataset()
    return EvaluationSpec(
        evaluation_id="eval-protected-001",
        dataset_version="panel-v1",
        population_sha256=dataset.row_identity_sha256,
        procedure_ids=(procedure.procedure_id,),
        evaluation_role="PROTECTED",
        outcome_access_policy="SEALED_UNTIL_EVALUATION",
        protected_source_ids=("protected-panel",),
    )


def _family(*, frozen: bool) -> ProcedureSearchFamily:
    return ProcedureSearchFamily(
        family_id="family-001",
        research_question="Does proc-a improve protected proper scores?",
        procedure_ids=("proc-a",),
        datasets_touched=("panel-v1",),
        search_method="single-predeclared-procedure",
        frozen=frozen,
    )


def _dataset():
    return fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=(
            {
                "match_id": "m1",
                "event_time": "2026-01-01T12:00:00+00:00",
                "player_a_id": "a",
                "player_b_id": "b",
                "tour": "ATP",
            },
        ),
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )


def _graph() -> ExposureGraph:
    graph = ExposureGraph()
    graph.add(
        ExposureRecord(
            exposure_id="exp-development",
            actor="researcher",
            source_ids=("history-development",),
            information_kinds=(ExposureKind.RAW_OUTCOMES,),
            description="Development exposure.",
            decision_ids=("proc-a",),
        )
    )
    return graph


def _binding(
    procedure: ForecastingProcedureSpec,
    evaluation: EvaluationSpec,
    family: ProcedureSearchFamily,
):
    return build_canonical_evaluation_binding(
        procedure_spec=procedure,
        evaluation_spec=evaluation,
        dataset=_dataset(),
        code=fingerprint_code_components({"trainer.py": b"v1"}),
        exposure_graph=_graph(),
        search_family=family,
        constitution=DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    )


def _result(
    procedure: ForecastingProcedureSpec,
    evaluation: EvaluationSpec,
) -> EvaluationResult:
    return EvaluationResult(
        evaluation_spec_sha256=evaluation.semantic_sha256,
        procedure_spec_sha256=procedure.semantic_sha256,
        evaluation_id=evaluation.evaluation_id,
        procedure_id=procedure.procedure_id,
        n=100,
        brier=0.20,
        log_loss=0.58,
        mean_prediction=0.52,
        observed_rate=0.51,
    )


def _receipt(evaluation: EvaluationSpec) -> ProtectedOpenReceipt:
    return ProtectedOpenReceipt(
        schema_version="tennis-workbench-protected-open-v1",
        dataset_id="panel-v1",
        protected_source_id="protected-panel",
        content_sha256="4" * 64,
        evaluation_id=evaluation.evaluation_id,
        procedure_ids=evaluation.procedure_ids,
        purpose="one protected evaluation",
        human_approver="reviewer",
        opened_at_utc="2026-09-14T05:00:00+00:00",
        irreversible=True,
        boundary_status="OS_CREDENTIAL_ENFORCED",
    )


def _ledger(tmp_path: Path) -> ResearchLifecycleLedger:
    return ResearchLifecycleLedger(
        tmp_path / "history",
        now=lambda: datetime(2026, 9, 14, 5, 0, tzinfo=UTC),
    )


def _register_through_freeze(
    ledger: ResearchLifecycleLedger,
) -> tuple[
    ForecastingProcedureSpec,
    EvaluationSpec,
    ProcedureSearchFamily,
]:
    procedure = _procedure()
    evaluation = _evaluation(procedure)
    open_family = _family(frozen=False)
    frozen_family = _family(frozen=True)

    ledger.register_procedure(procedure)
    ledger.register_evaluation(evaluation)
    ledger.register_search_family(open_family)
    ledger.freeze_search_family(frozen_family, reason="search family frozen before results")
    return procedure, evaluation, frozen_family


def test_empty_history_is_not_reported_as_verified_pass(tmp_path: Path) -> None:
    audit = _ledger(tmp_path).verify()

    assert audit.status == "EMPTY"
    assert audit.event_count == 0


def test_complete_protected_lifecycle_replays_and_verifies(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    procedure, evaluation, family = _register_through_freeze(ledger)

    ledger.record_protected_open(_receipt(evaluation))
    ledger.record_result(
        _result(procedure, evaluation),
        binding=_binding(procedure, evaluation, family),
    )
    ledger.close_evaluation(
        evaluation,
        verdict="NO_IMPROVEMENT",
        reason="candidate did not clear the frozen promotion threshold",
    )

    audit = ledger.verify()
    assert audit.status == "PASS"
    assert audit.event_count == 7
    assert audit.procedure_count == 1
    assert audit.evaluation_count == 1
    assert audit.family_count == 1
    assert audit.protected_open_count == 1
    assert audit.result_count == 1
    assert audit.closed_evaluation_count == 1


def test_protected_result_cannot_be_recorded_before_irreversible_open(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    procedure, evaluation, family = _register_through_freeze(ledger)

    with pytest.raises(ValueError, match="before irreversible open"):
        ledger.record_result(
            _result(procedure, evaluation),
            binding=_binding(procedure, evaluation, family),
        )

    assert ledger.verify().event_count == 4


def test_result_requires_frozen_registered_search_family(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    procedure = _procedure()
    evaluation = _evaluation(procedure)
    frozen_family = _family(frozen=True)

    ledger.register_procedure(procedure)
    ledger.register_evaluation(evaluation)
    ledger.record_protected_open(_receipt(evaluation))

    with pytest.raises(ValueError, match="frozen registered search family"):
        ledger.record_result(
            _result(procedure, evaluation),
            binding=_binding(procedure, evaluation, frozen_family),
        )


def test_close_requires_every_registered_procedure_result(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    _, evaluation, _ = _register_through_freeze(ledger)
    ledger.record_protected_open(_receipt(evaluation))

    with pytest.raises(ValueError, match="every registered procedure"):
        ledger.close_evaluation(
            evaluation,
            verdict="INCONCLUSIVE",
            reason="attempted early close",
        )


def test_search_family_cannot_change_while_freezing(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    procedure = _procedure()
    ledger.register_procedure(procedure)
    ledger.register_search_family(_family(frozen=False))

    changed = _family(frozen=True).model_copy(
        update={"parameter_search_count": 1}
    )
    with pytest.raises(ValueError, match="changed while being frozen"):
        ledger.freeze_search_family(changed, reason="invalid mutation")


def test_protected_open_requires_enforced_boundary_and_registered_source(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    procedure = _procedure()
    evaluation = _evaluation(procedure)
    ledger.register_procedure(procedure)
    ledger.register_evaluation(evaluation)

    weak = _receipt(evaluation)
    weak = ProtectedOpenReceipt(
        **{
            **asdict_receipt(weak),
            "boundary_status": "NOT_PHYSICALLY_ENFORCED",
        }
    )
    with pytest.raises(ValueError, match="credential-enforced"):
        ledger.record_protected_open(weak)

    wrong_source = ProtectedOpenReceipt(
        **{
            **asdict_receipt(_receipt(evaluation)),
            "protected_source_id": "other-source",
        }
    )
    with pytest.raises(ValueError, match="not registered"):
        ledger.record_protected_open(wrong_source)


def asdict_receipt(receipt: ProtectedOpenReceipt) -> dict[str, object]:
    return {
        "schema_version": receipt.schema_version,
        "dataset_id": receipt.dataset_id,
        "protected_source_id": receipt.protected_source_id,
        "content_sha256": receipt.content_sha256,
        "evaluation_id": receipt.evaluation_id,
        "procedure_ids": receipt.procedure_ids,
        "purpose": receipt.purpose,
        "human_approver": receipt.human_approver,
        "opened_at_utc": receipt.opened_at_utc,
        "irreversible": receipt.irreversible,
        "boundary_status": receipt.boundary_status,
    }


def test_closed_evaluation_can_be_invalidated_but_not_reopened(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    procedure, evaluation, family = _register_through_freeze(ledger)
    ledger.record_protected_open(_receipt(evaluation))
    ledger.record_result(
        _result(procedure, evaluation),
        binding=_binding(procedure, evaluation, family),
    )
    ledger.close_evaluation(
        evaluation,
        verdict="PROMOTED",
        reason="frozen gate passed",
    )
    ledger.invalidate_evaluation(
        evaluation,
        reason="later audit found an analysis implementation defect",
    )

    audit = ledger.verify()
    assert audit.invalidated_evaluation_count == 1

    with pytest.raises(ValueError, match="invalidated more than once"):
        ledger.invalidate_evaluation(evaluation, reason="duplicate")


def test_history_tampering_is_detected_before_any_new_append(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    procedure = _procedure()
    ledger.register_procedure(procedure)

    event_path = next((tmp_path / "history" / "events").glob("*.json"))
    payload = json.loads(event_path.read_text(encoding="utf-8"))
    payload["event"]["subject_id"] = "rewritten"
    event_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="digest mismatch"):
        ledger.verify()

    with pytest.raises(ValueError, match="digest mismatch"):
        ledger.register_evaluation(_evaluation(procedure))
