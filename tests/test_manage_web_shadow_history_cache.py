from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import manage_web_shadow_history_cache as cache


def _populate_files(root: Path) -> None:
    for relative in cache._HASHED_FILES:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.as_posix().encode("utf-8"))


def _history():
    good = SimpleNamespace(
        pre_match=SimpleNamespace(event_date=date(2026, 6, 2)),
        outcome=SimpleNamespace(walkover=False, retirement=False),
    )
    walkover = SimpleNamespace(
        pre_match=SimpleNamespace(event_date=date(2026, 6, 1)),
        outcome=SimpleNamespace(walkover=True, retirement=False),
    )
    return [good, walkover]


def _write_expected_spec(root: Path) -> Path:
    path = root / "expected-history-cache.json"
    payload = {
        "schema_version": cache._SCHEMA,
        "binding": {
            "archive_repo": "Aneeshers/tennis-sackmann-archive",
            "archive_commit": "a" * 40,
            "matches_2026_blob": "b" * 40,
            "qual_itf_2026_blob": "c" * 40,
            "expected_history_max_date": "2026-06-02",
        },
        "history": {
            "canonical_match_count": 2,
            "eligible_match_count": 1,
            "max_eligible_event_date": "2026-06-02",
        },
        "files_sha256": {
            relative.as_posix(): cache._sha256_file(root / relative)
            for relative in cache._HASHED_FILES
        },
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _kwargs(root: Path, expected_spec_path: Path) -> dict[str, object]:
    return {
        "root": root,
        "expected_spec_path": expected_spec_path,
        "archive_repo": "Aneeshers/tennis-sackmann-archive",
        "archive_commit": "a" * 40,
        "matches_2026_blob": "b" * 40,
        "qual_itf_2026_blob": "c" * 40,
        "expected_history_max_date": "2026-06-02",
    }


def test_history_cache_receipt_round_trips(monkeypatch, tmp_path: Path) -> None:
    _populate_files(tmp_path)
    monkeypatch.setattr(cache, "load_canonical_parquet", lambda **kwargs: _history())
    expected_spec = _write_expected_spec(tmp_path)

    receipt = cache.write_history_cache_receipt(**_kwargs(tmp_path, expected_spec))
    monkeypatch.setattr(
        cache,
        "load_canonical_parquet",
        lambda **kwargs: (_ for _ in ()).throw(
            AssertionError("warm verification must not reload canonical history")
        ),
    )
    observed = cache.verify_history_cache_receipt(**_kwargs(tmp_path, expected_spec))

    assert observed == receipt
    assert receipt["history"] == {
        "canonical_match_count": 2,
        "eligible_match_count": 1,
        "max_eligible_event_date": "2026-06-02",
    }


def test_history_cache_rejects_file_tampering(monkeypatch, tmp_path: Path) -> None:
    _populate_files(tmp_path)
    monkeypatch.setattr(cache, "load_canonical_parquet", lambda **kwargs: _history())
    expected_spec = _write_expected_spec(tmp_path)
    cache.write_history_cache_receipt(**_kwargs(tmp_path, expected_spec))

    tampered = tmp_path / "data/wta_players.csv"
    tampered.write_text("tampered", encoding="utf-8")

    with pytest.raises(RuntimeError, match="hash mismatch"):
        cache.verify_history_cache_receipt(**_kwargs(tmp_path, expected_spec))


def test_history_cache_rejects_binding_drift(monkeypatch, tmp_path: Path) -> None:
    _populate_files(tmp_path)
    monkeypatch.setattr(cache, "load_canonical_parquet", lambda **kwargs: _history())
    expected_spec = _write_expected_spec(tmp_path)
    cache.write_history_cache_receipt(**_kwargs(tmp_path, expected_spec))

    changed = _kwargs(tmp_path, expected_spec)
    changed["archive_commit"] = "d" * 40
    with pytest.raises(RuntimeError, match="binding differs"):
        cache.verify_history_cache_receipt(**changed)


def test_history_cache_rejects_wrong_max_date(monkeypatch, tmp_path: Path) -> None:
    _populate_files(tmp_path)
    monkeypatch.setattr(cache, "load_canonical_parquet", lambda **kwargs: _history())
    expected_spec = _write_expected_spec(tmp_path)
    changed = _kwargs(tmp_path, expected_spec)
    changed["expected_history_max_date"] = "2026-06-01"

    with pytest.raises(RuntimeError, match="maximum date differs"):
        cache.write_history_cache_receipt(**changed)


def test_cache_identity_excludes_timestamped_build_reports() -> None:
    paths = {path.as_posix() for path in cache._HASHED_FILES}
    assert "data/wta-live-base/wta_manifest.json" not in paths
    assert "data/wta-live-base/build_output.json" not in paths
    assert "data/wta-live-base/wta_pre_match.parquet" in paths
    assert "data/wta-live-base/wta_outcomes.parquet" in paths
    assert "data/wta-live-base/wta_stats.parquet" in paths
