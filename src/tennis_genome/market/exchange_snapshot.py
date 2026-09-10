from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

ExchangeDataPackage = Literal["BASIC", "ADVANCED", "PRO"]
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ExchangeRunnerSnapshot:
    selection_id: int
    selection_name: str
    status: str | None = None
    best_back_price: float | None = None
    best_back_size: float | None = None
    best_lay_price: float | None = None
    best_lay_size: float | None = None
    last_traded_price: float | None = None
    total_matched: float | None = None

    def __post_init__(self) -> None:
        if self.selection_id <= 0:
            raise ValueError("selection_id must be positive")
        if not self.selection_name.strip():
            raise ValueError("selection_name must be non-empty")
        for name, value in (
            ("best_back_price", self.best_back_price),
            ("best_lay_price", self.best_lay_price),
            ("last_traded_price", self.last_traded_price),
        ):
            if value is not None and not float(value) > 1.0:
                raise ValueError(f"{name} must be greater than 1.0")
        for name, value in (
            ("best_back_size", self.best_back_size),
            ("best_lay_size", self.best_lay_size),
            ("total_matched", self.total_matched),
        ):
            if value is not None and float(value) < 0.0:
                raise ValueError(f"{name} must be non-negative")


@dataclass(frozen=True)
class ExchangeMarketSnapshot:
    """One immutable reconstructed Betfair Exchange market state."""

    exchange_snapshot_id: str
    provider: str
    data_package: ExchangeDataPackage
    source_file_sha256: str
    source_message_sha256: str
    source_message_index: int
    source_market_id: str
    source_event_id: str
    event_type_id: str | None
    market_type: str
    event_name: str
    market_time: datetime
    published_at: datetime
    market_status: str
    in_play: bool
    runners: tuple[ExchangeRunnerSnapshot, ...]
    market_base_rate: float | None = None
    market_total_matched: float | None = None
    regulators: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "exchange_snapshot_id",
            "provider",
            "source_market_id",
            "source_event_id",
            "market_type",
            "event_name",
            "market_status",
        ):
            if not str(getattr(self, name)).strip():
                raise ValueError(f"{name} must be non-empty")
        if self.source_message_index < 0:
            raise ValueError("source_message_index must be non-negative")
        if self.data_package not in {"BASIC", "ADVANCED", "PRO"}:
            raise ValueError("unsupported Exchange data package")
        for name, value in (
            ("source_file_sha256", self.source_file_sha256),
            ("source_message_sha256", self.source_message_sha256),
        ):
            if not _SHA256_RE.fullmatch(value):
                raise ValueError(f"{name} must be lowercase SHA-256 hex")
        for name, value in (
            ("market_time", self.market_time),
            ("published_at", self.published_at),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{name} must be timezone-aware")
        ids = [runner.selection_id for runner in self.runners]
        if len(ids) != len(set(ids)):
            raise ValueError("runner selection IDs must be unique")
        if self.market_base_rate is not None and self.market_base_rate < 0.0:
            raise ValueError("market_base_rate must be non-negative")
        if self.market_total_matched is not None and self.market_total_matched < 0.0:
            raise ValueError("market_total_matched must be non-negative")

    @property
    def seconds_to_start_at_snapshot(self) -> float:
        return (self.market_time - self.published_at).total_seconds()

    @property
    def is_strictly_preplay(self) -> bool:
        return not self.in_play and self.published_at < self.market_time

    @property
    def has_two_way_executable_quotes(self) -> bool:
        if len(self.runners) != 2:
            return False
        return all(
            runner.best_back_price is not None
            and runner.best_back_size is not None
            and runner.best_lay_price is not None
            and runner.best_lay_size is not None
            for runner in self.runners
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["market_time"] = self.market_time.isoformat()
        payload["published_at"] = self.published_at.isoformat()
        return payload
