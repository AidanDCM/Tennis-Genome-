# Acquisition CI green-but-blocked audit — 2026-11-12 UTC

## Baseline and hypothesis
Main: `8af76720a6291b166263fa1cd8191504f84ed6b6`. Immutable champion untouched. Test H1: a successful scheduled WTA result acquisition run necessarily attempts official-source fetch, result compilation and settlement dry-run. Prespecified success: all three steps actually execute; failure: any is skipped. Population: latest scheduled result-acquisition run `43147568821` (2026-11-12 03:20 UTC), not a forecasting sample. Control: job conclusion alone.

## Executed reproducible audit
Source: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43147568821
Read `GET /repos/AidanDCM/Tennis-Genome-/actions/runs/43147568821/jobs` and job `130948866789` logs. Counted step conclusions programmatically: 16 total, 5 success, 11 skipped, zero failures. Logs explicitly print `A result proposal is already open; leaving it immutable.`. Official source fetch, finished-row compilation, settlement dry-run, repository contract check all **skipped**. The workflow has a fail-closed gate for open `automation/wta-web-shadow-results-*` PRs; this protects immutability but makes a green workflow conclusion an invalid proxy for healthy acquisition.

Blocking PR: https://github.com/AidanDCM/Tennis-Genome-/pull/428, head `automation/wta-web-shadow-results-wta-results-20261109t083951z` SHA `e676c961d674ffd32d254bb96f738ae7242e211f`. Its snapshot reports one proposed Chennai result, 13 unresolved predictions and two Hong Kong identity conflicts (`web:wta:1074:2026:LS031`, `web:wta:1074:2026:LS020`). Preserve both exclusions. No settlement published.

Reproduction:
```bash
gh api repos/AidanDCM/Tennis-Genome-/actions/runs/43147568821/jobs --jq '.jobs[0].steps | {total:length, skipped:map(select(.conclusion=="skipped"))|length, successful:map(select(.conclusion=="success"))|length}'
gh run view 43147568821 --repo AidanDCM/Tennis-Genome- --log | grep 'A result proposal is already open'
gh pr view 428 --repo AidanDCM/Tennis-Genome- --json headRefName,headRefOid,state
```
Result: **H1 rejected**. This is an operational reliability failure of the *green status interpretation*, not a failure of the intended fail-closed gate. No model ablation or accuracy improvement is claimed.

## Independent forecasting evidence and caveats
Main non-production WTA Web Shadow scorecard: 85 eligible, 46 correct (54.12%), Brier 0.251461, log loss 0.696908, 16 pending. Fixed p=0.5 benchmark Brier 0.25, log loss ln(2)=0.693147; historical shadow is worse on both. Paired historical Elo population 78, Genome 41 correct, Elo 42; no statistical superiority established. Qualified production-forward N and champion checksum not independently refreshed this run. Do not conflate shadow with production.

## Research rotation: missing labels and distribution shift
- Su (2024), *On Truthing Issues in Supervised Classification*, JMLR https://www.jmlr.org/papers/v25/19-301.html — missing/conflicting labels invalidate naive evaluation; transferable: explicit unresolved and identity-conflict denominators. No implementation copied; license not assessed.
- Dominitz and Manski (2024), *Comprehensive OOS Evaluation of Predictive Algorithms with Statistical Decision Theory*, https://www.nber.org/papers/w32269 — warns that test populations can differ from future targets. Transfer: report capture/settlement selection by tour, tournament and time; not a directly comparable tennis benchmark. Code and reproduction not assessed.
- Loveday et al. (2024), https://arxiv.org/abs/2311.18258 — proper scoring rules and threshold-aware diagnostics; retain paired Brier/log loss and calibration, not accuracy alone. Not reproduced; license not assessed.

## Prioritized next executable queue
1. Human review PR #428 Chennai evidence and the real-function dry-run from PR #447; do not merge/promote automatically. Preserve Hong Kong exclusions.
2. Add a narrowly scoped, separately reviewable workflow diagnostic that reports `blocked_by_open_result_pr` distinctly from `acquisition_executed`, and asserts the skip condition in a synthetic CI test. Avoid bypassing the gate or creating a second competing result proposal.
3. After safe review and PR gate clearance, inspect a fresh scheduled run's actual fetch/compile/dry-run steps, source digests and qualified settlement denominators.
4. Only after new locked forward observations, preregister paired champion versus fixed 0.5 and Elo with Brier/log loss, CI and untouched holdout.
