from __future__ import annotations

from pathlib import Path
import subprocess


LAUNCHER = Path("scripts/run_dynamic_state_less_aggressive_real.sh")


def test_real_launcher_is_valid_bash() -> None:
    completed = subprocess.run(
        ["bash", "-n", str(LAUNCHER)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr


def test_real_launcher_pins_exact_research_snapshot_and_hash_gate() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")

    assert "83733587353df8a41f2fd4f516147d5aa83f5a8d" in text
    assert "row_count\": 77850" in text
    assert "row_count\": 71419" in text
    assert "d1003f47322a58ff92ec1dc98d68168c136a7423a58cfd8e9f43530a6b252442" in text
    assert "16c1b6ff231c10169142a6e038d035d56c082f843fe509084eda5436d4b39262" in text
    assert "9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0" in text
    assert "1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8" in text
    assert "56b542915523a5e78bf7eedf91b6fbfea5a83f0a10498496bd4689747e08c0d9" in text
    assert "db75fe1b22ab48c64e024a5acadc44ec1b18f536516ef7fb02f806c672bf1df1" in text


def test_real_launcher_exposes_no_candidate_or_parameter_override() -> None:
    text = LAUNCHER.read_text(encoding="utf-8")

    assert "dynamic_state_search_runner" in text
    assert "--candidate" not in text
    assert "--process-variance" not in text
    assert "--half-life" not in text
    assert "--max-variance" not in text
    assert "--bonferroni" not in text
    assert "--selection" not in text
    assert "len(spec.candidates) == 8" in text
    assert "spec.primary_claim_count == 32" in text
    assert "spec.bonferroni_alpha - 0.0015625" in text
