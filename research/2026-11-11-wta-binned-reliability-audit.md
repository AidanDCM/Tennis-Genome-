# 2026-11-11 WTA Web Shadow binned reliability audit (non-production)

## Source and evidence status
- Main SHA: `8af76720a6291b166263fa1cd8191504f84ed6b6`.
- Scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`: https://github.com/AidanDCM/Tennis-Genome-/blob/8af76720a6291b166263fa1cd8191504f84ed6b6/web-shadow/scorecard.json
- Main active-results blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` still lists the Hong Kong result only. Acquisition PR #428 https://github.com/AidanDCM/Tennis-Genome-/pull/428 is open, unmerged, with 1 captured result, 13 unresolved predictions and 2 held-out identity conflicts. No new qualified forward observation established.
- Scope: 85 historical eligible WTA Web Shadow outcomes, `production_eligible=false`; 16 pending. Frozen champion SHA and production-forward aggregate not independently reverified.

## Prespecified descriptive hypothesis and outcome
H1: Confidence-bin reliability penalty is smaller than bin resolution benefit on the current 85 scored records. Baseline: fixed 0.5 forecast (Brier 0.25), and existing reported Genome Brier 0.2514610585394295. Success criterion: reliability < resolution, plus independent future chronological validation before any model claim. No tuning, no model change, no holdout access.
Computed from *four existing fixed confidence buckets* (n, correct, mean selected probability):
`(43,22,.549139773488359), (25,13,.6370589191083283), (12,7,.7522953972274985), (5,4,.8337957046078553)`.
- N=85; K=46; selected winner accuracy=.5411764705882353; mean selected confidence=.6204236062056107; gap=-.0792471356173754.
- Binned reliability sum(n/N*(pbar_k-ybar_k)^2)=**0.008839596303522776**.
- Binned resolution sum(n/N*(ybar_k-ybar)^2)=**0.004765054585445671**.
- Base uncertainty ybar*(1-ybar)=**0.2483044982698962**.
- Coarsened-bin approximation uncertainty + reliability - resolution = **0.2523790399879733** vs actual full-record Brier **0.2514610585394295**. Difference arises because bin means discard within-bin probability variation; do NOT claim exact Murphy decomposition of the unbinned forecasts.
- Reliability > resolution by **0.004074541718077105**; H1 **FAILED**. This is a descriptive diagnosis, not proof of out-of-sample miscalibration or a justification to recalibrate on these same observations.
- Negative finding: the existing actual Brier is also worse than the fixed 0.5 Brier by 0.0014610585394295. Paired uncertainty cannot be reconstructed from aggregate bins.

## Reproduce (Python 3, no dependencies)
```python
b=[(43,22,.549139773488359),(25,13,.6370589191083283),(12,7,.7522953972274985),(5,4,.8337957046078553)]
N=sum(n for n,k,p in b); y=sum(k for n,k,p in b)/N
rel=sum(n/N*(p-k/n)**2 for n,k,p in b)
res=sum(n/N*(k/n-y)**2 for n,k,p in b)
print(N, y, rel, res, y*(1-y)+rel-res)
```
Expected: `85 0.5411764705882353 0.008839596303522776 0.004765054585445671 0.2523790399879733`.

## Research and contrary evidence
- Murphy (1973), https://doi.org/10.1175/1520-0450(1973)012%3C0595:ANVPOT%3E2.0.CO;2 : reliability, resolution and inherent uncertainty, not winner accuracy alone.
- Siegert (published 2016), https://doi.org/10.1002/qj.2985 : simplified decomposition and recalibration comparison. Our grouped approximation must not be mistaken for exact individual-level decomposition.
- Bröcker (2009), https://doi.org/10.1002/qj.456 : proper scoring rules, reliability and resolution. Different weather evaluation populations, no transferable tennis performance claims. No external code or datasets imported; license of potential implementations not assessed.

## Prioritized executable queue
1. Restore official WTA result capture/identity coverage: inspect PR #428 unresolved 13 and conflicts 2; preserve fail-closed exclusion and review proposed Chennai evidence.
2. Add deterministic non-sensitive settlement summary to isolated CI for PR #428 and inspect exact-head artifacts; do not publish canonical scorecard.
3. Refresh frozen champion SHA, production-qualified forward N and immutable receipts.
4. Pre-register a *new*, chronologically forward paired champion-vs-fixed-0.5-vs-Elo evaluation (Brier, log loss, accuracy CI, calibration and tour/surface/time coverage) with untouched holdout and multiple-comparison control. Do not fit calibration on the shadow sample then evaluate it on itself.

No odds, market data, automatic promotion, merge or settlement publication.
