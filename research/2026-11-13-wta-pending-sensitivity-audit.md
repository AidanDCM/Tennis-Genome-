# WTA Web Shadow pending-label sensitivity audit — 2026-11-13

## Scope and immutable evidence
Main source commit: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`.
Scorecard: https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json (blob `c9636ac9d86c256ccf241e652b9456034c451fc3`).
Non-production Web Shadow only; no production champion or settlement mutation.

## Preregistered diagnostic
Hypothesis: with 15 unobserved pending outcomes, the observed 47/86 winner accuracy alone cannot guarantee >50% accuracy over the 101 completed-or-pending evaluation-eligible candidates, even under the *optimistic assumption* that all 15 pending would become completed and scoreable.
Baseline: observed 47/86 and constant 50% accuracy reference.
Acceptance: lower worst-case accuracy bound >0.5. Failure: lower bound <=0.5.
This is a missing-label sensitivity calculation, not a trained model, a prospective experiment, or an imputation of results. The three non-COMPLETED settled records remain excluded.

## Executed check and observations
Read the main-branch JSON with connected GitHub, parsed it using JavaScript, asserted exact 104 entries, 104 unique IDs, 15 pending, 86 primary scored, 47 correct. All five checks passed.
- 104 predictions = 89 settled + 15 pending.
- 86 primary scored, 47 correct, observed accuracy 0.5465116279; 95% Wilson interval (z=1.96) [0.4415598142, 0.6474857950].
- Conditional potential cohort N=101 = 86 scored + 15 pending (not 104, because three terminal non-COMPLETED outcomes are excluded).
- Worst case all 15 pending incorrect: 47/101 = 0.4653465347.
- Best case all 15 pending correct: 62/101 = 0.6138613861.
- Worst-case lower bound <0.5; prespecified hypothesis **rejected**. These are logical sensitivity limits, not estimates or confidence intervals.
- Pending groups: Seoul 9, Singapore 4, event 1074 2. Match IDs below.
- Existing 79-match paired Genome–Elo cohort is distinct. No new paired model inference or calibration fit.

## Reproduce (Python standard library, no dependencies)
```bash
python - <<'PY'
import json, math
s=json.load(open('web-shadow/scorecard.json'))
rows=[r for slate in s['slates'] for r in slate['predictions']]
pending=[r for r in rows if r['status']=='PENDING']
n=s['metrics']['settled_match_count']; k=s['metrics']['correct_prediction_count']
assert (len(rows),len({r['match_id'] for r in rows}),len(pending),n,k)==(104,104,15,86,47)
N=n+len(pending)
print('observed',k/n,'conditional bounds',k/N,(k+len(pending))/N)
assert k/N < 0.5
PY
```

## Pending immutable match IDs
```text
web:wta:seoul:2026:r32:sakatsume-preston
web:wta:seoul:2026:r32:ruse-lys
web:wta:seoul:2026:r32:montgomery-park
web:wta:seoul:2026:r32:zarazua-bondar
web:wta:seoul:2026:r32:ma-jones
web:wta:seoul:2026:r32:ku-ibragimova
web:wta:seoul:2026:r32:birrell-zidansek
web:wta:seoul:2026:r32:zakharova-ostapenko
web:wta:seoul:2026:r32:kenin-charaeva
web:wta:singapore:2026:r32:oliynykova-wolff
web:wta:singapore:2026:r32:parks-yamaguchi
web:wta:singapore:2026:r16:sasnovich-andreeva
web:wta:singapore:2026:r16:anisimova-gibson
web:wta:1074:2026:LS031
web:wta:1074:2026:LS020
```

## External research and contrary evidence
- Sale & Ramdas (2025), *Online Selective Conformal Prediction: Errors and Solutions*, TMLR: https://mcml.ai/publications/sr25a/ . Selection changes calibration validity; their sequential exchangeability design does **not** automatically transfer to missing tennis outcomes. No code imported, implementation license not verified.
- Manokhin & Grønhaug (2026), *Classifier Calibration at Scale*: https://www.alphaxiv.org/abs/2601.19944 . Held-out calibration splits across tabular datasets suggest comparing simple calibrators, but randomized folds are unsuitable as Tennis Genome's chronological final validation. Preprint; license and reproducibility not independently verified.
- Turtel et al. (2026), *How Proper Scoring Rules Shape LLM Forecasting*: https://arxiv.org/abs/2608.28482 . Different proper-score objectives can produce different calibration profiles; single-seed caveat, different domain and no comparable tennis population. No implementation imported.
- Counterargument: worst/best bounds are intentionally extreme; they do not prove biased missingness or estimate actual pending outcomes. Do not apply inverse-probability weights without independently verified missingness mechanisms.

## Negative findings and next executable queue
1. Read latest WTA acquisition Actions run and its gate outcome. Main workflow `.github/workflows/wta_web_shadow_results.yml` schedules `41 * * * *` but an open result proposal may block actual fetching. Existing PR #428 must be reviewed rather than bypassed.
2. Independently adjudicate the 12 legacy candidate source matches, round/tournament identity, official result and provenance, preserving original pre-start evidence. Never backfill predictions or settlements.
3. Retrieve immutable production champion digest and qualified prospective forward denominator; keep non-production WTA Web Shadow separate.
4. Extract match-level locked Genome/Elo predictions and outcomes on 79 common matches, then preregister chronological paired Brier/log-loss uncertainty analysis, retaining untouched holdout and explicit coverage.

No odds, market data, result backfill, model promotion, or changes to production code.
