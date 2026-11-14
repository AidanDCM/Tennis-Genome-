"""Regression guards for WTA empty-intake evidence semantics.

This is a workflow-contract test, not a live provider-availability test.
"""

from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/wta_web_shadow_intake.yml"


def test_empty_intake_is_not_a_selected_proposal() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'echo "selected=false" >> "${GITHUB_OUTPUT}"' in text
    assert "No eligible unseen matches in the frozen intake window." in text
    assert "steps.intake.outputs.selected == 'true'" in text


def test_unexpected_intake_error_is_not_silenced() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cat "${stderr}" >&2' in text
    assert 'exit "${status}"' in text


def test_acquisition_artifact_retained_even_without_selection() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "always() &&" in text
    assert "actions/upload-artifact@v4" in text
    assert "wta-intake-source-${{ github.run_id }}" in text
