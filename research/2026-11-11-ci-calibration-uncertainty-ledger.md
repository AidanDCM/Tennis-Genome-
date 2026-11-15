# Tennis Genome — CI closure and calibration uncertainty audit (2026-11-11)

## Scope and frozen evidence
Main scorecard blob: `60082a6292087e2b6e902faca79f2f4c847d8fdb` at [web-shadow/scorecard.json](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json). Research only: historical non-production WTA Web Shadow; **not** qualified forward production evaluation. No settlements, models or trust gates modified.

## Exact-head CI closure
[PR #439](https://github.com/AidanDCM/Tennis-Genome-/pull/439) head `b212015348107fed25c054f22d377af2b37487a5`; [run 42997967903](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42997967903) completed **success**. GitHub jobs API shows checkout, Python setup, installation, Ruff, Pytest, diagnostic upload all successful. This verifies existing replay/corrupt-ZIP tests, **not** a two-distinct-batch durability replay. No independent local pytest was executed.

## Prespecified audit hypothesis and method
H1: The apparent historical overconfidence (selected win probability > observed accuracy) is detectable in the aggregate, but small-bin estimates are too imprecise to justify fitting a new calibrator. Baseline: reported aggregate scorecard, no model change. Population: all 85 eligible historical Web Shadow outcomes, **not** independent prospective validation. Metric: weighted selected-probability minus realized winner accuracy; Wilson 95% intervals for proportions. Success: bucket denominators reconcile to 85, successes to 46, and weighted gap reproduces scorecard. Failure: mismatch or incomplete buckets. This is a descriptive audit; no calibration fit or holdout evaluation.

Reproducible Node/JavaScript (requires checked-out repository):
```sh
node - <<'JS'
const s=require('./web-shadow/scorecard.json'), b=s.metrics.confidence_buckets;
const n=b.reduce((x,r)=>x+r.match_count,0), k=b.reduce((x,r)=>x+r.correct_prediction_count,0);
const p=b.reduce((x,r)=>x+r.match_count*r.mean_selected_probability,0)/n;
if(n!==85||k!==46||Math.abs(k/n-p-s.metrics.calibration_gap_accuracy_minus_mean_selected_probability)>1e-12) throw Error('reconciliation failed');
console.log({n,k,accuracy:k/n,mean_selected_probability:p,gap:k/n-p});
JS
```
Observed from connected GitHub scorecard parsed in a JavaScript tool execution: n=85, correct=46, accuracy=0.5411764705882353, mean selected probability=0.6204236062056107, accuracy-minus-confidence=-0.0792471356173754. Wilson 95% for accuracy: [0.43576, 0.64303].
Bucket n/correct/observed-minus-confidence/Wilson 95%:
- 0.50–0.60: 43/22, -0.03751, [0.36752,0.65383]
- 0.60–0.70: 25/13, -0.11706, [0.33498,0.69969]
- 0.70–0.80: 12/7, -0.16896, [0.31951,0.80674]
- 0.80–0.90: 5/4, -0.03380, [0.37553,0.96378]

Negative result: none of the small buckets independently establishes a statistically reliable calibration correction; these historical observations are reused and **must not** be used to claim prospective gains. Scorecard reports Brier 0.251461, log loss 0.696908. Paired Elo comparison on 78: genome Brier 0.252433 vs Elo 0.259745; log loss 0.698682 vs 0.722719, accuracy 41/78 vs 42/78; no per-match paired uncertainty test performed.

## External research (no code or data reused)
- Dimitriadis, Gneiting & Jordan (2020), [CORP reliability diagrams](https://arxiv.org/abs/2008.03033): automated isotonic calibration diagnostics avoid arbitrary histogram bins; preprint description, check peer-reviewed version and license before reuse. Fitting isotonic on these 85 outcomes would leak evaluation outcomes; reserve for predeclared training folds only.
- Jewson (2025), [prediction reliability bias](https://doi.org/10.3390/stats8040109): finite-sample parameter uncertainty can distort forecast reliability; methodological, not a tennis result; open-access article, code/license not reused.
- Pic et al. (2025), [complementary proper scores](https://doi.org/10.5194/ascmo-11-23-2025): peer-reviewed CC BY 4.0, simulation/weather populations; scoring approaches not directly comparable to WTA accuracy.

## Prioritized next executable queue
1. Implement **two distinct synthetic batches** with separate locked prediction IDs, match IDs, artifact IDs and workflow IDs; run local pytest and exact-head CI, prove batch 2 preserves batch 1 receipt and scorecard contribution and replay rejects safely. Avoid production records.
2. Inspect PR #428 acquisition gate and publisher invocation; determine reviewer-safe unblock path without merging autonomously.
3. Independently establish official WTA round semantics and identity/provenance before considering any pending settlements.
4. Once qualified prospective N exists, preregister paired champion-vs-simplified Elo challenger, strictly chronological Brier/log loss, coverage, calibration, and uncertainty; never tune on final holdout.

No code changes to production, no champion promotion, no result backfill.
