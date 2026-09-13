from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from tennis_genome.data.canonical import Tour
from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.independent.prediction import IndependentPrediction
from tennis_genome.profiles.state import MatchProfilePair
from tennis_genome.ratings.serve_return import ServeReturnSnapshot

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MatchupInput:
    """Provider-neutral, market-blind state presented to the matchup calculator."""

    prediction_id: str
    match_id: str
    tour: Tour
    player_a_id: str
    player_b_id: str
    created_at: datetime
    prediction_cutoff_at: datetime
    foundational: FoundationalSnapshot
    source_manifest_hashes: tuple[str, ...]
    best_of: int = 3
    profile_pair: MatchProfilePair | None = None
    serve_return: ServeReturnSnapshot | None = None

    def __post_init__(self) -> None:
        if not self.prediction_id or not self.match_id:
            raise ValueError("prediction_id and match_id must be non-empty")
        if not self.player_a_id or not self.player_b_id:
            raise ValueError("player IDs must be non-empty")
        if self.player_a_id == self.player_b_id:
            raise ValueError("player IDs must be distinct")
        if self.foundational.match_id != self.match_id:
            raise ValueError("foundational snapshot match_id differs from matchup input")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if (
            self.prediction_cutoff_at.tzinfo is None
            or self.prediction_cutoff_at.utcoffset() is None
        ):
            raise ValueError("prediction_cutoff_at must be timezone-aware")
        if self.created_at < self.prediction_cutoff_at:
            raise ValueError("created_at cannot be before prediction_cutoff_at")
        if not self.source_manifest_hashes:
            raise ValueError("at least one source manifest hash is required")
        if any(
            not isinstance(value, str) or not _SHA256_RE.fullmatch(value)
            for value in self.source_manifest_hashes
        ):
            raise ValueError("source manifest hashes must be lowercase SHA-256 hex")
        if len(set(self.source_manifest_hashes)) != len(self.source_manifest_hashes):
            raise ValueError("source manifest hashes must be unique")

        if self.tour == "ATP":
            if self.profile_pair is None:
                raise ValueError("ATP matchup calculation requires a profile_pair")
            pair = self.profile_pair
            if pair.match_id != self.match_id:
                raise ValueError("profile_pair match_id differs from matchup input")
            if pair.event_date != self.foundational.event_date:
                raise ValueError("profile_pair date differs from foundational snapshot")
            if pair.player_a.player_id != self.player_a_id:
                raise ValueError("profile_pair Player A identity differs from matchup input")
            if pair.player_b.player_id != self.player_b_id:
                raise ValueError("profile_pair Player B identity differs from matchup input")
            if pair.player_a.tour != "ATP" or pair.player_b.tour != "ATP":
                raise ValueError("ATP profile_pair must contain ATP players")
        elif self.tour == "WTA":
            if self.serve_return is None:
                raise ValueError("WTA matchup calculation requires serve_return state")
            if self.best_of not in (3, 5):
                raise ValueError("WTA PointSim requires best_of 3 or 5")
            if self.serve_return.match_id != self.match_id:
                raise ValueError("serve_return match_id differs from matchup input")
            if self.serve_return.event_date != self.foundational.event_date:
                raise ValueError("serve_return date differs from foundational snapshot")
        else:
            raise ValueError(f"unsupported tour: {self.tour!r}")


@dataclass(frozen=True)
class FairDecimalOdds:
    player_a: float | None
    player_b: float | None


@dataclass(frozen=True)
class CoreLogitDriver:
    """One exact additive strict-Core logit term after frozen preprocessing."""

    feature: str
    contribution: float

    def to_dict(self) -> dict[str, object]:
        return {
            "feature": self.feature,
            "contribution": self.contribution,
        }


@dataclass(frozen=True)
class MatchupCalculation:
    """Human-facing wrapper around the frozen market-blind prediction."""

    prediction: IndependentPrediction
    player_a_id: str
    player_b_id: str
    fair_decimal_odds: FairDecimalOdds
    production_bundle_sha256: str
    core_logit_intercept: float
    core_logit_drivers: tuple[CoreLogitDriver, ...]
    assessment_status: str = "DIAGNOSTIC_ONLY_NO_HARD_PASS"

    def __post_init__(self) -> None:
        if not self.player_a_id or not self.player_b_id:
            raise ValueError("calculation player IDs must be non-empty")
        if self.player_a_id == self.player_b_id:
            raise ValueError("calculation player IDs must be distinct")
        if not _SHA256_RE.fullmatch(self.production_bundle_sha256):
            raise ValueError("production bundle SHA must be lowercase SHA-256 hex")
        names = [driver.feature for driver in self.core_logit_drivers]
        if not names or len(names) != len(set(names)):
            raise ValueError("Core logit driver names must be non-empty and unique")

    def to_dict(self) -> dict[str, object]:
        return {
            "prediction": self.prediction.to_dict(),
            "player_a_id": self.player_a_id,
            "player_b_id": self.player_b_id,
            "fair_decimal_odds": {
                "player_a": self.fair_decimal_odds.player_a,
                "player_b": self.fair_decimal_odds.player_b,
            },
            "production_bundle_sha256": self.production_bundle_sha256,
            "core_explanation": {
                "scale": "strict_core_logit_additive_terms",
                "intercept": self.core_logit_intercept,
                "drivers": [driver.to_dict() for driver in self.core_logit_drivers],
            },
            "assessment_status": self.assessment_status,
        }
