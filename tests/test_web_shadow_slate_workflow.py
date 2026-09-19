from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_slate.yml")


def test_web_shadow_slate_workflow_is_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "run_web_shadow_slate.py" in text
    assert "active-slate.json" in text
    assert "FROZEN_LOCAL_HISTORY" not in text or "provider" in text.lower()


def test_web_shadow_slate_rebuilds_history_once() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("tennis_genome.pipeline.build_dataset") == 1
    assert "predicted + skipped differs from slate denominator" in text
