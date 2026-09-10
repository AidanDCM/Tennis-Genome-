from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

ResolutionMethod = Literal["provider_id", "exact_alias", "manual_verified"]
RESOLVER_VERSION = "market-identity-v1"


@dataclass(frozen=True)
class MarketIdentityResolution:
    match_id: str
    provider: str
    source_event_id: str
    source_selection_a: str
    source_selection_b: str
    player_a_id: str
    player_b_id: str
    resolved_at: datetime
    method: ResolutionMethod
    resolver_version: str = RESOLVER_VERSION

    def __post_init__(self) -> None:
        for name in (
            "match_id",
            "provider",
            "source_event_id",
            "source_selection_a",
            "source_selection_b",
            "player_a_id",
            "player_b_id",
            "resolver_version",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.player_a_id == self.player_b_id:
            raise ValueError("resolved player IDs must be different")
        if self.resolved_at.tzinfo is None or self.resolved_at.utcoffset() is None:
            raise ValueError("resolved_at must be timezone-aware")

    def canonical_json(self) -> str:
        payload = asdict(self)
        payload["resolved_at"] = self.resolved_at.isoformat()
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def resolution_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()
