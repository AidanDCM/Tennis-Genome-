from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_results.yml")


def test_result_acquisition_runs_hourly_manually_and_self_smokes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cron: "41 * * * *"' in text
    assert "workflow_dispatch:" in text
    assert "branches:\n      - main" in text
    assert '".github/workflows/wta_web_shadow_results.yml"' in text


def test_result_acquisition_has_narrow_write_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "issues: write" not in text
    assert "packages: write" not in text


def test_result_acquisition_preserves_single_review_proposal() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'startswith("automation/wta-web-shadow-results-")' in text
    assert "An unpublished result proposal branch already exists" in text
    assert "Cleaning stale result branch with existing PR" in text
    assert "A result proposal is already open" in text


def test_result_acquisition_uses_official_sources_and_existing_settlement_contract() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts.fetch_web_shadow_wta_source" in text
    assert "scripts.build_web_shadow_wta_results" in text
    assert "scripts.settle_web_shadow_result_batch" in text
    assert "result proposal differs from settlement batch denominator" in text


def test_result_acquisition_confines_mutations_and_runs_full_checks() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'path == "web-shadow/active-results.json"' in text
    assert 'parts[:2] == ("web-shadow", "results")' in text
    assert 'evidence_prefix = f"web-shadow/result-evidence/{snapshot_id}/"' in text
    assert "result acquisition changed an unexpected path" in text
    assert "python -m ruff check ." in text
    assert "python -m pytest -q" in text
    assert "git diff --check" in text


def test_result_acquisition_never_auto_merges_and_preserves_blocked_branch() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "gh pr create" in text
    assert "Auto-merge: disabled" in text
    assert "requires manual PR publication" in text
    assert "compare/main...${BRANCH_NAME}?expand=1" in text
    assert "preserved the validated proposal branch" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
