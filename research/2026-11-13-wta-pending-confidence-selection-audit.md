# 2026-11-13 — WTA Web Shadow missing-label confidence selection audit

Status: **READ-ONLY, NON-PRODUCTION**. No settlement, model, prediction, or gate change.

## Evidence and exact source
- Main scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json
- Main scorecard blob SHA: `c9636ac9d86c256ccf241e652b9456034c451fc3`.
- Workflow source: `.github/workflows/wta_web_shadow_results.yml`, blob `f49387bb740a664ef5a72ee850203301062dbf2a`, scheduled at minute 41 hourly.
- Prior retained source run: https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43395571661
- Main reference SHA at time of source lookup: `40bb697ec786527b7ed1a4c67d6d0a92aea17782` (verify against repository before any new deployment).

## Prespecified descriptive hypothesis
H1: The pending and settled populations have a difference of **at least 0.05** in mean selected-winner probability, a practical signal of confidence-dependent label selection. H0: absolute difference <0.05. This is a diagnostic threshold, not a significance test or causal claim. Comparison population is all 104 scorecard predictions; statuses are immutable in this audit. Check counts and IDs before computing means.

## Reproduction
Run from repository root at the pinned main SHA:

```bash
python - <<'PY'
import json
from pathlib import Path
d=json.loads(Path('web-shadow/scorecard.json').read_text())
rows=[p for s in d['slates'] for p in s['predictions']]
assert len(rows)==104 and len({p['match_id'] for p in rows})==104
pending=[p for p in rows if p['status']=='PENDING']
settled=[p for p in rows if p['status']=='SETTLED']
assert len(pending)==15 and len(settled)==89
mean=lambda xs:sum(p['selected_probability'] for p in xs)/len(xs)
for name,xs in [('pending',pending),('settled',settled)]:
 print(name,len(xs),mean(xs),sum(p['selected_probability']>=0.7 for p in xs))
print('abs_difference',abs(mean(pending)-mean(settled)))
PY
```

## Executed result
Equivalent JavaScript numerical checks executed against the GitHub connector's actual parsed scorecard JSON. Counts and uniqueness checked; 104 records = 89 settled + 15 pending. Pending: mean selected probability **0.6175356703134085**, 2/15 at >=0.70, range [0.5057441333416045, 0.7966701734492774]. Settled: mean **0.6199547463964248**, 18/89 at >=0.70, range [0.5011373563106344, 0.876712889598141]. Absolute mean difference **0.0024190760830163**. **H1 rejected**; this does NOT show missing labels are random, since selection may depend on event, identity, round, chronology, or other factors.

Pending strata: Seoul 9 mean 0.5809606216912434, Singapore 4 mean 0.6756130260611217, event 1074 2 mean 0.6659686776177256. Thus aggregate similarity masks tournament composition. No outcomes imputed; no inference about true accuracy or calibrated superiority.

## Independent research and contrary evidence
- Loveday, Taggart, Khanarmuei (2024), *A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts*, https://doi.org/10.1175/WAF-D-23-0201.1. Proper scores and decision thresholds; weather evaluation, not tennis. Publisher license requires review before any reuse.
- Su (2024), *On Truthing Issues in Supervised Classification*, https://www.jmlr.org/beta/papers/v25/19-301.html. Missing and conflicting labels require explicit evaluation design; no code imported, implementation license not inspected.
- Dominitz and Manski (2024), *Comprehensive OOS Evaluation of Predictive Algorithms with Statistical Decision Theory*, https://www.nber.org/papers/w32269. Contrarian caution: evaluating only observed population can fail to describe future target population; no software imported.

## Performance tier and limitations
Previously verified non-production shadow scorecard: 47/86 correct (54.65%), Brier 0.2513224181341722, log loss 0.6966212008671667, 15 pending. Fixed-0.5 Brier 0.25 and log loss ln(2) ~0.693147 are better on the 86 scored. The 79-match paired Elo cohort is different. Production champion checksum, production qualified-forward N, latest scheduled workflow result, and all 15 source crosswalks **not independently refreshed**. No paired chronological evaluation or model ablation performed. This diagnostic must not be treated as model selection.

## Next executable queue
1. Inspect latest scheduled acquisition job logs and retained source artifact; construct read-only match-by-match crosswalk of all 15 pending IDs with source identity, round, tournament, draw and chronology; retain both exact-ID adversarial conflicts.
2. Add regression tests for read-only reason classifications; do not alter completed-only settlement or pre-start gates.
3. Verify frozen champion digest and qualified production forward evidence from main; assemble immutable chronological paired predictions before evaluating a simple shrinkage challenger on future observations, preserving untouched holdout.
