from __future__ import annotations

import bz2
import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, BinaryIO

from tennis_genome.market.exchange_snapshot import (
    ExchangeDataPackage,
    ExchangeMarketSnapshot,
    ExchangeRunnerSnapshot,
)

_PROVIDER = "betfair_exchange"
_TENNIS_EVENT_TYPE_ID = "2"
_MATCH_ODDS = "MATCH_ODDS"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_iso_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Betfair datetime must be timezone-aware")
    return parsed


def _published_at(milliseconds: int) -> datetime:
    return datetime.fromtimestamp(milliseconds / 1000.0, tz=UTC)


def _open_lines(path: Path) -> BinaryIO:
    if path.suffix.lower() == ".bz2":
        return bz2.open(path, "rb")
    return path.open("rb")


@dataclass
class _RunnerState:
    selection_id: int
    name: str | None = None
    status: str | None = None
    ltp: float | None = None
    total_matched: float | None = None
    advanced_back: dict[int, tuple[float, float]] = field(default_factory=dict)
    advanced_lay: dict[int, tuple[float, float]] = field(default_factory=dict)
    pro_back: dict[float, float] = field(default_factory=dict)
    pro_lay: dict[float, float] = field(default_factory=dict)

    @staticmethod
    def _update_level_ladder(
        ladder: dict[int, tuple[float, float]],
        updates: object,
    ) -> None:
        if not isinstance(updates, list):
            return
        for update in updates:
            if not isinstance(update, list) or len(update) != 3:
                raise ValueError("Betfair batb/batl update must be [level, price, volume]")
            level, price, volume = int(update[0]), float(update[1]), float(update[2])
            if level < 0 or price <= 1.0 or volume < 0.0:
                raise ValueError("invalid Betfair level price/volume update")
            if volume == 0.0:
                ladder.pop(level, None)
            else:
                ladder[level] = (price, volume)

    @staticmethod
    def _update_price_ladder(ladder: dict[float, float], updates: object) -> None:
        if not isinstance(updates, list):
            return
        for update in updates:
            if not isinstance(update, list) or len(update) != 2:
                raise ValueError("Betfair atb/atl update must be [price, volume]")
            price, volume = float(update[0]), float(update[1])
            if price <= 1.0 or volume < 0.0:
                raise ValueError("invalid Betfair price/volume update")
            if volume == 0.0:
                ladder.pop(price, None)
            else:
                ladder[price] = volume

    def apply_change(self, change: dict[str, Any]) -> None:
        if "ltp" in change and change["ltp"] is not None:
            self.ltp = float(change["ltp"])
        if "tv" in change and change["tv"] is not None:
            self.total_matched = float(change["tv"])
        if "batb" in change:
            self._update_level_ladder(self.advanced_back, change["batb"])
        if "batl" in change:
            self._update_level_ladder(self.advanced_lay, change["batl"])
        if "atb" in change:
            self._update_price_ladder(self.pro_back, change["atb"])
        if "atl" in change:
            self._update_price_ladder(self.pro_lay, change["atl"])

    def _best_advanced(
        self,
        ladder: dict[int, tuple[float, float]],
    ) -> tuple[float | None, float | None]:
        if not ladder:
            return None, None
        level = min(ladder)
        return ladder[level]

    def best_back(self, data_package: ExchangeDataPackage) -> tuple[float | None, float | None]:
        if data_package == "PRO" and self.pro_back:
            price = max(self.pro_back)
            return price, self.pro_back[price]
        if data_package in {"ADVANCED", "PRO"}:
            return self._best_advanced(self.advanced_back)
        return None, None

    def best_lay(self, data_package: ExchangeDataPackage) -> tuple[float | None, float | None]:
        if data_package == "PRO" and self.pro_lay:
            price = min(self.pro_lay)
            return price, self.pro_lay[price]
        if data_package in {"ADVANCED", "PRO"}:
            return self._best_advanced(self.advanced_lay)
        return None, None


@dataclass
class _MarketState:
    market_id: str
    event_id: str | None = None
    event_type_id: str | None = None
    market_type: str | None = None
    event_name: str | None = None
    market_time: datetime | None = None
    status: str | None = None
    in_play: bool = False
    market_base_rate: float | None = None
    market_total_matched: float | None = None
    regulators: tuple[str, ...] = ()
    runners: dict[int, _RunnerState] = field(default_factory=dict)

    def apply_market_definition(self, definition: dict[str, Any]) -> None:
        if "eventId" in definition and definition["eventId"] is not None:
            self.event_id = str(definition["eventId"])
        if "eventTypeId" in definition and definition["eventTypeId"] is not None:
            self.event_type_id = str(definition["eventTypeId"])
        if "marketType" in definition and definition["marketType"] is not None:
            self.market_type = str(definition["marketType"])
        if "eventName" in definition and definition["eventName"] is not None:
            self.event_name = str(definition["eventName"])
        if "marketTime" in definition and definition["marketTime"] is not None:
            self.market_time = _parse_iso_datetime(str(definition["marketTime"]))
        if "status" in definition and definition["status"] is not None:
            self.status = str(definition["status"])
        if "inPlay" in definition:
            self.in_play = bool(definition["inPlay"])
        if "marketBaseRate" in definition and definition["marketBaseRate"] is not None:
            self.market_base_rate = float(definition["marketBaseRate"])
        regulators = definition.get("regulators")
        if isinstance(regulators, list):
            self.regulators = tuple(str(value) for value in regulators)
        runners = definition.get("runners")
        if isinstance(runners, list):
            for item in runners:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                selection_id = int(item["id"])
                state = self.runners.setdefault(selection_id, _RunnerState(selection_id))
                if item.get("name") is not None:
                    state.name = str(item["name"])
                if item.get("status") is not None:
                    state.status = str(item["status"])

    def apply_market_change(self, change: dict[str, Any]) -> None:
        definition = change.get("marketDefinition")
        if isinstance(definition, dict):
            self.apply_market_definition(definition)
        if "tv" in change and change["tv"] is not None:
            self.market_total_matched = float(change["tv"])
        runner_changes = change.get("rc")
        if isinstance(runner_changes, list):
            for runner_change in runner_changes:
                if not isinstance(runner_change, dict) or "id" not in runner_change:
                    continue
                selection_id = int(runner_change["id"])
                state = self.runners.setdefault(selection_id, _RunnerState(selection_id))
                state.apply_change(runner_change)

    def is_tennis_match_odds(self) -> bool:
        if self.market_type != _MATCH_ODDS:
            return False
        if self.event_type_id is not None and self.event_type_id != _TENNIS_EVENT_TYPE_ID:
            return False
        named_runners = [runner for runner in self.runners.values() if runner.name]
        return len(named_runners) == 2

    def snapshot(
        self,
        *,
        data_package: ExchangeDataPackage,
        source_file_sha256: str,
        source_message_sha256: str,
        source_message_index: int,
        published_at: datetime,
    ) -> ExchangeMarketSnapshot | None:
        if not self.is_tennis_match_odds():
            return None
        if self.event_id is None or self.event_name is None or self.market_time is None:
            return None
        if self.status is None:
            return None
        runner_snapshots: list[ExchangeRunnerSnapshot] = []
        for runner in sorted(self.runners.values(), key=lambda item: item.selection_id):
            if runner.name is None:
                continue
            back_price, back_size = runner.best_back(data_package)
            lay_price, lay_size = runner.best_lay(data_package)
            runner_snapshots.append(
                ExchangeRunnerSnapshot(
                    selection_id=runner.selection_id,
                    selection_name=runner.name,
                    status=runner.status,
                    best_back_price=back_price,
                    best_back_size=back_size,
                    best_lay_price=lay_price,
                    best_lay_size=lay_size,
                    last_traded_price=runner.ltp,
                    total_matched=runner.total_matched,
                )
            )
        if len(runner_snapshots) != 2:
            return None
        snapshot_key = "|".join(
            (
                _PROVIDER,
                source_file_sha256,
                str(source_message_index),
                self.market_id,
                published_at.isoformat(),
            )
        )
        return ExchangeMarketSnapshot(
            exchange_snapshot_id=_sha256_bytes(snapshot_key.encode("utf-8")),
            provider=_PROVIDER,
            data_package=data_package,
            source_file_sha256=source_file_sha256,
            source_message_sha256=source_message_sha256,
            source_message_index=source_message_index,
            source_market_id=self.market_id,
            source_event_id=self.event_id,
            event_type_id=self.event_type_id,
            market_type=self.market_type or _MATCH_ODDS,
            event_name=self.event_name,
            market_time=self.market_time,
            published_at=published_at,
            market_status=self.status,
            in_play=self.in_play,
            market_base_rate=self.market_base_rate,
            market_total_matched=self.market_total_matched,
            regulators=self.regulators,
            runners=tuple(runner_snapshots),
        )


def iter_betfair_exchange_snapshots(
    path: str | Path,
    *,
    data_package: ExchangeDataPackage,
) -> Iterator[ExchangeMarketSnapshot]:
    """Reconstruct eligible two-runner tennis MATCH_ODDS states from one Betfair file."""

    source_path = Path(path)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if data_package not in {"BASIC", "ADVANCED", "PRO"}:
        raise ValueError("data_package must be BASIC, ADVANCED, or PRO")

    source_file_sha256 = _sha256_file(source_path)
    markets: dict[str, _MarketState] = {}
    with _open_lines(source_path) as handle:
        for message_index, raw_line in enumerate(handle):
            raw_message = raw_line.rstrip(b"\r\n")
            if not raw_message:
                continue
            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid Betfair JSON at message index {message_index}") from exc
            if not isinstance(message, dict) or message.get("op") != "mcm":
                continue
            if "pt" not in message:
                raise ValueError("Betfair MarketChangeMessage is missing pt")
            published_at = _published_at(int(message["pt"]))
            source_message_sha256 = _sha256_bytes(raw_message)
            changes = message.get("mc")
            if not isinstance(changes, list):
                continue
            for change in changes:
                if not isinstance(change, dict) or "id" not in change:
                    continue
                market_id = str(change["id"])
                state = markets.setdefault(market_id, _MarketState(market_id=market_id))
                state.apply_market_change(change)
                snapshot = state.snapshot(
                    data_package=data_package,
                    source_file_sha256=source_file_sha256,
                    source_message_sha256=source_message_sha256,
                    source_message_index=message_index,
                    published_at=published_at,
                )
                if snapshot is not None:
                    yield snapshot


def load_betfair_exchange_snapshots(
    path: str | Path,
    *,
    data_package: ExchangeDataPackage,
) -> list[ExchangeMarketSnapshot]:
    return list(iter_betfair_exchange_snapshots(path, data_package=data_package))
