from __future__ import annotations

from math import log1p

from tennis_genome.data.canonical import Tour
from tennis_genome.profiles.state import PlayerProfileSnapshot

_COMMON_STRICT_FEATURES = (
    "elo_rating",
    "form_result_30",
    "form_result_90",
    "form_point_30",
    "form_point_90",
    "event_gap_days",
    "log_minutes_7",
    "log_minutes_14",
    "log_minutes_28",
    "matches_14",
    "matches_28",
    "log_previous_event_minutes",
)

_ATP_STRICT_ADDITIONS = (
    "serve_rating",
    "return_rating",
    "age_years",
    "age_curve",
    "young_indicator",
    "veteran_indicator",
    "height_cm",
)

_WTA_CONDITIONAL_ADDITIONS = (
    "serve_rating",
    "return_rating",
)


def profile_strength_feature_names(
    tour: Tour,
    *,
    include_conditional: bool = False,
) -> tuple[str, ...]:
    """Return the preregistered Profile Strength feature representation."""
    if tour == "ATP":
        return _COMMON_STRICT_FEATURES + _ATP_STRICT_ADDITIONS
    if include_conditional:
        return _COMMON_STRICT_FEATURES + _WTA_CONDITIONAL_ADDITIONS
    return _COMMON_STRICT_FEATURES


def _log_optional(value: float | int | None) -> float | None:
    if value is None:
        return None
    return log1p(float(value))


def _age_curve(age: float | None) -> float | None:
    if age is None:
        return None
    return (age - 27.0) ** 2


def _young(age: float | None) -> float | None:
    if age is None:
        return None
    return float(age <= 23.0)


def _veteran(age: float | None) -> float | None:
    if age is None:
        return None
    return float(age >= 32.0)


def profile_strength_feature_values(
    snapshot: PlayerProfileSnapshot,
    *,
    include_conditional: bool = False,
) -> tuple[float | None, ...]:
    """Transform one profile into the preregistered player-side feature vector."""
    values: dict[str, float | None] = {
        "elo_rating": snapshot.elo_rating,
        "serve_rating": snapshot.serve_rating,
        "return_rating": snapshot.return_rating,
        "form_result_30": snapshot.form_result_30,
        "form_result_90": snapshot.form_result_90,
        "form_point_30": snapshot.form_point_30,
        "form_point_90": snapshot.form_point_90,
        "event_gap_days": snapshot.event_gap_days,
        "log_minutes_7": _log_optional(snapshot.minutes_7),
        "log_minutes_14": _log_optional(snapshot.minutes_14),
        "log_minutes_28": _log_optional(snapshot.minutes_28),
        "matches_14": float(snapshot.matches_14),
        "matches_28": float(snapshot.matches_28),
        "log_previous_event_minutes": _log_optional(snapshot.previous_event_minutes),
        "age_years": snapshot.age_years,
        "age_curve": _age_curve(snapshot.age_years),
        "young_indicator": _young(snapshot.age_years),
        "veteran_indicator": _veteran(snapshot.age_years),
        "height_cm": None if snapshot.height_cm is None else float(snapshot.height_cm),
    }
    names = profile_strength_feature_names(
        snapshot.tour,
        include_conditional=include_conditional,
    )
    return tuple(values[name] for name in names)
