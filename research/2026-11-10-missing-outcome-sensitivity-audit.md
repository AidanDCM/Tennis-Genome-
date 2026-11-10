# Iteration 30 — missing-outcome sensitivity audit (2026-11-10)

## Scope and provenance
Read-only numerical experiment; no outcome backfill, no prediction edits, no champion promotion. Main commit from GitHub recent commit search: `8af76720a6291b166263fa1cd8191504f84ed6b6`. Main `web-shadow/scorecard.json` read directly; main `web-shadow/active-results.json` blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`. Open PRs #428, #429, #430 confirmed through connected GitHub search. PR #428 retained 16 inspected pending predictions, one captured result, 13 unresolved, two identity conflicts; proposal not incorporated. Main active-results manifest still points to Hong Kong result.

## Prespecified falsifiable audit
Hypothesis: if the 16 currently pending predictions eventually become valid scored outcomes, extreme outcome-selection scenarios can change the interpretation of observed 46/85 historical winner accuracy relative to 50%. Baseline: 46 correct / 85 scored, non-production Web Shadow. Population: same 85 scored plus 16 pending in scorecard, not qualified forward and not necessarily all finishable. Comparison: all 16 incorrect versus all 16 correct, purely hypothetical. Pass criterion: 50% lies strictly inside the identification interval. Fail if not. No outcomes are invented or assigned.

Reproduce:
```python
correct, scored, pending=46,85,16
lo=correct/(scored+pending)
hi=(correct+pending)/(scored+pending)
print(lo,hi,pending/(scored+pending))
assert lo < 0.5 < hi
```
Executed locally with Python: lower 0.45544554455445546; upper 0.6138613861386139; width 0.15841584158415842; assertion PASS. Current scored-only accuracy 0.5411764705882353. This is a worst-case accounting bound **conditional on all 16 eventually becoming eligible**; it is NOT an interval estimate, forecast, new settlement, or prospective performance claim. The pending population is not assumed exchangeable with scored matches; some may never be qualified.

## Research and contrary evidence
- Dominitz and Manski (2024), *Comprehensive OOS Evaluation of Predictive Algorithms with Statistical Decision Theory*, https://www.nber.org/papers/w32269 : emphasizes target-population uncertainty and extrapolation; working paper, code license not assessed; adapt explicit evaluation-population accounting, not numerical results.
- Kweon and Yu (2024), *Doubly Calibrated Estimator for Recommendation on Data Missing Not At Random*, https://arxiv.org/abs/2403.00817 : recommendation data and simulated/real experiments, not tennis; warns propensity and imputation models themselves can be miscalibrated; no code copied, reuse license not audited. Do not apply inverse-probability weighting before estimating trustworthy missingness mechanisms.
- Loveday et al. (2023), *A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts*, https://arxiv.org/abs/2311.18258 : meteorological binary forecasts and proper scores; supports evaluating probability quality separately from winner accuracy, not transferable win-rate claims.

## Negative evidence and limits
This audit provides no evidence of predictive improvement. Worst-case bounds span 50%; result capture remains gated by open PR #428; two identity conflicts remain excluded. Main scorecard is historical non-production only. Forward qualified N was not refreshed in this iteration; previous verified aggregate reported zero. Exact-head CI for this documentation commit not yet verified.

## Next executable queue
1. Inspect PR #428's source and settlement contract, seek human-reviewed disposition; do not bypass immutable proposal gate.
2. Test blocked-receipt workflow on reviewed main or isolated safe event; inspect artifact and no-mutation invariants.
3. Audit all 13 unresolved prediction IDs against provider coverage and match-date windows; keep identity conflicts excluded.
4. Once genuinely new locked outcomes qualify, conduct chronological paired champion–challenger Brier/log-loss, accuracy and cluster uncertainty; keep untouched holdout.
