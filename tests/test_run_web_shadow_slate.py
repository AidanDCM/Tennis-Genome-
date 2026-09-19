from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

from scripts import run_web_shadow_slate as runner


def _write_fixture(root: Path, name: str) -> Path:
    path = root / "web-shadow" / "fixtures" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}", encoding="utf-8")
    return path


def _target(name: str) -> SimpleNamespace:
    suffix = "1" if name == "first" else "2"
    return SimpleNamespace(
        match_id=f"web:wta:test:{suffix}",
        player_a_id=f"wta:id:{suffix}00",
        player_b_id=f"wta:id:{suffix}99",
        event_date=date(2026, 9, 20),
    )


def _patch_shared_runtime(monkeypatch) -> dict[str, int]:
    calls = {
        "history": 0,
        "snapshots": 0,
        "calculator": 0,
    }

    prepared = SimpleNamespace(
        base_history=(object(), object()),
        max_history_date=date(2026, 6, 2),
        history_mode="FROZEN_LOCAL_HISTORY_ONLY",
    )

    def prepare_history(**kwargs):
        calls["history"] += 1
        return prepared

    def load_calculator(path):
        calls["calculator"] += 1
        return object()

    def load_fixture(path):
        return SimpleNamespace()

    def load_target(path, fixture):
        name = path.parent.name
        return _target(name)

    def target_counts(prepared_history, target):
        return {
            target.player_a_id: 10,
            target.player_b_id: 12,
        }

    def snapshots(*, prepared, targets):
        calls["snapshots"] += 1
        return (
            {
                target.match_id: SimpleNamespace(match_id=target.match_id)
                for target in targets
            },
            {
                target.match_id: SimpleNamespace(match_id=target.match_id)
                for target in targets
            },
            1 if targets else 0,
        )

    monkeypatch.setattr(runner, "prepare_web_shadow_history", prepare_history)
    monkeypatch.setattr(runner, "load_validated_matchup_calculator", load_calculator)
    monkeypatch.setattr(runner, "load_web_shadow_fixture", load_fixture)
    monkeypatch.setattr(runner, "load_web_shadow_target_state", load_target)
    monkeypatch.setattr(runner, "target_history_counts", target_counts)
    monkeypatch.setattr(runner, "prepare_web_shadow_snapshots", snapshots)
    return calls


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
    calls = _patch_shared_runtime(monkeypatch)

    def build_target(*, fixture_path, target_state_path, normalized_fixture_path, **kwargs):
        if fixture_path.name == "second.json":
            raise RuntimeError("no frozen historical matches")
        target_state_path.parent.mkdir(parents=True, exist_ok=True)
        target_state_path.write_text("{}", encoding="utf-8")
        normalized_fixture_path.write_text("{}", encoding="utf-8")
        return {}

    def build_input(*, output_path, manifest_path, **kwargs):
        output_path.write_text("{}", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "target_history_match_counts": {"wta:id:100": 10, "wta:id:199": 12},
            "minimum_point_exposure": 500,
        }

    def predict(*, output_path, calculator, **kwargs):
        assert calculator is not None
        record = {
            "fixture": {
                "match_id": "web:wta:test:1",
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
    assert summary["shared_history_load_count"] == 1
    assert summary["shared_feature_date_pass_count"] == 1
    assert summary["shared_calculator_load_count"] == 1
    assert calls == {"history": 1, "snapshots": 1, "calculator": 1}


def test_same_day_targets_share_one_feature_preparation(
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
    calls = _patch_shared_runtime(monkeypatch)

    def build_target(*, target_state_path, normalized_fixture_path, **kwargs):
        target_state_path.parent.mkdir(parents=True, exist_ok=True)
        target_state_path.write_text("{}", encoding="utf-8")
        normalized_fixture_path.write_text("{}", encoding="utf-8")
        return {}

    def build_input(
        *,
        output_path,
        manifest_path,
        prepared_history,
        foundational_snapshot,
        serve_return_snapshot,
        **kwargs,
    ):
        assert prepared_history is not None
        assert foundational_snapshot.match_id == serve_return_snapshot.match_id
        output_path.write_text("{}", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "target_history_match_counts": {"a": 1, "b": 1},
            "minimum_point_exposure": 100,
        }

    def predict(*, fixture_path, output_path, calculator, **kwargs):
        suffix = "1" if fixture_path.parent.name == "first" else "2"
        record = {
            "fixture": {
                "match_id": f"web:wta:test:{suffix}",
                "scheduled_start": "2026-09-20T12:00:00+08:00",
            },
            "selected_player": "Alpha",
            "p_player_a": 0.55,
            "p_player_b": 0.45,
            "record_sha256": suffix * 64,
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

    assert summary["predicted_target_count"] == 2
    assert summary["skipped_target_count"] == 0
    assert summary["shared_feature_target_count"] == 2
    assert summary["shared_feature_date_pass_count"] == 1
    assert calls == {"history": 1, "snapshots": 1, "calculator": 1}
