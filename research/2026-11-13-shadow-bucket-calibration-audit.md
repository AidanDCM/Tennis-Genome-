# WTA Web Shadow bucket calibration audit — 2026-11-13

Status: NON-PRODUCTION, retrospective descriptive audit; not an independent prospective model experiment.

Source: [main scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json), blob SHA c9636ac9d86c256ccf241e652b9456034c451fc3. Base commit 40bb697ec786527b7ed1a4c67d6d0a92aea17782. Sample: 86 scored WTA shadow predictions, 47 correct, from scorecard confidence buckets; 15 pending excluded. No row-level outcome or timing validation performed.

## Prespecified diagnostic

Hypothesis: selected-player confidence buckets show directional overconfidence relative to their observed hit frequencies. Null descriptive comparator: fixed 0.5 selected-player probability, Brier 0.25 and log loss ln(2). This is NOT a valid newly trained challenger or a statistically independent paired improvement test. Success criterion for an actionable research lead: all bucket observed-minus-predicted gaps nonpositive and aggregate gap negative; model promotion requires entirely new prospective chronological paired evidence.

## Executed numerical calculation

Read raw scorecard JSON through connected GitHub fetch_file and evaluated, for each bucket, n, k, expected correct n * mean selected probability, and observed accuracy minus mean confidence. Aggregate expected correct is sum of bucket expectations. The descriptive standardized discrepancy uses sum n*p*(1-p) as a bucket-mean approximation; within-bucket heterogeneity and selection dependence make it non-inferential.

| Confidence | n | correct | expected correct | accuracy minus mean confidence |
|---|---:|---:|---:|---:|
| 0.50–0.60 | 44 | 23 | 24.124 | -0.0255 |
| 0.60–0.70 | 25 | 13 | 15.926 | -0.1171 |
| 0.70–0.80 | 12 | 7 | 9.028 | -0.1690 |
| 0.80–0.90 | 5 | 4 | 4.169 | -0.0338 |
| Total | 86 | 47 | 53.247 | -0.07263 |

Approximate standardized residual (47 - 53.24658)/sqrt(sum n*p*(1-p)) = -1.411; not a formal p-value. Scorecard Brier 0.251322418 versus fixed-0.5 0.25 (difference +0.001322418); log loss 0.696621201 versus ln(2) 0.693147181 (difference +0.003474020). **Negative result:** shadow probabilities underperform a naive 0.5 reference on proper scores, and apparent overconfidence is not proof that recalibration improves future results. Accuracy 47/86 is not production accuracy.

Reproduction: fetch the pinned scorecard JSON; for each element of `metrics.confidence_buckets`, calculate `match_count * mean_selected_probability` and `accuracy - mean_selected_probability`; sum expectations; compare `metrics.brier_score` with 0.25 and `metrics.log_loss` with `math.log(2)`. No code changed and no CI triggered by this calculation.

## Contrary research and adaptation

Gneiting & Raftery (2007), [Strictly Proper Scoring Rules, Prediction, and Estimation](https://doi.org/10.1198/016214506000001437), motivates ranking calibrated probabilities by proper scoring rather than hit rate. Evaluate proposed shrinkage only on chronologically later locked predictions; never fit shrinkage on this scorecard then advertise its same-sample gain. License for external text/code not assumed; no code imported.

## Queue

1. Verify PR #490 exact-head CI and preserve its fail-closed pending result diagnostics; independently corroborate 12 round-mismatch candidates before any settlement.
2. Audit pre-start source coverage for new predictions and obtain additional qualified forward observations; keep WTA shadow separate from immutable champion.
3. On a predeclared future-only cohort, compare unchanged champion with fixed 0.5 and a single preregistered shrinkage challenger using paired Brier/log loss and uncertainty intervals. No retrospective tuning on this sample.

No frozen champion, result, settlement, trust gate, or production scorecard changed.
