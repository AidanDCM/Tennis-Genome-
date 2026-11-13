# 2026-11-13 WTA Web Shadow calibration–resolution diagnostic (read-only)

## Scope and preregistered decision
Immutable non-production scorecard on main: blob `c9636ac9d86c256ccf241e652b9456034c451fc3`, main `40bb697ec786527b7ed1a4c67d6d0a92aea17782`. Population: all 86 COMPLETED scored predictions, 47 correct; no pending, walkover or retirement results imputed. This is an **aggregate bucket diagnostic**, not a trained or prospectively tested challenger. Hypothesis: reliability penalty exceeds bucket resolution on the four fixed scorecard confidence buckets; null/failure: reliability <= resolution. Baseline: fixed 0.5 Brier 0.25, log loss ln(2); comparison: immutable Genome scorecard.

## Executed numerical experiment
Read `web-shadow/scorecard.json` via connected GitHub fetch_file; parsed JSON; executed the following deterministic JS calculation on its four published bins:
```js
const b=j.metrics.confidence_buckets;
const n=b.reduce((s,x)=>s+x.match_count,0);
const y=b.reduce((s,x)=>s+x.correct_prediction_count,0)/n;
const REL=b.reduce((s,x)=>s+x.match_count/n*(x.mean_selected_probability-x.accuracy)**2,0);
const RES=b.reduce((s,x)=>s+x.match_count/n*(x.accuracy-y)**2,0);
const UNC=y*(1-y);
const ECE=b.reduce((s,x)=>s+x.match_count/n*Math.abs(x.mean_selected_probability-x.accuracy),0);
```
Observed n=86, correct=47, REL=0.008366866342530466, RES=0.004418768539915107, UNC=0.24783666846944294, bucket decomposition 0.2517847662720583, actual Brier=0.2513224181341722, difference actual-minus-bucket=-0.00046234813788609275, ECE=0.07263465522676532. Thus REL > RES, descriptive hypothesis supported. **Do not equate bucket decomposition to exact match-level Brier**: within-bin variation causes the residual. High-confidence >=0.70: 17 scored, 11 correct (64.71%), mean selected probability 77.63%. This subgroup is small and chosen from existing bins, not an independent confirmation.

The fixed-0.5 baseline beats full-sample Genome: Brier 0.25 vs 0.2513224181341722; log loss 0.69314718056 vs 0.6966212008671667. No calibration fit, retraining, or forward gain claimed. Non-production WTA Web Shadow has 104 predictions, 89 settled, 86 scored, 15 pending; baseline comparison on 79 distinct eligible paired matches must not be conflated with 86.

## Research and contrary evidence
- Waghmare & Ziegel, *Proper Scoring Rules for Estimation and Forecast Evaluation*, Annual Review of Statistics and Its Application (2026, first online 2025-11-13), https://doi.org/10.1146/annurev-statistics-042424-050626 ; CC BY 4.0 review, supports reliability/resolution interpretation, not a tennis implementation.
- Gneiting et al., *Evaluating probabilistic classifiers: The triptych*, International Journal of Forecasting (2024), https://doi.org/10.1016/j.ijforecast.2023.09.007 ; argues one metric is insufficient; no code imported, implementation license not verified.
- Pic et al., *Proper scoring rules for multivariate probabilistic forecasts based on aggregation and transformation*, Advances in Statistical Climatology, Meteorology and Oceanography (2025), https://doi.org/10.5194/ascmo-11-23-2025 ; CC BY 4.0 weather study, population not comparable to tennis.
- Contrary: stable reliability diagrams (PNAS 2021), https://doi.org/10.1073/pnas.2016191118 ; binned ECE is sensitive to bin choices and cannot independently establish a correct recalibration function.

## Trust gates, negative results, and next executable queue
Main workflow `.github/workflows/wta_web_shadow_results.yml` blob `f49387bb740a664ef5a72ee850203301062dbf2a` is scheduled `41 * * * *` and has a single-proposal gate; latest run not freshly verified. Earlier acquisition run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661 fetched 10 official sources but selected zero: 13 legacy unresolved and 2 exact-ID conflicts. Twelve plausible pair rows have round discrepancies, one pair absent. Keep all unresolved; no historical backfill. Frozen champion checksum and qualified production-forward N not independently verified here.

1. **Highest value:** construct immutable 15-ID read-only prediction-to-source crosswalk with tournament/draw/round/player/time/provenance, adversarial identity negatives, without settling.
2. Verify latest acquisition job logs and independent champion checksum / forward settlement denominator.
3. Extract 86 immutable match-level predictions, labels and timestamps to measure chronological paired Brier/log loss and uncertainty; do not fit or select a recalibrator on the final holdout.
4. On *newly prospectively locked* data, compare predeclared simple shrinkage challenger with champion and fixed-0.5 baseline; report accuracy CI, proper scores, calibration, coverage, surface/tour/time drift. No promotion without review.

No production code, prediction, settlement, workflow or champion changed. No gambling or market-derived features.
