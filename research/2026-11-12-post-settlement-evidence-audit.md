# Post-settlement prospective evidence audit — 2026-11-12

## Immutable read inputs
- Main commit: `3fcbd3ca5f5651704898347d18a9b9853d43b3f6` (settlement PR #469).
- Main WTA shadow scorecard blob: `c9636ac9d86c256ccf241e652b9456034c451fc3`, [source](https://github.com/AidanDCM/Tennis-Genome-/blob/3fcbd3ca5f5651704898347d18a9b9853d43b3f6/web-shadow/scorecard.json).
- [Acquisition PR #428](https://github.com/AidanDCM/Tennis-Genome-/pull/428) merged; [settlement PR #469](https://github.com/AidanDCM/Tennis-Genome-/pull/469) merged; [gate safety PR #458](https://github.com/AidanDCM/Tennis-Genome-/pull/458) remains open.
- Frozen [independent model manifest](https://github.com/AidanDCM/Tennis-Genome-/blob/3fcbd3ca5f5651704898347d18a9b9853d43b3f6/artifacts/tge_independent_v1_manifest.json): development-frozen, not independently validated as complete architecture. No change made.

## Prespecified read-only experiment
H0: the newly merged completed settlement does not materially establish model superiority over a fixed probability of 0.5; compare Brier and log loss to fixed-0.5 on identical 86 scored WTA shadow outcomes, plus 95% Wilson accuracy interval. Success for the alternative would require both proper scores below fixed-0.5 and interval excluding 0.5. These are descriptive checks, not a preregistered prospective promotion gate.

Reproduce using Python 3 standard library, on the pinned scorecard:
```bash
python - <<'PY'
import json,math,urllib.request
url='https://raw.githubusercontent.com/AidanDCM/Tennis-Genome-/3fcbd3ca5f5651704898347d18a9b9853d43b3f6/web-shadow/scorecard.json'
d=json.load(urllib.request.urlopen(url)); m=d['metrics']; n=m['settled_match_count']; k=m['correct_prediction_count']; p=k/n; z=1.96
den=1+z*z/n; c=(p+z*z/(2*n))/den; h=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
print(n,k,p,(c-h,c+h),m['brier_score']-.25,m['log_loss']-math.log(2))
PY
```
Executed equivalent JavaScript arithmetic on the GitHub connector's exact current scorecard content.

## Observed
- Terminal settlements 89; completed scored 86; non-completed 3; pending 15.
- Accuracy 47/86 = 0.5465116279; Wilson 95% = [0.4415598142, 0.6474857950].
- Genome Brier 0.2513224181 vs fixed 0.5 Brier 0.2500000000 (Genome worse by 0.0013224181).
- Genome log loss 0.6966212009 vs fixed 0.5 log loss 0.6931471806 (Genome worse by 0.0034740203).
- Elo paired N=79 (Genome Brier 0.2522696015, Elo Brier 0.2578582137). Seven completed scored predictions still have no Elo baseline. Do not mix 79 and 86 denominators.
- Prior observed scorecard: 46/85, 88 terminal, 16 pending; this main scorecard adds one correct completed outcome. These values are a historical comparison, not an independent forward champion test.
- Hypothesis of demonstrated superiority **rejected**. Confidence interval includes 50%; proper scores are worse than fixed 0.5.
- **Evidence tier:** non-production WTA Web Shadow only. No qualified FULL-STACK-FORWARD denominator or production champion improvement verified.

## Acquisition and trust blockers
- Main acquisition workflow `.github/workflows/wta_web_shadow_results.yml` blob `2a698a6f56297aee054a94dc49a28fefaaff2d35` still uses fail-open `steps.pr_gate.outputs.blocked != 'true'` guards. Fix PR #458 and dependent #457/#461 require review. No runtime gate-state integration verified.
- PR #470 documents two Nov 13 provider fixtures excluded due to event identity / current-state gates; zero forecasts frozen. Do not fabricate predictions.
- Earlier two Hong Kong identity conflicts remain excluded. Do not reinterpret excluded observations.
- No code imported, no models tuned, no settled evidence changed.

## Literature / contrary evidence
- Wang & Drekic (2026), [Boosting markovian tennis prediction](https://doi.org/10.1177/22150218251412670), 2011–2022 men's/women's data with 2014, 2018, 2022 testing; point-based ensembles may help, but noncontiguous test years and match populations differ from prospective locked evidence. External code license not checked.
- Landfried & Mocskos (2025), [TrueSkill Through Time](https://www.jstatsoft.org/article/view/v112i06), historical smoothing uses future information when reconstructing past skills: a direct leakage risk for pre-match prediction unless a strictly causal filter is used. Replication materials exist; implementation license not checked.
- Poudel et al. (2026), [Unified Tennis Benchmark](https://doi.org/10.3390/analytics5030022), ATP temporal splits; sophisticated models show modest differences over Elo. Its ATP population is not comparable to this WTA shadow cohort. No implementation imported.

## Prioritized executable queue
1. Non-mutating real GitHub Actions integration matrix: gate success/blocked/failed/skipped/empty, with no settlement writes. Preserve fail-closed policy; review #457/#458/#461.
2. Inspect latest result acquisition runs and pending IDs for missing results and identity conflicts; restore only trustworthy pre-start capture.
3. Establish qualified production forward N and immutable champion checksum independently.
4. On *new* locked matches, preregister common-cohort paired champion/Elo/fixed-0.5 Brier and log-loss with chronological intervals and drift checks. Untouched holdout remains untouched.

No automatic promotion or merge.
