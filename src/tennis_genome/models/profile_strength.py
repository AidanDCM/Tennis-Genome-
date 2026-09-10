from __future__ import annotations

from dataclasses import dataclass
from math import exp, log

import numpy as np
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

from tennis_genome.data.canonical import Tour
from tennis_genome.profiles.features import (
    profile_strength_feature_names,
    profile_strength_feature_values,
)
from tennis_genome.profiles.state import MatchProfilePair, PlayerProfileSnapshot
from tennis_genome.ratings.elo import EloConfig, expected_score


@dataclass(frozen=True)
class ProfileStrengthPrediction:
    match_id: str
    probability_a: float
    profile_score_a: float
    profile_score_b: float
    elo_probability_a: float
    elo_score_a: float
    elo_score_b: float
    profile_gap_a: float
    profile_gap_b: float
    profile_gap_match: float


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        z = exp(-value)
        return 1.0 / (1.0 + z)
    z = exp(value)
    return z / (1.0 + z)


def elo_strength_coordinate(
    rating: float,
    *,
    config: EloConfig | None = None,
) -> float:
    """Map an absolute Elo rating to its individual log-odds coordinate."""
    cfg = config or EloConfig()
    return (rating - cfg.initial_rating) * log(10.0) / cfg.scale


class ProfileStrengthModel:
    """Pairwise symmetric scalar-strength model over Player Profile v1.

    Preprocessing is fit on player-side training profiles only. Player A and B
    are transformed separately, the model trains on `z_a - z_b`, and logistic
    regression has no intercept. The learned decision logit is therefore exactly
    `S_profile(A) - S_profile(B)` and swapping player order inverts probability.
    """

    def __init__(
        self,
        tour: Tour,
        *,
        include_conditional: bool = False,
        elo_config: EloConfig | None = None,
    ) -> None:
        self.tour = tour
        self.include_conditional = include_conditional
        self.elo_config = elo_config or EloConfig()
        self.feature_names = profile_strength_feature_names(
            tour,
            include_conditional=include_conditional,
        )
        self._imputer: SimpleImputer | None = None
        self._scaler: StandardScaler | None = None
        self._model: LogisticRegression | None = None

    @property
    def is_fitted(self) -> bool:
        return self._model is not None

    def _raw_row(self, profile: PlayerProfileSnapshot) -> list[float]:
        if profile.tour != self.tour:
            raise ValueError(
                f"profile tour {profile.tour!r} does not match model tour {self.tour!r}"
            )
        values = profile_strength_feature_values(
            profile,
            include_conditional=self.include_conditional,
        )
        return [float("nan") if value is None else float(value) for value in values]

    def fit(
        self,
        pairs: list[MatchProfilePair],
        outcomes_a: list[bool],
    ) -> ProfileStrengthModel:
        if len(pairs) != len(outcomes_a):
            raise ValueError("profile-pair and outcome lengths must match")
        if not pairs:
            raise ValueError("training data is empty")
        if len({bool(value) for value in outcomes_a}) < 2:
            raise ValueError("training data must contain both outcome classes")

        rows: list[list[float]] = []
        for pair in pairs:
            rows.append(self._raw_row(pair.player_a))
            rows.append(self._raw_row(pair.player_b))

        imputer = SimpleImputer(
            strategy="median",
            add_indicator=False,
            keep_empty_features=True,
        )
        player_matrix = imputer.fit_transform(rows)
        scaler = StandardScaler()
        standardized = scaler.fit_transform(player_matrix)
        a_rows = standardized[0::2]
        b_rows = standardized[1::2]
        pair_differences = a_rows - b_rows

        model = LogisticRegression(
            C=1.0,
            solver="lbfgs",
            max_iter=1000,
            fit_intercept=False,
        )
        model.fit(pair_differences, [int(value) for value in outcomes_a])

        self._imputer = imputer
        self._scaler = scaler
        self._model = model
        return self

    def _standardized_profile(self, profile: PlayerProfileSnapshot) -> np.ndarray:
        if self._imputer is None or self._scaler is None or self._model is None:
            raise RuntimeError("model is not fitted")
        raw = np.asarray([self._raw_row(profile)], dtype=float)
        imputed = self._imputer.transform(raw)
        return self._scaler.transform(imputed)[0]

    def profile_score(self, profile: PlayerProfileSnapshot) -> float:
        if self._model is None:
            raise RuntimeError("model is not fitted")
        standardized = self._standardized_profile(profile)
        return float(np.dot(self._model.coef_[0], standardized))

    def predict_pair(self, pair: MatchProfilePair) -> ProfileStrengthPrediction:
        score_a = self.profile_score(pair.player_a)
        score_b = self.profile_score(pair.player_b)
        probability_a = _sigmoid(score_a - score_b)

        elo_score_a = elo_strength_coordinate(
            pair.player_a.elo_rating,
            config=self.elo_config,
        )
        elo_score_b = elo_strength_coordinate(
            pair.player_b.elo_rating,
            config=self.elo_config,
        )
        elo_probability_a = expected_score(
            pair.player_a.elo_rating,
            pair.player_b.elo_rating,
            scale=self.elo_config.scale,
        )
        gap_a = score_a - elo_score_a
        gap_b = score_b - elo_score_b

        return ProfileStrengthPrediction(
            match_id=pair.match_id,
            probability_a=probability_a,
            profile_score_a=score_a,
            profile_score_b=score_b,
            elo_probability_a=elo_probability_a,
            elo_score_a=elo_score_a,
            elo_score_b=elo_score_b,
            profile_gap_a=gap_a,
            profile_gap_b=gap_b,
            profile_gap_match=gap_a - gap_b,
        )

    def predict_pairs(
        self,
        pairs: list[MatchProfilePair],
    ) -> list[ProfileStrengthPrediction]:
        return [self.predict_pair(pair) for pair in pairs]
