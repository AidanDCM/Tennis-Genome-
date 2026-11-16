# WTA Web Shadow scorecard structural integrity audit — 2026-11-14

## Prespecified hypothesis and negative control
Hypothesis: the main-branch non-production scorecard contains at least one duplicated match ID, missing prediction SHA, or disagreement between enumerated status counts and top-level totals. Reject if all invariants hold. This is an operational provenance check, **not** an estimate of model skill.

## Immutable evidence
- Repository main search-resolved commit: `6b2b6855054fadf3801fd10ea0cf5290a965f067`
- [Scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/scorecard.json), Git blob `c9636ac9d86c256ccf241e652b9456034c451fc3`
- [Intake configuration](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/intake-config.json), blob `0431001e2cdf48a9742fba931344ac77a975562d`
- [Result configuration](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/result-config.json), blob `c9c443e6c84e40549e089a9a5c26b46e96b66a22`

## Reproduce (Python 3 standard library)
```bash
curl -fsSL https://raw.githubusercontent.com/AidanDCM/Tennis-Genome-/6b2b6855054fadf3801fd10ea0cf5290a965f067/web-shadow/scorecard.json -o /tmp/tg-shadow-scorecard.json
python - <<'PY'
import json
from collections import Counter
x=json.load(open('/tmp/tg-shadow-scorecard.json'))
rows=[p for s in x['slates'] for p in s['predictions']]
ids=[p['match_id'] for p in rows]
counts=Counter(p['status'] for p in rows)
assert len(x['slates'])==29
assert len(rows)==104
assert len(set(ids))==len(ids)
assert counts=={'SETTLED':89,'PENDING':15}
assert all(p.get('prediction_record_sha256') for p in rows)
assert counts['SETTLED']==x['settled_match_count']
assert counts['PENDING']==x['pending_match_count']
assert x['production_eligible'] is False
assert x['metrics']['settled_match_count']==86
assert x['metrics']['correct_prediction_count']==47
print('PASS: 29 slates, 104 unique predictions, 89 settled, 15 pending, 0 missing prediction hashes, 86 scored, 47 correct')
PY
```

## Observed run (connector-side read and JS assertions, 2026-11-14)
Enumerated 29 slates, 104 predictions, 104 distinct match IDs; 89 SETTLED, 15 PENDING, zero missing prediction SHA. The scored denominator is 86, not 89; **do not silently treat all settlements as scored**. 47/86 = 54.65% non-production winner accuracy, Brier 0.2513224181, log loss 0.6966212009. Pending ID cohort: 9 Seoul, 4 Singapore, 2 Hong Kong. The status and uniqueness hypothesis was **rejected**; no structural failure found.

This does **not** validate underlying receipt bytes, prediction creation times, winner labels, the production champion, or the 3 settled-but-unscored reasons. No backfill or settlement was made. The reported 79 paired Elo observations are a separate subset.

## Research and contrary evidence
Loveday, Taggart & Khanarmuei (2024), [A User-Focused Approach to Evaluating Probabilistic and Categorical Forecasts](https://doi.org/10.1175/WAF-D-23-0201.1), Weather and Forecasting, 39, 1163–1180. Published August 2024; demonstrates proper scoring and threshold-dependent verification on weather and synthetic forecasts, not WTA tennis. It argues against relying on accuracy alone. Reproducible conceptual diagnostics; published article reuse is subject to AMS permissions. Adapt Brier/log-loss and a predeclared threshold analysis after prospective N increases, without retroactive threshold selection.

## Next executable queue
1. Audit the **three settled-but-unscored** records using settlement reason codes and immutable receipt SHA; confirm scoring exclusions without changing them.
2. Verify raw pre-start prediction receipts and frozen champion identity, then enumerate independently qualified production-forward N.
3. Fetch genuinely upcoming official WTA fixtures and dry-run a future-only intake expansion with explicit rejection reasons; do not admit historical fixtures.
4. Once new paired qualified forecasts accrue, preregister one simple 0.5-shrinkage challenger and compare paired Brier/log loss in chronological order; preserve untouched final holdout.

No model promotion, identity override, production change or outcome-derived feature introduced.
