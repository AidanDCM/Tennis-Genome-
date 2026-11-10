# Research iteration 28 — 2026-11-10 — acquisition-gate verification and selection-bias audit

Status: research only; no production or settlement changes. PR #430 remains draft; PR #428 remains open; PR #429 remains draft.

## Source evidence
- Main acquisition workflow: https://github.com/AidanDCM/Tennis-Genome-/blob/main/.github/workflows/wta_web_shadow_results.yml — checkout ref main, gate skips acquisition when result proposal PR exists; branch code in #430 is not deployed by scheduled main workflow.
- Main active result manifest: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/active-results.json ; blob SHA 52d8645a3389c9b2d8ba5a6c87e520e23ab80a25; references 2026-11-08 Hong Kong LS001.
- Main non-production scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json ; 85 scored, 46 correct, Brier 0.2514610585394295, log loss 0.6969082732945988, 88 settled records, 16 pending. This is NOT qualified forward challenger performance.
- Open result proposal #428: https://github.com/AidanDCM/Tennis-Genome-/pull/428 ; 16 pending examined; 1 captured; 13 unmatched; 2 identity conflicts; not merged.
- Diagnostic PR #430 head 9c0311f169b04d78c385bf1f15769202d9a1d12c; exact-head PR CI https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42887823404 passed Ruff, Pytest and diagnostics. This is NOT an acquisition-workflow end-to-end test.

## Falsifiable operational hypothesis
The gate classifies a present open proposal distinctly from an orphan branch, while allowing acquisition only if neither exists. Baseline: main's undifferentiated blocked flag. Challenger: PR #430's OPEN_RESULT_PR vs ORPHAN_RESULT_BRANCH receipt. Population: synthetic gate-state cases, NOT actual result records. Prespecified pass: all four cases match expected status and acquisition attempt boolean.

Executed in Python (standalone deterministic simulation, not workflow execution):
```python
def gate(open_pr_count, orphan_count):
    if open_pr_count > 0: return "OPEN_RESULT_PR", False
    if orphan_count > 0: return "ORPHAN_RESULT_BRANCH", False
    return None, True
cases=[(1,0,"OPEN_RESULT_PR",False),(0,1,"ORPHAN_RESULT_BRANCH",False),(0,0,None,True),(1,1,"OPEN_RESULT_PR",False)]
for a,b,status,attempt in cases:
    assert gate(a,b)==(status,attempt)
```
Result: PASS 4/4; limited to an independent simulation of the intended logic, not actual GitHub Actions receipt emission. No end-to-end blocked receipt was retrieved. The real acquisition remains blocked by open #428.

## External methodological research
- Kleen (2024), Journal of Applied Econometrics, https://doi.org/10.1002/jae.3056 : simulations and economic-data evaluation of score sensitivity to noisy observations. Not tennis; no directly comparable performance; no code copied. Supports preserving strict identity matching rather than trusting score robustness.
- Pagano et al. (2024), BAMS, https://doi.org/10.1175/BAMS-D-22-0257.1 : operational weather forecast verification challenges; cross-domain evidence, not tennis performance. Emphasizes verification coverage.
- Kweon and Yu (2024), https://arxiv.org/abs/2403.00817 : missing-not-at-random selection and calibration in recommender systems; transfer is conceptual only; no estimator adapted without trustworthy observation propensities.

## Negative results and decision
No new qualified forward settlements verified; no Brier or log-loss challenger comparison is possible. Do not infer predictive gains from passing diagnostic CI. An open immutable proposal is blocking fresh result collection; receipt code alone does not restore throughput. No champion modification, settlement mutation, PR merge or model promotion.

## Prioritized next executable queue
1. Human-review disposition of #428 without relaxing identity/timing gates; ensure retained source and settlement dry-run are verified before any merge/close.
2. After review of #430, verify a real blocked receipt on main workflow; assert correct reason, run SHA, artifact and no mutation.
3. Restore acquisition, inspect all 13 unmatched predictions and source provenance; publish per-run coverage and freshness.
4. Once qualified paired prospective N > 0, compute chronological champion/challenger Brier, log loss, accuracy, intervals and surface breakdowns, with frozen challenger selection.
