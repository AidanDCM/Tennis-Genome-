from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from tennis_genome.data.canonical import (
    HistoricalMatch,
    MatchOutcome,
    MatchStats,
    PreMatchState,
)
from tennis_genome.experiments.pattern_confirm import FrozenMarketCoreFit
from tennis_genome.experiments.pattern_confirm_live import (
    append_live_rows,
    build_live_record,
    evaluate_live_family,
    live_record_as_dict,
    load_live_settlements,
    verify_live_record,
)
from tennis_genome.experiments.pattern_confirm_live_identity import (
    build_identity_mapping,
    parse_sportradar_prematch_event,
)
from tennis_genome.experiments.pattern_confirm_production import (
    verify_core_artifact,
    verify_profile_artifact,
)
from tennis_genome.experiments.pattern_confirm_sportradar_crosswalk import (
    crosswalk_as_dict,
    seal_crosswalk,
)
from tennis_genome.experiments.pattern_confirm_sportradar_pipeline import (
    training_population_hash,
)
from tennis_genome.experiments.pattern_confirm_sportradar_source_package import (
    build_live_source_package,
    source_package_as_dict,
)

ROOT = Path(__file__).resolve().parents[1]


def _fit() -> FrozenMarketCoreFit:
    return FrozenMarketCoreFit(
        experiment_id="PATTERN-CONFIRM-001",
        version="pattern-confirm-v1",
        source_bundle_sha256="d" * 64,
        source_claim="synthetic",
        training_rows_sha256="e" * 64,
        training_n=100,
        training_start_year=2016,
        training_end_year=2025,
        intercept=0.0,
        market_logit_slope=1.0,
        core_logit_slope=0.0,
        artifact_sha256="622d07e4a5d010b927ddf1c37900868a61d2e81d67c287f2a41dddaf4932b732",
    )


def _profile():
    artifact = verify_profile_artifact(
        json.loads((ROOT / "research/installment_01/profile_production_001.json").read_text())
    )
    base = _base_history()
    return replace(
        artifact,
        training_n=len(base),
        training_rows_sha256=training_population_hash(base),
    )


def _core():
    artifact = verify_core_artifact(
        json.loads((ROOT / "research/installment_01/core_production_001.json").read_text())
    )
    base = _base_history()
    return replace(
        artifact,
        training_n=len(base),
        training_rows_sha256=training_population_hash(base),
    )


def _summary(
    *,
    event_id: str = "sr:sport_event:123",
    status: str = "not_started",
    start: str = "2026-09-12T17:00:00+00:00",
) -> dict[str, object]:
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start,
            "start_time_confirmed": True,
            "sport_event_context": {
                "category": {"id": "sr:category:3", "name": "ATP"},
                "competition": {
                    "id": "sr:competition:55",
                    "name": "ATP Miami, USA Men Singles",
                    "type": "singles",
                    "level": "atp_1000",
                },
                "round": {"name": "round_of_32"},
                "mode": {"best_of": 3},
                "season": {
                    "id": "sr:season:2026-test",
                    "name": "ATP Miami 2026",
                    "start_date": "2026-09-07",
                    "end_date": "2026-09-20",
                    "year": "2026",
                    "competition_id": "sr:competition:55",
                },
            },
            "competitors": [
                {
                    "id": "sr:competitor:11",
                    "name": "Paul, Tommy",
                    "qualifier": "home",
                    "virtual": False,
                },
                {
                    "id": "sr:competitor:22",
                    "name": "Fritz, Taylor",
                    "qualifier": "away",
                    "virtual": False,
                },
            ],
        },
        "sport_event_status": {"status": status},
    }


def _mapping():
    event = parse_sportradar_prematch_event(_summary())
    return build_identity_mapping(
        market_event_id="odds-event-1",
        market_player_a_name="Tommy Paul",
        market_player_b_name="Taylor Fritz",
        player_a_canonical_id="canonical-a",
        player_b_canonical_id="canonical-b",
        sportradar_event=event,
        method="EXPLICIT_CROSSWALK",
        created_at="2026-09-12T15:00:00+00:00",
    )


def _pre(
    match_id: str,
    event_date: date,
    *,
    a: str,
    b: str,
    order: int,
) -> PreMatchState:
    return PreMatchState(
        match_id=match_id,
        tour="ATP",
        event_date=event_date,
        source_order=order,
        tournament_id="sr:season:fixture",
        tournament_name="Fixture Open",
        tournament_level="A",
        surface="Hard",
        round="R32",
        best_of=3,
        player_a_id=a,
        player_b_id=b,
        player_a_name=a,
        player_b_name=b,
        rank_a=None,
        rank_b=None,
        rank_points_a=None,
        rank_points_b=None,
        seed_a=None,
        seed_b=None,
        entry_a=None,
        entry_b=None,
        hand_a="R",
        hand_b="R",
        height_cm_a=185,
        height_cm_b=190,
        age_years_a=25.0,
        age_years_b=26.0,
        ioc_a="USA",
        ioc_b="USA",
    )


def _history_match(
    match_id: str,
    event_date: date,
    *,
    a: str,
    b: str,
    order: int,
    a_won: bool,
) -> HistoricalMatch:
    return HistoricalMatch(
        pre_match=_pre(match_id, event_date, a=a, b=b, order=order),
        outcome=MatchOutcome(
            match_id=match_id,
            a_won=a_won,
            score=None,
            retirement=False,
            walkover=False,
        ),
        stats=MatchStats(
            match_id=match_id,
            service_points_a=60,
            service_points_b=58,
            first_serve_points_won_a=28,
            second_serve_points_won_a=14,
            first_serve_points_won_b=25,
            second_serve_points_won_b=13,
            duration_minutes=92,
        ),
    )


def _base_history() -> list[HistoricalMatch]:
    return [
        _history_match(
            "b1", date(2025, 1, 2), a="canonical-a", b="canonical-c", order=1, a_won=True
        ),
        _history_match(
            "b2", date(2025, 2, 4), a="canonical-b", b="canonical-c", order=2, a_won=False
        ),
        _history_match(
            "b3", date(2025, 3, 6), a="canonical-a", b="canonical-b", order=3, a_won=True
        ),
        _history_match(
            "b4", date(2025, 4, 8), a="canonical-c", b="canonical-a", order=4, a_won=False
        ),
    ]


def _crosswalk_payload() -> dict[str, object]:
    return crosswalk_as_dict(
        seal_crosswalk(
            {
                "sr:competitor:11": "canonical-a",
                "sr:competitor:22": "canonical-b",
            }
        )
    )


def _source_package_payload(
    *,
    captured_at: datetime | None = None,
    match_id: str = "future-1",
) -> dict[str, object]:
    mapping = _mapping()
    summary = _summary()
    season_info = {
        "season": {
            "id": mapping.season_id,
            "competition_id": mapping.competition_id,
            "competition": {
                "id": mapping.competition_id,
                "name": mapping.competition_name,
                "type": "singles",
                "level": "atp_1000",
            },
            "info": {"surface": "hard", "number_of_competitors": 32},
        }
    }
    profile_a = {
        "competitor": {
            "id": mapping.player_a_sportradar_id,
            "country_code": "USA",
        },
        "info": {
            "date_of_birth": "1998-01-01",
            "handedness": "right",
            "height": 185,
        },
    }
    profile_b = {
        "competitor": {
            "id": mapping.player_b_sportradar_id,
            "country_code": "USA",
        },
        "info": {
            "date_of_birth": "1997-01-01",
            "handedness": "right",
            "height": 188,
        },
    }
    competitions = {
        "competitions": [
            {
                "id": mapping.competition_id,
                "name": mapping.competition_name,
                "type": "singles",
                "level": "atp_1000",
                "category": {"id": "sr:category:3", "name": "ATP"},
            }
        ]
    }
    seasons = {"seasons": []}

    def get_json(url: str, *, headers: dict[str, str]) -> object:
        assert headers == {"x-api-key": "test-secret"}
        if "/sport_events/" in url:
            return summary
        if f"/seasons/{mapping.season_id}/info.json" in url:
            return season_info
        if f"/competitors/{mapping.player_a_sportradar_id}/" in url:
            return profile_a
        if f"/competitors/{mapping.player_b_sportradar_id}/" in url:
            return profile_b
        if url.endswith("/competitions.json"):
            return competitions
        if url.endswith("/seasons.json"):
            return seasons
        raise AssertionError(url)

    package = build_live_source_package(
        match_id=match_id,
        base_history=_base_history(),
        identity_mapping=mapping,
        crosswalk_payload=_crosswalk_payload(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        api_key="test-secret",
        access_level="trial",
        captured_at=captured_at or datetime(2026, 9, 12, 16, 53, 30, tzinfo=UTC),
        get_json=get_json,
    )
    return source_package_as_dict(package)


def _raw(**updates: object) -> dict[str, object]:
    raw: dict[str, object] = {
        "match_id": "future-1",
        "tour": "ATP",
        "market_provider": "THE_ODDS_API_V4_PINNACLE_V1",
        "market_source": "PINNACLE_H2H_V1",
        "market_event_id": "odds-event-1",
        "player_a_market_name": "Tommy Paul",
        "player_b_market_name": "Taylor Fritz",
        "sportradar_summary": _summary(),
        "provider_match_state": "PREMATCH",
        "provider_snapshot_at": "2026-09-12T16:54:00+00:00",
        "ingested_at": "2026-09-12T16:54:20+00:00",
        "prediction_generated_at": "2026-09-12T16:54:25+00:00",
        "prediction_committed_at": "2026-09-12T16:54:30+00:00",
        "decimal_odds_a": 1.80,
        "decimal_odds_b": 2.10,
    }
    raw.update(updates)
    return raw


def _build(
    raw: dict[str, object] | None = None,
    *,
    source_package_payload: dict[str, object] | None = None,
):
    return build_live_record(
        _raw() if raw is None else raw,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        identity_mapping=_mapping(),
        source_package_payload=source_package_payload or _source_package_payload(),
        crosswalk_payload=_crosswalk_payload(),
    )


def _timeline(
    *,
    event_id: str = "sr:sport_event:123",
    actual_start: str | None = "2026-09-12T17:01:00+00:00",
) -> dict[str, object]:
    events: list[dict[str, object]] = []
    if actual_start is not None:
        events.append({"id": 1, "type": "match_started", "time": actual_start})
    return {"sport_event": {"id": event_id}, "timeline": events}


def test_live_intake_computes_market_and_binds_models_and_identity() -> None:
    record = _build()
    expected = (1 / 1.80) / ((1 / 1.80) + (1 / 2.10))
    assert record.market_probability_a == pytest.approx(expected)
    assert (
        record.profile_model_sha256
        == "cc82e93a8465f9430b16316a1f9bf770951631de0aff7d17f8374e5cff523351"
    )
    assert (
        record.core_model_sha256
        == "5097257e2c7e5cf7225b4ce7fd08b405b494766d0c9126427f476fd7b952dbb7"
    )
    assert record.identity_mapping_sha256 == _mapping().artifact_sha256
    assert record.market_event_id == "odds-event-1"
    assert record.sportradar_event_id == "sr:sport_event:123"
    assert record.prospective_state_sha256 == record.prospective_state.artifact_sha256
    assert record.core_probability_a == record.prospective_state.core_probability_a
    assert record.profile_gap == record.prospective_state.profile_gap


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"market_provider": "OTHER"}, "frozen Pinnacle"),
        ({"provider_match_state": "LIVE"}, "PREMATCH"),
        ({"decimal_odds_a": 1.0}, "decimal odds"),
        ({"profile_gap": 0.0}, "externally supplied"),
        ({"core_probability_a": 0.5}, "externally supplied"),
        ({"market_event_id": "wrong"}, "verified identity mapping"),
        ({"player_a_market_name": "Taylor Fritz"}, "competitor names"),
        (
            {
                "sportradar_summary": _summary(status="live"),
            },
            "pre-match",
        ),
        (
            {
                "provider_snapshot_at": "2026-09-12T16:56:00+00:00",
                "ingested_at": "2026-09-12T16:56:20+00:00",
                "prediction_generated_at": "2026-09-12T16:56:25+00:00",
                "prediction_committed_at": "2026-09-12T16:56:30+00:00",
            },
            "five minutes",
        ),
        ({"ingested_at": "2026-09-12T16:59:30+00:00"}, "stale"),
    ],
)
def test_live_intake_fails_closed(updates: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _build(_raw(**updates))


def test_append_rejects_missing_mapping_and_cross_batch_duplicate() -> None:
    first = _build()
    mapping = _mapping()
    with pytest.raises(ValueError, match="no verified identity mapping"):
        append_live_rows(
            existing_rows=[],
            new_rows=[_raw()],
            identity_mappings={},
            source_packages={"future-1": _source_package_payload()},
            crosswalk_payload=_crosswalk_payload(),
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )
    with pytest.raises(ValueError, match="duplicate"):
        append_live_rows(
            existing_rows=[live_record_as_dict(first)],
            new_rows=[_raw()],
            identity_mappings={mapping.market_event_id: mapping},
            source_packages={"future-1": _source_package_payload()},
            crosswalk_payload=_crosswalk_payload(),
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_actual_start_audit_excludes_moved_early_match() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start="2026-09-12T16:57:00+00:00"),
                "outcome_a": True,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    report = evaluate_live_family(
        [record],
        settlements,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        ledger_sha256="6" * 64,
        settlement_sha256="7" * 64,
    )
    assert len(report.timing_exclusions) == 1
    assert report.timing_exclusions[0].reason == "PROVIDER_SNAPSHOT_NOT_T_MINUS_5"
    assert all(
        item["available_qualifying_n"] == 0 for item in report.core_confirmation["hypotheses"]
    )


def test_missing_match_started_is_auditable_exclusion_not_schedule_fallback() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start=None),
                "outcome_a": True,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    report = evaluate_live_family(
        [record],
        settlements,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        ledger_sha256="6" * 64,
        settlement_sha256="7" * 64,
    )
    assert report.timing_exclusions[0].reason == "ACTUAL_START_UNVERIFIED"
    assert report.timing_exclusions[0].actual_start is None


def test_settlement_identity_mismatch_fails() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": "sr:sport_event:wrong",
                "sportradar_timeline": _timeline(event_id="sr:sport_event:wrong"),
                "outcome_a": False,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    with pytest.raises(ValueError, match="Sportradar event ID"):
        evaluate_live_family(
            [record],
            settlements,
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
            ledger_sha256="6" * 64,
            settlement_sha256="7" * 64,
        )


def test_eligible_verified_start_flows_into_existing_confirmation_engine() -> None:
    record = _build()
    settlements = load_live_settlements(
        [
            {
                "match_id": record.match_id,
                "sportradar_event_id": record.sportradar_event_id,
                "sportradar_timeline": _timeline(actual_start="2026-09-12T17:01:00+00:00"),
                "outcome_a": True,
                "retirement": False,
                "walkover": False,
            }
        ]
    )
    report = evaluate_live_family(
        [record],
        settlements,
        fit=_fit(),
        profile_artifact=_profile(),
        core_artifact=_core(),
        ledger_sha256="6" * 64,
        settlement_sha256="7" * 64,
    )
    assert not report.timing_exclusions
    by_id = {item["hypothesis_id"]: item for item in report.core_confirmation["hypotheses"]}
    matched = set(record.core_record.matched_hypotheses)
    assert set(by_id) == {"PC-ATP-PG-LOW", "PC-ATP-PG-ABS-HIGH"}
    for hypothesis_id, item in by_id.items():
        assert item["available_qualifying_n"] == (1 if hypothesis_id in matched else 0)


def test_rehashed_semantic_tampering_still_fails_closed() -> None:
    record = _build()
    payload = live_record_as_dict(record)
    payload["player_a_market_name"] = "Wrong Player"
    unsigned = dict(payload)
    unsigned.pop("record_sha256")
    payload["record_sha256"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    with pytest.raises(ValueError, match="market player A"):
        verify_live_record(
            payload,
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
            identity_mapping=_mapping(),
            source_package_payload=_source_package_payload(),
            crosswalk_payload=_crosswalk_payload(),
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("retirement", "false"),
        ("walkover", 0),
        ("outcome_a", "false"),
    ],
)
def test_settlement_requires_real_json_booleans(field: str, value: object) -> None:
    record = _build()
    raw: dict[str, object] = {
        "match_id": record.match_id,
        "sportradar_event_id": record.sportradar_event_id,
        "sportradar_timeline": _timeline(),
        "outcome_a": True,
        "retirement": False,
        "walkover": False,
    }
    raw[field] = value
    with pytest.raises(ValueError, match="JSON boolean"):
        load_live_settlements([raw])


def test_exact_champion_artifact_hashes_are_runtime_pinned() -> None:
    with pytest.raises(ValueError, match="Market\+Core fit is not the frozen"):
        build_live_record(
            _raw(),
            fit=replace(_fit(), artifact_sha256="9" * 64),
            profile_artifact=_profile(),
            core_artifact=_core(),
            identity_mapping=_mapping(),
            source_package_payload=_source_package_payload(),
            crosswalk_payload=_crosswalk_payload(),
        )
    with pytest.raises(ValueError, match="Profile artifact is not the frozen"):
        build_live_record(
            _raw(),
            fit=_fit(),
            profile_artifact=replace(_profile(), artifact_sha256="9" * 64),
            core_artifact=_core(),
            identity_mapping=_mapping(),
            source_package_payload=_source_package_payload(),
            crosswalk_payload=_crosswalk_payload(),
        )
    with pytest.raises(ValueError, match="Core artifact is not the frozen"):
        build_live_record(
            _raw(),
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=replace(_core(), artifact_sha256="9" * 64),
            identity_mapping=_mapping(),
            source_package_payload=_source_package_payload(),
            crosswalk_payload=_crosswalk_payload(),
        )


def test_live_row_requires_source_package_companion() -> None:
    mapping = _mapping()
    with pytest.raises(ValueError, match="no verified source package"):
        append_live_rows(
            existing_rows=[],
            new_rows=[_raw()],
            identity_mappings={mapping.market_event_id: mapping},
            source_packages={},
            crosswalk_payload=_crosswalk_payload(),
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )


def test_source_package_must_exist_before_prediction_generation() -> None:
    late = _source_package_payload(captured_at=datetime(2026, 9, 12, 16, 54, 26, tzinfo=UTC))
    with pytest.raises(ValueError, match="captured after prediction generation"):
        _build(source_package_payload=late)


def test_caller_cannot_supply_standalone_prospective_state() -> None:
    package = _source_package_payload()
    raw = _raw(prospective_state=package["prospective_state"])
    with pytest.raises(ValueError, match="externally supplied"):
        _build(raw, source_package_payload=package)


def test_market_side_swap_is_reoriented_to_canonical_player_a() -> None:
    canonical = _build()
    swapped = _build(
        _raw(
            player_a_market_name="Taylor Fritz",
            player_b_market_name="Tommy Paul",
            decimal_odds_a=2.10,
            decimal_odds_b=1.80,
        )
    )
    assert swapped.player_a_id == canonical.player_a_id
    assert swapped.player_b_id == canonical.player_b_id
    assert swapped.market_probability_a == pytest.approx(canonical.market_probability_a)
    assert swapped.decimal_odds_a == canonical.decimal_odds_a
    assert swapped.decimal_odds_b == canonical.decimal_odds_b


def test_duplicate_provider_event_is_rejected_even_with_new_internal_id() -> None:
    first = _build()
    second_package = _source_package_payload(match_id="future-2")
    mapping = _mapping()
    with pytest.raises(ValueError, match="duplicate (market_event_id|sportradar_event_id)"):
        append_live_rows(
            existing_rows=[live_record_as_dict(first)],
            new_rows=[_raw(match_id="future-2")],
            identity_mappings={mapping.market_event_id: mapping},
            source_packages={
                "future-1": _source_package_payload(),
                "future-2": second_package,
            },
            crosswalk_payload=_crosswalk_payload(),
            fit=_fit(),
            profile_artifact=_profile(),
            core_artifact=_core(),
        )
