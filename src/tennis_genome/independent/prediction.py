from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from tennis_genome.data.canonical import Tour
from tennis_genome.independent.spec import MODEL_VERSION, architecture_hash

_MARKET_OR_OUTCOME_KEYS = frozenset(
    {
        "bookmaker",
        "odds",
        "american_odds",
        "decimal_odds",
        "market_snapshot_id",
        "market_probability",
        "market_novig_probability",
        "edge",
        "edge_pp",
        "expected_value",
        "expected_value_per_unit",
        "stake",
        "stake_units",
        "closing_line_value",
        "realized_profit",
        "realized_profit_units",
        "outcome",
        "winner",
        "outcome_player_a_won",
    }
)
_FORBIDDEN_KEY_FRAGMENTS = (
    "bookmaker",
    "sportsbook",
    "odds",
    "market",
    "stake",
    "profit",
    "payout",
    "closing_line",
    "closingline",
    "expected_value",
    "expectedvalue",
    "novig",
    "no_vig",
    "outcome",
    "winner",
)
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _is_forbidden_key(key: str) -> bool:
    normalized = key.lower()
    if normalized in _MARKET_OR_OUTCOME_KEYS:
        return True
    if any(fragment in normalized for fragment in _FORBIDDEN_KEY_FRAGMENTS):
        return True
    tokens = {token for token in re.split(r"[^a-z0-9]+", normalized) if token}
    return bool(tokens.intersection({"edge", "ev", "vig", "clv", "price"}))


def _forbidden_keys(value: object) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).lower()
            if _is_forbidden_key(normalized):
                found.add(normalized)
            found.update(_forbidden_keys(nested))
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for nested in value:
            found.update(_forbidden_keys(nested))
    return found


def reject_market_or_outcome_fields(payload: Mapping[str, Any]) -> None:
    """Fail closed if market, staking, or realized-outcome data enter the engine boundary."""

    forbidden = sorted(_forbidden_keys(payload))
    if forbidden:
        raise ValueError(
            "market/outcome fields are forbidden inside TGE-Independent-v1: " + ", ".join(forbidden)
        )


@dataclass(frozen=True)
class IndependentPrediction:
    prediction_id: str
    match_id: str
    tour: Tour
    created_at: datetime
    prediction_cutoff_at: datetime
    p_player_a: float
    p_player_b: float
    architecture_hash: str = field(default_factory=architecture_hash)
    model_version: str = MODEL_VERSION
    component_probabilities: dict[str, float] = field(default_factory=dict)
    diagnostics: dict[str, float | int | bool | None] = field(default_factory=dict)
    source_manifest_hashes: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.prediction_id:
            raise ValueError("prediction_id must be non-empty")
        if not self.match_id:
            raise ValueError("match_id must be non-empty")
        if self.model_version != MODEL_VERSION:
            raise ValueError("IndependentPrediction must use the frozen model version")
        if self.architecture_hash != architecture_hash():
            raise ValueError("architecture_hash does not match the frozen model spec")
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if (
            self.prediction_cutoff_at.tzinfo is None
            or self.prediction_cutoff_at.utcoffset() is None
        ):
            raise ValueError("prediction_cutoff_at must be timezone-aware")
        if self.created_at < self.prediction_cutoff_at:
            raise ValueError("created_at cannot be before prediction_cutoff_at")
        if not 0.0 <= self.p_player_a <= 1.0:
            raise ValueError("p_player_a must be in [0, 1]")
        if not 0.0 <= self.p_player_b <= 1.0:
            raise ValueError("p_player_b must be in [0, 1]")
        if abs((self.p_player_a + self.p_player_b) - 1.0) > 1e-9:
            raise ValueError("player probabilities must sum to one")
        if not self.source_manifest_hashes:
            raise ValueError("at least one source manifest hash is required")
        if len(set(self.source_manifest_hashes)) != len(self.source_manifest_hashes):
            raise ValueError("source manifest hashes must be unique")
        if not all(_SHA256_RE.fullmatch(value) for value in self.source_manifest_hashes):
            raise ValueError("source manifest hashes must be lowercase SHA-256 hex")
        for name, probability in self.component_probabilities.items():
            if not name:
                raise ValueError("component probability names must be non-empty")
            if not 0.0 <= probability <= 1.0:
                raise ValueError("component probabilities must be in [0, 1]")
        reject_market_or_outcome_fields(self.component_probabilities)
        reject_market_or_outcome_fields(self.diagnostics)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["prediction_cutoff_at"] = self.prediction_cutoff_at.isoformat()
        reject_market_or_outcome_fields(payload)
        return payload
