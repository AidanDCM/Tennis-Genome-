# WTA shadow calibration bucket audit — 2026-11-12

Non-production; descriptive audit only. No model, settlement, champion, or trust gate changed.

## Prespecified test
H1: each of four existing confidence buckets has nonnegative observed accuracy minus mean selected probability. Baseline: fixed probability 0.5 on identical 86 completed matches. Failure: any negative bucket gap. No parameter search or refitting; no use of pending outcomes.

Source: [main scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json), blob `c9636ac9d86c256ccf241e652b9456034c451fc3`; 86 scored, 47 correct, 89 terminal, 15 pending. Sample IDs: four scorecard confidence buckets covering all 86 scored observations. Individual match IDs not enumerated in this aggregate audit.

## Executed results
Read the complete JSON via connected GitHub and executed deterministic JavaScript over `metrics.confidence_buckets`. Bucket (n, correct, mean selected probability, accuracy minus mean probability):

- 0.50–0.60: (44, 23, 0.548263, -0.025536)
- 0.60–0.70: (25, 13, 0.637059, -0.117059)
- 0.70–0.80: (12, 7, 0.752295, -0.168962)
- 0.80–0.90: (5, 4, 0.833796, -0.033796)

Weighted absolute bucket gap (ECE) = **0.0726346552**; signed mean gap = **-0.0726346552**. All four gaps negative, rejecting H1 descriptively. These are in-sample reliability diagnostics of existing locked forecasts, not a statistical significance test, calibration guarantee, or a newly fit model. The scorecard itself reports mean selected probability 0.619146 versus observed accuracy 0.546512. Brier 0.251322418 versus fixed-0.5 0.25 (difference +0.001322418); log loss 0.696621201 versus ln(2) 0.693147181. The fixed baseline is better on both aggregate proper scores.

## Reproduction
```javascript
const d = JSON.parse(scorecardText);
const b = d.metrics.confidence_buckets;
const n = b.reduce((s,x)=>s+x.match_count,0);
const ece = b.reduce((s,x)=>s+x.match_count*Math.abs(x.accuracy-x.mean_selected_probability),0)/n;
const signed = b.reduce((s,x)=>s+x.match_count*(x.accuracy-x.mean_selected_probability),0)/n;
console.log(n,ece,signed,b.map(x=>[x.label,x.match_count,x.correct_prediction_count,x.accuracy-x.mean_selected_probability]));
```

## Research and limitations
- Dimitriadis, Gneiting & Jordan (2020), [Reliability diagrams and score decompositions revisited](https://arxiv.org/abs/2008.03033): adaptive reproducible calibration diagnostics (CORP), unlike arbitrary four-bin summaries; no external code imported, license not verified.
- Loveday, Taggart & Khanarmuei (2024), [A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts](https://journals.ametsoc.org/abstract/journals/wefo/39/8/WAF-D-23-0201.1.xml): binary forecast verification using proper scoring rules and threshold-dependent diagnostics; thunderstorm population, not tennis; AMS reuse license, no implementation imported.
- Pic et al. (2025), [Proper scoring rules based on aggregation and transformation](https://doi.org/10.5194/ascmo-11-23-2025): complementary scores may rank misspecified forecasts differently; multivariate weather setting not directly comparable; R code linked in article, code license not checked.

Small and uneven buckets, repeated evaluation of the same shadow cohort, selection bias, and no independently refreshed production-forward denominator preclude a generalization claim. Do not fit calibration on these scored observations and report performance on them as independent. Prior evidence: [PR #474](https://github.com/AidanDCM/Tennis-Genome-/pull/474) (13 legacy pending joins, two exact MatchID conflicts); [PR #473](https://github.com/AidanDCM/Tennis-Genome-/pull/473) (source hashes verified, two player conflicts).

## Next executable queue
1. Classify the 13 legacy pending matches against retained source rows with immutable event/round/player identity checks; read-only diagnostics only.
2. Add regression-tested diagnostic-only mismatch categories on isolated branch; run pytest/Ruff and exact-head CI.
3. Test blocked/failed/skipped acquisition gate states without writes.
4. After *new* qualified prospective observations, preregister chronological paired champion vs simple baseline scoring and uncertainty; untouched final holdout.

No settlement, prediction backfill, model promotion, or workflow modification.
