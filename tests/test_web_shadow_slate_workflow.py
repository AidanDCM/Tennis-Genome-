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


def test_web_shadow_slate_enforces_shared_preparation() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "shared_history_load_count" in text
    assert "shared_calculator_load_count" in text
    assert "shared_feature_target_count" in text
    assert "shared_feature_date_pass_count" in text
    assert "did not share one history load" in text
    assert "did not share one calculator load" in text


def test_web_shadow_slate_reruns_on_engine_changes() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for path in (
        '"web-shadow/fixtures/**"',
        '"scripts/run_web_shadow_slate.py"',
        '"scripts/build_web_shadow_local_input.py"',
        '"scripts/build_web_shadow_target_state.py"',
        '"scripts/run_web_shadow_prediction.py"',
        '"src/tennis_genome/features/**"',
        '"src/tennis_genome/ratings/**"',
        '"src/tennis_genome/evaluation/**"',
        '"src/tennis_genome/calculator/**"',
        '"src/tennis_genome/prospective/web_shadow.py"',
        '"artifacts/tge_independent_v1_production/**"',
    ):
        assert path in text


def test_web_shadow_slate_uses_verified_history_cache() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/cache@v4" in text
    assert "id: history-cache" in text
    assert "data/wta-live-base" in text
    assert "data/wta_players.csv" in text
    assert "scripts/manage_web_shadow_history_cache.py" in text
    assert '".github/workflows/wta_web_shadow_slate.yml"' in text
    assert text.count("steps.history-cache.outputs.cache-hit != 'true'") == 4
    assert "scripts.manage_web_shadow_history_cache write" in text
    assert "scripts.manage_web_shadow_history_cache verify" in text
    assert "history-cache-receipt.json" in text


def test_expected_cache_spec_is_only_used_by_cache_manager() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.count("--expected-spec config/web_shadow_history_cache.json") == 2
    runner = text.split("python -m scripts.run_web_shadow_slate", 1)[1]
    runner = runner.split("2>&1 | tee web-shadow-slate-summary.json", 1)[0]
    assert "--expected-spec" not in runner


def test_web_shadow_slate_enables_pip_cache() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert 'cache: "pip"' in text
    assert "cache-dependency-path: requirements/ci.lock" in text


def test_history_cache_omits_timestamped_build_reports() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    cache_block = text.split("name: Restore pinned Web Shadow history cache", 1)[1]
    cache_block = cache_block.split("- name: Download pinned WTA history", 1)[0]
    assert "wta_manifest.json" not in cache_block
    assert "build_output.json" not in cache_block
    assert "wta_pre_match.parquet" in cache_block
    assert "wta_outcomes.parquet" in cache_block
    assert "wta_stats.parquet" in cache_block
