from pathlib import Path

WORKFLOW = Path(".github/workflows/wta_web_shadow_auto_settlement.yml")


def test_auto_settlement_only_consumes_successful_main_push_batches() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'workflows:\n      - "WTA Web Shadow Settlement Batch"' in text
    assert "types:\n      - completed" in text
    assert "branches:\n      - main" in text
    assert "github.event.workflow_run.conclusion == 'success'" in text
    assert "github.event.workflow_run.event == 'push'" in text
    assert "github.event.workflow_run.head_branch == 'main'" in text
    assert (
        "github.event.workflow_run.head_repository.full_name == github.repository"
        in text
    )


def test_auto_settlement_has_minimum_write_permissions() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions: read" in text
    assert "contents: write" in text
    assert "pull-requests: write" in text
    assert "packages: write" not in text
    assert "issues: write" not in text


def test_auto_settlement_resolves_exact_artifact_identity() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'artifact_name="web-shadow-settlement-batch-${SOURCE_RUN_ID}"' in text
    assert "actions/runs/${SOURCE_RUN_ID}/artifacts?per_page=100" in text
    assert "expected exactly one live settlement artifact" in text
    assert "settlement artifact workflow run identity mismatch" in text
    assert "settlement artifact source SHA differs from triggering run" in text
    assert "downloaded settlement artifact digest differs from GitHub metadata" in text


def test_auto_settlement_uses_transactional_applier_and_checks_provenance() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "scripts.apply_web_shadow_settlement_batch" in text
    assert "--source-workflow-run-id" in text
    assert "--source-workflow-sha" in text
    assert "--settlement-artifact-id" in text
    assert "--settlement-artifact-sha256" in text
    assert "settlement apply run ID differs from triggering run" in text
    assert "settlement apply source SHA differs from triggering run" in text
    assert "settlement batch receipt path differs from triggering run" in text


def test_auto_settlement_confines_mutation_and_runs_full_checks() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'path == "web-shadow/scorecard.json"' in text
    assert 'receipt_prefix = f"web-shadow/settlement-batches/{source_run_id}/"' in text
    assert 'parts[3] == "settlements"' in text
    assert "immutable settlement-file count drift" in text
    assert "summary, manifest, and artifact receipt" in text
    assert "ruff check ." in text
    assert "pytest" in text


def test_auto_settlement_is_idempotent_and_never_auto_merges() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'branch="ops/web-shadow-auto-settlement-${SOURCE_RUN_ID}"' in text
    assert "already represented by" in text
    assert "closed without merge" in text
    assert "remote branch" in text
    assert "gh pr create" in text
    assert "No provider requests, model changes, production routing changes" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
