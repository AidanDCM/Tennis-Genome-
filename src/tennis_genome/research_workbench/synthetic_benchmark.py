from __future__ import annotations

import hashlib
import json
import math

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import minimize

from .contracts import EvaluationSpec, ForecastingProcedureSpec, WorkbenchRecord
from .evaluation import EvaluationResult, evaluate_probabilities
from .exposure import ExposureGraph, ExposureKind, ExposureRecord
from .synthetic import SyntheticWorld


class SyntheticBenchmarkReport(WorkbenchRecord):
    """Protected known-truth comparison of simple forecasting procedures."""

    world_name: str
    world_seed: int
    train_n: int
    protected_n: int
    protected_population_sha256: str
    baseline: EvaluationResult
    calibration: EvaluationResult
    interaction: EvaluationResult


def _logit(probabilities: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.log(probabilities) - np.log1p(-probabilities)


def _sigmoid(values: NDArray[np.float64]) -> NDArray[np.float64]:
    return 1.0 / (1.0 + np.exp(-values))


def _fit_logistic(design: NDArray[np.float64], outcomes: NDArray[np.int_]) -> NDArray[np.float64]:
    if design.ndim != 2 or design.shape[0] != outcomes.shape[0]:
        raise ValueError("logistic design must align with outcomes")
    x = np.column_stack((np.ones(design.shape[0], dtype=float), design))
    y = outcomes.astype(float)

    def objective(parameters: NDArray[np.float64]) -> tuple[float, NDArray[np.float64]]:
        linear = x @ parameters
        loss = float(np.mean(np.logaddexp(0.0, linear) - y * linear))
        residual = _sigmoid(linear) - y
        gradient = np.mean(x * residual[:, None], axis=0)
        return loss, np.asarray(gradient, dtype=float)

    result = minimize(
        lambda parameters: objective(parameters)[0],
        np.zeros(x.shape[1], dtype=float),
        jac=lambda parameters: objective(parameters)[1],
        method="BFGS",
        options={"maxiter": 1000, "gtol": 1e-9},
    )
    if not result.success or not np.all(np.isfinite(result.x)) or not math.isfinite(result.fun):
        raise RuntimeError(f"synthetic challenger fit failed: {result.message}")
    return np.asarray(result.x, dtype=float)


def _predict_logistic(
    design: NDArray[np.float64], parameters: NDArray[np.float64]
) -> NDArray[np.float64]:
    x = np.column_stack((np.ones(design.shape[0], dtype=float), design))
    probabilities = _sigmoid(x @ parameters)
    if not np.all(np.isfinite(probabilities)):
        raise RuntimeError("synthetic challenger produced non-finite probabilities")
    return np.asarray(probabilities, dtype=float)


def _interaction_feature(world: SyntheticWorld) -> NDArray[np.float64]:
    positions = {name: index for index, name in enumerate(world.feature_names)}
    if "x1" in positions and "x2" in positions:
        left, right = positions["x1"], positions["x2"]
    elif len(world.feature_names) >= 2:
        left, right = 0, 1
    else:
        raise ValueError("interaction benchmark requires at least two features")
    return np.asarray(world.features[:, left] * world.features[:, right], dtype=float)


def _population_sha256(world: SyntheticWorld, split_index: int) -> str:
    hasher = hashlib.sha256()
    metadata = json.dumps(
        {
            "world": world.name,
            "seed": world.seed,
            "split_index": split_index,
            "protected_n": int(world.outcomes.shape[0] - split_index),
            "feature_names": world.feature_names,
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    hasher.update(metadata)
    for array in (
        world.features[split_index:],
        world.baseline_probability[split_index:],
        world.outcomes[split_index:],
    ):
        contiguous = np.ascontiguousarray(array)
        hasher.update(str(contiguous.dtype).encode("ascii"))
        hasher.update(str(contiguous.shape).encode("ascii"))
        hasher.update(contiguous.tobytes())
    return hasher.hexdigest()


def _procedure(
    *,
    procedure_id: str,
    name: str,
    feature_set: tuple[str, ...],
    training_method: str,
    prediction_method: str,
    exposure_id: str,
    source_code_sha: str,
) -> ForecastingProcedureSpec:
    return ForecastingProcedureSpec(
        procedure_id=procedure_id,
        name=name,
        version="synthetic-benchmark-v1",
        input_contract="synthetic-known-truth-v1",
        feature_set=feature_set,
        training_method=training_method,
        calibration="identity" if training_method == "none" else "logistic",
        prediction_method=prediction_method,
        required_data=("synthetic_pre_event_state",),
        development_exposure_ids=(exposure_id,),
        source_code_sha=source_code_sha,
        runtime_id="python-3.11-pinned",
        random_seed=None,
    )


def run_synthetic_benchmark(
    world: SyntheticWorld,
    *,
    source_code_sha: str,
    train_fraction: float = 0.60,
) -> SyntheticBenchmarkReport:
    """Fit simple challengers on development rows and score one protected holdout.

    The baseline uses the world-supplied forecast. The calibration challenger can only
    recalibrate the baseline logit. The interaction challenger additionally receives one
    explicit pairwise interaction. All three procedures are scored through the protected
    workbench evaluator, so the benchmark exercises exposure enforcement as well as model
    behavior.
    """

    n = int(world.outcomes.shape[0])
    if n < 200:
        raise ValueError("synthetic benchmark requires at least 200 observations")
    if not 0.50 <= train_fraction <= 0.80:
        raise ValueError("train_fraction must be between 0.50 and 0.80")
    split_index = int(n * train_fraction)
    if split_index <= 0 or split_index >= n:
        raise ValueError("train_fraction produced an empty train or protected partition")

    development_source = f"synthetic:{world.name}:{world.seed}:development"
    protected_source = f"synthetic:{world.name}:{world.seed}:protected"
    exposure_id = f"synthetic-fit:{world.name}:{world.seed}"
    graph = ExposureGraph()
    graph.add(
        ExposureRecord(
            exposure_id=exposure_id,
            actor="synthetic-benchmark-runner",
            source_ids=(development_source,),
            information_kinds=(ExposureKind.RAW_OUTCOMES,),
            description="Fit benchmark challengers using development outcomes only.",
            decision_ids=("synthetic-baseline", "synthetic-calibration", "synthetic-interaction"),
        )
    )

    baseline_spec = _procedure(
        procedure_id="synthetic-baseline",
        name="Synthetic baseline",
        feature_set=("baseline_probability",),
        training_method="none",
        prediction_method="world_supplied_probability",
        exposure_id=exposure_id,
        source_code_sha=source_code_sha,
    )
    calibration_spec = _procedure(
        procedure_id="synthetic-calibration",
        name="Synthetic calibration challenger",
        feature_set=("baseline_probability",),
        training_method="logistic_recalibration",
        prediction_method="fitted_logistic_recalibration",
        exposure_id=exposure_id,
        source_code_sha=source_code_sha,
    )
    interaction_spec = _procedure(
        procedure_id="synthetic-interaction",
        name="Synthetic interaction challenger",
        feature_set=("baseline_probability", "pairwise_interaction"),
        training_method="logistic_with_pairwise_interaction",
        prediction_method="fitted_logistic_interaction",
        exposure_id=exposure_id,
        source_code_sha=source_code_sha,
    )

    evaluation_spec = EvaluationSpec(
        evaluation_id=f"synthetic-protected:{world.name}:{world.seed}",
        dataset_version=f"synthetic:{world.name}:v1",
        population_sha256=_population_sha256(world, split_index),
        procedure_ids=(
            baseline_spec.procedure_id,
            calibration_spec.procedure_id,
            interaction_spec.procedure_id,
        ),
        evaluation_role="PROTECTED",
        outcome_access_policy="SEALED_UNTIL_EVALUATION",
        protected_source_ids=(protected_source,),
    )

    train = slice(0, split_index)
    protected = slice(split_index, n)
    baseline_logit = _logit(np.asarray(world.baseline_probability, dtype=float))
    calibration_parameters = _fit_logistic(
        baseline_logit[train, None], world.outcomes[train]
    )
    interaction_feature = _interaction_feature(world)
    interaction_parameters = _fit_logistic(
        np.column_stack((baseline_logit[train], interaction_feature[train])),
        world.outcomes[train],
    )

    protected_outcomes = world.outcomes[protected]
    baseline_probability = world.baseline_probability[protected]
    calibration_probability = _predict_logistic(
        baseline_logit[protected, None], calibration_parameters
    )
    interaction_probability = _predict_logistic(
        np.column_stack((baseline_logit[protected], interaction_feature[protected])),
        interaction_parameters,
    )

    return SyntheticBenchmarkReport(
        world_name=world.name,
        world_seed=world.seed,
        train_n=split_index,
        protected_n=n - split_index,
        protected_population_sha256=evaluation_spec.population_sha256,
        baseline=evaluate_probabilities(
            evaluation_spec=evaluation_spec,
            procedure_spec=baseline_spec,
            probabilities=baseline_probability,
            outcomes=protected_outcomes,
            exposure_graph=graph,
        ),
        calibration=evaluate_probabilities(
            evaluation_spec=evaluation_spec,
            procedure_spec=calibration_spec,
            probabilities=calibration_probability,
            outcomes=protected_outcomes,
            exposure_graph=graph,
        ),
        interaction=evaluate_probabilities(
            evaluation_spec=evaluation_spec,
            procedure_spec=interaction_spec,
            probabilities=interaction_probability,
            outcomes=protected_outcomes,
            exposure_graph=graph,
        ),
    )
