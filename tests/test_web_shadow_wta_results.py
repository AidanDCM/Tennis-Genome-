from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.freeze_web_shadow_artifact import _canonical_sha256
from scripts.web_shadow_wta_result_core import (
    _score,
    _status,
    build_wta_web_shadow_results,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _config(repo_root: Path) -> Path:
    path = repo_root / "web-shadow/intake-config.json"
    _write_json(
        path,
        {
            "schema_version": "tennis-genome-web-shadow-intake-config-v1",
            "production_eligible": False,
            "selection_rule": {
                "minimum_lead_hours": 8,
                "maximum_horizon_hours": 48,
                "maximum_matches_per_slate": 8,
            },
            "tournaments": [
                {
                    "group_id": 1024,
                    "year": 2026,
                    "slug": "seoul",
                    "display_name": "Korea Open",
                    "tournament_id": "web:wta:seoul:2026",
                    "tournament_level": "I",
                }
            ],
        },
    )
    return path


def _prediction(
    repo_root: Path,
    *,
    match_id: str = "web:wta:1024:2026:LS001",
    player_a: str = "Alpha One",
    player_b: str = "Beta Two",
    round_name: str = "R32",
) -> tuple[Path, dict[str, object]]:
    path = repo_root / "web-shadow/slates/test-slate/predictions/test.json"
    payload: dict[str, object] = {
        "record_type": "WEB_SHADOW_PREDICTION",
        "schema_version": "tennis-genome-web-shadow-v1",
        "production_eligible": False,
        "committed_at": "2026-09-21T12:00:00+00:00",
        "p_player_a": 0.6,
        "p_player_b": 0.4,
        "selected_player": player_a,
        "model_source_sha": "a" * 40,
        "input_manifest_sha256": "b" * 64,
        "fixture": {
            "match_id": match_id,
            "tour": "WTA",
            "tournament": "Korea Open",
            "round": round_name,
            "surface": "Hard",
            "scheduled_start": "2026-09-22T10:00:00+00:00",
            "player_a": player_a,
            "player_b": player_b,
            "source_url": "https://example.com/source",
            "source_observed_at": "2026-09-21T11:00:00+00:00",
            "tournament_id": "web:wta:seoul:2026",
            "tournament_level": "I",
            "schedule_source_url": (
                "https://api.wtatennis.com/tennis/tournaments/1024/2026/matches"
            ),
        },
    }
    payload["record_sha256"] = _canonical_sha256(payload)
    _write_json(path, payload)
    return path, payload


def _scorecard(
    repo_root: Path,
    *,
    prediction_path: Path,
    prediction: dict[str, object],
) -> Path:
    path = repo_root / "web-shadow/scorecard.json"
    _write_json(
        path,
        {
            "schema_version": "tennis-genome-web-shadow-scorecard-v1",
            "production_eligible": False,
            "official_slate_count": 1,
            "pending_match_count": 1,
            "settled_match_count": 0,
            "baseline_match_count": 0,
            "slates": [
                {
                    "slate_id": "test-slate",
                    "status": "PENDING_SETTLEMENT",
                    "predictions": [
                        {
                            "match_id": prediction["fixture"]["match_id"],
                            "prediction_path": prediction_path.relative_to(
                                repo_root
                            ).as_posix(),
                            "prediction_record_sha256": prediction["record_sha256"],
                            "selected_player": prediction["selected_player"],
                            "selected_probability": 0.6,
                            "scheduled_start": "2026-09-22T10:00:00+00:00",
                            "status": "PENDING",
                        }
                    ],
                }
            ],
        },
    )
    return path


def _row(
    *,
    match_id: str = "LS001",
    state: str = "F",
    player_a: str = "Alpha One",
    player_b: str = "Beta Two",
    winner: str = "2",
    round_id: str = "5",
    score: str = "6-3,6-4",
    result: str = "A. One d B. Two 6-3,6-4",
) -> dict[str, object]:
    first_a, last_a = player_a.split(" ", 1)
    first_b, last_b = player_b.split(" ", 1)
    return {
        "DrawMatchType": "S",
        "DrawLevelType": "M",
        "EventID": "1024",
        "EventYear": 2026,
        "MatchID": match_id,
        "RoundID": round_id,
        "MatchState": state,
        "PlayerNameFirstA": first_a,
        "PlayerNameLastA": last_a,
        "PlayerNameFirstB": first_b,
        "PlayerNameLastB": last_b,
        "Winner": winner,
        "ScoreString": score,
        "ResultString": result,
        "Message": "",
        "LastUpdated": "2026-09-22T14:30:00+00:00",
    }


def _sources(
    tmp_path: Path,
    *,
    rows: list[dict[str, object]],
    observed_at: str = "2026-09-22T15:00:00+00:00",
) -> tuple[Path, Path, bytes]:
    source_root = tmp_path / "sources"
    source_root.mkdir(parents=True)
    raw = json.dumps({"matches": rows}, separators=(",", ":")).encode("utf-8")
    matches = source_root / "seoul-matches.json"
    matches.write_bytes(raw)
    manifest = tmp_path / "acquisition-manifest.json"
    _write_json(
        manifest,
        {
            "schema_version": "tennis-genome-web-shadow-wta-acquisition-v1",
            "production_eligible": False,
            "observed_at": observed_at,
            "source_records": [
                {
                    "group_id": 1024,
                    "year": 2026,
                    "slug": "seoul",
                    "matches_filename": "seoul-matches.json",
                    "matches_sha256": hashlib.sha256(raw).hexdigest(),
                    "matches_source_url": (
                        "https://api.wtatennis.com/tennis/tournaments/1024/2026/matches"
                    ),
                }
            ],
        },
    )
    return source_root, manifest, raw


def _build(
    tmp_path: Path,
    *,
    match_id: str = "web:wta:1024:2026:LS001",
    rows: list[dict[str, object]] | None = None,
) -> tuple[Path, dict[str, object], bytes]:
    repo_root = tmp_path / "repo"
    config = _config(repo_root)
    prediction_path, prediction = _prediction(repo_root, match_id=match_id)
    scorecard = _scorecard(
        repo_root,
        prediction_path=prediction_path,
        prediction=prediction,
    )
    source_root, acquisition, raw = _sources(
        tmp_path,
        rows=rows if rows is not None else [_row()],
    )
    summary = build_wta_web_shadow_results(
        config_path=config,
        scorecard_path=scorecard,
        acquisition_manifest_path=acquisition,
        source_root=source_root,
        repo_root=repo_root,
        observed_at="2026-09-22T15:00:00+00:00",
        snapshot_id="wta-results-20260922t150000z",
    )
    return repo_root, summary, raw


def test_official_match_id_compiles_finished_result_and_retains_sources(
    tmp_path: Path,
) -> None:
    repo_root, summary, raw = _build(tmp_path)

    assert summary["result_count"] == 1
    result_path = repo_root / summary["result_paths"][0]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["winner"] == "Alpha One"
    assert result["status"] == "COMPLETED"
    assert result["score"] == "6-3 6-4"
    assert result["match_id"] == "web:wta:1024:2026:LS001"
    assert result["production_eligible"] is False

    active = json.loads(
        (repo_root / "web-shadow/active-results.json").read_text(encoding="utf-8")
    )
    assert active["result_paths"] == summary["result_paths"]
    retained = (
        repo_root
        / "web-shadow/result-evidence/wta-results-20260922t150000z"
        / "sources/seoul-matches.json"
    )
    assert retained.read_bytes() == raw


def test_legacy_match_id_resolves_by_tournament_player_pair_and_round(
    tmp_path: Path,
) -> None:
    repo_root, summary, _ = _build(
        tmp_path,
        match_id="web:wta:seoul:2026:r32:alpha-beta",
    )
    result = json.loads(
        (repo_root / summary["result_paths"][0]).read_text(encoding="utf-8")
    )
    assert result["match_id"] == "web:wta:seoul:2026:r32:alpha-beta"
    assert summary["result_count"] == 1


def test_unfinished_official_match_produces_no_repository_mutation(
    tmp_path: Path,
) -> None:
    repo_root, summary, _ = _build(tmp_path, rows=[_row(state="U")])

    assert summary["result_count"] == 0
    assert summary["unfinished_prediction_count"] == 1
    assert not (repo_root / "web-shadow/active-results.json").exists()
    assert not (repo_root / "web-shadow/result-evidence").exists()


def test_official_match_id_player_mismatch_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="player identity mismatch"):
        _build(tmp_path, rows=[_row(player_a="Gamma Three")])


def test_legacy_identity_ambiguity_fails_closed(tmp_path: Path) -> None:
    rows = [_row(match_id="LS001"), _row(match_id="LS002")]
    with pytest.raises(ValueError, match="legacy Web Shadow result identity is ambiguous"):
        _build(
            tmp_path,
            match_id="web:wta:seoul:2026:r32:alpha-beta",
            rows=rows,
        )


@pytest.mark.parametrize(
    ("winner_code", "expected"),
    [("2", "Alpha One"), ("3", "Beta Two")],
)
def test_winner_code_maps_to_official_player_side(
    tmp_path: Path,
    winner_code: str,
    expected: str,
) -> None:
    repo_root, summary, _ = _build(
        tmp_path,
        rows=[_row(winner=winner_code)],
    )
    result = json.loads(
        (repo_root / summary["result_paths"][0]).read_text(encoding="utf-8")
    )
    assert result["winner"] == expected


@pytest.mark.parametrize(
    ("result_string", "score_string", "expected_status", "expected_score"),
    [
        ("A. One d B. Two 6-3 ret.", "6-3", "RETIREMENT", "6-3"),
        ("A. One w/o B. Two", "", "WALKOVER", "W/O"),
        ("A. One d B. Two defaulted", "", "DEFAULTED", "DEFAULT"),
    ],
)
def test_abnormal_finish_classification(
    result_string: str,
    score_string: str,
    expected_status: str,
    expected_score: str,
) -> None:
    row = _row(result=result_string, score=score_string)
    status = _status(row)
    assert status == expected_status
    assert _score(row, status=status) == expected_score
