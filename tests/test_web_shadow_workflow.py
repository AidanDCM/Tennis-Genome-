from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/wta_web_shadow_manual.yml")


def test_web_shadow_workflow_is_manual_and_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "workflow_run:" not in text
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "build_web_shadow_local_input.py" in text
    assert "run_web_shadow_prediction.py" in text
    assert "FROZEN_LOCAL_HISTORY_ONLY" in text


def test_web_shadow_workflow_restricts_fixture_and_target_paths() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "web-shadow/fixtures/*.json" in text
    assert "web-shadow/targets/*.json" in text
