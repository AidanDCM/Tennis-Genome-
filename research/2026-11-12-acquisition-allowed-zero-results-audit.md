# 2026-11-12 WTA acquisition: successful gate, zero qualified results

## Pre-specified hypothesis and comparison
Hypothesis: after merging fail-closed PR #458, the first main-branch acquisition run passes the gate, actually fetches official sources and compiles them, but only proposes a result if a completed pending prediction passes identity/provenance matching. Baseline: prior green acquisition runs could skip fetching behind an open PR. Success: gate explicitly allowed, fetch and compile steps succeeded, no result PR if result_count=0. Failure: gate bypass, mutation with zero results, or source steps skipped. This is an operational experiment, not predictive-model testing.

## Observed execution (not a simulation)
- Main SHA: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`, merged [PR #458](https://github.com/AidanDCM/Tennis-Genome-/pull/458) at 2026-11-12T17:33:40Z.
- [Workflow run #43270738286](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286), job `131366271710`, completed success.
- Exact job logs: `WTA_RESULT_ACQUISITION_GATE_STATE=acquisition_allowed`; setup, source fetch, and result compile steps all **success**. Dry-run settlement, mutation-scope verification, full contract check, commit and PR steps all **skipped** because zero matches selected.
- Compiler output (2026-11-12T17:34:14Z): `{"identity_conflict_count":2,"pending_prediction_count":15,"result_count":0,"snapshot_id":"wta-results-20261112t173349z","unfinished_prediction_count":0,"unresolved_prediction_count":13}`.
- Source artifact: [#13967128659](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286/artifacts/13967128659), 124496 bytes, GitHub-reported SHA-256 `87c1a606aec15261b3a9295e767ff2e0add4db28a6ccc162d79ab9ad278ea2ce`. Artifact contents not downloaded/independently verified in this iteration.
- Main scorecard blob `c9636ac9d86c256ccf241e652b9456034c451fc3`: 89 terminal, 86 eligible scored, 47 correct, 15 pending, 79 paired Elo, `production_eligible=false`. Brier 0.2513224181, log loss 0.6966212009 vs fixed 0.5 Brier 0.25, log loss ln(2)=0.69314718056. No independent production-forward denominator established.
- Reproduction (read-only): `gh api repos/AidanDCM/Tennis-Genome-/actions/runs/43270738286/jobs --jq '.jobs[].steps[] | [.name,.conclusion] | @tsv'`; `gh api repos/AidanDCM/Tennis-Genome-/actions/jobs/131366271710/logs | grep -E 'WTA_RESULT_ACQUISITION_GATE_STATE|identity_conflict_count|No currently pending'`; `gh api repos/AidanDCM/Tennis-Genome-/contents/web-shadow/scorecard.json?ref=40bb697ec786527b7ed1a4c67d6d0a92aea17782`.

## Negative evidence / limits
The previous fail-open guard is no longer present on main, but no actual failed/skipped gate runtime scenario was induced. Successful source collection does **not** mean any pending match qualified: 13 remain unresolved, 2 have identity conflicts. Do not backfill or force settlement. The run did not execute pytest or Ruff (full-contract step skipped). No champion change or model gain.

## External research, evaluated cautiously
- Waghmare and Ziegel (first published online 2025-11-13, journal 2026), [Proper Scoring Rules for Estimation and Forecast Evaluation](https://doi.org/10.1146/annurev-statistics-042424-050626), CC BY 4.0 review: evaluate Brier/log loss on exactly paired verified outcomes; theoretical review, not a tennis benchmark; no code imported.
- Wessel et al. (2025), [Enforcing tail calibration when training probabilistic forecast models](https://arxiv.org/abs/2506.13687), wind-speed simulations/models: optimizing proper scores need not guarantee calibration under misspecification; tail improvements can trade off against common-event calibration. Different outcome space and population; implementation license not verified; no code imported.
- Contrary evidence: current shadow Brier 0.251322 is worse than the fixed-0.5 benchmark 0.25, so do not add complexity without independent prospective validation.

## Prioritized next executable queue
1. Download and checksum-verify artifact #13967128659, inspect per-source provenance/coverage and exact reasons for 13 unresolved and 2 identity conflicts; never override identity gates.
2. Add non-mutating runtime integration coverage for failed, skipped, blocked and empty-output gate outcomes; verify downstream write steps remain skipped.
3. Inspect API/source completeness and event-identity coverage for newly scheduled fixtures; preserve pre-start timing and source receipts.
4. Refresh frozen champion SHA and independently qualified production-forward N; only compare new locked chronological paired observations (Brier/log loss, calibration, CIs and coverage).
