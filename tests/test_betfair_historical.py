from __future__ import annotations

import bz2
import json
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import pytest

from tennis_genome.data.canonical import PreMatchState
from tennis_genome.market.exchange_snapshot import (
    ExchangeMarketSnapshot,
    ExchangeRunnerSnapshot,
)
from tennis_genome.market.historical_checkpoints import select_preplay_checkpoints
from tennis_genome.market.historical_join import resolve_betfair_market_to_pre_match
from tennis_genome.market.providers.betfair_historical import (
    load_betfair_exchange_snapshots,
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


def test_advanced_stream_reconstructs_best_quotes_and_zero_removal(
    tmp_path: Path,
) -> None:
    market_time = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)
    first_time = market_time - timedelta(hours=2)
    second_time = market_time - timedelta(hours=1)
    messages = [
        {
            "op": "mcm",
            "pt": _millis(first_time),
            "mc": [
                {
                    "id": "1.100",
                    "marketDefinition": _definition(market_time),
                    "tv": 2500.0,
                    "rc": [
                        {
                            "id": 101,
                            "ltp": 1.80,
                            "tv": 1200.0,
                            "batb": [[0, 1.79, 100.0], [1, 1.78, 80.0]],
                            "batl": [[0, 1.81, 90.0], [1, 1.82, 70.0]],
                        },
                        {
                            "id": 202,
                            "ltp": 2.20,
                            "tv": 1300.0,
                            "batb": [[0, 2.18, 75.0]],
                            "batl": [[0, 2.22, 65.0]],
                        },
                    ],
                }
            ],
        },
        {
            "op": "mcm",
            "pt": _millis(second_time),
            "mc": [
                {
                    "id": "1.100",
                    "rc": [
                        {
                            "id": 101,
                            "batb": [[0, 1.79, 0.0], [1, 1.80, 110.0]],
                            "batl": [[0, 1.81, 0.0], [1, 1.83, 50.0]],
                            "ltp": 1.82,
                        }
                    ],
                }
            ],
        },
    ]
    path = tmp_path / "market.bz2"
    _write_bz2(path, messages)

    snapshots = load_betfair_exchange_snapshots(path, data_package="ADVANCED")
    assert len(snapshots) == 2
    first, second = snapshots
    alpha_first = next(r for r in first.runners if r.selection_id == 101)
    alpha_second = next(r for r in second.runners if r.selection_id == 101)
    assert alpha_first.best_back_price == pytest.approx(1.79)
    assert alpha_first.best_lay_price == pytest.approx(1.81)
    assert alpha_second.best_back_price == pytest.approx(1.80)
    assert alpha_second.best_lay_price == pytest.approx(1.83)
    assert alpha_second.last_traded_price == pytest.approx(1.82)
    assert first.has_two_way_executable_quotes is True
    assert len(first.source_file_sha256) == 64
    assert len(first.source_message_sha256) == 64


def test_pro_stream_uses_best_prices_from_full_ladder(tmp_path: Path) -> None:
    market_time = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)
    messages = [
        {
            "op": "mcm",
            "pt": _millis(market_time - timedelta(hours=1)),
            "mc": [
                {
                    "id": "1.200",
                    "marketDefinition": _definition(market_time),
                    "rc": [
                        {
                            "id": 101,
                            "atb": [[1.77, 10.0], [1.80, 20.0], [1.79, 30.0]],
                            "atl": [[1.84, 10.0], [1.82, 20.0], [1.83, 30.0]],
                        },
                        {
                            "id": 202,
                            "atb": [[2.18, 10.0]],
                            "atl": [[2.22, 10.0]],
                        },
                    ],
                }
            ],
        }
    ]
    path = tmp_path / "market.bz2"
    _write_bz2(path, messages)
    snapshot = load_betfair_exchange_snapshots(path, data_package="PRO")[0]
    alpha = next(r for r in snapshot.runners if r.selection_id == 101)
    assert alpha.best_back_price == pytest.approx(1.80)
    assert alpha.best_lay_price == pytest.approx(1.82)


def _manual_snapshot(
    *,
    market_time: datetime,
    published_at: datetime,
    status: str = "OPEN",
) -> ExchangeMarketSnapshot:
    runners = (
        ExchangeRunnerSnapshot(
            selection_id=1,
            selection_name="Rafael Nadal",
            best_back_price=1.60,
            best_back_size=100.0,
            best_lay_price=1.62,
            best_lay_size=100.0,
        ),
        ExchangeRunnerSnapshot(
            selection_id=2,
            selection_name="Novak Djokovic",
            best_back_price=2.60,
            best_back_size=100.0,
            best_lay_price=2.64,
            best_lay_size=100.0,
        ),
    )
    return ExchangeMarketSnapshot(
        exchange_snapshot_id=f"snapshot-{published_at.timestamp()}",
        provider="betfair_exchange",
        data_package="ADVANCED",
        source_file_sha256="a" * 64,
        source_message_sha256="b" * 64,
        source_message_index=0,
        source_market_id="1.300",
        source_event_id="event-3",
        event_type_id="2",
        market_type="MATCH_ODDS",
        event_name="Nadal v Djokovic",
        market_time=market_time,
        published_at=published_at,
        market_status=status,
        in_play=False,
        runners=runners,
    )


def test_checkpoint_selection_is_strictly_preplay_and_uses_current_market_time() -> None:
    market_time = datetime(2026, 1, 10, 18, 0, tzinfo=UTC)
    snapshots = [
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(hours=25),
        ),
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(hours=7),
        ),
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(hours=2),
        ),
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(minutes=20),
        ),
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(minutes=5),
        ),
        _manual_snapshot(
            market_time=market_time,
            published_at=market_time - timedelta(minutes=1),
            status="SUSPENDED",
        ),
    ]
    checkpoints = select_preplay_checkpoints(snapshots)
    by_name = {checkpoint.checkpoint_name: checkpoint for checkpoint in checkpoints}
    assert by_name["T-24H"].seconds_to_start == pytest.approx(25 * 60 * 60)
    assert by_name["T-6H"].seconds_to_start == pytest.approx(7 * 60 * 60)
    assert by_name["T-1H"].seconds_to_start == pytest.approx(2 * 60 * 60)
    assert by_name["T-15M"].seconds_to_start == pytest.approx(20 * 60)
    assert by_name["CLOSE_PREPLAY"].seconds_to_start == pytest.approx(5 * 60)


def _pre_match(
    *,
    match_id: str,
    event_date: date,
    player_a_name: str,
    player_b_name: str,
) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=0,
        tournament_id="tournament-1",
        tournament_name="Example Open",
        tournament_level="G",
        surface="Hard",
        round="F",
        best_of=5,
        player_a_id=f"{match_id}-a",
        player_b_id=f"{match_id}-b",
        player_a_name=player_a_name,
        player_b_name=player_b_name,
        rank_a=1,
        rank_b=2,
        rank_points_a=10000,
        rank_points_b=9000,
    )


def test_join_is_order_and_accent_safe_without_outcome_access() -> None:
    market_time = datetime(2021, 9, 12, 20, 0, tzinfo=UTC)
    snapshot = _manual_snapshot(
        market_time=market_time,
        published_at=market_time - timedelta(hours=1),
    )
    canonical = _pre_match(
        match_id="us-open-final",
        event_date=date(2021, 9, 6),
        player_a_name="Novák Djokovic",
        player_b_name="Rafael Nadal",
    )
    result = resolve_betfair_market_to_pre_match(snapshot, [canonical])
    assert result.status == "MATCHED"
    assert result.join is not None
    assert result.join.match_id == "us-open-final"
    assert result.join.source_selection_a_name == "Novak Djokovic"
    assert result.join.source_selection_b_name == "Rafael Nadal"
    assert result.join.tournament_date_offset_days == 6
    assert len(result.join.join_hash) == 64


def test_join_fails_closed_when_pair_and_date_window_are_ambiguous() -> None:
    market_time = datetime(2021, 9, 12, 20, 0, tzinfo=UTC)
    snapshot = _manual_snapshot(
        market_time=market_time,
        published_at=market_time - timedelta(hours=1),
    )
    first = _pre_match(
        match_id="match-one",
        event_date=date(2021, 9, 6),
        player_a_name="Novak Djokovic",
        player_b_name="Rafael Nadal",
    )
    second = _pre_match(
        match_id="match-two",
        event_date=date(2021, 9, 7),
        player_a_name="Rafael Nadal",
        player_b_name="Novak Djokovic",
    )
    result = resolve_betfair_market_to_pre_match(snapshot, [first, second])
    assert result.status == "AMBIGUOUS"
    assert result.join is None
    assert result.candidate_match_ids == ("match-one", "match-two")


def test_basic_data_is_not_marked_executable(tmp_path: Path) -> None:
    market_time = datetime(2026, 1, 2, 18, 0, tzinfo=UTC)
    messages = [
        {
            "op": "mcm",
            "pt": _millis(market_time - timedelta(hours=1)),
            "mc": [
                {
                    "id": "1.400",
                    "marketDefinition": _definition(market_time),
                    "rc": [
                        {"id": 101, "ltp": 1.80},
                        {"id": 202, "ltp": 2.20},
                    ],
                }
            ],
        }
    ]
    path = tmp_path / "basic.bz2"
    _write_bz2(path, messages)
    snapshot = load_betfair_exchange_snapshots(path, data_package="BASIC")[0]
    assert snapshot.has_two_way_executable_quotes is False
    assert all(runner.last_traded_price is not None for runner in snapshot.runners)
