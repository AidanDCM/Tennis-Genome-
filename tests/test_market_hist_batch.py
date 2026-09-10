from __future__ import annotations

import bz2
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pandas as pd
import pytest

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.historical_batch import (
    build_market_hist_records,
    load_pre_match_states,
    summarize_market_hist_records,
)


def _millis(value: datetime) -> int:
    return int(value.timestamp() * 1000)


def _write_bz2(path: Path, messages: list[dict[str, object]]) -> None:
    with bz2.open(path, "wt", encoding="utf-8") as handle:
        for message in messages:
            handle.write(json.dumps(message, separators=(",", ":")))
            handle.write("\n")


def _definition(market_time: datetime) -> dict[str, object]:
    return {
        "eventId": "event-1",
        "eventTypeId": "2",
        "marketType": "MATCH_ODDS",
        "marketTime": market_time.isoformat().replace("+00:00", "Z"),
        "status": "OPEN",
        "inPlay": False,
        "marketBaseRate": 5.0,
        "eventName": "Player Alpha v Player Beta",
        "runners": [
            {"id": 101, "name": "Player Alpha", "status": "ACTIVE"},
            {"id": 202, "name": "Player Beta", "status": "ACTIVE"},
        ],
    }


def _message(
    *,
    market_time: datetime,
    published_at: datetime,
    include_definition: bool,
) -> dict[str, object]:
    change: dict[str, object] = {
        "id": "1.100",
        "tv": 5000.0,
        "rc": [
            {
                "id": 101,
                "ltp": 1.80,
                "batb": [[0, 1.79, 100.0]],
                "batl": [[0, 1.81, 90.0]],
            },
            {
                "id": 202,
                "ltp": 2.20,
                "batb": [[0, 2.18, 75.0]],
                "batl": [[0, 2.22, 65.0]],
            },
        ],
    }
    if include_definition:
        change["marketDefinition"] = _definition(market_time)
    return {
        "op": "mcm",
        "pt": _millis(published_at),
        "mc": [change],
    }


def _pre_match() -> PreMatchState:
    return PreMatchState(
        match_id="match-1",
        tour="ATP",
        event_date=date(2021, 9, 6),
        source_order=0,
        tournament_id="tournament-1",
        tournament_name="Example Open",
        tournament_level="G",
        surface="Hard",
        round="F",
        best_of=5,
        player_a_id="beta-id",
        player_b_id="alpha-id",
        player_a_name="Player Beta",
        player_b_name="Player Alpha",
        rank_a=2,
        rank_b=1,
        rank_points_a=9000,
        rank_points_b=10000,
    )


def test_batch_builds_deterministic_oriented_checkpoint_records(tmp_path: Path) -> None:
    market_time = datetime(2021, 9, 12, 20, 0, tzinfo=UTC)
    published_times = (
        market_time - timedelta(hours=25),
        market_time - timedelta(hours=7),
        market_time - timedelta(hours=2),
        market_time - timedelta(minutes=20),
        market_time - timedelta(minutes=5),
    )
    messages = [
        _message(
            market_time=market_time,
            published_at=published_at,
            include_definition=index == 0,
        )
        for index, published_at in enumerate(published_times)
    ]
    source = tmp_path / "market.bz2"
    _write_bz2(source, messages)

    records, inspected, with_snapshots = build_market_hist_records(
        betfair_root=tmp_path,
        pre_match_states=[_pre_match()],
        data_package="ADVANCED",
    )
    assert inspected == 1
    assert with_snapshots == 1
    assert len(records) == 1
    record = records[0]
    assert record.join_status == "MATCHED"
    assert record.join is not None
    assert record.join.source_selection_a_id == 202
    assert record.join.source_selection_b_id == 101
    assert [item.checkpoint_name for item in record.checkpoints] == [
        "T-24H",
        "T-6H",
        "T-1H",
        "T-15M",
        "CLOSE_PREPLAY",
    ]
    close = record.checkpoints[-1]
    assert close.selection_a_name == "Player Beta"
    assert close.selection_b_name == "Player Alpha"
    assert close.best_back_a == pytest.approx(2.18)
    assert close.best_lay_a == pytest.approx(2.22)
    assert close.best_back_b == pytest.approx(1.79)
    assert close.best_lay_b == pytest.approx(1.81)
    assert close.executable_two_way is True
    assert len(close.record_hash) == 64

    summary = summarize_market_hist_records(
        records,
        data_package="ADVANCED",
        files_inspected=inspected,
        files_with_snapshots=with_snapshots,
    )
    assert summary.markets_matched == 1
    assert summary.join_rate == pytest.approx(1.0)
    assert summary.checkpoint_counts["CLOSE_PREPLAY"] == 1
    assert summary.executable_checkpoint_counts["T-15M"] == 1
    assert len(summary.output_sha256) == 64

    second, _, _ = build_market_hist_records(
        betfair_root=tmp_path,
        pre_match_states=[_pre_match()],
        data_package="ADVANCED",
    )
    second_summary = summarize_market_hist_records(
        second,
        data_package="ADVANCED",
        files_inspected=1,
        files_with_snapshots=1,
    )
    assert second_summary.output_sha256 == summary.output_sha256


def test_batch_rejects_same_market_in_multiple_source_files(tmp_path: Path) -> None:
    market_time = datetime(2021, 9, 12, 20, 0, tzinfo=UTC)
    message = _message(
        market_time=market_time,
        published_at=market_time - timedelta(hours=1),
        include_definition=True,
    )
    _write_bz2(tmp_path / "first.bz2", [message])
    _write_bz2(tmp_path / "second.bz2", [message])

    with pytest.raises(ValueError, match="appeared in more than one source file"):
        build_market_hist_records(
            betfair_root=tmp_path,
            pre_match_states=[_pre_match()],
            data_package="ADVANCED",
        )


def test_pre_match_loader_rejects_outcome_columns(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {
                "match_id": "match-1",
                "tour": "ATP",
                "event_date": date(2021, 9, 6),
                "source_order": 0,
                "tournament_id": "tournament-1",
                "tournament_name": "Example Open",
                "tournament_level": "G",
                "surface": "Hard",
                "round": "F",
                "best_of": 5,
                "player_a_id": "a",
                "player_b_id": "b",
                "player_a_name": "Player Alpha",
                "player_b_name": "Player Beta",
                "rank_a": 1,
                "rank_b": 2,
                "rank_points_a": 10000,
                "rank_points_b": 9000,
                "a_won": True,
            }
        ]
    )
    path = tmp_path / "pre_match.parquet"
    frame.to_parquet(path, index=False)
    with pytest.raises(ValueError, match="outcome fields leaked"):
        load_pre_match_states(path)
