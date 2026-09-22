from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import scripts.build_web_shadow_wta_intake as cli


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        config=tmp_path / "config.json",
        source_root=tmp_path / "source",
        repo_root=tmp_path / "repo",
        observed_at="2026-09-22T10:00:00+00:00",
        snapshot_id="snapshot",
    )


def test_cli_returns_distinct_no_eligible_exit_code(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    def no_matches(**_: object) -> dict[str, object]:
        raise RuntimeError("deterministic WTA intake found no eligible unseen matches")

    monkeypatch.setattr(cli, "build_wta_web_shadow_intake", no_matches)

    assert cli._run(_args(tmp_path)) == cli.NO_ELIGIBLE_EXIT_CODE
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "NO_ELIGIBLE_MATCHES"


def test_cli_does_not_mask_other_runtime_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def broken(**_: object) -> dict[str, object]:
        raise RuntimeError("WTA intake source denominator accounting drift")

    monkeypatch.setattr(cli, "build_wta_web_shadow_intake", broken)

    with pytest.raises(RuntimeError, match="source denominator accounting drift"):
        cli._run(_args(tmp_path))


def test_cli_success_prints_manifest(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    expected = {
        "schema_version": "tennis-genome-web-shadow-wta-intake-v1",
        "selected_match_count": 2,
    }

    def success(**_: object) -> dict[str, object]:
        return expected

    monkeypatch.setattr(cli, "build_wta_web_shadow_intake", success)

    assert cli._run(_args(tmp_path)) == 0
    assert json.loads(capsys.readouterr().out) == expected
