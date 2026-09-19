from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_settlement.yml")


def test_web_shadow_settlement_workflow_is_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "settle_web_shadow_prediction.py" in text
    assert '"web-shadow/active-result.json"' in text
    assert "web-shadow/results/*.json" in text
    assert "WEB_SHADOW_SETTLEMENT" in text
