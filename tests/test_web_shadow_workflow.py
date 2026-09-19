from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_manual.yml")


def test_web_shadow_workflow_is_provider_free_and_forward_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in text
    assert "schedule:" not in text
    assert "workflow_run:" not in text
    assert "SPORTRADAR" not in text
    assert "API_TENNIS" not in text
    assert "build_web_shadow_target_state.py" in text
    assert "build_web_shadow_local_input.py" in text
    assert "run_web_shadow_prediction.py" in text
    assert "PINNED_PUBLIC_HISTORY_THROUGH_2026_06_02" in text


def test_web_shadow_workflow_rebuilds_pinned_local_history() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Aneeshers/tennis-sackmann-archive" in text
    assert "83733587353df8a41f2fd4f516147d5aa83f5a8d" in text
    assert "wta_matches_${year}.csv" in text
    assert "wta_matches_2026.csv" in text
    assert "wta_matches_qual_itf_2026.csv" in text
    assert "4989661bc24d621417b344d22c5e5a2b8ef5119e" in text
    assert "429fe4fc3a7736fda1d5c711ae587a6146490cf0" in text
    assert "PINNED_HISTORY_MAX_DATE: 2026-06-02" in text
    assert "wta_players.csv" in text
    assert "tennis_genome.pipeline.build_dataset" in text
    assert "scripts.reconcile_web_shadow_2026_history" in text
    assert "wta_matches_qual_itf_2026_reconciled.csv" in text
    assert "2026-source-reconciliation.json" in text


def test_web_shadow_workflow_has_auditable_active_candidate_trigger() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"web-shadow/active-candidate.json"' in text
    assert "web-shadow/fixtures/*.json" in text
    assert "source-fixture.json" in text
    assert "normalized-fixture.json" in text
