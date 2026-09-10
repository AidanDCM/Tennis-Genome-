from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

MarketType = Literal["h2h"]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class MarketSnapshot:
    """One immutable two-way pre-match market observation in canonical A/B orientation."""

    market_snapshot_id: str
    match_id: str
    provider: str
    bookmaker: str
    market_type: MarketType
    collected_at: datetime
    observed_at: datetime
    player_a_id: str
    player_b_id: str
    selection_a_name: str
    selection_b_name: str
    decimal_odds_a: float
    decimal_odds_b: float
    source_event_id: str
    source_payload_sha256: str
    identity_resolution_hash: str
    commence_at: datetime | None = None
    source_market_id: str | None = None
    is_live: bool = False
    is_suspended: bool = False

    def __post_init__(self) -> None:
        for name in (
            "market_snapshot_id",
            "match_id",
            "provider",
            "bookmaker",
            "player_a_id",
            "player_b_id",
            "selection_a_name",
            "selection_b_name",
            "source_event_id",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.market_type != "h2h":
            raise ValueError("MarketSnapshot v1 supports h2h only")
        if self.player_a_id == self.player_b_id:
            raise ValueError("player_a_id and player_b_id must be different")
        for name, value in (
            ("collected_at", self.collected_at),
            ("observed_at", self.observed_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        if self.commence_at is not None:
            if self.commence_at.tzinfo is None or self.commence_at.utcoffset() is None:
                raise ValueError("commence_at must be timezone-aware")
            if not self.is_live and self.observed_at > self.commence_at:
                raise ValueError("pre-match market observation cannot be after commence_at")
        if self.collected_at < self.observed_at:
            raise ValueError("collected_at cannot be before observed_at")
        for name, value in (
            ("decimal_odds_a", self.decimal_odds_a),
            ("decimal_odds_b", self.decimal_odds_b),
        ):
            if not float(value) > 1.0:
                raise ValueError(f"{name} must be greater than 1.0")
        if not _SHA256_RE.fullmatch(self.source_payload_sha256):
            raise ValueError("source_payload_sha256 must be lowercase SHA-256 hex")
        if not _SHA256_RE.fullmatch(self.identity_resolution_hash):
            raise ValueError("identity_resolution_hash must be lowercase SHA-256 hex")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for field in ("collected_at", "observed_at", "commence_at"):
            value = getattr(self, field)
            payload[field] = value.isoformat() if value is not None else None
        return payload
