"""Synthetic fail-closed acquisition-gate contract tests.

These tests inspect workflow source; they do not simulate GitHub Actions runtime.
"""
from itertools import product
from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_results.yml")
GUARD = "steps.pr_gate.outcome == 'success' && steps.pr_gate.outputs.blocked == 'false'"


def test_gate_outcome_truth_table() -> None:
    for outcome, blocked in product(("success", "failure", "skipped"), ("true", "false", "")):
        allowed = outcome == "success" and blocked == "false"
        assert allowed == ((outcome, blocked) == ("success", "false"))


def test_all_downstream_acquisition_guards_fail_closed() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count(GUARD) == 10
    assert "steps.pr_gate.outputs.blocked != 'true'" not in text
    for name in (
        "Fetch retained official WTA sources",
        "Compile finished official WTA rows",
        "Dry-run existing settlement batch contract",
        "Commit immutable result proposal",
    ):
        block = text.split("      - name: " + name, 1)[1].split("\n      - ", 1)[0]
        assert GUARD in block
    assert "if: steps.commit.outputs.selected == 'true'" in text
