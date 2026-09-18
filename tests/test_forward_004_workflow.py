import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_forward_004_workflow_is_chained_only_from_trusted_capture() -> None:
    workflow = (
        _ROOT / ".github/workflows/wta_forward_004_auto_shadow_chain.yml"
    ).read_text(encoding="utf-8")

    assert "Prospective Trusted Provider Capture Anchor" in workflow
    assert "github.event.workflow_run.conclusion == 'success'" in workflow
    assert (
        'run.get("path") != ".github/workflows/prospective_provider_capture_anchor.yml"'
        in workflow
    )
    assert 'run.get("head_branch") != "main"' in workflow
    assert 'run.get("event") != "workflow_dispatch"' in workflow
    assert 'API_TENNIS_HISTORY_ARTIFACT_ID: "10531692054"' in workflow
    assert "scripts/wta_live_prediction_forward_004.py" in workflow
    assert "prospective_evidence_anchor.yml/dispatches" in workflow
    assert "api_tennis_prospective_evidence.yml/dispatches" in workflow
    assert (
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
        in workflow
    )


def test_api_tennis_evidence_workflow_chains_to_shadow_and_guards_duplicates() -> None:
    workflow = (
        _ROOT / ".github/workflows/api_tennis_prospective_evidence.yml"
    ).read_text(encoding="utf-8")

    assert "actions: write" in workflow
    assert "Refuse duplicate completed evidence artifact" in workflow
    assert 'name="api-tennis-prospective-evidence-${PREDICTION_ARTIFACT_ID}"' in workflow
    assert "provider_request_count') != 1" in workflow
    assert "target_outcome_consumed') is not False" in workflow
    assert "same_day_history_consumed') is not False" in workflow
    assert "id: upload" in workflow
    assert "steps.upload.outputs.artifact-id" in workflow
    assert "challenger_shadow_from_prediction_artifact.yml/dispatches" in workflow


def test_forward_004_selector_freezes_minimum_lead_contract() -> None:
    source = (
        _ROOT / "scripts/wta_live_prediction_forward_004.py"
    ).read_text(encoding="utf-8")

    assert "MIN_CAPTURE_LEAD = timedelta(minutes=90)" in source
    assert "earliest_confirmed_resolvable_wta_main_tour_singles" in source
    assert 'event.get("start_time_confirmed") is not True' in source
    assert (
        'competition.get("level", "")).lower() not in h.ALLOWED_LEVELS'
        in source
    )


def test_full_slate_manual_workflow_fans_out_legacy_compatible_artifacts() -> None:
    workflow = (
        _ROOT / ".github/workflows/wta_forward_004_full_slate_manual.yml"
    ).read_text(encoding="utf-8")

    assert "package-targets:" in workflow
    assert "fromJSON(needs.predict-slate.outputs.target_matrix)" in workflow
    assert "forward-004-full-slate-bundle-${{ github.run_id }}" in workflow
    assert "name: wta-forward-004-slate-${{ matrix.artifact_stem }}-" in workflow
    assert "per-match-artifact/provider-run.json" in workflow
    assert "per-match-artifact/forward-004-target-resolution.json" in workflow
    assert "per-match-artifact/prediction-work/prediction-record-sha256.txt" in workflow
    assert "per-match-artifact/prediction-work/chain-head-sha256.txt" in workflow
    assert "slate-parent-receipt.json" in workflow

    parent_name = "name: forward-004-full-slate-bundle-${{ github.run_id }}"
    assert parent_name in workflow
    assert "name: wta-forward-004-full-slate-manual-" not in workflow
    assert "prospective_evidence_anchor.yml/dispatches" not in workflow


def test_api_tennis_full_slate_capture_is_one_request_and_nonpublishing() -> None:
    workflow = (
        _ROOT / ".github/workflows/api_tennis_slate_extension_capture.yml"
    ).read_text(encoding="utf-8")

    assert "full_slate_artifact_id:" in workflow
    assert "history_artifact_id:" in workflow
    assert "capture_api_tennis_slate_extension.py" in workflow
    assert "provider_request_count" in workflow
    assert "shared_capture_scope" in workflow
    assert 'name: api-tennis-slate-extension-${{ inputs.full_slate_artifact_id }}' in workflow
    assert "challenger_shadow_from_prediction_artifact.yml/dispatches" not in workflow
    assert "prospective_evidence_anchor.yml/dispatches" not in workflow
