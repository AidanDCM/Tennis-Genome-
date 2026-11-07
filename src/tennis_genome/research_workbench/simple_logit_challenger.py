"""A deliberately small, market-blind research challenger.

The ranking arm is exploratory until each target ranking has independent T0 evidence.
This module does not change the sealed production predictor.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

import numpy as np
from sklearn.linear_model import LogisticRegression

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.features.foundational import FoundationalSnapshot

BASE_FEATURES = (
    "elo_logit",
    "serve_return_edge",
    "form_result_30_diff",
    "form_point_30_diff",
    "minutes_14_diff",
    "event_gap_days_diff",
    "age_diff",
    "age_curve_diff",
    "height_diff",
    "left_hand_diff",
    "best_of_five_elo",
    "surface_hard_elo",
    "surface_clay_elo",
    "surface_grass_elo",
)
RANK_FEATURES = ("rank_log_ratio", "rank_points_log_ratio")


@dataclass(frozen=True)
class ChallengerExample:
    snapshot: FoundationalSnapshot
    state: PreMatchState
    outcome_a: bool | None = None


def _feature_row(example: ChallengerExample, *, include_rank: bool) -> np.ndarray:
    if example.snapshot.match_id != example.state.match_id:
        raise ValueError("snapshot and pre-match state identify different matches")
    if example.snapshot.event_date != example.state.event_date:
        raise ValueError("snapshot and pre-match state have different event dates")
    values = []
    for name in BASE_FEATURES:
        value = getattr(example.snapshot, name)
        number = 0.0 if value is None else float(value)
        if not math.isfinite(number):
            raise ValueError(f"non-finite feature: {name}")
        values.append(number)
    if include_rank:
        a, b = example.state.rank_a, example.state.rank_b
        pa, pb = example.state.rank_points_a, example.state.rank_points_b
        if any(
            value is None or not math.isfinite(float(value)) or value <= 0
            for value in (a, b, pa, pb)
        ):
            raise ValueError("ranking arm requires positive ranks and points for both players")
        assert a is not None and b is not None and pa is not None and pb is not None
        values.extend((math.log(b / a), math.log(pa / pb)))
    return np.asarray(values, dtype=float)


class SimpleLogitChallenger:
    """Fit mirrored player differences with no intercept or mean centering."""

    def __init__(self, *, include_rank: bool = False, c: float = 0.5) -> None:
        if not math.isfinite(c) or c <= 0:
            raise ValueError("regularization C must be finite and positive")
        self.include_rank = include_rank
        self.c = c
        self._scale: np.ndarray | None = None
        self._model: LogisticRegression | None = None
        self._training_end: date | None = None

    @property
    def feature_names(self) -> tuple[str, ...]:
        return BASE_FEATURES + RANK_FEATURES if self.include_rank else BASE_FEATURES

    def fit(self, examples: Sequence[ChallengerExample]) -> SimpleLogitChallenger:
        if not examples or any(example.outcome_a is None for example in examples):
            raise ValueError("training requires nonempty labeled examples")
        x = np.vstack([_feature_row(row, include_rank=self.include_rank) for row in examples])
        y = np.asarray([bool(row.outcome_a) for row in examples], dtype=int)
        scale = np.std(x, axis=0)
        scale[scale == 0] = 1.0
        x_scaled = x / scale
        mirrored_x = np.vstack((x_scaled, -x_scaled))
        mirrored_y = np.concatenate((y, 1 - y))
        model = LogisticRegression(C=self.c, fit_intercept=False, max_iter=1000)
        model.fit(mirrored_x, mirrored_y)
        self._scale = scale
        self._model = model
        self._training_end = max(row.snapshot.event_date for row in examples)
        return self

    def predict_probability_a(self, example: ChallengerExample) -> float:
        if self._model is None or self._scale is None:
            raise RuntimeError("challenger must be fitted before prediction")
        if self._training_end is not None and example.snapshot.event_date <= self._training_end:
            raise ValueError("target must occur after every training match date")
        x = _feature_row(example, include_rank=self.include_rank) / self._scale
        return float(self._model.predict_proba(x.reshape(1, -1))[0, 1])
