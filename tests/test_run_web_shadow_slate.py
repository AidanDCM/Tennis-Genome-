from __future__ import annotations

import json
from pathlib import Path

from scripts import run_web_shadow_slate as runner


def _write_fixture(root: Path, name: str) -> Path:
    path = root / "web-shadow" / "fixtures" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def test_load_slate_rejects_duplicate_fixture_paths(monkeypatch, tmp_path: Path) -> None:
    fixture = _write_fixture(tmp_path, "one")
    slate = tmp_path / "web-shadow" / "active-slate.json"
    slate.write_text(
        json.dumps(
            {
                "fixture_paths": [
                    fixture.relative_to(tmp_path).as_posix(),
                    fixture.relative_to(tmp_path).as_posix(),
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    try:
        runner._load_slate(Path("web-shadow/active-slate.json"))
    except ValueError as exc:
        assert "duplicate fixture path" in str(exc)
    else:
        raise AssertionError("duplicate fixture path should fail")


def test_slate_runner_preserves_predicted_plus_skipped_denominator(
    monkeypatch,
    tmp_path: Path,
) -> None:
    first = _write_fixture(tmp_path, "first")
    second = _write_fixture(tmp_path, "second")
    slate = tmp_path / "web-shadow" / "active-slate.json"
    slate.write_text(
        json.dumps(
            {
                "fixture_paths": [
                    first.relative_to(tmp_path).as_posix(),
                    second.relative_to(tmp_path).as_posix(),
                ]
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)

    def build_target(*, fixture_path, target_state_path, normalized_fixture_path, **kwargs):
        if fixture_path.name == "second.json":
            raise RuntimeError("no frozen historical matches")
        target_state_path.parent.mkdir(parents=True, exist_ok=True)
        target_state_path.write_text("{}", encoding="utf-8")
        normalized_fixture_path.write_text("{}", encoding="utf-8")
        return {"player_a_id": "wta:id:1", "player_b_id": "wta:id:2"}

    def build_input(*, output_path, manifest_path, **kwargs):
        output_path.write_text("{}", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "target_history_match_counts": {"wta:id:1": 10, "wta:id:2": 12},
            "minimum_point_exposure": 500,
        }

    def predict(*, output_path, **kwargs):
        record = {
            "fixture": {
                "match_id": "web:wta:test:first",
                "scheduled_start": "2026-09-20T12:00:00+08:00",
            },
            "selected_player": "Alpha",
            "p_player_a": 0.6,
            "p_player_b": 0.4,
            "record_sha256": "a" * 64,
            "production_eligible": False,
        }
        output_path.write_text(json.dumps(record), encoding="utf-8")
        return record

    monkeypatch.setattr(runner, "build_web_shadow_target_state", build_target)
    monkeypatch.setattr(runner, "build_local_web_shadow_matchup", build_input)
    monkeypatch.setattr(runner, "run_web_shadow_prediction", predict)

    summary = runner.run_web_shadow_slate(
        slate_path=Path("web-shadow/active-slate.json"),
        registry_path=tmp_path / "players.csv",
        base_dir=tmp_path / "base",
        bundle_path=tmp_path / "bundle.json",
        model_source_sha="b" * 40,
        output_root=tmp_path / "output",
    )

    assert summary["eligible_target_count"] == 2
    assert summary["predicted_target_count"] == 1
    assert summary["skipped_target_count"] == 1
    assert summary["production_eligible"] is False
    assert summary["skipped_targets"][0]["reason"] == "no frozen historical matches"
