# WTA Web Shadow: terminal versus scored denominator audit (2026-11-14)

## Evidence and falsifiable test

Read current main scorecard [blob c9636ac9d86c256ccf241e652b9456034c451fc3](https://github.com/AidanDCM/Tennis-Genome-/blob/main/web-shadow/scorecard.json) and scorecard validator [blob 62d32b2580fb33b4432d41e05d092b4d16c70dd1](https://github.com/AidanDCM/Tennis-Genome-/blob/main/scripts/validate_web_shadow_scorecard.py). Hypothesis: all terminal SETTLED predictions are evaluation-eligible. Failure criterion: scored count < settled count. Observed 89 SETTLED, 86 scored, 15 PENDING among 104 unique records; hypothesis rejected, 3 terminal but unscored. Validator explicitly permits COMPLETED, RETIREMENT, WALKOVER, DEFAULTED as terminal statuses, but only COMPLETED is eligible for scoring. This *explains the contract mechanism*, **not** the individual statuses of the three excluded records, which require receipt inspection. All 89 SETTLED entries have result and settlement SHA fields. No label backfill or changes.

## Executed calculations

Read JSON and flattened all 29 slate predictions using GitHub connector. Counted SETTLED=89, PENDING=15, scored=86. Summed bucket counts 44+25+12+5=86 and correct 23+13+7+4=47. Wilson 95% interval for 47/86 = [0.44156, 0.64749]. Brier 0.2513224181341722 vs fixed 0.5 = 0.25 (delta +0.0013224181). Log loss 0.6966212008671667 vs log(2)=0.6931471805599453 (delta +0.0034740203). Non-production shadow only. This does not verify raw receipts or production champion.

Reproduction after checkout of pinned source:

```bash
python - <<'PY'
import json, math
s=json.load(open('web-shadow/scorecard.json'))
p=[x for slate in s['slates'] for x in slate['predictions']]
assert len(p)==104 and sum(x['status']=='SETTLED' for x in p)==89
assert sum(x['status']=='PENDING' for x in p)==15
assert all(x.get('settlement_record_sha256') and x.get('result_record_sha256') for x in p if x['status']=='SETTLED')
b=s['metrics']['confidence_buckets']
assert sum(x['match_count'] for x in b)==s['metrics']['settled_match_count']==86
assert sum(x['correct_prediction_count'] for x in b)==47
print('PASS: 104 total; 89 settled; 15 pending; 86 scored; 47 correct; 3 excluded')
PY
```

## Independent research

- Su (2024), [On Truthing Issues in Supervised Classification](https://www.jmlr.org/beta/papers/v25/19-301.html), JMLR open-access: distinguishes noisy, missing, and conflicting labels. Adaptation: audit terminal-status exclusion before model comparison; not evidence that excluded tennis matches are mislabeled.
- Pic et al. (2025), [Proper scoring rules for multivariate probabilistic forecasts](https://doi.org/10.5194/ascmo-11-23-2025), CC BY 4.0, atmospheric multivariate evaluation, not tennis binary matches: multiple scores can diagnose different aspects; does not justify tuning on the same cohort.
- Dominitz & Manski (2024), [Comprehensive OOS Evaluation](https://www.nber.org/papers/w32269): target-population shift matters; prospective coverage must be measured explicitly.

## Negative result and prioritized next queue

1. Fetch and independently hash all three terminal-but-unscored settlement receipts, record exact match IDs/statuses; never change immutable outcomes.
2. Inspect current pre-start intake source coverage and qualified production-forward champion receipts; quantify missingness and zero-selection reasons.
3. After new chronologically locked paired observations, preregister one conservative shrinkage-versus-frozen-champion test, Brier/log loss primary, untouched final holdout and multiple-comparison accounting. No wagering inputs.

No production change, no promotion, no claimed model improvement. Human review required.
