# WTA Web Shadow selection-sensitivity audit — 2026-11-12

## Provenance and prespecified question
Read-only experiment on main commit `8af76720a6291b166263fa1cd8191504f84ed6b6`, scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`, [scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/web-shadow/scorecard.json). Active results blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`. PR [#428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) still open at inspection, containing 1 Chennai proposal, 13 unresolved and 2 Hong Kong identity conflicts. [Main acquisition workflow](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/.github/workflows/wta_web_shadow_results.yml) blob `2a698a6f56297aee054a94dc49a28fefaaff2d35` still uses `steps.pr_gate.outputs.blocked != 'true'` and can skip source fetching when a result PR exists. The fail-closed correction and tests remain unmerged in [#458](https://github.com/AidanDCM/Tennis-Genome-/pull/458) and [#461](https://github.com/AidanDCM/Tennis-Genome-/pull/461).

**Question:** Is the reported 46/85 WTA shadow accuracy robust to uncertainty from the 16 pending predictions? Baseline: observed 46/85 only. Prespecified sensitivity: assume, *solely for an arithmetic stress test*, all 16 pending are subsequently qualified and are either all incorrect or all correct. Success criterion for a strong descriptive majority: both extremes exceed 50%. Failure: lower bound <= 50%. This is **not** a model comparison or prospective settlement. No outcome is imputed into official records.

## Reproducible calculation
```python
import math
n, correct, pending = 85, 46, 16
z = 1.959963984540054
p = correct / n
den = 1 + z*z/n
center = (p + z*z/(2*n)) / den
half = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/den
print('observed', p, 'Wilson95', center-half, center+half)
print('conditional extremes', correct/(n+pending), (correct+pending)/(n+pending))
print('Brier excess', 0.2514610585394295-0.25)
print('log loss excess', 0.6969082732945988-math.log(2))
```

## Actual numerical results
- Observed accuracy 46/85 = 0.54117647; Wilson 95% interval [0.43576336, 0.64302868]. The interval includes 0.50.
- **Conditional** if all 16 pending become eligible: extreme accuracy range [46/101 = 0.45544554, 62/101 = 0.61386139]. The lower extreme fails the >50% descriptive majority criterion. This is a partial-identification sensitivity calculation, **not** a forecast of their outcomes, a qualified denominator, or a license to count pending records.
- Current 85-scored non-production sample Brier 0.25146106, 0.00146106 worse than fixed 0.5; log loss 0.69690827, 0.00376109 worse than log(2). No paired per-match differences or chronological uncertainty estimates were available from these aggregates.
- The scorecard also reports `settled_match_count=88` versus `metrics.settled_match_count=85`; the latter is the metric denominator. Do not conflate them.
- **Negative result:** The apparent 54.1% accuracy is neither a statistically established >50% success rate nor robust to the specified missing-outcome extreme. It cannot justify model promotion.

## Research comparison (no external code imported)
- Poudel, Schmidt, Jones (2026), [Unified Benchmark](https://doi.org/10.3390/analytics5030022), published July 3 2026: 133,138 ATP matches with temporal splits, Elo and ML under common conditions; enhanced Elo 65.87%, best classical ML 66.30%, hybrid 67.52%. Different ATP population, feature set and history; not directly comparable to WTA shadow. Paper open access; no implementation license or code reproducibility verified. Transferable idea: common chronological evaluation and simple rating baselines.
- Krall et al. (2025), [World Tennis Number algorithm-change evaluation](https://doi.org/10.52383/itfcoaching.v32i94.559), published January 9 2025: 2,956 junior matches, comparing pre/post rating versions and another rating; limited evidence of improvement across divisions. Different population and metric; caution against assumed gains from complexity. No external code adopted.
- Contrary evidence: more sophisticated rating or ML is not guaranteed to outperform simpler baselines on new populations. Neither reference is a prospective WTA replication.

## Safety and next queue
No model, champion, result, settlement, identity, or trust-gate changes. No sportsbook, odds, or market inputs. This ledger is exploratory descriptive analysis, not an eligible production-forward evaluation.

1. Human-review [#428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) using immutable source and identity gates, then verify acquisition actually executes; preserve both Hong Kong exclusions.
2. Review dependent safety fix [#457](https://github.com/AidanDCM/Tennis-Genome-/pull/457), [#458](https://github.com/AidanDCM/Tennis-Genome-/pull/458), [#461](https://github.com/AidanDCM/Tennis-Genome-/pull/461), and test real allowed/blocked/failed gate states without writes.
3. On new *qualified, pre-locked* matches, log capture coverage, denominator, timestamps, champion SHA and paired simple-baseline Brier/log loss with confidence intervals. Keep final holdout untouched.
