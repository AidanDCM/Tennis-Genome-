from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from tennis_genome.research_workbench import (
    EvaluationSpec,
    ExposureGraph,
    ExposureKind,
    ExposureRecord,
    ForecastingProcedureSpec,
    ImmutableResearchRegistry,
    evaluate_probabilities,
    interaction_world,
    miscalibration_world,
    null_world,
)


def _procedure(**overrides: object) -> ForecastingProcedureSpec:
    payload: dict[str, object] = {
        "procedure_id": "proc-calibration-v1",
        "name": "Calibration challenger",
        "version": "1",
        "input_contract": "chronological-tennis-v2",
        "feature_set": ("core_probability", "surface"),
        "training_method": "logistic_calibration",
        "hyperparameters_json": '{"l2":1.0,"max_iter":200}',
        "calibration": "logistic",
        "prediction_method": "predict_proba",
        "required_data": ("core_probability", "surface"),
        "development_exposure_ids": (),
        "parent_procedure_ids": (),
        "source_code_sha": "6cc945f6883e470a53f3b18b504968cd99bd8a99",
        "runtime_id": "python-3.11-pinned",
        "random_seed": 20260913,
    }
    payload.update(overrides)
    return ForecastingProcedureSpec(**payload)


def _evaluation(*, role: str = "DEVELOPMENT") -> EvaluationSpec:
    return EvaluationSpec(
        evaluation_id="eval-001",
        dataset_version="chronological-panel-v1",
        population_sha256="a" * 64,
        procedure_ids=("proc-calibration-v1",),
        evaluation_role=role,
        outcome_access_policy=(
            "SEALED_UNTIL_EVALUATION" if role == "PROTECTED" else "OUTCOMES_VISIBLE"
        ),
    )


def test_procedure_spec_is_canonical_and_frozen() -> None:
    first = _procedure(hyperparameters_json='{ "max_iter": 200, "l2": 1.0 }')
    second = _procedure(hyperparameters_json='{"l2":1.0,"max_iter":200}')

    assert first.hyperparameters_json == '{"l2":1.0,"max_iter":200}'
    assert first.semantic_sha256 == second.semantic_sha256
    with pytest.raises(ValidationError):
        first.name = "mutated"  # type: ignore[misc]


def test_independent_procedure_rejects_downstream_market_semantics() -> None:
    with pytest.raises(ValidationError, match="downstream market semantics"):
        _procedure(feature_set=("core_probability", "bookmaker_odds"))


def test_protected_evaluation_requires_sealed_outcomes() -> None:
    with pytest.raises(ValidationError, match="protected evaluations"):
        EvaluationSpec(
            evaluation_id="protected-001",
            dataset_version="future-panel-v1",
            population_sha256="b" * 64,
            procedure_ids=("proc-calibration-v1",),
            evaluation_role="PROTECTED",
            outcome_access_policy="OUTCOMES_VISIBLE",
        )


def test_exposure_graph_inherits_sources_and_blocks_false_independence() -> None:
    graph = ExposureGraph()
    graph.add(
        ExposureRecord(
            exposure_id="exp-root",
            actor="researcher",
            source_ids=("history-2010-2018",),
            information_kinds=(ExposureKind.RESIDUAL_ANALYSIS,),
            description="Reviewed residual structure.",
            decision_ids=("add-trajectory-family",),
        )
    )
    graph.add(
        ExposureRecord(
            exposure_id="exp-child",
            actor="procedure-designer",
            source_ids=("feature-catalog-v1",),
            information_kinds=(ExposureKind.FEATURE_SUMMARY,),
            description="Designed challenger after residual review.",
            parent_exposure_ids=("exp-root",),
            decision_ids=("proc-v2",),
        )
    )

    assert graph.ancestors("exp-child") == frozenset({"exp-root"})
    assert graph.inherited_source_ids("exp-child") == frozenset(
        {"history-2010-2018", "feature-catalog-v1"}
    )
    with pytest.raises(ValueError, match="not independent"):
        graph.assert_independent(
            exposure_ids=("exp-child",),
            protected_source_ids=("history-2010-2018",),
        )


def test_exposure_graph_requires_registered_parents() -> None:
    graph = ExposureGraph()
    with pytest.raises(ValueError, match="registered first"):
        graph.add(
            ExposureRecord(
                exposure_id="child",
                actor="researcher",
                source_ids=("source",),
                information_kinds=(ExposureKind.SOURCE_METADATA,),
                description="invalid child",
                parent_exposure_ids=("missing",),
            )
        )


def test_probability_evaluation_uses_registered_proper_scores() -> None:
    result = evaluate_probabilities(
        evaluation_spec=_evaluation(),
        procedure_id="proc-calibration-v1",
        probabilities=[0.8, 0.3],
        outcomes=[1, 0],
    )

    assert result.n == 2
    assert math.isclose(result.brier, 0.065)
    assert math.isclose(result.log_loss, -(math.log(0.8) + math.log(0.7)) / 2.0)
    assert result.mean_prediction == pytest.approx(0.55)
    assert result.observed_rate == pytest.approx(0.5)


def test_probability_evaluation_rejects_non_finite_or_boundary_probabilities() -> None:
    spec = _evaluation()
    with pytest.raises(ValueError, match="finite"):
        evaluate_probabilities(
            evaluation_spec=spec,
            procedure_id="proc-calibration-v1",
            probabilities=[0.6, float("nan")],
            outcomes=[1, 0],
        )
    with pytest.raises(ValueError, match="strictly between"):
        evaluate_probabilities(
            evaluation_spec=spec,
            procedure_id="proc-calibration-v1",
            probabilities=[1.0, 0.4],
            outcomes=[1, 0],
        )


def test_registry_is_content_addressed_idempotent_and_tamper_evident(tmp_path: Path) -> None:
    registry = ImmutableResearchRegistry(tmp_path / "registry")
    procedure = _procedure()

    path = registry.register("procedures", procedure)
    assert path.name == f"{procedure.semantic_sha256}.json"
    first_payload = json.loads(path.read_text(encoding="utf-8"))
    assert first_payload["semantic_sha256"] == procedure.semantic_sha256
    assert registry.register("procedures", procedure) == path

    path.write_text("{}\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="modified"):
        registry.register("procedures", procedure)


def test_synthetic_worlds_are_reproducible_and_immutable() -> None:
    first = null_world(n=1000, seed=7)
    second = null_world(n=1000, seed=7)
    assert np.array_equal(first.features, second.features)
    assert np.array_equal(first.outcomes, second.outcomes)
    assert np.array_equal(first.baseline_probability, first.true_probability)
    assert not first.features.flags.writeable

    miscalibrated = miscalibration_world(n=1000, seed=7)
    assert float(np.mean(np.abs(miscalibrated.true_probability - miscalibrated.baseline_probability))) > 0.02

    interaction = interaction_world(n=1000, seed=7)
    assert float(np.mean(np.abs(interaction.true_probability - interaction.baseline_probability))) > 0.05
    with pytest.raises(ValueError):
        interaction.features[0, 0] = 999.0
