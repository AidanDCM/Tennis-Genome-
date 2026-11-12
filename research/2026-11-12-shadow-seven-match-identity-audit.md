# WTA Web Shadow seven-match baseline coverage audit — 2026-11-12

## Frozen source and hypothesis
Main commit: `8af76720a6291b166263fa1cd8191504f84ed6b6`; scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`. Non-production only. Hypothesis (prespecified before settlement inspection): all seven settled records missing a baseline_path are the seven omitted from the 85-match vs 78-match comparison; expected seven records, and their outcomes should reproduce the previous 5/7 arithmetic. Failure if counts or correct flags disagree. This is an audit of previously frozen evidence, not a new prospective test or new model.

## Executed read-only procedure
GitHub connector fetch_file on `web-shadow/scorecard.json`, filter `status == SETTLED && !baseline_path`, then fetch each referenced `settlement_path` and read `prediction_correct`. Reproduce with:

```python
import json
from pathlib import Path
s=json.loads(Path('web-shadow/scorecard.json').read_text())
rows=[p for slate in s['slates'] for p in slate['predictions'] if p['status']=='SETTLED' and not p.get('baseline_path')]
for p in rows:
    z=json.loads(Path(p['settlement_path']).read_text())
    print(p['match_id'],z['prediction_correct'])
print('count',len(rows),'correct',sum(json.loads(Path(p['settlement_path']).read_text())['prediction_correct'] for p in rows))
```

## Actual output
Total settled entries in scorecard: 88; settled without baseline_path: 7; correct: 5/7. The 85 scored vs 78 paired difference is seven; the seven missing-baseline entries are all completed settlements. Three other settled entries do not enter scored metrics; reason not investigated here. The seven missing-baseline rows all occurred on September 20, 2026, in two early slates. Thus missing baseline is chronological/coverage-linked rather than a random subset. No Elo predictions may be invented or retrofitted.

| Match ID | Slate | Correct | Settlement path |
|---|---|---|---|
| `web:wta:singapore:2026:RS007` | `2026-09-19-run-35456454045` | false | `web-shadow/slates/2026-09-19-run-35456454045/settlements/singapore-2026-rs007-friedsam-kulikova.json` |
| `web:wta:seoul:2026:qfnl:ma-lee` | `2026-09-19-run-35456454045` | true | `web-shadow/slates/2026-09-19-run-35456454045/settlements/seoul-2026-qfnl-ma-lee.json` |
| `web:wta:seoul:2026:qfnl:shubladze-astakhova` | `2026-09-19-run-35456454045` | false | `web-shadow/slates/2026-09-19-run-35456454045/settlements/seoul-2026-qfnl-shubladze-astakhova.json` |
| `web:wta:seoul:2026:qfnl:yao-kuramochi` | `2026-09-19-run-35456454045` | true | `web-shadow/slates/2026-09-19-run-35456454045/settlements/seoul-2026-qfnl-yao-kuramochi.json` |
| `web:wta:seoul:2026:qfnl:ibragimova-saito` | `2026-09-19-run-35456454045` | true | `web-shadow/slates/2026-09-19-run-35456454045/settlements/seoul-2026-qfnl-ibragimova-saito.json` |
| `web:wta:singapore:2026:RS005` | `2026-09-19-run-35457838597` | true | `web-shadow/slates/2026-09-19-run-35457838597/settlements/singapore-2026-rs005-hibino-ito.json` |
| `web:wta:singapore:2026:RS006` | `2026-09-19-run-35457838597` | true | `web-shadow/slates/2026-09-19-run-35457838597/settlements/singapore-2026-rs006-yamaguchi-okamura.json` |

## Negative findings and caveats
Observed 5/7 agrees with earlier aggregate reconstruction, but does not demonstrate an Elo comparison for these matches or causality. Need verify exactly 78 of the 81 baseline_path settled rows are scoreable; 3 unscored settlements remain. The 85-match WTA shadow is not production evidence; overall 46/85 accuracy, Brier 0.2514610585394295, log loss 0.6969082732945988, 16 pending. Fixed-0.5 baseline Brier 0.25 and log loss 0.693147. Production champion SHA and qualified production-forward N not revalidated. Main acquisition gate remains fail-open (`steps.pr_gate.outputs.blocked != 'true'`); draft safety PRs #458/#461 not merged. PR #428 still open with 13 unresolved and 2 identity conflicts excluded. No new settlements or model changes.

## Research (read 2026-11-12)
- Waghmare & Ziegel, *Proper Scoring Rules for Estimation and Forecast Evaluation*, https://doi.org/10.1146/annurev-statistics-042424-050626 : compare identical forecast/observation pairs; scoring rules can rank misspecified models differently. Review, not an imported implementation; code license not evaluated.
- Choe & Ramdas (2023), *Comparing Sequential Forecasters*, https://doi.org/10.1287/opre.2021.0792 : anytime-valid paired sequential comparisons; different sport/weather populations, not reproduced here; implementation license not checked. No external code imported.

## Next executable queue
1. Inspect all three settled-but-unscored records, classify exclusion reasons from immutable settlement status, and prove a complete 88=85+3 and 85=78+7 partition by match IDs.
2. Add a read-only test asserting baseline coverage and scorecard denominator consistency; do not change scoring policy retrospectively.
3. Obtain review of #428 and safe fail-closed acquisition gate #458/#461; run non-mutating gate behavior test before any merge.
4. After genuinely new qualified pre-start predictions accumulate, preregister paired champion vs Elo vs fixed-0.5 Brier/log loss, coverage, calibration and chronological intervals; keep holdout untouched.

No odds, wagering, promotion, or settlement mutation.
