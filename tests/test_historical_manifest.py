from __future__ import annotations

import json
from pathlib import Path

import pytest

from tennis_genome.market.historical_manifest import (
    build_historical_source_manifest,
    load_historical_source_manifest,
    verify_historical_source_manifest,
    write_historical_source_manifest,
)


def _source_tree(root: Path) -> None:
    (root / "2024" / "01").mkdir(parents=True)
    (root / "2024" / "01" / "market-a.bz2").write_bytes(b"alpha")
    (root / "2024" / "01" / "market-b.json").write_text("beta\n", encoding="utf-8")


def test_manifest_is_deterministic_and_round_trips(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    first = build_historical_source_manifest(
        root=root,
        data_package="ADVANCED",
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    second = build_historical_source_manifest(
        root=root,
        data_package="advanced",
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    assert first == second
    assert first.file_count == 2
    assert [item.relative_path for item in first.files] == [
        "2024/01/market-a.bz2",
        "2024/01/market-b.json",
    ]
    output = tmp_path / "manifest.json"
    write_historical_source_manifest(first, output)
    loaded = load_historical_source_manifest(output)
    assert loaded == first
    verify_historical_source_manifest(loaded, root=root)


def test_manifest_detects_source_content_tampering(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    manifest = build_historical_source_manifest(
        root=root,
        data_package="PRO",
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    target = root / "2024" / "01" / "market-a.bz2"
    target.write_bytes(b"omega")
    with pytest.raises(ValueError, match="hash changed"):
        verify_historical_source_manifest(manifest, root=root)


def test_manifest_detects_extra_or_missing_source_file(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    manifest = build_historical_source_manifest(
        root=root,
        data_package="ADVANCED",
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    extra = root / "extra.jsonl"
    extra.write_text("{}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="file set differs"):
        verify_historical_source_manifest(manifest, root=root)
    extra.unlink()
    (root / "2024" / "01" / "market-b.json").unlink()
    with pytest.raises(ValueError, match="file set differs"):
        verify_historical_source_manifest(manifest, root=root)


def test_manifest_rejects_post_2025_interval(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    with pytest.raises(ValueError, match="end by 2025-12-31"):
        build_historical_source_manifest(
            root=root,
            data_package="ADVANCED",
            requested_start_date="2025-01-01",
            requested_end_date="2026-01-01",
        )


def test_manifest_rejects_unsupported_package(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    with pytest.raises(ValueError, match="ADVANCED or PRO"):
        build_historical_source_manifest(
            root=root,
            data_package="BASIC",
            requested_start_date="2024-01-01",
            requested_end_date="2024-12-31",
        )


def test_manifest_loader_detects_metadata_tampering(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    _source_tree(root)
    manifest = build_historical_source_manifest(
        root=root,
        data_package="ADVANCED",
        requested_start_date="2024-01-01",
        requested_end_date="2024-12-31",
    )
    output = tmp_path / "manifest.json"
    write_historical_source_manifest(manifest, output)
    payload = json.loads(output.read_text(encoding="utf-8"))
    payload["total_bytes"] += 1
    output.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="total_bytes mismatch"):
        load_historical_source_manifest(output)


def test_empty_source_file_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "betfair"
    root.mkdir()
    (root / "empty.bz2").write_bytes(b"")
    with pytest.raises(ValueError, match="empty file"):
        build_historical_source_manifest(
            root=root,
            data_package="ADVANCED",
            requested_start_date="2024-01-01",
            requested_end_date="2024-12-31",
        )
