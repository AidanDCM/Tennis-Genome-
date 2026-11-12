# WTA Web Shadow excluded-cohort arithmetic audit — 2026-11-12

## Immutable source and scope
Main commit: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
Main scorecard: [web-shadow/scorecard.json](https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/web-shadow/scorecard.json), blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`.
This is **non-production WTA Web Shadow**, not qualified production-forward evidence. No settlements, predictions, model weights, or gates changed.

## Preregistered arithmetic test
H0: the seven scored observations excluded from the Elo-paired cohort have the same aggregate Genome accuracy and proper-score loss as the 78 paired observations. Baseline: paired 78; comparison: excluded 7 inferred by subtraction from overall 85. Test: exact arithmetic differences only; without individual records no inferential rejection or statistical significance is claimed.

Observed overall: 85 scored, 46 correct, Brier 0.2514610585394295, log loss 0.6969082732945988.
Paired Genome: 78 scored, 41 correct, Brier 0.25243282736841877, log loss 0.6986819892394467.
Paired Elo: 78 scored, 42 correct, Brier 0.2597451903841716, log loss 0.7227188854273178.
Implied excluded seven: 5 correct / 7 (71.4286%); Brier 0.24063277730212057; log loss 0.6771440099091512.
Differences excluded minus paired Genome: accuracy +18.8645 percentage points; Brier -0.0118000500662982; log loss -0.0215379793302955. These are descriptive, not proof of selection mechanism.

## Reproduction (Python 3, no dependencies)
```bash
python - <<'PY'
n, m = 85, 78
correct_all, correct_pair = 46, 41
b_all, b_pair = 0.2514610585394295, 0.25243282736841877
l_all, l_pair = 0.6969082732945988, 0.6986819892394467
assert n > m and correct_all >= correct_pair
print('excluded_N', n-m, 'excluded_correct', correct_all-correct_pair)
print('excluded_accuracy', (correct_all-correct_pair)/(n-m))
print('excluded_brier', (n*b_all-m*b_pair)/(n-m))
print('excluded_log_loss', (n*l_all-m*l_pair)/(n-m))
assert abs((n*b_all-m*b_pair)/(n-m)-0.24063277730212057) < 1e-12
assert abs((n*l_all-m*l_pair)/(n-m)-0.6771440099091512) < 1e-12
PY
```
Sample identifiers: the 85 overall and 78 Elo-comparable scorecard aggregates; exact seven match IDs are **not provided by these aggregates** and require reconstruction from immutable match-level prediction/baseline records. The 88 settled records are a separate count.

## Evidence gates and operational findings
Main `web-shadow/active-results.json` still points to the Hong Kong result. [PR #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) remains open with one proposed Chennai result, 13 unresolved predictions and two Hong Kong MatchID player-pair conflicts excluded. [PR #458](https://github.com/AidanDCM/Tennis-Genome-/pull/458) and [PR #461](https://github.com/AidanDCM/Tennis-Genome-/pull/461) contain unmerged fail-closed gate and tests. No production champion checksum or qualified forward denominator independently re-established here.

## Literature / contrary evidence
Clegg and Cartlidge (2025), [Temporal Directed Graph Neural Networks](https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/), accepted manuscript CC BY, uses 2007–2024 ATP data with a later out-of-sample cohort; graph accuracy 66.0% vs weighted Elo 65.6% on that population. This is not comparable to WTA shadow; model complexity is not a substitute for paired evaluation. No implementation imported or license for code established.

## Negative findings and queue
1. Cannot identify the seven excluded matches or their missing-Elo causes from aggregates alone; cannot compute paired uncertainty, chronology, surface or drift.
2. Resolve #428 through human review without relaxing player identity, chronology, or source provenance; do not auto-merge.
3. Review the #457/#458/#461 dependency chain; run isolated non-mutating gate integration tests.
4. Build a read-only match-ID alignment audit from pre-start Genome/Elo records and settlements; report seven IDs and missingness reasons.
5. Only after prospective evidence resumes, preregister a paired chronological champion/Elo/fixed-0.5 comparison; preserve untouched final holdout and report Brier, log loss, calibration, coverage and confidence intervals.
