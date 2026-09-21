from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_auto_freeze.yml")


def test_auto_freeze_only_consumes_successful_main_push_runs() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'workflows:\n      - "WTA Web Shadow Slate"' in text
    assert "types:\n      - completed" in text
    assert "branches:\n      - main" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in text
    )


def test_auto_freeze_has_minimum_write_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions: read" in text
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "packages: write" not in text
    assert "issues: write" not in text


def test_auto_freeze_resolves_and_verifies_exact_bound_artifact() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'artifact_name="web-shadow-bound-evidence-${SOURCE_RUN_ID}"' in text
    assert "actions/runs/${SOURCE_RUN_ID}/artifacts?per_page=100" in text
    assert "expected exactly one live bound artifact" in text
    assert "artifact workflow run identity mismatch" in text
    assert "bound artifact source SHA differs from triggering run" in text
    assert "^sha256:[0-9a-fA-F]{64}$" in text
    assert "downloaded bound artifact digest differs from GitHub metadata" in text


def test_auto_freeze_uses_transactional_bound_freezer_and_rechecks_provenance() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts.freeze_web_shadow_bound_evidence" in text
    assert "--bound-artifact-id" in text
    assert "--bound-artifact-sha256" in text
    assert "freeze summary run ID differs from triggering run" in text
    assert "freeze summary source SHA differs from triggering run" in text


def test_auto_freeze_confines_mutation_and_runs_full_checks() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'path == "web-shadow/scorecard.json"' in text
    assert 'allowed_prefix = f"web-shadow/slates/{slate_id}/"' in text
    assert "auto-freeze changed an unexpected path" in text
    assert "ruff check ." in text
    assert "pytest" in text


def test_auto_freeze_is_idempotent_and_never_auto_merges() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'branch="ops/web-shadow-auto-freeze-${SOURCE_RUN_ID}"' in text
    assert "already represented by" in text
    assert "closed without merge" in text
    assert "remote branch" in text
    assert "gh pr create" in text
    assert "No provider requests, model changes, production routing changes" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
