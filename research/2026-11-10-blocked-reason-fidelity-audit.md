# Iteration 26 — blocked acquisition reason fidelity (2026-11-10)

Scope: draft PR #430, research/diagnostic only. No result records, pre-start predictions, trust gates or champion changed.

## Verified evidence
- Previous PR CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42867954445 completed success (Ruff and pytest passed), job 130011241247. Its log uploaded CI diagnostic artifact 13787932563. This was **not** an acquisition-workflow execution.
- Previous workflow source blob 515196def146cbba53f3b3f19ddb0fdeb7c2b115; reviewed gate and receipt. The receipt formerly labeled both open-PR and orphan-branch blockers as BLOCKED_EXISTING_PROPOSAL.
- Updated workflow commit 183817134c0de6a769d7b18e75c3608f1440c53f, blob c9efbf5564d3468b8188a19035d607ba11b321dc. Branch source re-fetched to verify.
- Five exact-source static assertions executed and passed: OPEN_RESULT_PR reason present, ORPHAN_RESULT_BRANCH reason present, receipt reads gate output, blocked-only receipt guard intact, acquisition remains guarded. These do not establish end-to-end behavior.
- No workflow runs were returned for the updated commit at inspection. **Exact-head CI and real blocked artifact remain unverified**.

## Falsifiable operational experiment
Hypothesis: an acquisition gate can distinguish two distinct blocked causes in an immutable diagnostic receipt without altering gating.
Baseline: generic BLOCKED_EXISTING_PROPOSAL for either cause.
Challenger: OPEN_RESULT_PR or ORPHAN_RESULT_BRANCH from the existing gate; acquisition_attempted=false.
Success: actual gated run publishes receipt with correct reason and no acquisition or result mutations; failure: missing artifact, wrong reason, or any weakened gate.
Test commands:
```bash
gh pr view 430 --repo AidanDCM/Tennis-Genome-
gh run view 42867954445 --repo AidanDCM/Tennis-Genome- --log
gh pr diff 430 --repo AidanDCM/Tennis-Genome-
```
On future main execution inspect artifact contents and branch SHA; note the workflow checks out main, so PR-only CI cannot validate actual receipt behavior.

## Research and limits
- Ferro (2017), https://doi.org/10.1002/qj.3115: imperfect observations distort proper-score comparisons; weather examples, not tennis. No code reused, publication license not checked. Identity conflicts should be excluded rather than given guessed winners.
- Pic et al. (2025), https://doi.org/10.5194/ascmo-11-23-2025: multiple proper scoring rules illuminate distinct forecast weaknesses; multivariate weather study, CC BY 4.0 article, not a tennis accuracy benchmark. Retain paired Brier and log loss.
- Mason (2008), https://doi.org/10.1002/met.51: confidence intervals cannot correct evaluation-design bias. No code reused.
- Previously recorded WTA Web Shadow (non-production) 46/85, Brier 0.251461, log loss 0.696908; NOT newly refreshed. Prior forward aggregate reported zero qualified observations; NOT freshly verified. No model ablation was justified on the repeatedly examined historical sample.
- Previously retained intake: 16 pending, 1 result proposed, 13 unresolved, 2 identity conflicts. PR #428 remains the reported throughput blocker; current disposition not independently checked in this iteration.

## Priority queue
1. Verify exact-head PR #430 CI and obtain an actual blocked receipt on main after review; distinguish successful no-op from fresh acquisition.
2. Human-review result PR #428 and safely restore throughput without relaxing identity/provenance gates.
3. Audit unresolved prediction IDs and source coverage, then quantify qualified prospective sample N.
4. Only after fresh locked matched outcomes, prespecify paired champion vs research-only fixed log-odds slope 0.5, Brier/log loss, date clusters and untouched holdout.
