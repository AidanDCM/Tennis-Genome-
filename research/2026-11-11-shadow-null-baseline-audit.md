# 2026-11-11 non-production WTA shadow null-model audit

## Source and scope
- Main-branch scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json
- Git blob SHA: `60082a6292087e2b6e902faca79f2f4c847d8fdb`; sample: all 85 eligible non-production WTA Web Shadow observations; 16 pending excluded. Not qualified production-forward evidence.
- No feature/model changes, no settlement publication, no prospective evidence newly accepted.

## Preregistered comparison
Hypothesis: the current non-production shadow has lower mean binary Brier score than the fixed 0.5 probability forecast on exactly the same eligible observations. Null baseline is fixed before inspecting individual outcomes; criterion for an observed descriptive win is Brier < 0.25. A meaningful model-selection win additionally requires independent chronological paired forward validation; aggregate historical results alone cannot satisfy that condition. No hyperparameter search.

## Reproducible computation
```python
import json, math
s=json.load(open('web-shadow/scorecard.json'))
m=s['metrics']; n=m['settled_match_count']; k=m['correct_prediction_count']
z=1.95996398454; p=k/n; d=1+z*z/n
c=(p+z*z/(2*n))/d
h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
print(n,k,p,(c-h,c+h),m['brier_score']-.25,m['log_loss']-math.log(2))
```

## Observed output (calculated from fetched raw scorecard)
- n=85, correct=46, accuracy=0.541176471, Wilson 95% interval [0.435763, 0.643029].
- Genome Brier=0.251461059 vs fixed 0.5 Brier=0.250000000; Genome minus null=0.001461059 (**negative finding**: fixed null wins descriptively).
- Genome log loss=0.696908273 vs fixed 0.5 log loss=0.693147181; Genome minus null=0.003761093 (**negative finding**).
- Calibration gap accuracy minus mean selected probability=-0.079247136; aggregate confidence suggests overconfidence, but this is a diagnostic, not an independently fitted recalibrator.
- Production eligible=false. This comparison is not prospective, not a paired Elo comparison, and has no independent error-bar estimate for Brier differences.

## Research comparison and limitations
- Bunker et al. (online 2023), https://doi.org/10.1177/17543371231212235 : annual expanding-window ATP tests, not a comparable WTA population; exclude disallowed features, and do not import code without licensing review.
- Buhamra et al. (2024), https://doi.org/10.3233/JSA-240670 : rolling evaluation and interpretable regression, ATP Grand Slams; CC BY-NC 4.0 article, not blanket software license.
- Ferrer & Ramos (2024), https://arxiv.org/abs/2408.02841 : calibration diagnostics cannot substitute for proper scoring rules; preprint, different domain.

## Next executable queue
1. Re-read PR #428 acquisition trust gates and identify the first failing prospective capture/identity gate; preserve conflicts as excluded.
2. Run the existing settlement integration against PR #428 in isolated CI and publish deterministic non-sensitive output summary for review; do not publish canonical evidence.
3. Refresh production-qualified forward aggregate and frozen champion hash before any model comparison.
4. Pre-register a future simple 0.5/Elo/champion paired chronological comparison on newly locked observations, with untouched final holdout and paired uncertainty.

No model promoted, no trust gate weakened, no outcome backfilled.
