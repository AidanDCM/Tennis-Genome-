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
    assert "FROZEN_LOCAL_HISTORY_ONLY" in text


def test_web_shadow_workflow_rebuilds_pinned_local_history() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Aneeshers/tennis-sackmann-archive" in text
    assert "83733587353df8a41f2fd4f516147d5aa83f5a8d" in text
    assert "wta_matches_${year}.csv" in text
    assert "wta_players.csv" in text
    assert "tennis_genome.pipeline.build_dataset" in text


def test_web_shadow_workflow_has_auditable_active_candidate_trigger() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert '"web-shadow/active-candidate.json"' in text
    assert "web-shadow/fixtures/*.json" in text
    assert "source-fixture.json" in text
    assert "normalized-fixture.json" in text
