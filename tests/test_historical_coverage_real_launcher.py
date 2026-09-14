from __future__ import annotations

import subprocess

LAUNCHER = "scripts/run_historical_coverage_audit_real.sh"


def _text() -> str:
    with open(LAUNCHER, encoding="utf-8") as handle:
        return handle.read()


def test_coverage_launcher_is_valid_bash() -> None:
    completed = subprocess.run(
        ["bash", "-n", LAUNCHER],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_coverage_launcher_pins_exact_archived_snapshot_and_hashes() -> None:
    text = _text()
    assert "83733587353df8a41f2fd4f516147d5aa83f5a8d" in text
    assert '"row_count": 77850' in text
    assert '"row_count": 71419' in text
    for digest in (
        "d1003f47322a58ff92ec1dc98d68168c136a7423a58cfd8e9f43530a6b252442",
        "16c1b6ff231c10169142a6e038d035d56c082f843fe509084eda5436d4b39262",
        "9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0",
        "1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8",
        "56b542915523a5e78bf7eedf91b6fbfea5a83f0a10498496bd4689747e08c0d9",
        "db75fe1b22ab48c64e024a5acadc44ec1b18f536516ef7fb02f806c672bf1df1",
    ):
        assert digest in text


def test_coverage_launcher_cannot_open_dynamic_candidate_outcomes() -> None:
    text = _text()
    assert "historical_coverage_audit" in text
    assert "dynamic_state_search_runner" not in text
    assert "dynamic_state_less_aggressive" not in text
    assert "candidate" not in text.lower()
    assert "selection_status" not in text
    assert "selected_candidate" not in text


def test_coverage_launcher_keeps_result_descriptive_only() -> None:
    text = _text()
    assert "DESCRIPTIVE_ONLY" in text
    assert "No year is excluded or promoted by this audit" in text
    assert "does not establish causality" in text
