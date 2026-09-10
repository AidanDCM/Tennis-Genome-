from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from tennis_genome.data.canonical import PreMatchState, Surface, Tour
from tennis_genome.market.exchange_snapshot import ExchangeDataPackage, ExchangeMarketSnapshot
from tennis_genome.market.historical_checkpoints import (
    CheckpointName,
    HistoricalMarketCheckpoint,
    select_preplay_checkpoints,
)
from tennis_genome.market.historical_join import (
    HistoricalMarketJoin,
    HistoricalMarketJoinResult,
    resolve_betfair_market_to_pre_match,
)
from tennis_genome.market.providers.betfair_historical import load_betfair_exchange_snapshots

_BATCH_VERSION = "market-hist-001-batch-v1"
_SUPPORTED_SUFFIXES = {"", ".bz2", ".json", ".jsonl", ".txt"}
_VALID_TOURS = {"ATP", "WTA"}
_VALID_SURFACES = {"Hard", "Clay", "Grass", "Carpet", "Unknown"}
_PRE_MATCH_FORBIDDEN = {"a_won", "score", "retirement", "walkover"}
_PRE_MATCH_REQUIRED = {
    "match_id",
    "tour",
    "event_date",
    "source_order",
    "tournament_id",
    "tournament_name",
    "tournament_level",
    "surface",
    "round",
    "best_of",
    "player_a_id",
    "player_b_id",
    "player_a_name",
    "player_b_name",
    "rank_a",
    "rank_b",
    "rank_points_a",
    "rank_points_b",
}


@dataclass(frozen=True)
class OrientedExchangeCheckpoint:
    record_hash: str
    checkpoint_id: str
    join_hash: str
    source_market_id: str
    source_event_id: str
    match_id: str
    tour: Tour
    checkpoint_name: CheckpointName
    published_at: datetime
    market_time: datetime
    seconds_to_start: float
    checkpoint_lag_seconds: float
    data_package: ExchangeDataPackage
    market_base_rate: float | None
    market_total_matched: float | None
    source_file_sha256: str
    source_message_sha256: str
    selection_a_id: int
    selection_b_id: int
    selection_a_name: str
    selection_b_name: str
    best_back_a: float | None
    best_back_size_a: float | None
    best_lay_a: float | None
    best_lay_size_a: float | None
    last_traded_a: float | None
    best_back_b: float | None
    best_back_size_b: float | None
    best_lay_b: float | None
    best_lay_size_b: float | None
    last_traded_b: float | None
    executable_two_way: bool

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["published_at"] = self.published_at.isoformat()
        payload["market_time"] = self.market_time.isoformat()
        return payload


@dataclass(frozen=True)
class MarketHistMarketRecord:
    source_market_id: str
    source_event_id: str
    source_file: str
    source_file_sha256: str
    data_package: ExchangeDataPackage
    join_status: str
    normalized_runner_names: tuple[str, str]
    candidate_match_ids: tuple[str, ...]
    join: HistoricalMarketJoin | None
    checkpoints: tuple[OrientedExchangeCheckpoint, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_market_id": self.source_market_id,
            "source_event_id": self.source_event_id,
            "source_file": self.source_file,
            "source_file_sha256": self.source_file_sha256,
            "data_package": self.data_package,
            "join_status": self.join_status,
            "normalized_runner_names": list(self.normalized_runner_names),
            "candidate_match_ids": list(self.candidate_match_ids),
            "join": None if self.join is None else self.join.to_dict(),
            "checkpoints": [checkpoint.to_dict() for checkpoint in self.checkpoints],
        }


@dataclass(frozen=True)
class MarketHistSummary:
    batch_version: str
    data_package: ExchangeDataPackage
    files_inspected: int
    files_with_snapshots: int
    markets_reconstructed: int
    markets_matched: int
    markets_unmatched: int
    markets_ambiguous: int
    join_rate: float
    checkpoint_counts: dict[str, int]
    executable_checkpoint_counts: dict[str, int]
    package_counts: dict[str, int]
    output_sha256: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _optional_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def _optional_float(value: object) -> float | None:
    if value is None or pd.isna(value):
        return None
    return float(value)


def _optional_text(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def _event_date(value: object) -> date:
    if value is None or pd.isna(value):
        raise ValueError("canonical event_date cannot be missing")
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _tour(value: object) -> Tour:
    text = str(value)
    if text not in _VALID_TOURS:
        raise ValueError(f"invalid canonical tour: {text}")
    return cast(Tour, text)


def _surface(value: object) -> Surface:
    text = str(value)
    if text not in _VALID_SURFACES:
        raise ValueError(f"invalid canonical surface: {text}")
    return cast(Surface, text)


def load_pre_match_states(path: str | Path) -> list[PreMatchState]:
    """Load only the canonical pre-match table for outcome-free market joining."""

    frame = pd.read_parquet(Path(path))
    leaked = sorted(_PRE_MATCH_FORBIDDEN.intersection(frame.columns))
    if leaked:
        raise ValueError(f"outcome fields leaked into pre-match table: {leaked}")
    missing = sorted(_PRE_MATCH_REQUIRED.difference(frame.columns))
    if missing:
        raise ValueError(f"pre-match table missing required columns: {missing}")
    if frame["match_id"].astype(str).duplicated().any():
        raise ValueError("pre-match table contains duplicate match_id values")

    states: list[PreMatchState] = []
    for row in frame.itertuples(index=False):
        values = row._asdict()
        states.append(
            PreMatchState(
                match_id=str(values["match_id"]),
                tour=_tour(values["tour"]),
                event_date=_event_date(values["event_date"]),
                source_order=int(values["source_order"]),
                tournament_id=str(values["tournament_id"]),
                tournament_name=str(values["tournament_name"]),
                tournament_level=_optional_text(values.get("tournament_level")),
                surface=_surface(values["surface"]),
                round=_optional_text(values.get("round")),
                best_of=_optional_int(values.get("best_of")),
                player_a_id=str(values["player_a_id"]),
                player_b_id=str(values["player_b_id"]),
                player_a_name=str(values["player_a_name"]),
                player_b_name=str(values["player_b_name"]),
                rank_a=_optional_int(values.get("rank_a")),
                rank_b=_optional_int(values.get("rank_b")),
                rank_points_a=_optional_int(values.get("rank_points_a")),
                rank_points_b=_optional_int(values.get("rank_points_b")),
                draw_size=_optional_int(values.get("draw_size")),
                seed_a=_optional_int(values.get("seed_a")),
                seed_b=_optional_int(values.get("seed_b")),
                entry_a=_optional_text(values.get("entry_a")),
                entry_b=_optional_text(values.get("entry_b")),
                hand_a=_optional_text(values.get("hand_a")),
                hand_b=_optional_text(values.get("hand_b")),
                height_cm_a=_optional_int(values.get("height_cm_a")),
                height_cm_b=_optional_int(values.get("height_cm_b")),
                age_years_a=_optional_float(values.get("age_years_a")),
                age_years_b=_optional_float(values.get("age_years_b")),
                ioc_a=_optional_text(values.get("ioc_a")),
                ioc_b=_optional_text(values.get("ioc_b")),
            )
        )
    return states


def discover_betfair_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists():
        raise FileNotFoundError(root_path)
    files = [
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.relative_to(root_path).as_posix())


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _runner_by_id(snapshot: ExchangeMarketSnapshot, selection_id: int):
    matches = [runner for runner in snapshot.runners if runner.selection_id == selection_id]
    if len(matches) != 1:
        raise RuntimeError("joined Betfair selection ID is unavailable in checkpoint snapshot")
    return matches[0]


def _oriented_record_hash(payload: dict[str, object]) -> str:
    key = {"version": _BATCH_VERSION, **payload}
    return hashlib.sha256(_canonical_json_bytes(key)).hexdigest()


def _orient_checkpoint(
    checkpoint: HistoricalMarketCheckpoint,
    snapshot: ExchangeMarketSnapshot,
    join: HistoricalMarketJoin,
) -> OrientedExchangeCheckpoint:
    source_a = _runner_by_id(snapshot, join.source_selection_a_id)
    source_b = _runner_by_id(snapshot, join.source_selection_b_id)
    payload: dict[str, object] = {
        "checkpoint_id": checkpoint.checkpoint_id,
        "join_hash": join.join_hash,
        "match_id": join.match_id,
        "selection_a_id": source_a.selection_id,
        "selection_b_id": source_b.selection_id,
        "best_back_a": source_a.best_back_price,
        "best_lay_a": source_a.best_lay_price,
        "best_back_b": source_b.best_back_price,
        "best_lay_b": source_b.best_lay_price,
        "published_at": checkpoint.published_at.isoformat(),
    }
    return OrientedExchangeCheckpoint(
        record_hash=_oriented_record_hash(payload),
        checkpoint_id=checkpoint.checkpoint_id,
        join_hash=join.join_hash,
        source_market_id=checkpoint.source_market_id,
        source_event_id=checkpoint.source_event_id,
        match_id=join.match_id,
        tour=join.tour,
        checkpoint_name=checkpoint.checkpoint_name,
        published_at=checkpoint.published_at,
        market_time=checkpoint.market_time,
        seconds_to_start=checkpoint.seconds_to_start,
        checkpoint_lag_seconds=checkpoint.checkpoint_lag_seconds,
        data_package=cast(ExchangeDataPackage, checkpoint.data_package),
        market_base_rate=snapshot.market_base_rate,
        market_total_matched=snapshot.market_total_matched,
        source_file_sha256=checkpoint.source_file_sha256,
        source_message_sha256=checkpoint.source_message_sha256,
        selection_a_id=source_a.selection_id,
        selection_b_id=source_b.selection_id,
        selection_a_name=source_a.selection_name,
        selection_b_name=source_b.selection_name,
        best_back_a=source_a.best_back_price,
        best_back_size_a=source_a.best_back_size,
        best_lay_a=source_a.best_lay_price,
        best_lay_size_a=source_a.best_lay_size,
        last_traded_a=source_a.last_traded_price,
        best_back_b=source_b.best_back_price,
        best_back_size_b=source_b.best_back_size,
        best_lay_b=source_b.best_lay_price,
        best_lay_size_b=source_b.best_lay_size,
        last_traded_b=source_b.last_traded_price,
        executable_two_way=checkpoint.executable_two_way,
    )


def _process_market(
    *,
    source_file: str,
    snapshots: list[ExchangeMarketSnapshot],
    pre_match_states: list[PreMatchState],
    days_before_tournament_start: int,
    days_after_tournament_start: int,
) -> MarketHistMarketRecord:
    ordered = sorted(
        snapshots,
        key=lambda item: (
            item.published_at,
            item.source_message_index,
            item.exchange_snapshot_id,
        ),
    )
    reference = ordered[0]
    join_result: HistoricalMarketJoinResult = resolve_betfair_market_to_pre_match(
        reference,
        pre_match_states,
        days_before_tournament_start=days_before_tournament_start,
        days_after_tournament_start=days_after_tournament_start,
    )
    checkpoints: tuple[OrientedExchangeCheckpoint, ...] = ()
    if join_result.join is not None:
        snapshot_by_id = {item.exchange_snapshot_id: item for item in ordered}
        selected = select_preplay_checkpoints(ordered)
        checkpoints = tuple(
            _orient_checkpoint(
                checkpoint,
                snapshot_by_id[checkpoint.exchange_snapshot_id],
                join_result.join,
            )
            for checkpoint in selected
        )
    return MarketHistMarketRecord(
        source_market_id=reference.source_market_id,
        source_event_id=reference.source_event_id,
        source_file=source_file,
        source_file_sha256=reference.source_file_sha256,
        data_package=reference.data_package,
        join_status=join_result.status,
        normalized_runner_names=join_result.normalized_runner_names,
        candidate_match_ids=join_result.candidate_match_ids,
        join=join_result.join,
        checkpoints=checkpoints,
    )


def build_market_hist_records(
    *,
    betfair_root: str | Path,
    pre_match_states: list[PreMatchState],
    data_package: ExchangeDataPackage,
    days_before_tournament_start: int = 4,
    days_after_tournament_start: int = 21,
) -> tuple[list[MarketHistMarketRecord], int, int]:
    root = Path(betfair_root)
    files = discover_betfair_files(root)
    records: list[MarketHistMarketRecord] = []
    files_with_snapshots = 0
    seen_market_ids: set[str] = set()

    for path in files:
        snapshots = load_betfair_exchange_snapshots(path, data_package=data_package)
        if not snapshots:
            continue
        files_with_snapshots += 1
        grouped: dict[str, list[ExchangeMarketSnapshot]] = defaultdict(list)
        for snapshot in snapshots:
            grouped[snapshot.source_market_id].append(snapshot)
        for market_id in sorted(grouped):
            if market_id in seen_market_ids:
                raise ValueError(
                    f"Betfair market {market_id} appeared in more than one source file"
                )
            seen_market_ids.add(market_id)
            records.append(
                _process_market(
                    source_file=path.relative_to(root).as_posix(),
                    snapshots=grouped[market_id],
                    pre_match_states=pre_match_states,
                    days_before_tournament_start=days_before_tournament_start,
                    days_after_tournament_start=days_after_tournament_start,
                )
            )
    records.sort(key=lambda row: (row.source_market_id, row.source_file))
    return records, len(files), files_with_snapshots


def _records_sha256(records: list[MarketHistMarketRecord]) -> str:
    payload = [record.to_dict() for record in records]
    return hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()


def summarize_market_hist_records(
    records: list[MarketHistMarketRecord],
    *,
    data_package: ExchangeDataPackage,
    files_inspected: int,
    files_with_snapshots: int,
) -> MarketHistSummary:
    statuses = Counter(record.join_status for record in records)
    checkpoint_counts: Counter[str] = Counter()
    executable_counts: Counter[str] = Counter()
    package_counts = Counter(record.data_package for record in records)
    for record in records:
        for checkpoint in record.checkpoints:
            checkpoint_counts[checkpoint.checkpoint_name] += 1
            if checkpoint.executable_two_way:
                executable_counts[checkpoint.checkpoint_name] += 1
    matched = statuses["MATCHED"]
    total = len(records)
    return MarketHistSummary(
        batch_version=_BATCH_VERSION,
        data_package=data_package,
        files_inspected=files_inspected,
        files_with_snapshots=files_with_snapshots,
        markets_reconstructed=total,
        markets_matched=matched,
        markets_unmatched=statuses["UNMATCHED"],
        markets_ambiguous=statuses["AMBIGUOUS"],
        join_rate=matched / total if total else 0.0,
        checkpoint_counts=dict(sorted(checkpoint_counts.items())),
        executable_checkpoint_counts=dict(sorted(executable_counts.items())),
        package_counts=dict(sorted(package_counts.items())),
        output_sha256=_records_sha256(records),
    )


def write_market_hist_artifact(
    *,
    output_dir: str | Path,
    records: list[MarketHistMarketRecord],
    summary: MarketHistSummary,
) -> None:
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    records_path = destination / "market_hist_001_records.jsonl"
    summary_path = destination / "market_hist_001_summary.json"
    with records_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record.to_dict(), sort_keys=True) + "\n")
    summary_path.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build MARKET-HIST-001 Betfair artifact")
    parser.add_argument("--betfair-root", required=True, type=Path)
    parser.add_argument("--pre-match", required=True, type=Path)
    parser.add_argument(
        "--data-package",
        required=True,
        choices=("BASIC", "ADVANCED", "PRO"),
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--days-before", type=int, default=4)
    parser.add_argument("--days-after", type=int, default=21)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    states = load_pre_match_states(args.pre_match)
    records, files_inspected, files_with_snapshots = build_market_hist_records(
        betfair_root=args.betfair_root,
        pre_match_states=states,
        data_package=cast(ExchangeDataPackage, args.data_package),
        days_before_tournament_start=args.days_before,
        days_after_tournament_start=args.days_after,
    )
    summary = summarize_market_hist_records(
        records,
        data_package=cast(ExchangeDataPackage, args.data_package),
        files_inspected=files_inspected,
        files_with_snapshots=files_with_snapshots,
    )
    write_market_hist_artifact(
        output_dir=args.output_dir,
        records=records,
        summary=summary,
    )
    print(json.dumps(summary.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
