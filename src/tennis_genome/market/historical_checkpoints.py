from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

from tennis_genome.market.exchange_snapshot import ExchangeMarketSnapshot

CheckpointName = Literal["T-24H", "T-6H", "T-1H", "T-15M", "CLOSE_PREPLAY"]
_CHECKPOINT_SECONDS: tuple[tuple[CheckpointName, int], ...] = (
    ("T-24H", 24 * 60 * 60),
    ("T-6H", 6 * 60 * 60),
    ("T-1H", 60 * 60),
    ("T-15M", 15 * 60),
)


@dataclass(frozen=True)
class HistoricalMarketCheckpoint:
    checkpoint_id: str
    source_market_id: str
    source_event_id: str
    checkpoint_name: CheckpointName
    target_seconds_to_start: int | None
    exchange_snapshot_id: str
    published_at: datetime
    market_time: datetime
    seconds_to_start: float
    checkpoint_lag_seconds: float
    data_package: str
    source_file_sha256: str
    source_message_sha256: str
    market_status: str
    executable_two_way: bool

    def __post_init__(self) -> None:
        if self.seconds_to_start <= 0.0:
            raise ValueError("historical checkpoint must be strictly pre-play")
        if self.checkpoint_lag_seconds < 0.0:
            raise ValueError("checkpoint_lag_seconds must be non-negative")
        if self.market_status != "OPEN":
            raise ValueError("historical checkpoint must come from an OPEN market")
        if self.target_seconds_to_start is not None:
            if self.seconds_to_start < self.target_seconds_to_start:
                raise ValueError("fixed checkpoint cannot be later than requested horizon")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        payload["market_time"] = self.market_time.isoformat()
        return payload


def _checkpoint_id(snapshot: ExchangeMarketSnapshot, checkpoint_name: str) -> str:
    key = "|".join(
        (
            "betfair-checkpoint-v1",
            snapshot.source_market_id,
            checkpoint_name,
            snapshot.exchange_snapshot_id,
        )
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _eligible(snapshot: ExchangeMarketSnapshot) -> bool:
    return (
        snapshot.market_type == "MATCH_ODDS"
        and snapshot.market_status == "OPEN"
        and snapshot.is_strictly_preplay
        and len(snapshot.runners) == 2
    )


def _build_checkpoint(
    snapshot: ExchangeMarketSnapshot,
    *,
    name: CheckpointName,
    target_seconds: int | None,
) -> HistoricalMarketCheckpoint:
    seconds_to_start = snapshot.seconds_to_start_at_snapshot
    lag = seconds_to_start if target_seconds is None else seconds_to_start - target_seconds
    return HistoricalMarketCheckpoint(
        checkpoint_id=_checkpoint_id(snapshot, name),
        source_market_id=snapshot.source_market_id,
        source_event_id=snapshot.source_event_id,
        checkpoint_name=name,
        target_seconds_to_start=target_seconds,
        exchange_snapshot_id=snapshot.exchange_snapshot_id,
        published_at=snapshot.published_at,
        market_time=snapshot.market_time,
        seconds_to_start=seconds_to_start,
        checkpoint_lag_seconds=lag,
        data_package=snapshot.data_package,
        source_file_sha256=snapshot.source_file_sha256,
        source_message_sha256=snapshot.source_message_sha256,
        market_status=snapshot.market_status,
        executable_two_way=snapshot.has_two_way_executable_quotes,
    )


def select_preplay_checkpoints(
    snapshots: list[ExchangeMarketSnapshot],
) -> tuple[HistoricalMarketCheckpoint, ...]:
    if not snapshots:
        return ()
    market_ids = {snapshot.source_market_id for snapshot in snapshots}
    if len(market_ids) != 1:
        raise ValueError("checkpoint selection requires snapshots from exactly one market")

    eligible = sorted(
        (snapshot for snapshot in snapshots if _eligible(snapshot)),
        key=lambda snapshot: (
            snapshot.published_at,
            snapshot.source_message_index,
            snapshot.exchange_snapshot_id,
        ),
    )
    if not eligible:
        return ()

    result: list[HistoricalMarketCheckpoint] = []
    for name, target_seconds in _CHECKPOINT_SECONDS:
        candidates = [
            snapshot
            for snapshot in eligible
            if snapshot.seconds_to_start_at_snapshot >= target_seconds
        ]
        if candidates:
            result.append(
                _build_checkpoint(
                    candidates[-1],
                    name=name,
                    target_seconds=target_seconds,
                )
            )

    result.append(
        _build_checkpoint(
            eligible[-1],
            name="CLOSE_PREPLAY",
            target_seconds=None,
        )
    )
    return tuple(result)
