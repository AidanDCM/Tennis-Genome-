from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench import (
    ChronologySemantics,
    DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    EvaluationSpec,
    ExposureGraph,
    ExposureKind,
    ExposureRecord,
    ForecastingProcedureSpec,
    ProcedureSearchFamily,
    build_canonical_evaluation_binding,
    fingerprint_code_components,
    fingerprint_match_population,
)


def _rows() -> list[dict[str, str]]:
    return [
        {
            "match_id": "m1",
            "event_time": "2026-01-01T12:00:00+00:00",
            "player_a_id": "a",
            "player_b_id": "b",
            "tour": "ATP",
        },
        {
            "match_id": "m2",
            "event_time": "2026-01-01T15:00:00+00:00",
            "player_a_id": "c",
            "player_b_id": "d",
            "tour": "ATP",
        },
    ]


def _procedure(*, exposure_ids: tuple[str, ...] = ("exp-dev",)) -> ForecastingProcedureSpec:
    return ForecastingProcedureSpec(
        procedure_id="proc-a",
        name="Simple challenger",
        version="1",
        input_contract="chronological-tennis-v2",
        feature_set=("core_probability",),
        training_method="logistic",
        calibration="identity",
        prediction_method="predict_proba",
        required_data=("core_probability",),
        development_exposure_ids=exposure_ids,
        source_code_sha="a" * 40,
        runtime_id="python-3.11-pinned",
        random_seed=7,
    )


def _graph() -> ExposureGraph:
    graph = ExposureGraph()
    graph.add(
        ExposureRecord(
            exposure_id="exp-dev",
            actor="researcher",
            source_ids=("history-development",),
            information_kinds=(ExposureKind.RAW_OUTCOMES,),
            description="Development-only fitting exposure.",
            decision_ids=("proc-a",),
        )
    )
    return graph


def test_dataset_fingerprint_binds_order_identity_and_availability() -> None:
    rows = _rows()
    first = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=rows,
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )
    second = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=deepcopy(rows),
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )

    assert first == second
    assert first.row_count == 2
    assert first.row_identity_sha256 == second.row_identity_sha256
    assert first.sha256 == second.sha256

    changed = deepcopy(rows)
    changed[1]["player_b_id"] = "different"
    changed_fingerprint = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=changed,
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )
    assert changed_fingerprint.row_identity_sha256 != first.row_identity_sha256


def test_dataset_fingerprint_fails_closed_on_duplicate_unsorted_or_naive_rows() -> None:
    rows = _rows()
    duplicate = deepcopy(rows)
    duplicate[1]["match_id"] = "m1"
    with pytest.raises(ValueError, match="duplicate match_id"):
        fingerprint_match_population(
            dataset_id="panel-v1",
            ordered_rows=duplicate,
            source_manifest_sha256="1" * 64,
            availability_contract_sha256="2" * 64,
            schema_version="canonical-v4",
        )

    unsorted = list(reversed(rows))
    with pytest.raises(ValueError, match="non-decreasing"):
        fingerprint_match_population(
            dataset_id="panel-v1",
            ordered_rows=unsorted,
            source_manifest_sha256="1" * 64,
            availability_contract_sha256="2" * 64,
            schema_version="canonical-v4",
        )

    naive = deepcopy(rows)
    naive[0]["event_time"] = "2026-01-01T12:00:00"
    with pytest.raises(ValueError, match="timezone-aware"):
        fingerprint_match_population(
            dataset_id="panel-v1",
            ordered_rows=naive,
            source_manifest_sha256="1" * 64,
            availability_contract_sha256="2" * 64,
            schema_version="canonical-v4",
        )


def test_code_fingerprint_is_deterministic_and_byte_sensitive() -> None:
    first = fingerprint_code_components(
        {
            "trainer.py": b"fit-v1",
            "evaluator.py": b"score-v1",
        }
    )
    second = fingerprint_code_components(
        {
            "evaluator.py": b"score-v1",
            "trainer.py": b"fit-v1",
        }
    )
    changed = fingerprint_code_components(
        {
            "trainer.py": b"fit-v2",
            "evaluator.py": b"score-v1",
        }
    )

    assert first == second
    assert first.sha256 != changed.sha256


def test_search_family_counts_full_attempt_universe_and_requires_freeze() -> None:
    family = ProcedureSearchFamily(
        family_id="challenger-baseline-001",
        research_question="Do simple challengers improve protected proper scores?",
        procedure_ids=("proc-a", "proc-b"),
        datasets_touched=("panel-v1",),
        unregistered_variant_count=3,
        parameter_search_count=10,
        feature_versions=("feature-contract-v1",),
        search_method="registered-grid",
        frozen=False,
    )

    assert family.total_trials == 15
    with pytest.raises(ValueError, match="frozen search family"):
        family.assert_canonical_claim_allowed(("proc-a", "proc-b"))

    frozen = family.model_copy(update={"frozen": True})
    with pytest.raises(ValueError, match="every registered procedure"):
        frozen.assert_canonical_claim_allowed(("proc-a",))
    frozen.assert_canonical_claim_allowed(("proc-a", "proc-b"))


def test_exposure_graph_fingerprint_changes_with_exposure_contents() -> None:
    first = _graph()
    second = _graph()
    assert first.semantic_sha256 == second.semantic_sha256

    second.add(
        ExposureRecord(
            exposure_id="exp-extra",
            actor="researcher",
            source_ids=("feature-summary-v2",),
            information_kinds=(ExposureKind.FEATURE_SUMMARY,),
            description="Additional feature inspection.",
        )
    )
    assert first.semantic_sha256 != second.semantic_sha256


def test_canonical_binding_requires_exact_dataset_family_and_exposure_identity() -> None:
    dataset = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=_rows(),
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )
    procedure = _procedure()
    evaluation = EvaluationSpec(
        evaluation_id="protected-001",
        dataset_version="panel-v1",
        population_sha256=dataset.row_identity_sha256,
        procedure_ids=("proc-a",),
        evaluation_role="PROTECTED",
        outcome_access_policy="SEALED_UNTIL_EVALUATION",
        protected_source_ids=("future-panel",),
    )
    family = ProcedureSearchFamily(
        family_id="family-001",
        research_question="Does proc-a improve protected proper scores?",
        procedure_ids=("proc-a",),
        datasets_touched=("panel-v1",),
        search_method="single-predeclared-procedure",
        frozen=True,
    )
    code = fingerprint_code_components(
        {
            "state.py": b"state-v1",
            "trainer.py": b"trainer-v1",
            "evaluator.py": b"evaluator-v1",
        }
    )
    graph = _graph()

    binding = build_canonical_evaluation_binding(
        procedure_spec=procedure,
        evaluation_spec=evaluation,
        dataset=dataset,
        code=code,
        exposure_graph=graph,
        search_family=family,
        constitution=DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
    )

    assert binding.procedure_spec_sha256 == procedure.semantic_sha256
    assert binding.evaluation_spec_sha256 == evaluation.semantic_sha256
    assert binding.dataset_fingerprint_sha256 == dataset.sha256
    assert binding.code_fingerprint_sha256 == code.sha256
    assert binding.exposure_graph_sha256 == graph.semantic_sha256
    assert binding.constitution_sha256 == DEFAULT_TENNIS_RESEARCH_CONSTITUTION.semantic_sha256

    wrong_family = family.model_copy(update={"datasets_touched": ("other-panel",)})
    with pytest.raises(ValueError, match="not declared"):
        build_canonical_evaluation_binding(
            procedure_spec=procedure,
            evaluation_spec=evaluation,
            dataset=dataset,
            code=code,
            exposure_graph=graph,
            search_family=wrong_family,
            constitution=DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
        )


def test_canonical_binding_rejects_unregistered_exposure_or_unfrozen_family() -> None:
    dataset = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=_rows(),
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )
    procedure = _procedure(exposure_ids=("missing",))
    evaluation = EvaluationSpec(
        evaluation_id="protected-001",
        dataset_version="panel-v1",
        population_sha256=dataset.row_identity_sha256,
        procedure_ids=("proc-a",),
        evaluation_role="PROTECTED",
        outcome_access_policy="SEALED_UNTIL_EVALUATION",
        protected_source_ids=("future-panel",),
    )
    family = ProcedureSearchFamily(
        family_id="family-001",
        research_question="Does proc-a improve protected proper scores?",
        procedure_ids=("proc-a",),
        datasets_touched=("panel-v1",),
        search_method="single-predeclared-procedure",
        frozen=True,
    )
    code = fingerprint_code_components({"trainer.py": b"trainer-v1"})

    with pytest.raises(ValueError, match="unregistered exposure"):
        build_canonical_evaluation_binding(
            procedure_spec=procedure,
            evaluation_spec=evaluation,
            dataset=dataset,
            code=code,
            exposure_graph=ExposureGraph(),
            search_family=family,
            constitution=DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
        )

    with pytest.raises(ValueError, match="frozen search family"):
        build_canonical_evaluation_binding(
            procedure_spec=_procedure(),
            evaluation_spec=evaluation,
            dataset=dataset,
            code=code,
            exposure_graph=_graph(),
            search_family=family.model_copy(update={"frozen": False}),
            constitution=DEFAULT_TENNIS_RESEARCH_CONSTITUTION,
        )


def test_fingerprint_models_reject_forged_digest() -> None:
    dataset = fingerprint_match_population(
        dataset_id="panel-v1",
        ordered_rows=_rows(),
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v4",
    )
    with pytest.raises(ValidationError, match="does not reproduce"):
        dataset.model_copy(update={"sha256": "f" * 64}, deep=True).__class__(
            **{**dataset.model_dump(), "sha256": "f" * 64}
        )



def test_date_only_fingerprint_preserves_source_precision_without_fake_time() -> None:
    rows = [
        {
            "match_id": "m1",
            "event_date": "2026-01-01",
            "player_a_id": "a",
            "player_b_id": "b",
            "tour": "ATP",
        },
        {
            "match_id": "m2",
            "event_date": "2026-01-01",
            "player_a_id": "c",
            "player_b_id": "d",
            "tour": "ATP",
        },
        {
            "match_id": "m3",
            "event_date": "2026-01-02",
            "player_a_id": "e",
            "player_b_id": "f",
            "tour": "ATP",
        },
    ]

    fingerprint = fingerprint_match_population(
        dataset_id="date-panel-v1",
        ordered_rows=rows,
        source_manifest_sha256="1" * 64,
        availability_contract_sha256="2" * 64,
        schema_version="canonical-v3",
        chronology_semantics=ChronologySemantics.EVENT_DATE_MATCH_ID,
    )

    assert fingerprint.chronology_semantics == ChronologySemantics.EVENT_DATE_MATCH_ID
    assert fingerprint.first_order_key == "2026-01-01|m1"
    assert fingerprint.last_order_key == "2026-01-02|m3"


def test_date_only_fingerprint_rejects_arbitrary_same_day_order() -> None:
    rows = [
        {
            "match_id": "m2",
            "event_date": "2026-01-01",
            "player_a_id": "a",
            "player_b_id": "b",
            "tour": "ATP",
        },
        {
            "match_id": "m1",
            "event_date": "2026-01-01",
            "player_a_id": "c",
            "player_b_id": "d",
            "tour": "ATP",
        },
    ]

    with pytest.raises(ValueError, match="registered chronology"):
        fingerprint_match_population(
            dataset_id="date-panel-v1",
            ordered_rows=rows,
            source_manifest_sha256="1" * 64,
            availability_contract_sha256="2" * 64,
            schema_version="canonical-v3",
            chronology_semantics=ChronologySemantics.EVENT_DATE_MATCH_ID,
        )


def test_exact_time_mode_does_not_accept_date_only_rows() -> None:
    rows = [
        {
            "match_id": "m1",
            "event_date": "2026-01-01",
            "player_a_id": "a",
            "player_b_id": "b",
            "tour": "ATP",
        }
    ]

    with pytest.raises(ValueError, match="requires event_time"):
        fingerprint_match_population(
            dataset_id="date-panel-v1",
            ordered_rows=rows,
            source_manifest_sha256="1" * 64,
            availability_contract_sha256="2" * 64,
            schema_version="canonical-v3",
        )
