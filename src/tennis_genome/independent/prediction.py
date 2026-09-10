from __future__ import annotations

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
        if not 0.0 <= self.p_player_a <= 1.0:
            raise ValueError("p_player_a must be in [0, 1]")
        if not 0.0 <= self.p_player_b <= 1.0:
            raise ValueError("p_player_b must be in [0, 1]")
        if abs((self.p_player_a + self.p_player_b) - 1.0) > 1e-9:
            raise ValueError("player probabilities must sum to one")
        if self.created_at < self.prediction_cutoff_at:
            raise ValueError("created_at cannot be before prediction_cutoff_at")
        for name, probability in self.component_probabilities.items():
            if not name:
                raise ValueError("component probability names must be non-empty")
            if not 0.0 <= probability <= 1.0:
                raise ValueError("component probabilities must be in [0, 1]")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["created_at"] = self.created_at.isoformat()
        payload["prediction_cutoff_at"] = self.prediction_cutoff_at.isoformat()
        return payload


def reject_market_or_outcome_fields(payload: dict[str, Any]) -> None:
    """Fail closed if market, staking, or realized-outcome data enter the engine boundary."""

    normalized = {str(key).lower() for key in payload}
    forbidden = sorted(normalized.intersection(_MARKET_OR_OUTCOME_KEYS))
    if forbidden:
        raise ValueError(
            "market/outcome fields are forbidden inside TGE-Independent-v1: "
            + ", ".join(forbidden)
        )
