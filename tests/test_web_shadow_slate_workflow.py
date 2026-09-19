from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_slate.yml")


def test_web_shadow_slate_workflow_is_provider_free() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "python -m scripts.run_web_shadow_slate" in text
    assert "active-slate.json" in text
    assert "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02" in text
    assert "wta_matches_2026.csv" in text
    assert "wta_matches_qual_itf_2026.csv" in text
    assert "PINNED_HISTORY_MAX_DATE: 2026-06-02" in text
    assert "scripts.reconcile_web_shadow_2026_history" in text
    assert "wta_matches_qual_itf_2026_reconciled.csv" in text
    assert "2026-source-reconciliation.json" in text
    assert "--expected-exact-duplicate-rows 216" in text
    assert "--expected-cross-source-overlap-rows 0" in text


def test_web_shadow_slate_rebuilds_history_once() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("tennis_genome.pipeline.build_dataset") == 1
    assert "predicted + skipped differs from slate denominator" in text


def test_web_shadow_slate_retains_failure_diagnostics() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "2>&1 | tee web-shadow-slate-summary.json" in text
    assert "if: always()" in text
    assert "if-no-files-found: warn" in text
