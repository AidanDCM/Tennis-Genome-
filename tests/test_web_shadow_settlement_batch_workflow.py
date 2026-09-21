from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_settlement_batch.yml")


def test_web_shadow_batch_settlement_workflow_is_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "settle_web_shadow_result_batch.py" in text
    assert '"web-shadow/active-results.json"' in text
    assert "web-shadow/scorecard.json" in text
    assert "settlement-batch-summary.json" in text


def test_web_shadow_batch_settlement_verifies_denominator() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "requested_result_count" in text
    assert "settlement_count" in text
    assert "result batch denominator drift" in text
    assert "production_eligible" in text


def test_web_shadow_batch_settlement_verifies_evaluation_and_evidence_hashes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "evaluation_eligible_count" in text
    assert "excluded_noncompleted_count" in text
    assert "evaluation denominator drift" in text
    assert "correct-count denominator drift" in text
    assert "empty evaluation cohort published accuracy" in text
    assert "result_record_sha256" in text
    assert "settlement_record_sha256" in text
