from __future__ import annotations

from pathlib import Path

import pytest

from tennis_genome.research_workbench.dynamic_state_diagnostic_runner import (
    _DIAGNOSTIC_CODE_COMPONENTS,
    _diagnostic_code_fingerprint,
)


def _repo_root(tmp_path: Path) -> Path:
    for relative in _DIAGNOSTIC_CODE_COMPONENTS:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    return tmp_path


def test_diagnostic_code_fingerprint_binds_all_registered_components(
    tmp_path: Path,
) -> None:
    repo = _repo_root(tmp_path)
    fingerprint = _diagnostic_code_fingerprint(repo)

    assert len(fingerprint.components) == len(_DIAGNOSTIC_CODE_COMPONENTS)
    assert {
        "src/tennis_genome/research_workbench/dynamic_state_diagnostic.py",
        "src/tennis_genome/research_workbench/dynamic_state_diagnostic_runner.py",
    }.issubset({name for name, _ in fingerprint.components})


def test_diagnostic_code_fingerprint_changes_with_diagnostic_code(tmp_path: Path) -> None:
    repo = _repo_root(tmp_path)
    first = _diagnostic_code_fingerprint(repo)

    changed = repo / "src/tennis_genome/research_workbench/dynamic_state_diagnostic.py"
    changed.write_text("changed diagnostic bytes\n", encoding="utf-8")
    second = _diagnostic_code_fingerprint(repo)

    assert first.sha256 != second.sha256


def test_diagnostic_code_fingerprint_fails_closed_on_missing_component(
    tmp_path: Path,
) -> None:
    repo = _repo_root(tmp_path)
    (repo / _DIAGNOSTIC_CODE_COMPONENTS[-1]).unlink()

    with pytest.raises(ValueError, match="required diagnostic code component is missing"):
        _diagnostic_code_fingerprint(repo)
