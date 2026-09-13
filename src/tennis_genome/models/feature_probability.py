from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler

from tennis_genome.features.foundational import FoundationalSnapshot


@dataclass(frozen=True)
class FittedFeatureModelMetadata:
    feature_names: tuple[str, ...]
    training_rows: int
    positive_rows: int
    negative_rows: int


def _snapshot_matrix(
    snapshots: Iterable[FoundationalSnapshot],
    feature_names: tuple[str, ...],
) -> list[list[float]]:
    matrix: list[list[float]] = []
    for snapshot in snapshots:
        row: list[float] = []
        for name in feature_names:
            value = getattr(snapshot, name)
            row.append(float("nan") if value is None else float(value))
        matrix.append(row)
    return matrix


def _pipeline() -> Pipeline:
    return make_pipeline(
        SimpleImputer(
            strategy="median",
            add_indicator=True,
            keep_empty_features=True,
        ),
        StandardScaler(),
        LogisticRegression(C=1.0, solver="lbfgs", max_iter=1000),
    )


class FeatureProbabilityModel:
    """Frozen predictive mapping from pre-match snapshots to probabilities.

    Dynamic tennis state belongs in ``FoundationalSnapshot`` construction. This
    class owns only the fitted mapping from those legal pre-match features to a
    probability, making it possible to freeze coefficients while player state
    continues to evolve during a forward holdout or live deployment.
    """

    def __init__(self, feature_names: Iterable[str]) -> None:
        names = tuple(feature_names)
        if not names:
            raise ValueError("at least one feature is required")
        if len(set(names)) != len(names):
            raise ValueError("feature names must be unique")
        self.feature_names = names
        self._pipeline: Pipeline | None = None
        self._metadata: FittedFeatureModelMetadata | None = None

    @property
    def is_fitted(self) -> bool:
        return self._pipeline is not None

    @property
    def metadata(self) -> FittedFeatureModelMetadata:
        if self._metadata is None:
            raise RuntimeError("model is not fitted")
        return self._metadata

    def fit(
        self,
        snapshots: Iterable[FoundationalSnapshot],
        outcomes_a: Iterable[bool],
    ) -> FeatureProbabilityModel:
        snapshot_list = list(snapshots)
        outcomes = [bool(value) for value in outcomes_a]
        if len(snapshot_list) != len(outcomes):
            raise ValueError("snapshot and outcome lengths must match")
        if not snapshot_list:
            raise ValueError("training data is empty")
        positive_rows = sum(outcomes)
        negative_rows = len(outcomes) - positive_rows
        if positive_rows == 0 or negative_rows == 0:
            raise ValueError("training data must contain both outcome classes")

        pipeline = _pipeline()
        pipeline.fit(
            _snapshot_matrix(snapshot_list, self.feature_names),
            [int(value) for value in outcomes],
        )
        self._pipeline = pipeline
        self._metadata = FittedFeatureModelMetadata(
            feature_names=self.feature_names,
            training_rows=len(outcomes),
            positive_rows=positive_rows,
            negative_rows=negative_rows,
        )
        return self

    def predict_probabilities(
        self,
        snapshots: Iterable[FoundationalSnapshot],
    ) -> list[float]:
        if self._pipeline is None:
            raise RuntimeError("model is not fitted")
        snapshot_list = list(snapshots)
        if not snapshot_list:
            return []
        return self._pipeline.predict_proba(_snapshot_matrix(snapshot_list, self.feature_names))[
            :, 1
        ].tolist()
