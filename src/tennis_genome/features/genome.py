from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from tennis_genome.data.canonical import Tour
from tennis_genome.features.foundational import FoundationalSnapshot
from tennis_genome.models.core_v1_spec import strict_a_features
from tennis_genome.profiles.features import (
    profile_strength_feature_names,
    profile_strength_feature_values,
)
from tennis_genome.profiles.state import MatchProfilePair

GENOME_VERSION = "genome-v1-core-plus-profile-means"


@dataclass(frozen=True)
class GenomeVector:
    """Leakage-safe, canonicalized numeric representation for similarity search."""

    match_id: str
    event_date: date
    tour: Tour
    player_a_id: str
    player_b_id: str
    orientation_sign: int
    feature_names: tuple[str, ...]
    values: tuple[float | None, ...]
    feature_version: str = GENOME_VERSION

    @property
    def missing_fraction(self) -> float:
        if not self.values:
            return 0.0
        return sum(value is None for value in self.values) / len(self.values)

    @property
    def digest(self) -> str:
        payload = {
            "match_id": self.match_id,
            "event_date": self.event_date.isoformat(),
            "tour": self.tour,
            "player_a_id": self.player_a_id,
            "player_b_id": self.player_b_id,
            "orientation_sign": self.orientation_sign,
            "feature_names": self.feature_names,
            "values": self.values,
            "feature_version": self.feature_version,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def canonical_orientation_sign(
    *,
    elo_logit: float,
    player_a_id: str,
    player_b_id: str,
) -> int:
    """Return orientation toward the Elo-favored side with deterministic tie-break."""
    if elo_logit > 0.0:
        return 1
    if elo_logit < 0.0:
        return -1
    return 1 if player_a_id <= player_b_id else -1


def canonical_probability(probability_a: float, *, orientation_sign: int) -> float:
    if orientation_sign not in (-1, 1):
        raise ValueError("orientation_sign must be -1 or +1")
    probability = float(probability_a)
    if not 0.0 <= probability <= 1.0:
        raise ValueError("probability must be in [0, 1]")
    return probability if orientation_sign == 1 else 1.0 - probability


def original_probability(probability_favorite: float, *, orientation_sign: int) -> float:
    return canonical_probability(
        probability_favorite,
        orientation_sign=orientation_sign,
    )


def canonical_outcome(outcome_a: bool, *, orientation_sign: int) -> bool:
    if orientation_sign not in (-1, 1):
        raise ValueError("orientation_sign must be -1 or +1")
    outcome = bool(outcome_a)
    return outcome if orientation_sign == 1 else not outcome


def _mean_optional(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    return (float(a) + float(b)) / 2.0


def build_genome_vector(
    pair: MatchProfilePair,
    foundational: FoundationalSnapshot,
) -> GenomeVector:
    """Build preregistered Genome v1 from Core features + profile-side means."""
    if pair.match_id != foundational.match_id:
        raise ValueError("profile pair and foundational snapshot match IDs differ")
    if pair.event_date != foundational.event_date:
        raise ValueError("profile pair and foundational snapshot dates differ")
    if pair.player_a.tour != pair.player_b.tour:
        raise ValueError("profile pair contains mixed tours")

    tour = pair.player_a.tour
    sign = canonical_orientation_sign(
        elo_logit=foundational.elo_logit,
        player_a_id=pair.player_a.player_id,
        player_b_id=pair.player_b.player_id,
    )

    core_names = strict_a_features(tour)
    core_values: list[float | None] = []
    for name in core_names:
        value = getattr(foundational, name)
        core_values.append(None if value is None else sign * float(value))

    profile_names = profile_strength_feature_names(
        tour,
        include_conditional=False,
    )
    a_values = profile_strength_feature_values(
        pair.player_a,
        include_conditional=False,
    )
    b_values = profile_strength_feature_values(
        pair.player_b,
        include_conditional=False,
    )
    profile_means = [_mean_optional(a, b) for a, b in zip(a_values, b_values, strict=True)]

    feature_names = tuple(f"core::{name}" for name in core_names) + tuple(
        f"profile_mean::{name}" for name in profile_names
    )
    values = tuple(core_values) + tuple(profile_means)
    if len(feature_names) != len(values):
        raise RuntimeError("Genome feature-name/value length mismatch")

    return GenomeVector(
        match_id=pair.match_id,
        event_date=pair.event_date,
        tour=tour,
        player_a_id=pair.player_a.player_id,
        player_b_id=pair.player_b.player_id,
        orientation_sign=sign,
        feature_names=feature_names,
        values=values,
    )
