from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from scripts import wta_live_prediction_forward_004 as fwd


def _helper():
    def qualified_competitors(event):
        comps = event["competitors"]
        home = next(item for item in comps if item["qualifier"] == "home")
        away = next(item for item in comps if item["qualifier"] == "away")
        return home, away

    def resolve_competitor(comp, by_name, explicit):
        sr = str(comp["id"])
        if sr in explicit:
            return explicit[sr]
        return by_name.get(str(comp["name"]))

    return SimpleNamespace(
        ALLOWED_LEVELS={"wta_250", "wta_500"},
        LEVEL_MAP={"wta_250": "I", "wta_500": "P"},
        SURFACE_MAP={"hard": "Hard", "clay": "Clay"},
        ROUND_MAP={"quarterfinal": "QF"},
        TARGET_MATCH_ID="sr:sport_event:1",
        TARGET_SEASON_ID="sr:season:1",
        TARGET_TOURNEY_DATE=datetime(2026, 9, 18, tzinfo=UTC).date(),
        PARRY_SR="sr:competitor:1",
        STEARNS_SR="sr:competitor:2",
        PARRY_CANONICAL="100",
        STEARNS_CANONICAL="200",
        qualified_competitors=qualified_competitors,
        resolve_competitor=resolve_competitor,
        optional_int=lambda value: None if value is None else int(value),
        provider_full_name=lambda value: value,
        age_years=lambda dob, when: 25.0,
    )


def _summary(
    *,
    event_id: str,
    start: str,
    home_name: str = "Alpha",
    away_name: str = "Beta",
    level: str = "wta_250",
    status: str = "not_started",
    confirmed: bool = True,
):
    return {
        "sport_event": {
            "id": event_id,
            "start_time": start,
            "start_time_confirmed": confirmed,
            "sport_event_context": {
                "category": {"id": "sr:category:6", "name": "WTA"},
                "competition": {
                    "id": "sr:competition:10",
                    "name": "Test WTA",
                    "type": "singles",
                    "level": level,
                },
                "season": {
                    "id": "sr:season:10",
                    "competition_id": "sr:competition:10",
                    "start_date": "2026-09-18",
                },
                "round": {"name": "quarterfinal"},
                "mode": {"best_of": 3},
            },
            "competitors": [
                {
                    "id": "sr:competitor:1",
                    "name": home_name,
                    "qualifier": "home",
                    "seed": 1,
                },
                {
                    "id": "sr:competitor:2",
                    "name": away_name,
                    "qualifier": "away",
                    "seed": 2,
                },
            ],
        },
        "sport_event_status": {"status": status, "match_status": status},
    }



def test_slate_selector_returns_all_eligible_targets_in_deterministic_order() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    by_name = {"Alpha": "100", "Beta": "200"}
    summaries = [
        _summary(event_id="sr:sport_event:30", start="2026-09-18T16:00:00+00:00"),
        _summary(event_id="sr:sport_event:20", start="2026-09-18T15:00:00+00:00"),
        _summary(event_id="sr:sport_event:10", start="2026-09-18T15:00:00+00:00"),
        _summary(
            event_id="sr:sport_event:too-soon",
            start="2026-09-18T13:00:00+00:00",
        ),
    ]

    slate = fwd.select_forward_004_targets(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed,
    )

    assert [resolution["event_id"] for _, resolution in slate] == [
        "sr:sport_event:10",
        "sr:sport_event:20",
        "sr:sport_event:30",
    ]
    assert all(
        resolution["selection_rule"]
        == "all_confirmed_resolvable_wta_main_tour_singles_sorted_by_start_then_event_id"
        for _, resolution in slate
    )


def test_slate_selector_fails_closed_on_duplicate_eligible_event_ids() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    duplicate = _summary(
        event_id="sr:sport_event:10",
        start="2026-09-18T15:00:00+00:00",
    )

    with pytest.raises(RuntimeError, match="duplicate eligible WTA event IDs"):
        fwd.select_forward_004_targets(
            h,
            summaries=[duplicate, duplicate],
            by_name={"Alpha": "100", "Beta": "200"},
            capture_observed_at=observed,
        )



def test_slate_executor_reuses_provider_responses_and_isolates_match_roots(
    tmp_path,
) -> None:
    provider_calls: list[str] = []

    def provider_get(path: str) -> dict[str, object]:
        provider_calls.append(path)
        return {"path": path}

    h = SimpleNamespace(
        http_json=provider_get,
        target_state_from_provider=lambda *args: None,
    )
    prepared_context = object()
    prepare_calls = 0

    def prepare_live_context():
        nonlocal prepare_calls
        prepare_calls += 1
        assert h.http_json("competitions.json") == {"path": "competitions.json"}
        assert h.http_json("seasons.json") == {"path": "seasons.json"}
        return prepared_context

    def run_prediction(*, root, prepared):
        assert prepared is prepared_context
        root.mkdir(parents=True, exist_ok=True)
        common = h.http_json("competitions.json")
        common_again = h.http_json("competitions.json")
        season = h.http_json("seasons/sr:season:10/info.json")
        target = h.http_json(f"sport_events/{h.TARGET_EVENT_ID}/summary.json")
        assert common == common_again == {"path": "competitions.json"}
        assert season == {"path": "seasons/sr:season:10/info.json"}
        assert target["sport_event"]["id"] == h.TARGET_EVENT_ID
        (root / "matchup-input.json").write_text(
            json.dumps({"match_id": h.TARGET_EVENT_ID}),
            encoding="utf-8",
        )
        digest = hashlib.sha256(h.TARGET_EVENT_ID.encode("utf-8")).hexdigest()
        return {
            "prediction_id": f"prediction-{h.TARGET_EVENT_ID}",
            "prediction_record_sha256": digest,
            "chain_head_sha256": digest,
            "p_player_a": 0.6,
            "p_player_b": 0.4,
        }

    module = SimpleNamespace(
        h=h,
        prepare_live_context=prepare_live_context,
        run_prediction=run_prediction,
    )
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    slate = []
    for event_id, start in (
        ("sr:sport_event:10", "2026-09-18T15:00:00+00:00"),
        ("sr:sport_event:20", "2026-09-18T16:00:00+00:00"),
    ):
        summary = _summary(event_id=event_id, start=start)
        resolution = {
            "schema_version": "wta-forward-004-target-resolution-v1",
            "forward_protocol": fwd.FORWARD_PROTOCOL,
            "selection_rule": (
                "all_confirmed_resolvable_wta_main_tour_singles_sorted_by_start_then_event_id"
            ),
            "minimum_capture_lead_minutes": "90",
            "capture_observed_at": observed.isoformat(),
            "event_id": event_id,
            "season_id": "sr:season:10",
            "competition_id": "sr:competition:10",
            "tournament_start_date": "2026-09-18",
            "scheduled_start": start,
            "player_a_canonical_id": "100",
            "player_a_sportradar_id": "sr:competitor:1",
            "player_b_canonical_id": "200",
            "player_b_sportradar_id": "sr:competitor:2",
        }
        slate.append((summary, resolution))

    original_http = h.http_json
    original_target_state = h.target_state_from_provider
    manifest = fwd.run_forward_004_slate(
        module=module,
        slate=tuple(slate),
        provider_batch_record_sha256="a" * 64,
        provider_anchor_comment_id=12345,
        output_root=tmp_path / "slate",
        now=datetime(2026, 9, 18, 13, 0, tzinfo=UTC),
    )

    assert provider_calls == [
        "competitions.json",
        "seasons.json",
        "seasons/sr:season:10/info.json",
    ]
    assert prepare_calls == 1
    assert manifest["provider_unique_request_count"] == 2
    assert manifest["eligible_target_count"] == 2
    assert manifest["target_count"] == 2
    assert manifest["skipped_target_count"] == 0
    assert h.http_json is original_http
    assert h.target_state_from_provider is original_target_state
    roots = [item["prediction_root"] for item in manifest["results"]]
    stems = [item["artifact_stem"] for item in manifest["results"]]
    assert len(set(roots)) == 2
    assert stems == ["sr-sport_event-10", "sr-sport_event-20"]
    for item in manifest["results"]:
        root = tmp_path / "slate" / item["prediction_root"]
        assert (root / "matchup-input.json").is_file()

    lifecycle = fwd.MatchLifecycleLedger(tmp_path / "slate" / "match-lifecycle-ledger")
    audit = lifecycle.verify()
    assert audit.lifecycle_count == 2
    assert set(audit.lifecycle_states.values()) == {"CHAMPION_PREDICTED"}


def test_slate_executor_skips_late_member_and_continues_later_target(tmp_path) -> None:
    predicted: list[str] = []

    prepared_context = object()
    prepare_calls = 0

    def prepare_live_context():
        nonlocal prepare_calls
        prepare_calls += 1
        return prepared_context

    def run_prediction(*, root, prepared):
        assert prepared is prepared_context
        root.mkdir(parents=True, exist_ok=True)
        event_id = h.TARGET_EVENT_ID
        predicted.append(event_id)
        (root / "matchup-input.json").write_text(
            json.dumps({"match_id": event_id}),
            encoding="utf-8",
        )
        digest = hashlib.sha256(event_id.encode("utf-8")).hexdigest()
        return {
            "prediction_id": f"prediction-{event_id}",
            "prediction_record_sha256": digest,
            "chain_head_sha256": digest,
            "p_player_a": 0.6,
            "p_player_b": 0.4,
        }

    h = SimpleNamespace(
        http_json=lambda path: {"path": path},
        target_state_from_provider=lambda *args: None,
    )
    module = SimpleNamespace(
        h=h,
        prepare_live_context=prepare_live_context,
        run_prediction=run_prediction,
    )
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    slate = []
    for event_id, start in (
        ("sr:sport_event:late", "2026-09-18T15:00:00+00:00"),
        ("sr:sport_event:future", "2026-09-18T17:00:00+00:00"),
    ):
        slate.append(
            (
                _summary(event_id=event_id, start=start),
                {
                    "event_id": event_id,
                    "season_id": "sr:season:10",
                    "competition_id": "sr:competition:10",
                    "tournament_start_date": "2026-09-18",
                    "scheduled_start": start,
                    "capture_observed_at": observed.isoformat(),
                    "player_a_canonical_id": "100",
                    "player_a_sportradar_id": "sr:competitor:1",
                    "player_b_canonical_id": "200",
                    "player_b_sportradar_id": "sr:competitor:2",
                },
            )
        )

    manifest = fwd.run_forward_004_slate(
        module=module,
        slate=tuple(slate),
        provider_batch_record_sha256="a" * 64,
        provider_anchor_comment_id=12345,
        output_root=tmp_path / "slate",
        now=datetime(2026, 9, 18, 15, 30, tzinfo=UTC),
    )

    assert prepare_calls == 1
    assert predicted == ["sr:sport_event:future"]
    assert manifest["eligible_target_count"] == 2
    assert manifest["target_count"] == 1
    assert manifest["skipped_target_count"] == 1
    assert manifest["skipped_targets"][0]["event_id"] == "sr:sport_event:late"
    assert manifest["skipped_targets"][0]["skip_reason"] == "SCHEDULED_START_REACHED"


def test_slate_executor_fails_when_all_members_are_late(tmp_path) -> None:
    h = SimpleNamespace(
        http_json=lambda path: {"path": path},
        target_state_from_provider=lambda *args: None,
    )
    prepare_calls = 0

    def prepare_live_context():
        nonlocal prepare_calls
        prepare_calls += 1
        return object()

    module = SimpleNamespace(
        h=h,
        prepare_live_context=prepare_live_context,
        run_prediction=lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("late target must not reach predictor")
        ),
    )
    summary = _summary(
        event_id="sr:sport_event:late",
        start="2026-09-18T15:00:00+00:00",
    )
    resolution = {
        "event_id": "sr:sport_event:late",
        "season_id": "sr:season:10",
        "competition_id": "sr:competition:10",
        "tournament_start_date": "2026-09-18",
        "scheduled_start": "2026-09-18T15:00:00+00:00",
        "player_a_canonical_id": "100",
        "player_a_sportradar_id": "sr:competitor:1",
        "player_b_canonical_id": "200",
        "player_b_sportradar_id": "sr:competitor:2",
    }

    with pytest.raises(RuntimeError, match="no targets remaining pre-start"):
        fwd.run_forward_004_slate(
            module=module,
            slate=((summary, resolution),),
            provider_batch_record_sha256="a" * 64,
            provider_anchor_comment_id=12345,
            output_root=tmp_path / "slate",
            now=datetime(2026, 9, 18, 15, 0, tzinfo=UTC),
        )
    assert prepare_calls == 1


def test_selector_uses_earliest_confirmed_resolvable_target_after_fixed_lead() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    by_name = {"Alpha": "100", "Beta": "200"}
    summaries = [
        _summary(event_id="sr:sport_event:later", start="2026-09-18T16:00:00+00:00"),
        _summary(event_id="sr:sport_event:early", start="2026-09-18T14:00:00+00:00"),
        _summary(event_id="sr:sport_event:too-soon", start="2026-09-18T13:00:00+00:00"),
    ]

    selected, resolution = fwd.select_forward_004_target(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed,
    )

    assert selected["sport_event"]["id"] == "sr:sport_event:early"
    assert resolution["event_id"] == "sr:sport_event:early"
    assert resolution["minimum_capture_lead_minutes"] == "90"
    assert resolution["player_a_canonical_id"] == "100"
    assert resolution["player_b_canonical_id"] == "200"


def test_selector_tie_breaks_by_event_id_and_rejects_ineligible_rows() -> None:
    h = _helper()
    observed = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)
    by_name = {"Alpha": "100", "Beta": "200"}
    start = "2026-09-18T15:00:00+00:00"
    summaries = [
        _summary(event_id="sr:sport_event:20", start=start),
        _summary(event_id="sr:sport_event:10", start=start),
        _summary(
            event_id="sr:sport_event:bad-level",
            start="2026-09-18T14:00:00+00:00",
            level="wta_125",
        ),
        _summary(
            event_id="sr:sport_event:unconfirmed",
            start="2026-09-18T14:00:00+00:00",
            confirmed=False,
        ),
        _summary(
            event_id="sr:sport_event:live",
            start="2026-09-18T14:00:00+00:00",
            status="live",
        ),
    ]

    selected, _ = fwd.select_forward_004_target(
        h,
        summaries=summaries,
        by_name=by_name,
        capture_observed_at=observed,
    )

    assert selected["sport_event"]["id"] == "sr:sport_event:10"


def test_selector_fails_when_no_resolvable_host_exists() -> None:
    h = _helper()
    with pytest.raises(RuntimeError, match="no resolvable pre-match WTA"):
        fwd.select_forward_004_target(
            h,
            summaries=[
                _summary(
                    event_id="sr:sport_event:1",
                    start="2026-09-18T16:00:00+00:00",
                    home_name="Unknown",
                )
            ],
            by_name={"Beta": "200"},
            capture_observed_at=datetime(2026, 9, 18, 12, 0, tzinfo=UTC),
        )


def test_generic_target_state_derives_level_surface_round_and_player_order() -> None:
    h = _helper()
    target = _summary(
        event_id="sr:sport_event:1",
        start="2026-09-18T16:00:00+00:00",
        level="wta_500",
    )
    by_id = {
        "100": {"hand": "R", "height": "180", "dob": "20000101", "country": "USA"},
        "200": {"hand": "L", "height": "175", "dob": "20010101", "country": "CAN"},
    }
    info = {
        "season": {
            "info": {
                "surface": "hard",
                "number_of_competitors": 32,
            }
        }
    }

    state = fwd._generic_target_state(h, target, info, by_id)

    assert state.tournament_level == "P"
    assert state.surface == "Hard"
    assert state.round == "QF"
    assert state.best_of == 3
    assert state.player_a_id == "100"
    assert state.player_b_id == "200"
    assert state.seed_a == 1
    assert state.seed_b == 2


def test_generic_target_state_fails_closed_on_unknown_surface() -> None:
    h = _helper()
    target = _summary(
        event_id="sr:sport_event:1",
        start="2026-09-18T16:00:00+00:00",
    )
    by_id = {
        "100": {"hand": "R", "height": "180", "dob": "20000101", "country": "USA"},
        "200": {"hand": "L", "height": "175", "dob": "20010101", "country": "CAN"},
    }

    with pytest.raises(RuntimeError, match="target surface is unsupported"):
        fwd._generic_target_state(
            h,
            target,
            {"season": {"info": {"surface": "ice"}}},
            by_id,
        )
