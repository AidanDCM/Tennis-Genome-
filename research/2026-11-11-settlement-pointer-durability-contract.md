# 2026-11-11 — Active-result pointer durability and replay contract audit

Evidence tier: read-only code audit and seven deterministic assertions; NOT a replay of the entire repository pytest suite; NOT prospective forecasting evidence.

## Prespecified question
H1: Replacing `web-shadow/active-results.json` does not silently append prior results into the next settlement batch. H2: A repeated prior result cannot be accepted once its prediction is no longer PENDING. H3: completed batch output is permanently preserved by this workflow.

Baseline: main's Hong Kong pointer; challenger: PR #428 Chennai pointer. Samples: `web-shadow/results/2026-11-08-hong-kong-2026-f-ls001-claire-liu-alexandra-eala-257608990b.json` and `web-shadow/results/2026-11-09-chennai-2026-f-ls001-janice-tjen-magda-linette-42775ef387.json`.

Sources (main at inspection): `scripts/settle_web_shadow_result_batch.py` blob `fe3da0495e67bcf3e9e6013d15307697df4af4d6`; `.github/workflows/wta_web_shadow_settlement_batch.yml` blob `81eea3a94f2b05b35f4209f658e9977221de3bcf`; `tests/test_settle_web_shadow_result_batch.py` blob `a20d9d85c10be39a45bc9a9deb2c13e1b04c9539`; `web-shadow/active-results.json` blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`; scorecard `web-shadow/scorecard.json` as inspected 2026-11-11; PR https://github.com/AidanDCM/Tennis-Genome-/pull/428.

## Observed source behavior
The batch settler reads ONLY result_paths in the active manifest, binds each result to a PENDING prediction in the official scorecard, rejects duplicate prediction paths and match IDs, and writes settlements plus a summary to the specified output directory. The GitHub workflow has contents: read and uploads that directory as an artifact with 90-day retention. It does NOT commit its settlements back into the repository's scorecard. Thus a replacement pointer is consistent with an ephemeral *batch* contract, but durable automatic incorporation of these results into the canonical scorecard is NOT demonstrated. Earlier settled scorecard rows are not erased by this workflow, but a newly processed result is not automatically promoted to the scorecard either. Artifact retention is finite. No claims of lost prior settlements.

## Executed test
A standalone Python source-contract check (strings from inspected exact blobs) asserted seven properties: pending required; nonpending rejected; duplicate prediction rejected; duplicate match rejected; workflow read-only; artifact retention 90 days; manifest push trigger. Observed PASS 7/7. This is static contract verification, not a full dynamic replay or exact-head CI. To reproduce, fetch the two blobs above and assert the literal guards `if not pending:`, `if prediction_path not in pending:`, `if prediction_path in seen_prediction_paths:`, `if match_id in seen_match_ids:`, `contents: read`, `retention-days: 90`, and `"web-shadow/active-results.json"`. Assert all seven true.

## Verdicts
H1 supported by direct code inspection; H2 supported by guard inspection, and existing `test_batch_rejects_nonpending_prediction` covers the case; H3 **rejected** as a claim of permanent persistence: 90-day artifact retention and no scorecard write. Not a confirmed defect, because durable canonical settlement may be an explicitly separate, reviewed process.

## Research
Waghmare and Ziegel, *Proper Scoring Rules for Estimation and Forecast Evaluation* (review online 2025; volume 2026), https://doi.org/10.1146/annurev-statistics-042424-050626 (CC BY 4.0). Proper scoring rules support comparing locked probabilistic forecasts, but cannot correct untrusted outcome linkage. Pic et al. (2025), https://doi.org/10.5194/ascmo-11-23-2025 (CC BY 4.0), provides complementary scoring approaches with weather simulations and real data; not comparable to tennis. No code copied.

## Next executable queue
1. Run a synthetic two-batch replay with isolated temporary scorecards, explicit scorecard publication step, and duplicate/replay negative controls. Do not weaken pending/identity/time/provenance gates.
2. Verify whether a separate reviewed workflow publishes batch artifacts into the canonical scorecard; inspect real run artifact contents and retention, not metadata alone.
3. Human-review PR #428's retained WTA evidence and settle safely; unblock acquisition without automatic merging.
4. After genuinely new qualified prospective settlements, compare frozen champion vs fixed challenger chronologically with paired Brier/log loss, calibration, coverage, uncertainty and drift. No production promotion without review.

No model change, no settlement change, no new qualified prospective observation.