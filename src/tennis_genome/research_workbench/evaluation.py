from __future__ import annotations

import math

import numpy as np
from pydantic import field_validator

from .contracts import EvaluationSpec, WorkbenchRecord


class EvaluationResult(WorkbenchRecord):
    """Reproducible proper-score summary for one procedure on one frozen evaluation."""

    evaluation_spec_sha256: str
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


def evaluate_probabilities(
    *,
    evaluation_spec: EvaluationSpec,
    procedure_id: str,
    probabilities: np.ndarray | list[float] | tuple[float, ...],
    outcomes: np.ndarray | list[int] | tuple[int, ...],
) -> EvaluationResult:
    """Evaluate one complete forecasting procedure using registered proper scores."""

    if procedure_id not in evaluation_spec.procedure_ids:
        raise ValueError(f"procedure_id {procedure_id!r} is not registered in this evaluation")
    p, y = _as_valid_arrays(probabilities, outcomes)
    brier = float(np.mean((p - y) ** 2))
    log_loss = float(-np.mean(y * np.log(p) + (1.0 - y) * np.log1p(-p)))
    values = (brier, log_loss, float(np.mean(p)), float(np.mean(y)))
    if not all(math.isfinite(value) for value in values):
        raise ValueError("evaluation produced a non-finite metric")
    return EvaluationResult(
        evaluation_spec_sha256=evaluation_spec.semantic_sha256,
        evaluation_id=evaluation_spec.evaluation_id,
        procedure_id=procedure_id,
        n=int(p.size),
        brier=brier,
        log_loss=log_loss,
        mean_prediction=float(np.mean(p)),
        observed_rate=float(np.mean(y)),
    )
