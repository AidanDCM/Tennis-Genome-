# Research iteration 25 — blocked WTA acquisition observability (2026-11-10)

Status: non-production diagnostic PR #430, **not merged**, no champion or settlement changes.

## Raw evidence and source anchors
- Main workflow: `.github/workflows/wta_web_shadow_results.yml`, prior blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`.
- Acquisition run 42798727961, job 129770464462: gate completed successfully, all fetch/compile/settlement/proposal steps skipped. https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42798727961
- Open immutable result proposal #428: 16 pending, 1 captured, 13 unresolved, 2 identity conflicts; unmerged. https://github.com/AidanDCM/Tennis-Genome-/pull/428
- Main active result manifest blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`; remains Hong Kong, not Chennai.
- Main scorecard: 46/85 accuracy (54.12%), Brier 0.251461, log loss 0.696908, 88 settled records; **WTA Web Shadow non-production only**.
- Forward aggregate workflow blob `1244a36a374d1fb38570ad3f51f0abc9864eab6f`. Prior observed aggregate run 42839698243 reported zero qualified forward observations; not independently refreshed in this iteration.

## Prespecified operational experiment
Hypothesis: a blocked acquisition can leave a machine-readable audit receipt without changing the safety gate or pretending to capture outcomes.
Baseline: successful no-op with no acquisition artifact. Challenger: explicit blocked receipt, run SHA/time, `acquisition_attempted=false`, `results_captured=null`, artifact upload. Success requires an actual blocked workflow run with receipt, unchanged existing proposal, no provider fetch or result mutation. Failure if workflow fails, produces no artifact, or alters gate behavior.

Implementation commit `3ae1f4de3796044e246cd30a80d0c41cb574fa12`, PR #430. Read-only static checks executed against fetched exact branch file: 6/6 passed (step present; blocked-only guard; artifact upload; original block gate retained; capture remains gated; explicit no-capture flag). These are NOT workflow execution or end-to-end CI evidence. Exact-head Actions status to be checked before merge/review.

## Research (contrary evidence and transferability)
- Pagano et al. (2024), *Challenges of Operational Weather Forecast Verification and Evaluation*, https://doi.org/10.1175/BAMS-D-22-0257.1 — published operational multi-agency workshop analysis, observation incompleteness and verification quality. Adapt acquisition freshness/coverage receipts; no tennis model comparison, license requires checking before copying.
- Pasche et al. (2025), *Validating Deep-Learning Weather Forecast Models on Recent High-Impact Extreme Events*, https://doi.org/10.1175/AIES-D-24-0033.1 — case-focused evaluation reveals benchmark gains need not survive unusual conditions. Reproducible code https://github.com/jonathanwider/DLWP-eval-extremes (license not independently audited); do not copy or compare reported skill to tennis. Adapt prespecified tour/surface/date drift slices only when forward N supports it.

## Reproduction
```bash
gh pr view 430 --repo AidanDCM/Tennis-Genome-
gh run view 42798727961 --repo AidanDCM/Tennis-Genome- --log
gh pr diff 430 --repo AidanDCM/Tennis-Genome-
```
No executable numerical forecasting experiment attempted: blocked forward population is the higher-value issue, and repeatedly examined 55 historical cases are unsuitable for new model selection.

## Negative results / limitations
- 0 new qualified forward outcomes established in this run.
- No CI pass established for commit 3ae1f4de at the time of writing.
- Receipt improves *observability*, not acquisition throughput: existing PR #428 still prevents new snapshots.
- Identity-conflicted LS031 and LS020 remain excluded.

## Priority queue
1. Verify exact-head PR #430 CI and blocked-receipt artifact; fix failures without weakening safety.
2. Review #428's provenance and result identity, then establish safe human-reviewed disposition so capture can resume.
3. Investigate 13 unresolved prediction IDs with retained official sources, record selection denominator and reasons.
4. Once qualified forward settlements exist, prespecify paired champion versus research-only fixed-slope 0.5 Brier/log-loss comparisons, untouched chronological holdout and confidence intervals.
