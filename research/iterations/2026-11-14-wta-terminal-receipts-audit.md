# WTA Web Shadow: three excluded terminal receipts (2026-11-14)

Base: main `6b2b6855054fadf3801fd10ea0cf5290a965f067`; scorecard blob `c9636ac9d86c256ccf241e652b9456034c451fc3`; validator blob `62d32b2580fb33b4432d41e05d092b4d16c70dd1`.

## Prespecified question
Are the three settled-but-unscored records explained by terminal statuses other than COMPLETED, with exact match IDs and record SHA commitments agreeing with the frozen scorecard? Pass only if exactly three non-COMPLETED terminal receipts reconcile; fail otherwise. No retrospective change permitted.

## Actual evidence, from pinned main
| Match ID | Status | Correct (excluded) | Settlement record SHA-256 | Git blob SHA |
|---|---|---|---|---|
| web:wta:2092:2026:LS013 | RETIREMENT | false | 611d39ed3d8758305fe793ce1cc613b7b587bca8b25b7ba08b42d757c501e01a | 3e0ce9626343b9e376eb60fd840abd9dfeafb674 |
| web:wta:1023:2026:LS013 | WALKOVER | false | 259258653524b466dbed610065e4e2991186d0234a7983c3d7cc7d5b1a33b85f | 6bb0386cd9e94c500d4ebfd800e67cf5df46d73e |
| web:wta:1152:2026:LS010 | WALKOVER | true | 592c58ea085af5757e83ce3df06f6afe7579dc30edef7cf1aa5775e73f318633 | eb5ce468e9e4297455d46a9f35d14e661f59a0a9 |

Links: [Ningbo](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b685/web-shadow/slates/2026-10-20-run-39503334433/settlements/ningbo-2026-r16-ls013-ekaterina-alexandrova-marta-kostyuk.json), [Guangzhou](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b685/web-shadow/slates/2026-10-28-run-40777341058/settlements/guangzhou-2026-r16-ls013-claire-liu-katerina-siniakova.json), [Singapore](https://github.com/AidanDCM/Tennis-Genome-/blob/6b2b685/web-shadow/slates/2026-09-22-run-35758950241/settlements/singapore-2026-r16-ls010-elise-mertens-barbora-krejcikova.json).

## Executed check and negative result
GitHub code search for non-COMPLETED statuses under web-shadow/slates returned one RETIREMENT and two WALKOVER records, no DEFAULTED. Each of the three raw settlement JSON records was fetched individually at pinned main, and match ID, status, prediction SHA and settlement record SHA were cross-checked against the 104-row scorecard. Exactly 89 SETTLED and 15 PENDING; 86 scored; 47 correct. The eligibility function in `scripts/validate_web_shadow_scorecard.py` returns true only for COMPLETED. Result: PASS. No evidence of denominator arithmetic defect. The three excluded receipts contain 1 correct and 2 incorrect outcomes, but remain ineligible. Counterfactual 48/89=53.93% is NOT a legitimate score.

Reproduction from repository root (requires local checkout and Python):
```bash
python - <<'PY'
import json
from pathlib import Path
s=json.loads(Path('web-shadow/scorecard.json').read_text())
rows=[p for slate in s['slates'] for p in slate['predictions']]
excluded=[]
for p in rows:
    if p['status']!='SETTLED': continue
    receipt=json.loads(Path(p['settlement_path']).read_text())
    assert receipt['match_id']==p['match_id']
    assert receipt['record_sha256']==p['settlement_record_sha256']
    assert receipt['prediction_record_sha256']==p['prediction_record_sha256']
    if receipt['status']!='COMPLETED': excluded.append((p['match_id'],receipt['status'],receipt['prediction_correct']))
assert len(rows)==104 and len(excluded)==3 and sorted(x[1] for x in excluded)==['RETIREMENT','WALKOVER','WALKOVER']
assert sum(p['status']=='SETTLED' for p in rows)==89
print(excluded)
PY
```

## Evidence tier and limits
This is a read-only non-production shadow receipt audit, not a new model test, CI validation, or full cryptographic recomputation of each canonical JSON digest. The production full-stack status file on main dated 2026-09-16 records qualified forward N=1, but current live external anchors were not reverified. No aggregate production accuracy is released. Shadow accuracy 47/86=54.65%, Brier .251322, log loss .696621; both proper scores worse than 50% reference (.25/.693147). No model gain.

## Research comparison
Su (2024), [On Truthing Issues in Supervised Classification](https://www.jmlr.org/papers/v25/19-301.html), discusses missing and conflicting labels; unlike its label-noise estimation settings, these terminal statuses are explicitly ineligible under the frozen match-completion estimand. Kleen (2024), [measurement error sensitivity](https://doi.org/10.1002/jae.3056), studies distributional forecast evaluation in economic data; it warns against unverified labels but is not a tennis benchmark. Do not use either paper to justify changing the status gate. No external claimed win rates are compared.

## Prioritized executable queue
1. Audit recent official tournament/fixture index, pin source bytes and timestamp, dry-run forward-only intake with gate-by-gate rejection counts; no historical additions.
2. Resolve the 15 pending records via bounded result-identity/provenance checks; never backfill or relax gates.
3. Reverify external champion forward anchors and settlement chain before reporting a new qualified N.
4. Once new locked paired observations exist, preregister one shrinkage challenger against frozen champion with paired Brier/log-loss and chronological evaluation; preserve final holdout.
