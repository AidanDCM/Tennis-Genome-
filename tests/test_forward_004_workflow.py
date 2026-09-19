import pathlib

_ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_legacy_forward_004_workflow_is_dispatch_only_and_still_validates_source() -> None:
    workflow = (
        _ROOT / ".github/workflows/wta_forward_004_auto_shadow_chain.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_run:" not in workflow
    assert "provider_run_id:" in workflow
    assert "PROVIDER_RUN_ID: ${{ inputs.provider_run_id }}" in workflow
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


def test_forward_orchestrator_is_sole_automatic_router_and_defaults_to_legacy() -> None:
    orchestrator = (
        _ROOT / ".github/workflows/wta_forward_automation_orchestrator.yml"
    ).read_text(encoding="utf-8")
    legacy = (
        _ROOT / ".github/workflows/wta_forward_004_auto_shadow_chain.yml"
    ).read_text(encoding="utf-8")
    full_slate = (
        _ROOT / ".github/workflows/wta_forward_004_full_slate_manual.yml"
    ).read_text(encoding="utf-8")
    config = __import__("json").loads(
        (_ROOT / "config/forward_automation.json").read_text(encoding="utf-8")
    )

    assert "workflow_run:" in orchestrator
    assert "Prospective Trusted Provider Capture Anchor" in orchestrator
    assert "github.event.workflow_run.conclusion == 'success'" in orchestrator
    assert (
        'run.get("path") != ".github/workflows/prospective_provider_capture_anchor.yml"'
        in orchestrator
    )
    assert 'run.get("head_branch") != "main"' in orchestrator
    assert 'run.get("event") != "workflow_dispatch"' in orchestrator
    assert "workflow_run:" not in legacy
    assert "workflow_run:" not in full_slate

    assert config == {
        "schema_version": "tennis-genome-forward-automation-mode-v1",
        "mode": "LEGACY_SINGLE_TARGET",
        "legacy_workflow": "wta_forward_004_auto_shadow_chain.yml",
        "full_slate_workflow": "wta_forward_004_full_slate_manual.yml",
    }


def test_forward_orchestrator_routes_only_two_versioned_modes() -> None:
    workflow = (
        _ROOT / ".github/workflows/wta_forward_automation_orchestrator.yml"
    ).read_text(encoding="utf-8")

    assert 'allowed = {"LEGACY_SINGLE_TARGET", "FULL_SLATE_V1"}' in workflow
    assert 'if mode == "FULL_SLATE_V1":' in workflow
    assert 'inputs["publish_prospective_evidence"] = True' in workflow
    assert 'if [ "${MODE}" = "LEGACY_SINGLE_TARGET" ]; then' in workflow
    assert 'elif [ "${MODE}" = "FULL_SLATE_V1" ]; then' in workflow
    assert "forward-route-receipt.json" in workflow
    assert 'name: forward-route-${{ github.event.workflow_run.id }}' in workflow


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


def test_full_slate_manual_publication_is_explicitly_opt_in_and_time_gated() -> None:
    workflow = (
        _ROOT / ".github/workflows/wta_forward_004_full_slate_manual.yml"
    ).read_text(encoding="utf-8")

    assert "publish_prospective_evidence:" in workflow
    assert "default: false" in workflow
    assert workflow.count("if: inputs.publish_prospective_evidence == true") == 2
    assert "capture-api-tennis-slate:" in workflow
    assert "uses: ./.github/workflows/api_tennis_slate_extension_capture.yml" in workflow
    assert "datetime.now(UTC) < scheduled" in workflow
    assert "event_id in prestart_ids" in workflow
    assert "captured < scheduled" in workflow
    assert "prospective_evidence_anchor.yml/dispatches" in workflow
    assert "api_tennis_prospective_evidence_from_shared.yml/dispatches" in workflow


def test_api_tennis_full_slate_capture_is_one_request_and_nonpublishing() -> None:
    workflow = (
        _ROOT / ".github/workflows/api_tennis_slate_extension_capture.yml"
    ).read_text(encoding="utf-8")

    assert "workflow_call:" in workflow
    assert "shared_extension_artifact_id:" in workflow
    assert "value: ${{ jobs.capture.outputs.artifact_id }}" in workflow
    assert "artifact_id: ${{ steps.upload.outputs.artifact-id }}" in workflow
    assert "full_slate_artifact_id:" in workflow
    assert "history_artifact_id:" in workflow
    assert "capture_api_tennis_slate_extension.py" in workflow
    assert "provider_request_count" in workflow
    assert "shared_capture_scope" in workflow
    assert 'name: api-tennis-slate-extension-${{ inputs.full_slate_artifact_id }}' in workflow
    assert "challenger_shadow_from_prediction_artifact.yml/dispatches" not in workflow
    assert "prospective_evidence_anchor.yml/dispatches" not in workflow


def test_shared_api_tennis_per_match_workflow_is_offline_and_shadow_compatible() -> None:
    workflow = (
        _ROOT / ".github/workflows/api_tennis_prospective_evidence_from_shared.yml"
    ).read_text(encoding="utf-8")

    assert "shared_extension_artifact_id:" in workflow
    assert "build_api_tennis_prospective_evidence_from_shared.py" in workflow
    assert "local_provider_request_count" in workflow
    assert "source_capture_provider_request_count" in workflow
    assert 'name: api-tennis-prospective-evidence-${{ inputs.prediction_artifact_id }}' in workflow
    assert "challenger_shadow_from_prediction_artifact.yml/dispatches" in workflow
    assert "API_TENNIS_API" not in workflow
    assert "api-tennis.com" not in workflow
