from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Mapping


@dataclass(frozen=True)
class MatchFingerprint:
    """Versioned pre-match representation used by models and similarity search."""

    match_id: str
    feature_version: str
    features: Mapping[str, float | int | bool | str | None]

    def digest(self) -> str:
        """Return deterministic hash for immutable prediction provenance."""
        payload = {
            "match_id": self.match_id,
            "feature_version": self.feature_version,
            "features": dict(sorted(self.features.items())),
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()
        return sha256(raw).hexdigest()


def delta(a: float | None, b: float | None) -> float | None:
    """Return A-B, preserving missingness instead of silently imputing."""
    if a is None or b is None:
        return None
    return float(a) - float(b)


def build_core_fingerprint(
    *,
    match_id: str,
    feature_version: str,
    elo_a: float | None,
    elo_b: float | None,
    surface_elo_a: float | None,
    surface_elo_b: float | None,
    serve_a: float | None = None,
    serve_b: float | None = None,
    return_a: float | None = None,
    return_b: float | None = None,
    form_a: float | None = None,
    form_b: float | None = None,
    rest_hours_a: float | None = None,
    rest_hours_b: float | None = None,
    age_a: float | None = None,
    age_b: float | None = None,
) -> MatchFingerprint:
    """Build the minimal v1 difference fingerprint.

    This intentionally does not impute missing values or assign similarity
    weights. Those decisions belong to fold-fitted preprocessing/model layers.
    """
    features: dict[str, float | int | bool | str | None] = {
        "delta_elo": delta(elo_a, elo_b),
        "delta_surface_elo": delta(surface_elo_a, surface_elo_b),
        "delta_serve": delta(serve_a, serve_b),
        "delta_return": delta(return_a, return_b),
        "a_serve_minus_b_return": delta(serve_a, return_b),
        "b_serve_minus_a_return": delta(serve_b, return_a),
        "delta_form": delta(form_a, form_b),
        "delta_rest_hours": delta(rest_hours_a, rest_hours_b),
        "delta_age": delta(age_a, age_b),
    }
    return MatchFingerprint(match_id=match_id, feature_version=feature_version, features=features)
