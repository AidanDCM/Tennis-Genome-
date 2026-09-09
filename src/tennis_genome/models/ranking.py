from __future__ import annotations

from dataclasses import dataclass
from math import log

import numpy as np
from sklearn.linear_model import LogisticRegression


@dataclass
class RankingLogitModel:
    """Calibrate ranking differences into win probabilities.

    The raw feature is log(rank_b / rank_a): positive values mean Player A has
    the better (numerically smaller) rank. Coefficients must be fitted only on
    historical matches preceding the evaluation fold.
    """

    c: float = 1.0
    max_iter: int = 1000

    def __post_init__(self) -> None:
        self._model: LogisticRegression | None = None

    @staticmethod
    def feature(rank_a: int, rank_b: int) -> float:
        if rank_a <= 0 or rank_b <= 0:
            raise ValueError("rank values must be positive")
        return log(rank_b / rank_a)

    def fit(self, rank_pairs: list[tuple[int, int]], outcomes: list[bool]) -> RankingLogitModel:
        if len(rank_pairs) != len(outcomes) or not rank_pairs:
            raise ValueError("rank_pairs and outcomes must have equal non-zero length")
        labels = {bool(value) for value in outcomes}
        if len(labels) < 2:
            raise ValueError("ranking calibration requires both outcome classes")

        x = np.asarray([[self.feature(a, b)] for a, b in rank_pairs], dtype=float)
        y = np.asarray([1 if outcome else 0 for outcome in outcomes], dtype=int)
        model = LogisticRegression(C=self.c, max_iter=self.max_iter, solver="lbfgs")
        model.fit(x, y)
        self._model = model
        return self

    def predict_proba(self, rank_a: int | None, rank_b: int | None) -> float | None:
        if rank_a is None or rank_b is None:
            return None
        if self._model is None:
            raise RuntimeError("model must be fitted before prediction")
        x = np.asarray([[self.feature(rank_a, rank_b)]], dtype=float)
        return float(self._model.predict_proba(x)[0, 1])
