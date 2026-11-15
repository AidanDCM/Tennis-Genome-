# 2026-11-12 — WTA Web Shadow terminal-status denominator reconciliation

## Scope and preregistered question
Read-only audit of main's `web-shadow/scorecard.json` (blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`) and immutable settlement records. Hypothesis: the three `SETTLED` entries absent from the 85-match score are non-COMPLETED terminal outcomes. Success: 88 scorecard SETTLED entries partition exactly into 85 COMPLETED and three excluded terminal statuses, with the three individually identified. Baseline: naive counting of all SETTLED entries as scored. No retrospective modifications or inferred winners.

## Actual execution
Using the connected GitHub `fetch_file` action, parsed the scorecard and fetched each of the 88 referenced settlement JSON files in five read-only batches (15,18,18,18,19). Counted `settlement.status` for each, and compared to the validator's `_settlement_is_evaluation_eligible` logic from `scripts/validate_web_shadow_scorecard.py` (blob `62d32b2580fb33b4432d41e05d092b4d16c70dd1`). The source accepts COMPLETED, RETIREMENT, WALKOVER, DEFAULTED as terminal but scores only COMPLETED. All 88 fetches succeeded.

Results: **85 COMPLETED, 2 WALKOVER, 1 RETIREMENT**; thus 88 SETTLED - 3 non-COMPLETED = **85 scored**. The three are:

| Match ID | Status | Scheduled start | Settlement file |
|---|---|---|---|
| `web:wta:1152:2026:LS010` | WALKOVER | 2026-09-23T14:30:00+08:00 | `web-shadow/slates/2026-09-22-run-35758950241/settlements/singapore-2026-r16-ls010-elise-mertens-barbora-krejcikova.json` |
| `web:wta:2092:2026:LS013` | RETIREMENT | 2026-10-21T19:00:00+08:00 | `web-shadow/slates/2026-10-20-run-39503334433/settlements/ningbo-2026-r16-ls013-ekaterina-alexandrova-marta-kostyuk.json` |
| `web:wta:1023:2026:LS013` | WALKOVER | 2026-10-29T13:00:00+08:00 | `web-shadow/slates/2026-10-28-run-40777341058/settlements/guangzhou-2026-r16-ls013-claire-liu-katerina-siniakova.json` |

All three have `baseline_path`, but are ineligible for winner-probability scoring. The seven COMPLETED entries without `baseline_path` were identified in [PR #467](https://github.com/AidanDCM/Tennis-Genome-/pull/467). Hence **88 SETTLED = 85 COMPLETED + 3 excluded terminal**, and **85 scored = 78 paired Genome/Elo + 7 missing-baseline**. No settlement data were changed.

## Reproduction
On a repository checkout of main SHA `8af76720a6291b166263fa1cd8191504f84ed6b6`:

```bash
python - <<'PY'
import json
from collections import Counter
from pathlib import Path
root=Path('.')
score=json.loads((root/'web-shadow/scorecard.json').read_text())
rows=[p for s in score['slates'] for p in s['predictions'] if p['status']=='SETTLED']
statuses=Counter(json.loads((root/p['settlement_path']).read_text())['status'] for p in rows)
print(len(rows),statuses)
assert len(rows)==88
assert statuses=={'COMPLETED':85,'WALKOVER':2,'RETIREMENT':1}
assert score['metrics']['settled_match_count']==85
assert score['baseline_comparison']['settled_match_count']==78
PY
```

The equivalent read-only connector experiment was actually executed; this shell command is supplied for independent reproduction, not claimed as run in this environment.

## Research and contrary evidence
- Kleen (2024), *Scaling and measurement error sensitivity of scoring rules for distribution forecasts*, https://doi.org/10.1002/jae.3056 — open-access theoretical/simulation evidence that verification errors can change forecast rankings. Different continuous-outcome setting, not directly transferable to tennis; no code imported or license assessed.
- Jonkers et al. (2026), *Proper Scoring Rules for Right-Censored Survival Data*, https://arxiv.org/abs/2606.06393 — discusses correct handling of censored observations and assumptions. Tennis retirements/walkovers are **not** ordinary independent right-censoring, so do not blindly apply IPCW or impute winners. No implementation reproduced; code license unknown.

## Negative results, gates, and next queue
- Rejected naive 88-observation denominator; the missing three are not silently dropped wins/losses.
- This resolves accounting, **not** prospective capture, calibrated superiority, or selection bias. 16 predictions remain pending; non-production WTA Web Shadow 46/85 accuracy, Brier 0.251461, log loss 0.696908, fixed 0.5 Brier 0.25. Do not promote or backfill.
- Main's acquisition gate remains under review in PRs #457/#458/#461; result-acquisition proposal #428 still requires human evidence/identity review. Immutable production champion and qualified forward N were not independently refreshed here.
- Priority 1: human-review-safe, no-write gate runtime integration test on #458/#461. Priority 2: review #428 provenance and source coverage. Priority 3: on *new* locked predictions, paired time-ordered champion/Elo/fixed-0.5 evaluation with Brier/log loss, calibration, CI and missingness accounting. Preserve untouched final holdout.
