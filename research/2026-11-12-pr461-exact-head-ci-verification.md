# 2026-11-12 PR #461 exact-head CI verification

## Prespecified audit
Hypothesis: the committed synthetic acquisition guard contract passes repository CI at its exact head. Baseline: prior representative local fixture (2 passed) was not the repository checkout. Acceptance: PR-head workflow run completes successfully with Ruff and pytest successful; otherwise reject. No assertion of runtime gate simulation.

## Evidence inspected
- Repository: https://github.com/AidanDCM/Tennis-Genome-
- PR: https://github.com/AidanDCM/Tennis-Genome-/pull/461
- Head SHA: f81832683826234e4e833782adcf6754dbeb7030
- Workflow run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43185872429 ; run number 2747, completed success.
- Job ID: 131072756834, completed success. Checkout, setup Python, install, Ruff, pytest, upload CI diagnostics all succeeded; Enforce checks skipped.
- Connector reproduction: fetch_commit_workflow_runs(repo_full_name=repo,commit_sha=head); fetch_workflow_run_jobs(repo_full_name=repo,run_id=43185872429).
- The actual test count, test-by-test stdout, and artifact bytes were not retrieved. CI proves repository execution of committed tests, not real gate failure/blocked/allowed GitHub Actions branches.
- Main branch acquisition guard remains unpatched according to preceding ledger. PR #428 unresolved and PRs #457/#458/#461 form an unmerged dependency chain. No settlement or champion change.
- Non-production WTA Web Shadow historical scorecard: 46/85 correct, Brier 0.251461, log loss 0.696908, 16 pending. Fixed 0.5 baseline Brier 0.25 and log loss 0.693147. Qualified production forward N and immutable champion checksum not independently verified in this audit.

## Research and contrary evidence
- Buhamra, Groll and Gerharz (2025), https://doi.org/10.1177/22150218251338954 : 5,013 men's Grand Slam matches 2011–2022; expanding-window forecasting beats rolling and CV-style approaches in their comparison. Does not transfer directly to WTA. Paper contains inputs not permitted in this project; do not copy them.
- Clegg and Cartlidge (2025), https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/ : temporal surface-specific graph model comparable to weighted Elo on their ATP out-of-sample population. Contrary evidence against assuming more complexity helps. Code licensing and independent reproduction not verified.
- No external code imported; source populations and metrics are not comparable to Tennis Genome's prospective cohort.

## Negative results and next executable queue
1. Download CI diagnostic artifact, inspect actual pytest summary and test warnings; verify SHA256 and run head.
2. Execute isolated true GitHub Actions blocked/failed/allowed behavior with all data writes disabled; source-level truth tables are insufficient.
3. Human-review PR #428 and resolve single-proposal acquisition stall without weakening player-pair identity or timing/provenance gates; LS031 and LS020 remain excluded.
4. Refresh main champion hash, forward-qualified sample and source coverage. Only after genuinely locked chronological observations accumulate, test frozen champion vs simple Elo and fixed 0.5 with paired Brier/log loss, accuracy confidence interval, calibration, surface/tour/coverage and multiplicity control. Preserve final holdout.
