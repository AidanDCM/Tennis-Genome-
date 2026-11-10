# Iteration 29 — matched-population baseline audit (2026-11-10)

Scope: read-only audit; no champion, prediction, identity, settlement or workflow changes. PR #430 remains draft and unmerged.

## Exact repository evidence
- Main SHA at inspected PR #430 base: `8af76720a6291b166263fa1cd8191504f84ed6b6` (not independently confirmed as current tip).
- Main scorecard `web-shadow/scorecard.json` blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`.
- Main active result manifest blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`: one Hong Kong result, not proposed Chennai result.
- Main acquisition workflow blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`: checks out main, blocks if an open result PR exists, and skips acquisition. Proposed receipt is on draft PR #430 only.
- Main forward aggregation workflow blob `1244a36a374d1fb38570ad3f51f0abc9864eab6f`: no-settlement branch writes zero-population manifest, but workflow source is NOT proof of latest execution.
- Open PRs at inspection: #428 acquisition, #429 calibration, #430 blocked receipt.
- Non-production WTA Web Shadow: 46/85 correct, Brier 0.2514610585394295, log loss 0.6969082732945988; 88 total settled, 16 pending. This is NOT independent qualified forward evidence.

## Falsifiable numerical audit executed
Hypothesis: on the *same* 78 settled matches with both model scores, Genome improves proper probability scores over overall Elo despite not improving classification accuracy.
Baseline: overall_elo_v1; comparison: Genome; population: 78 paired settled Web Shadow matches, per scorecard baseline_comparison (NOT untouched or prospective).
Prespecified pass for descriptive hypothesis: Brier and log loss strictly lower for Genome; report accuracy direction separately. Failure if either proper score is not lower. Do not interpret as statistically significant without paired match-level differences and date clustering.

Executed Python SciPy calculation using exact scorecard aggregates:
```python
from scipy.stats import binomtest
n=78
print(41/n-42/n)
print(0.2597451903841716-0.25243282736841877)
print(0.7227188854273178-0.6986819892394467)
print(binomtest(46,85).proportion_ci(method="wilson"))
assert 41 < 42
assert 0.2597451903841716 > 0.25243282736841877
assert 0.7227188854273178 > 0.6986819892394467
```
Actual output: accuracy difference -0.012820512820512775 (-1/78); Brier improvement +0.007312363015752832; log-loss improvement +0.024036896187871082; Wilson 95% accuracy interval for 46/85 = [0.4357633606996252, 0.6430286818098059]. All 3 assertions passed.
**Interpretation:** descriptive proper-score improvement on 78 shared historical observations, but accuracy 41/78 Genome vs 42/78 Elo. Neither superiority nor future generalization is established. Paired outcome-level score differences and chronological split unavailable in this aggregate, so no inferential claim.

## Research, contrary evidence, adaptation
- Bunker et al., *A comparative evaluation of Elo ratings- and machine learning-based methods for tennis match result prediction*, first online 2023-11-10, https://doi.org/10.1177/17543371231212235 : expanding annual ATP test years 2007–2020; supports chronologically matched Elo baselines. ATP differs from this WTA paper sample; license for code reuse not established; no code copied. Article also notes unusually high scores in prior random-split studies can signal leakage.
- *A Unified Benchmark of Machine Learning and Deep Neural Networks for Tennis Match Prediction*, published 2026-07-03, https://doi.org/10.3390/analytics5030022 : temporal evaluation of 133,138 ATP matches with aligned features; Elo competitive with complex networks, suggesting simplification deserves serious testing. ATP population and metric definitions are not comparable to WTA; no code reused and implementation license not audited.
- Contrary caution: same-source benchmark comparisons may be dominated by data coverage and split design; do not infer a universal accuracy ceiling or promote from these aggregate results.

## Negative evidence / blockers
- No new qualified prospective settlement established in this run; latest forward aggregate execution not retrieved.
- Existing #428 result proposal remains open and blocks fresh capture; 13 unresolved and 2 identity conflicts in its retained snapshot, no retrospective reconciliation.
- PR #430 cannot generate a blocked receipt from scheduled main until reviewed/merged; PR CI is not an end-to-end acquisition test.
- No exact-head CI for this documentation-only commit yet.

## Priority queue
1. Human-review #428 result proposal with identity and provenance evidence; safely disposition without bypassing immutable proposal gate.
2. Review #430 and test a real blocked receipt on main after approval; confirm status, artifact, source SHA, and no mutations.
3. Inspect 13 unresolved prediction IDs against retained official provider coverage and distinguish absent provider data from identity conflict.
4. Acquire new qualified locked forward outcomes; only then run paired champion/challenger Brier, log loss, calibration and date-cluster uncertainty with untouched holdout.
