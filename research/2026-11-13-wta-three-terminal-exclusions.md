# 2026-11-13 WTA Web Shadow: exact three baseline-path exclusions (read-only)

## Scope and immutable evidence
Main `40bb697ec786527b7ed1a4c67d6d0a92aea17782`; `web-shadow/scorecard.json` blob `c9636ac9d86c256ccf241e652b9456034c451fc3`; `scripts/apply_web_shadow_settlement_batch.py` blob `eeb98a1259b61dfc32aaf177da31d3622b9a70f4`; `scripts/validate_web_shadow_scorecard.py` blob `62d32b2580fb33b4432d41e05d092b4d16c70dd1`. Non-production only. No champion, production prediction or settlement mutation.

## Preregistered diagnostic and result
H0: the three-settlement gap (82 SETTLED with baseline_path, 79 eligible paired) cannot be fully explained by terminal non-COMPLETED status. Test: inspect all 82 corresponding immutable settlement JSON files on main and count non-COMPLETED; accept complete explanation only if exactly three, all have valid supported terminal status, and 82 - 3 = 79. GitHub fetch_file inspected all 82 settlement files in ordered batches (12,10,12,12,12,12,12). **H0 rejected**: exactly three non-COMPLETED:
- `web:wta:1152:2026:LS010` — `WALKOVER`
- `web:wta:2092:2026:LS013` — `RETIREMENT`
- `web:wta:1023:2026:LS013` — `WALKOVER`

All other 79 baseline-path settlement files returned `COMPLETED`; no fetch errors in successful batches. These are already settled, **not pending**. The evaluation gate accepts only `COMPLETED` and rejects `WALKOVER`, `RETIREMENT`, `DEFAULTED` for scoring. This fully explains the paired denominator, without inferring missing outcomes. Baseline-path presence is not evaluation eligibility. This is a code-and-data consistency audit, not new predictive evidence.

## Reproduction
```python
import json
from pathlib import Path
s=json.loads(Path("web-shadow/scorecard.json").read_text())
p=[x for slate in s["slates"] for x in slate["predictions"]]
with_baseline=[x for x in p if x["status"]=="SETTLED" and x.get("baseline_path")]
statuses={}
for x in with_baseline:
    z=json.loads(Path(x["settlement_path"]).read_text())
    statuses[x["match_id"]]=z["status"]
excluded={k:v for k,v in statuses.items() if v!="COMPLETED"}
assert len(with_baseline)==82
assert excluded=={
 "web:wta:1152:2026:LS010":"WALKOVER",
 "web:wta:2092:2026:LS013":"RETIREMENT",
 "web:wta:1023:2026:LS013":"WALKOVER",
}
assert sum(v=="COMPLETED" for v in statuses.values())==79
assert s["baseline_comparison"]["settled_match_count"]==79
print("PASS: 82 baseline paths, 3 terminal exclusions, 79 eligible")
```
Executed equivalent JSON/status checks through connected GitHub file reads, not local pytest. No exact-head CI was run; this branch changes documentation only.

## Forecasting evidence and limitations
Last main shadow scorecard: 104 predictions, 89 SETTLED, 86 primary scored, 79 paired Elo, 15 PENDING. Primary 47/86 accuracy, Brier 0.2513224181341722, log loss 0.6966212008671667; fixed 0.5 baseline Brier 0.25, log loss ~0.693147. On 79 paired cases Genome Brier 0.2522696014990375 vs Elo 0.2578582137265702, log loss 0.6983470279140795 vs 0.7186905603048556, accuracy 42/79 vs 43/79. These are existing aggregates; no match-level paired CI or chronological ablation run. Qualified production-forward N and frozen champion digest not independently refreshed. Do not treat these shadow observations as production-qualified.

## External research, contrary evidence, licenses
- Waghmare & Ziegel (review published March 2026), https://doi.org/10.1146/annurev-statistics-042424-050626: proper scores evaluate probability quality, not just classifications; CC BY 4.0 article; no software imported.
- Ferro (2017), https://doi.org/10.1002/qj.3115: observation errors can distort proper-score comparisons; meteorological setting, not tennis; no code imported or license assumed. This is a reason **not** to reclassify terminal matches as completed.
- Loveday et al. (2024), https://arxiv.org/abs/2311.18258: threshold-sensitive diagnostics complement aggregate proper scores; weather forecasts, no directly comparable tennis cohort, no implementation imported.

## Negative evidence and prioritized next queue
1. Audit current official acquisition workflow runs, unresolved 12 legacy round-discrepant source rows, and two exact-ID conflicts with independently retained source bytes. Never backfill or relax pre-start identity/provenance gates.
2. Refresh immutable production champion digest and qualified forward settlement N; record capture rate, exclusions and drift by tour/surface/date.
3. Extract match-level 79 paired forecasts and immutable outcomes for chronological paired Brier/log-loss intervals; preserve untouched holdout, avoid repeated holdout testing.
4. After sufficient newly locked prospective data, preregister a simple shrinkage-to-0.5 calibration challenger versus unchanged champion, evaluating coverage and proper scores. No promotion without review.
