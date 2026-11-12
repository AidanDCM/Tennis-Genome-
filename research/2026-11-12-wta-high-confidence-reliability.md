# WTA shadow high-confidence reliability audit — 2026-11-12

Evidence tier: historical NON-PRODUCTION WTA Web Shadow only. Main scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`, https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json .

## Prespecified diagnostic
Hypothesis: among frozen predictions with selected probability >= 0.70, observed accuracy is at least the average selected probability. Comparison: mean predicted confidence vs realized correct fraction. This is a descriptive diagnostic on already-seen historical bins, NOT a prospective model-selection test or a valid claim of statistical significance. Sample IDs: the scorecard's >=0.70 confidence buckets; individual IDs must be resolved before paired inference.

## Executed calculation (JavaScript over retrieved JSON)
```js
const b=scorecard.metrics.confidence_buckets.filter(x=>x.lower_bound>=0.70);
const n=b.reduce((s,x)=>s+x.match_count,0);
const correct=b.reduce((s,x)=>s+x.correct_prediction_count,0);
const mean=b.reduce((s,x)=>s+x.match_count*x.mean_selected_probability,0)/n;
console.log({n,correct,mean,accuracy:correct/n,gap:correct/n-mean});
```
Output: n=17, correct=11, mean=0.7762660758687799, accuracy=0.6470588235294118, gap=-0.12920725233936814. Wilson 95% accuracy interval [0.4130,0.8269] (normal z=1.96); contains mean predicted confidence. No reliable high-confidence calibration violation established. Historical scorecard: 46/85, Brier 0.2514610585, log loss 0.6969082733; 16 pending, production_eligible=false. Paired Elo comparison N=78, Brier difference baseline minus Genome +0.0073123630; not a confidence interval.

## Independent research
Bunker et al. (2023), https://doi.org/10.1177/17543371231212235, uses expanding annual ATP test years (2007–2020); useful chronological design, different population and no directly transferable score. Its publication includes features outside our permitted scope; import none. Unified Tennis Benchmark (2026), https://doi.org/10.3390/analytics5030022, common chronological ATP splits and diminishing model complexity gains; independent WTA replication and licensing not verified. Neither is a replacement for locked prospective comparisons.

## Negative findings and trust boundaries
Hypothesis not supported descriptively (observed below predicted), but uncertainty is wide. Bucket aggregation cannot recover per-match paired losses, chronological order, or robust calibration confidence intervals. No retrospective recalibration, champion edits, settlements, or promotion. Prior PR #428 identity conflicts LS031 and LS020 must remain excluded. Current qualified production-forward N and champion checksum not reverified in this iteration.

## Prioritized next executable experiments
1. Read retained raw Hong Kong rows and locked slate stable participant IDs for LS031 and LS020; preserve exact identity exclusion.
2. Emit deterministic read-only Chennai settlement summary with provenance and unchanged canonical-file digests in isolated CI.
3. Audit acquisition coverage and resume new pre-start locked predictions; verify production-forward gates.
4. Only with new qualified forward pairs, preregister frozen champion versus Elo and fixed-50% paired Brier/log loss, reliability, tour/surface/time, and uncertainty; retain untouched holdout.
