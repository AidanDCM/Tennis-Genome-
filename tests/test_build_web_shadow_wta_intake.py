from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_web_shadow_wta_intake import build_wta_web_shadow_intake


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _config(tmp_path: Path, *, maximum: int = 8) -> Path:
    path = tmp_path / "repo/web-shadow/intake-config.json"
    _write_json(
        path,
        {
            "schema_version": "tennis-genome-web-shadow-intake-config-v1",
            "production_eligible": False,
            "selection_rule": {
                "minimum_lead_hours": 8,
                "maximum_horizon_hours": 48,
                "maximum_matches_per_slate": maximum,
            },
            "tournaments": [
                {
                    "group_id": 1152,
                    "year": 2026,
                    "slug": "singapore",
                    "display_name": "Singapore Tennis Open",
                    "tournament_id": "web:wta:singapore:2026",
                    "tournament_level": "P",
                }
            ],
        },
    )
    return path


def _match(
    *,
    event_id: str,
    start: str,
    player_a: str = "Alpha One",
    player_b: str = "Beta Two",
    player_a_id: int = 101,
    player_b_id: int = 202,
    draw_type: str = "S",
    state: str = "U",
    unscheduled: bool = False,
    not_before: str = "",
    round_id: int = 5,
) -> dict[str, object]:
    return {
        "EventID": event_id,
        "MatchID": f"match-{event_id}",
        "DrawMatchType": draw_type,
        "MatchState": state,
        "Unscheduled": unscheduled,
        "NotBefore": not_before,
        "MatchTimeStamp": start,
        "RoundID": round_id,
        "PlayerA": {"id": player_a_id, "fullName": player_a},
        "PlayerB": {"id": player_b_id, "fullName": player_b},
    }


def _sources(tmp_path: Path, matches: list[dict[str, object]]) -> Path:
    root = tmp_path / "sources"
    _write_json(
        root / "singapore-tournament.json",
        {
            "tournamentGroup": {"id": 1152, "name": "SINGAPORE"},
            "year": 2026,
            "surface": "Hard",
        },
    )
    _write_json(root / "singapore-matches.json", {"matches": matches})
    return root


def _run(
    tmp_path: Path,
    matches: list[dict[str, object]],
    *,
    maximum: int = 8,
    snapshot: str = "test-snapshot",
) -> tuple[dict[str, object], Path]:
    repo = tmp_path / "repo"
    manifest = build_wta_web_shadow_intake(
        config_path=_config(tmp_path, maximum=maximum),
        source_root=_sources(tmp_path, matches),
        repo_root=repo,
        observed_at="2026-09-22T10:00:00+00:00",
        snapshot_id=snapshot,
    )
    return manifest, repo


def test_intake_materializes_sorted_model_blind_slate_and_evidence(
    tmp_path: Path,
) -> None:
    matches = [
        _match(
            event_id="LS002",
            start="2026-09-23T08:00:00+00:00",
            player_a="Gamma Three",
            player_b="Delta Four",
            player_a_id=303,
            player_b_id=404,
        ),
        _match(event_id="LS001", start="2026-09-23T06:00:00+00:00"),
    ]

    manifest, repo = _run(tmp_path, matches)

    assert manifest["selected_match_count"] == 2
    selected = manifest["selected"]
    assert [row["event_id"] for row in selected] == ["LS001", "LS002"]
    assert manifest["selection_rule"]["round_id_map"]["5"] == "R32"
    assert manifest["production_eligible"] is False
    assert manifest["source_match_count"] == 2
    assert manifest["excluded_match_count"] == 0
    assert manifest["exclusion_counts"] == {}

    slate = json.loads((repo / "web-shadow/active-slate.json").read_text())
    assert len(slate["fixture_paths"]) == 2
    first = json.loads((repo / slate["fixture_paths"][0]).read_text())
    assert first["match_id"] == "web:wta:1152:2026:LS001"
    assert first["round"] == "R32"
    assert first["surface"] == "Hard"
    assert first["tournament_level"] == "P"
    assert first["source_observed_at"] == "2026-09-22T10:00:00+00:00"

    evidence = repo / "web-shadow/intake-evidence/test-snapshot"
    assert (evidence / "intake-manifest.json").is_file()
    assert (evidence / "singapore/tournament.json").is_file()
    assert (evidence / "singapore/matches.json").is_file()
    assert len(manifest["source_records"][0]["matches_sha256"]) == 64


def test_intake_filters_schedule_and_state_before_selection(tmp_path: Path) -> None:
    matches = [
        _match(
            event_id="DOUBLE",
            start="2026-09-23T06:00:00+00:00",
            draw_type="D",
        ),
        _match(
            event_id="DONE",
            start="2026-09-23T06:00:00+00:00",
            state="F",
        ),
        _match(
            event_id="UNSCHED",
            start="2026-09-23T06:00:00+00:00",
            unscheduled=True,
        ),
        _match(
            event_id="FOLLOW",
            start="2026-09-23T06:00:00+00:00",
            not_before="Followed By",
        ),
        _match(event_id="SOON", start="2026-09-22T17:00:00+00:00"),
        _match(event_id="LATE", start="2026-09-24T12:00:01+00:00"),
        _match(event_id="GOOD", start="2026-09-23T06:00:00+00:00"),
    ]

    manifest, _ = _run(tmp_path, matches)

    assert manifest["selected_match_count"] == 1
    assert manifest["selected"][0]["event_id"] == "GOOD"
    assert manifest["source_match_count"] == 7
    assert manifest["excluded_match_count"] == 6
    assert manifest["exclusion_counts"] == {
        "insufficient_lead_time": 1,
        "not_singles": 1,
        "not_upcoming": 1,
        "outside_horizon": 1,
        "unscheduled": 2,
    }


def test_intake_applies_fixed_capacity_after_stable_sort(tmp_path: Path) -> None:
    matches = [
        _match(
            event_id="LS003",
            start="2026-09-23T06:00:00+00:00",
            player_a="C A",
            player_b="C B",
            player_a_id=301,
            player_b_id=302,
        ),
        _match(
            event_id="LS001",
            start="2026-09-23T06:00:00+00:00",
            player_a="A A",
            player_b="A B",
            player_a_id=101,
            player_b_id=102,
        ),
        _match(
            event_id="LS002",
            start="2026-09-23T06:00:00+00:00",
            player_a="B A",
            player_b="B B",
            player_a_id=201,
            player_b_id=202,
        ),
    ]

    manifest, _ = _run(tmp_path, matches, maximum=2)

    selected = manifest["selected"]
    assert [row["event_id"] for row in selected] == ["LS001", "LS002"]
    assert manifest["pre_capacity_eligible_count"] == 3
    assert manifest["selected_match_count"] == 2
    assert manifest["exclusion_counts"] == {"capacity": 1}
    assert manifest["source_match_count"] == 3
    assert manifest["excluded_match_count"] == 1


def _existing_fixture(
    repo: Path,
    *,
    match_id: str,
    start: str = "2026-09-23T06:00:00+00:00",
    player_a: str = "Alpha One",
    player_b: str = "Beta Two",
) -> None:
    _write_json(
        repo / "web-shadow/fixtures/existing.json",
        {
            "match_id": match_id,
            "tour": "WTA",
            "tournament": "Singapore Tennis Open",
            "round": "R32",
            "surface": "Hard",
            "scheduled_start": start,
            "player_a": player_a,
            "player_b": player_b,
            "source_url": "https://example.com",
            "source_observed_at": "2026-09-21T10:00:00+00:00",
            "tournament_id": "web:wta:singapore:2026",
            "tournament_level": "P",
            "schedule_source_url": "https://example.com/schedule",
        },
    )


def test_intake_excludes_existing_official_event_id(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _existing_fixture(repo, match_id="web:wta:1152:2026:LS001")
    matches = [
        _match(event_id="LS001", start="2026-09-23T06:00:00+00:00"),
        _match(
            event_id="LS002",
            start="2026-09-23T08:00:00+00:00",
            player_a="Gamma Three",
            player_b="Delta Four",
            player_a_id=303,
            player_b_id=404,
        ),
    ]

    manifest = build_wta_web_shadow_intake(
        config_path=_config(tmp_path),
        source_root=_sources(tmp_path, matches),
        repo_root=repo,
        observed_at="2026-09-22T10:00:00+00:00",
        snapshot_id="event-id-dedupe",
    )

    assert [row["event_id"] for row in manifest["selected"]] == ["LS002"]
    assert manifest["exclusion_counts"]["already_consumed"] == 1


def test_intake_excludes_old_manual_id_by_time_and_players(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _existing_fixture(
        repo,
        match_id="web:wta:singapore:2026:r32:alpha-beta",
        player_a="Béta-Two",
        player_b="Alpha One",
    )
    matches = [
        _match(event_id="LS001", start="2026-09-23T06:00:00+00:00"),
        _match(
            event_id="LS002",
            start="2026-09-23T08:00:00+00:00",
            player_a="Gamma Three",
            player_b="Delta Four",
            player_a_id=303,
            player_b_id=404,
        ),
    ]

    manifest = build_wta_web_shadow_intake(
        config_path=_config(tmp_path),
        source_root=_sources(tmp_path, matches),
        repo_root=repo,
        observed_at="2026-09-22T10:00:00+00:00",
        snapshot_id="legacy-id-dedupe",
    )

    assert [row["event_id"] for row in manifest["selected"]] == ["LS002"]
    assert manifest["exclusion_counts"]["already_consumed"] == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("Unscheduled", "false", "non-boolean Unscheduled"),
        ("MatchTimeStamp", "2026-09-23T06:00:00", "timezone-aware"),
        ("PlayerA", {"id": 101, "fullName": ""}, "player_a_name"),
    ],
)
def test_intake_fails_closed_on_upcoming_schema_drift(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    match = _match(event_id="LS001", start="2026-09-23T06:00:00+00:00")
    match[field] = value

    with pytest.raises(ValueError, match=message):
        _run(tmp_path, [match])


def test_intake_rejects_duplicate_upcoming_event_ids(tmp_path: Path) -> None:
    matches = [
        _match(event_id="LS001", start="2026-09-23T06:00:00+00:00"),
        _match(
            event_id="LS001",
            start="2026-09-23T08:00:00+00:00",
            player_a="Gamma Three",
            player_b="Delta Four",
            player_a_id=303,
            player_b_id=404,
        ),
    ]

    with pytest.raises(ValueError, match="duplicate WTA EventID"):
        _run(tmp_path, matches)


def test_intake_excludes_unsupported_round_without_guessing(tmp_path: Path) -> None:
    matches = [
        _match(
            event_id="QUAL",
            start="2026-09-23T06:00:00+00:00",
            round_id=99,
        ),
        _match(
            event_id="MAIN",
            start="2026-09-23T08:00:00+00:00",
            round_id=5,
            player_a="Gamma Three",
            player_b="Delta Four",
            player_a_id=303,
            player_b_id=404,
        ),
    ]

    manifest, _ = _run(tmp_path, matches)

    assert [row["event_id"] for row in manifest["selected"]] == ["MAIN"]
    assert manifest["exclusion_counts"]["unsupported_round_id"] == 1


def test_intake_rejects_tournament_identity_mismatch(tmp_path: Path) -> None:
    config = _config(tmp_path)
    source_root = _sources(
        tmp_path,
        [_match(event_id="LS001", start="2026-09-23T06:00:00+00:00")],
    )
    path = source_root / "singapore-tournament.json"
    payload = json.loads(path.read_text())
    payload["tournamentGroup"]["id"] = 9999
    _write_json(path, payload)

    with pytest.raises(ValueError, match="tournament identity mismatch"):
        build_wta_web_shadow_intake(
            config_path=config,
            source_root=source_root,
            repo_root=tmp_path / "repo",
            observed_at="2026-09-22T10:00:00+00:00",
            snapshot_id="identity",
        )


def test_intake_refuses_empty_slate_without_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    active = repo / "web-shadow/active-slate.json"
    _write_json(active, {"fixture_paths": ["web-shadow/fixtures/old.json"]})
    original = active.read_bytes()
    source_root = _sources(
        tmp_path,
        [
            _match(
                event_id="DONE",
                start="2026-09-23T06:00:00+00:00",
                state="F",
            )
        ],
    )

    with pytest.raises(RuntimeError, match="no eligible unseen matches"):
        build_wta_web_shadow_intake(
            config_path=_config(tmp_path),
            source_root=source_root,
            repo_root=repo,
            observed_at="2026-09-22T10:00:00+00:00",
            snapshot_id="empty",
        )

    assert active.read_bytes() == original
    assert not (repo / "web-shadow/intake-evidence/empty").exists()
