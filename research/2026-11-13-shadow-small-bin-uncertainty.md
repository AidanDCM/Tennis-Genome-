# WTA Web Shadow small-bin uncertainty audit — 2026-11-13

**Tier:** retrospective descriptive NON-PRODUCTION; not an independently qualified forward model test. **No result/settlement/model edits.**

## Source and prespecified diagnostic

Main commit `40bb697ec786527b7ed1a4c67d6d0a92aea17782`; [scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json), blob `c9636ac9d86c256ccf241e652b9456034c451fc3`; `metrics.confidence_buckets`. Cohort: 86 scored, 47 correct; 15 pending not assigned labels. IDs are the scored predictions enumerated under `slates[].predictions`; aggregate buckets do not permit independent per-record verification.

**Hypothesis:** the four observed underconfidence-direction gaps reported in PR #491 establish statistically unambiguous overconfidence. **Null/control:** each bucket's recorded mean forecast lies within the two-sided 95% Wilson score interval of its empirical success frequency. **Failure condition:** all four forecast means lie inside their intervals, undermining any claim of demonstrated bucketwise miscalibration. These are descriptive marginal intervals, not simultaneous intervals or a valid test of calibrated individual Bernoulli forecasts.

## Executed reproducible calculation

Python 3 standard library, no packages:
```python
import math
buckets=[(44,23,.5482632745914625),(25,13,.6370589191083283),(12,7,.7522953972274985),(5,4,.8337957046078553)]
def wilson(n,k,z=1.96):
    q=k/n; d=1+z*z/n
    c=(q+z*z/(2*n))/d
    h=z*math.sqrt(q*(1-q)/n+z*z/(4*n*n))/d
    return c-h,c+h
for n,k,p in buckets:
    lo,hi=wilson(n,k)
    print(n,k,round(lo,4),round(hi,4),round(p,4),lo<=p<=hi)
print('overall',wilson(86,47))
```

Actual output:
```
44 23 0.3794 0.6625 0.5483 True
25 13 0.3350 0.6997 0.6371 True
12 7 0.3195 0.8067 0.7523 True
5 4 0.3755 0.9638 0.8338 True
overall (0.44155981420304113, 0.6474857949579708)
```

**Negative result:** all four mean confidences are inside 95% Wilson intervals; directional point-estimate overconfidence is not strong bucket-level evidence. The 80–90% bucket has only 5 observations. Scorecard Brier 0.251322418 and log loss 0.696621201 remain worse than fixed-0.5 descriptive references (0.25 and ln 2), but this audit neither fits nor validates a new model. The Wilson intervals assume independent Bernoulli trials; shared players/events violate this approximation, likely making uncertainty greater. Multiple bucket inspection further weakens interpretation.

## External research, design and exclusions

- [Bunker et al. (2023)](https://doi.org/10.1177/17543371231212235): year-expanding ATP evaluation across 2007–2020 suggests chronological tests of simple logistic and rating baselines. Its feature set includes prohibited market inputs, so do **not** import those inputs or compare headline accuracy directly to our WTA cohort. No code/license assumed.
- [Bröcker and Smith (2007), Increasing the Reliability of Reliability Diagrams](https://doi.org/10.1175/WAF993.1): binning forecast probabilities introduces estimation uncertainty; report bin denominators and uncertainty rather than asserting calibration from point estimates. No code imported.
- [2026 unified tennis benchmark](https://doi.org/10.20944/preprints202605.2002.v1): reports close model performance with chronological evaluation; preprint, external data coverage and reproducibility unverified here. Treat as a contrary complexity hypothesis, not transferable evidence.

## CI and evidence gates

[PR #490 exact-head run 43463132892](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43463132892) and [PR #491 exact-head run 43464942178](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43464942178) returned completed/success from GitHub. Their run names reference merge commits, so verify checkouts/job logs before calling them exact-head source tests. This documentation branch has no production behavior changes.

The immutable champion, independently qualified forward count, and new pre-start capture were **not independently recomputed** in this iteration. WTA scorecard `settled_match_count=89`, `metrics.settled_match_count=86`, `pending_match_count=15`, paired Elo comparison N=79; these denominators must remain distinct.

## Prioritized next executable queue

1. Inspect PR #490 job checkout and source test logs, then independently adjudicate 12 round mismatches, one absent pair, and two exact-ID conflicts with independent source evidence. No retroactive settlement.
2. Repair or schedule genuinely pre-start capture with externally anchored provenance, and measure qualified forward accrual by week; retain immutable champion and untouched holdout.
3. Preregister **one** fixed shrinkage challenger on a future locked cohort, compare paired Brier/log loss with champion and 0.5, and report uncertainty, calibration and surface/tour coverage; no tuning on these 86 cases.
