"""A deliberately small, market-blind research challenger.

The ranking arm is exploratory until each target ranking has independent T0 evidence.
This module does not change the sealed production predictor.
"""

from __future__ import annotations

import hashlib
import json
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
_ARTIFACT_SCHEMA = "simple-logit-challenger-research-v1"


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
        self._tour: str | None = None
        self._training_rows: int | None = None

    @property
    def feature_names(self) -> tuple[str, ...]:
        return BASE_FEATURES + RANK_FEATURES if self.include_rank else BASE_FEATURES

    def fit(self, examples: Sequence[ChallengerExample]) -> SimpleLogitChallenger:
        if not examples or any(example.outcome_a is None for example in examples):
            raise ValueError("training requires nonempty labeled examples")
        tours = {example.state.tour for example in examples}
        if len(tours) != 1:
            raise ValueError("training must use one tour")
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
        self._tour = examples[0].state.tour
        self._training_rows = len(examples)
        return self

    def predict_probability_a(self, example: ChallengerExample) -> float:
        if self._model is None or self._scale is None:
            raise RuntimeError("challenger must be fitted before prediction")
        if example.state.tour != self._tour:
            raise ValueError("target tour differs from training tour")
        if self._training_end is not None and example.snapshot.event_date <= self._training_end:
            raise ValueError("target must occur after every training match date")
        x = _feature_row(example, include_rank=self.include_rank) / self._scale
        return float(self._model.predict_proba(x.reshape(1, -1))[0, 1])

    def freeze(
        self,
        *,
        tour: str,
        training_population_sha256: str,
        source_manifest_sha256: str,
    ) -> FrozenSimpleLogitChallenger:
        if (
            self._model is None
            or self._scale is None
            or self._training_end is None
            or self._training_rows is None
        ):
            raise RuntimeError("challenger must be fitted before freezing")
        if tour not in {"ATP", "WTA"} or tour != self._tour:
            raise ValueError("artifact tour must match training tour")
        for digest in (training_population_sha256, source_manifest_sha256):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("provenance digests must be lowercase SHA-256")
        return FrozenSimpleLogitChallenger(
            tour=tour,
            include_rank=self.include_rank,
            feature_names=self.feature_names,
            scale=tuple(float(value) for value in self._scale),
            coefficients=tuple(float(value) for value in self._model.coef_[0]),
            c=self.c,
            training_rows=self._training_rows,
            training_end=self._training_end,
            training_population_sha256=training_population_sha256,
            source_manifest_sha256=source_manifest_sha256,
        )


@dataclass(frozen=True)
class FrozenSimpleLogitChallenger:
    """Content-addressed, inference-only research artifact."""

    tour: str
    include_rank: bool
    feature_names: tuple[str, ...]
    scale: tuple[float, ...]
    coefficients: tuple[float, ...]
    c: float
    training_rows: int
    training_end: date
    training_population_sha256: str
    source_manifest_sha256: str

    def __post_init__(self) -> None:
        if type(self.include_rank) is not bool:
            raise ValueError("artifact rank flag must be a boolean")
        expected = BASE_FEATURES + RANK_FEATURES if self.include_rank else BASE_FEATURES
        if self.tour not in {"ATP", "WTA"} or self.feature_names != expected:
            raise ValueError("artifact tour or feature schema is invalid")
        for digest in (self.training_population_sha256, self.source_manifest_sha256):
            if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
                raise ValueError("artifact provenance digests must be lowercase SHA-256")
        if len(self.scale) != len(expected) or len(self.coefficients) != len(expected):
            raise ValueError("artifact coefficient dimensions do not match features")
        if any(not math.isfinite(value) or value <= 0 for value in self.scale):
            raise ValueError("artifact scaling must be finite and positive")
        if any(not math.isfinite(value) for value in self.coefficients):
            raise ValueError("artifact coefficients must be finite")
        if not math.isfinite(self.c) or self.c <= 0 or self.training_rows <= 0:
            raise ValueError("artifact training hyperparameters are invalid")

    def payload(self) -> dict[str, object]:
        return {
            "schema_version": _ARTIFACT_SCHEMA,
            "tour": self.tour,
            "include_rank": self.include_rank,
            "feature_names": list(self.feature_names),
            "scale": list(self.scale),
            "coefficients": list(self.coefficients),
            "c": self.c,
            "training_rows": self.training_rows,
            "training_end": self.training_end.isoformat(),
            "training_population_sha256": self.training_population_sha256,
            "source_manifest_sha256": self.source_manifest_sha256,
            "production_eligible": False,
            "historical_target_t0_verified": False,
        }

    @staticmethod
    def _digest(payload: dict[str, object]) -> str:
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def sealed_record(self) -> dict[str, object]:
        payload = self.payload()
        return {"payload": payload, "semantic_sha256": self._digest(payload)}

    @classmethod
    def from_sealed_record(cls, record: dict[str, object]) -> FrozenSimpleLogitChallenger:
        if set(record) != {"payload", "semantic_sha256"}:
            raise ValueError("artifact envelope has unexpected fields")
        payload = record["payload"]
        if not isinstance(payload, dict) or record["semantic_sha256"] != cls._digest(payload):
            raise ValueError("artifact semantic hash mismatch")
        if payload.get("schema_version") != _ARTIFACT_SCHEMA:
            raise ValueError("unsupported artifact schema")
        if payload.get("production_eligible") is not False:
            raise ValueError("research artifact cannot claim production eligibility")
        if payload.get("historical_target_t0_verified") is not False:
            raise ValueError("historical target T0 cannot be claimed verified")
        if set(payload) != {
            "schema_version",
            "tour",
            "include_rank",
            "feature_names",
            "scale",
            "coefficients",
            "c",
            "training_rows",
            "training_end",
            "training_population_sha256",
            "source_manifest_sha256",
            "production_eligible",
            "historical_target_t0_verified",
        }:
            raise ValueError("artifact payload has unexpected fields")
        return cls(
            tour=str(payload["tour"]),
            include_rank=payload["include_rank"],
            feature_names=tuple(payload["feature_names"]),
            scale=tuple(float(value) for value in payload["scale"]),
            coefficients=tuple(float(value) for value in payload["coefficients"]),
            c=float(payload["c"]),
            training_rows=int(payload["training_rows"]),
            training_end=date.fromisoformat(str(payload["training_end"])),
            training_population_sha256=str(payload["training_population_sha256"]),
            source_manifest_sha256=str(payload["source_manifest_sha256"]),
        )

    def predict_probability_a(self, example: ChallengerExample) -> float:
        if example.state.tour != self.tour:
            raise ValueError("target tour differs from frozen model")
        if example.snapshot.event_date <= self.training_end:
            raise ValueError("target must occur after frozen training end")
        row = _feature_row(example, include_rank=self.include_rank)
        logit = sum(
            coefficient * value / scale
            for coefficient, value, scale in zip(self.coefficients, row, self.scale, strict=True)
        )
        if logit >= 0:
            return 1.0 / (1.0 + math.exp(-logit))
        exp_logit = math.exp(logit)
        return exp_logit / (1.0 + exp_logit)
