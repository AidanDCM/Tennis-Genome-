from __future__ import annotations

import math

import numpy as np
from pydantic import field_validator

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .exposure import ExposureGraph


class EvaluationResult(WorkbenchRecord):
    """Reproducible proper-score summary for one procedure on one frozen evaluation."""

    evaluation_spec_sha256: str
    procedure_spec_sha256: str
    evaluation_id: str
    procedure_id: str
    n: int
    brier: float
    log_loss: float
    mean_prediction: float
    observed_rate: float

    @field_validator("n")
    @classmethod
    def _positive_n(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("n must be positive")
        return value


def _as_valid_arrays(
    probabilities: np.ndarray | list[float] | tuple[float, ...],
    outcomes: np.ndarray | list[int] | tuple[int, ...],
) -> tuple[np.ndarray, np.ndarray]:
    probability_array = np.asarray(probabilities, dtype=float)
    outcome_array = np.asarray(outcomes, dtype=float)
    if probability_array.ndim != 1 or outcome_array.ndim != 1:
        raise ValueError("probabilities and outcomes must be one-dimensional")
    if probability_array.size == 0 or probability_array.size != outcome_array.size:
        raise ValueError("probabilities and outcomes must have the same non-zero length")
    if not np.isfinite(probability_array).all() or not np.isfinite(outcome_array).all():
        raise ValueError("probabilities and outcomes must be finite")
    if ((probability_array <= 0.0) | (probability_array >= 1.0)).any():
        raise ValueError("probabilities must be strictly between zero and one")
    if not np.isin(outcome_array, (0.0, 1.0)).all():
        raise ValueError("outcomes must be binary zero/one values")
    return probability_array, outcome_array


def _enforce_evaluation_integrity(
    *,
    evaluation_spec: EvaluationSpec,
    procedure_spec: ForecastingProcedureSpec,
    exposure_graph: ExposureGraph | None,
) -> None:
    if procedure_spec.procedure_id not in evaluation_spec.procedure_ids:
        raise ValueError(
            f"procedure_id {procedure_spec.procedure_id!r} is not registered in this evaluation"
        )

    exposure_ids = procedure_spec.development_exposure_ids
    if exposure_ids:
        if exposure_graph is None:
            raise ValueError("procedure exposure lineage requires an ExposureGraph")
        exposure_graph.assert_registered(exposure_ids)

    if evaluation_spec.evaluation_role != "PROTECTED":
        return

    if exposure_graph is None:
        raise ValueError("protected evaluation requires an ExposureGraph")
    if not exposure_ids:
        raise ValueError("protected evaluation requires explicit procedure exposure lineage")
    exposure_graph.assert_independent(
        exposure_ids=exposure_ids,
        protected_source_ids=evaluation_spec.protected_source_ids,
    )


def evaluate_probabilities(
    *,
    evaluation_spec: EvaluationSpec,
    procedure_spec: ForecastingProcedureSpec,
    probabilities: np.ndarray | list[float] | tuple[float, ...],
    outcomes: np.ndarray | list[int] | tuple[int, ...],
    exposure_graph: ExposureGraph | None = None,
) -> EvaluationResult:
    """Evaluate one complete forecasting procedure using registered proper scores.

    Protected evaluation is fail-closed: the procedure must carry explicit, registered
    exposure lineage and that lineage must be independent of every protected source.
    """

    _enforce_evaluation_integrity(
        evaluation_spec=evaluation_spec,
        procedure_spec=procedure_spec,
        exposure_graph=exposure_graph,
    )
    p, y = _as_valid_arrays(probabilities, outcomes)
    brier = float(np.mean((p - y) ** 2))
    log_loss = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log1p(-p)))
    values = (brier, log_loss, float(np.mean(p)), float(np.mean(y)))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("evaluation produced a non-finite metric")
    return EvaluationResult(
        evaluation_spec_sha256=evaluation_spec.semantic_sha256,
        procedure_spec_sha256=procedure_spec.semantic_sha256,
        evaluation_id=evaluation_spec.evaluation_id,
        procedure_id=procedure_spec.procedure_id,
        n=int(p.size),
        brier=brier,
        log_loss=log_loss,
        mean_prediction=float(np.mean(p)),
        observed_rate=float(np.mean(y)),
    )
