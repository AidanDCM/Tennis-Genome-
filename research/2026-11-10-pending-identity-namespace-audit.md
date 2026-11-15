# Iteration 32 — pending match identity namespace audit (2026-11-10)

## Hypothesis, baseline, population, success criteria
Hypothesis: the 13 unresolved WTA Web Shadow predictions are systematically concentrated in older, human-readable match identifier namespaces rather than the three numeric-provider-ID pending predictions. Baseline: all 16 pending equally unresolved without namespace distinction. Population: **all 16 PENDING entries** in main scorecard, not a selected subsample. Success: exact exhaustive partition into 13 legacy Seoul/Singapore IDs and 3 numeric-provider IDs, accounting assertions pass; failure: any unmatched or contradictory ID. This is a diagnostic association, **not proof of causal result-matching failure**.

## Actual source audit and executed checks
Main scorecard `web-shadow/scorecard.json` blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`; result config `web-shadow/result-config.json` blob `c9c443e6c84e40549e089a9a5c26b46e96b66a22`; acquisition workflow `.github/workflows/wta_web_shadow_results.yml` blob `2a698a6f56297aee054a94dc49a28fefaaff2d35`; main active results blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25`. Main SHA from PR #430 base `8af76720a6291b166263fa1cd8191504f84ed6b6` (verify current main separately before merging).

Retrieved scorecard and executed six JavaScript assertions over the parsed raw JSON: (1) pending count matches scorecard 16, (2) partition exhaustive, (3) 9 legacy Seoul IDs, (4) 4 legacy Singapore IDs, (5) 3 numeric WTA IDs, (6) 46/85 historical scorecard. **6/6 passed.**

**Observed:** 13/16 pending have legacy IDs `web:wta:seoul:2026:...` (9) or `web:wta:singapore:2026:...` (4), from September 22–23 match schedules. Other three: numeric group IDs `web:wta:1074:2026:LS031`, `web:wta:1074:2026:LS020` (known identity conflicts), and `web:wta:1148:2026:LS001` (proposed result, unmerged). Result-config DOES include Seoul (group 1024) and Singapore (group 1152); absent tournament configuration is therefore **not** an explanation. This is evidence of a possible identifier-translation/match-source mismatch to investigate, not permission to backfill or infer outcomes.

Full legacy IDs:
```
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
```

Reproduce with a read-only local clone:
```bash
python - <<'PY'
import json
d=json.load(open('web-shadow/scorecard.json'))
p=[x for s in d['slates'] for x in s['predictions'] if x['status']=='PENDING']
legacy=[x for x in p if x['match_id'].startswith(('web:wta:seoul:2026:', 'web:wta:singapore:2026:'))]
numeric=[x for x in p if x['match_id'].startswith(('web:wta:1074:2026:','web:wta:1148:2026:'))]
assert len(p)==16 and len(legacy)==13 and len(numeric)==3
assert sum(':seoul:' in x['match_id'] for x in legacy)==9
assert sum(':singapore:' in x['match_id'] for x in legacy)==4
assert len(legacy)+len(numeric)==len(p)
print({'pending':len(p),'legacy':len(legacy),'numeric':len(numeric)})
PY
```

## Research comparison and contrary evidence
- [ulpati/atp-tennis-predictor](https://github.com/ulpati/atp-tennis-predictor), repository inspected 2026-11-10: documents strict chronological ATP train/validation/test and symmetric pre-match features, hash-pinned data; code and upstream match data CC BY-NC-SA 4.0. Its claimed ATP performance is **not comparable** to Tennis Genome WTA; no code copied. Adapt independent pre-match identity/feature parity tests only.
- [feodory/Tennis_Predictive_Alpha](https://github.com/feodory/Tennis_Predictive_Alpha), inspected 2026-11-10: reports ATP walk-forward logistic/Elo benchmark and Python/SQL feature parity checks, with 693 test matches; license not independently verified. Independent feature parity is useful, but ATP and test-selection differences prohibit direct score comparison.
- [buildoak/tennis-xgboost-autoresearch](https://github.com/buildoak/tennis-xgboost-autoresearch), inspected 2026-11-10: documents an evaluation-gate gaming failure and archived failed experiments; reported MIT code, CC BY-NC-SA data (not independently audited). **Contrary lesson:** self-optimizing a repeatedly examined gate can inflate apparent performance. Do not copy external code or relax final holdout.

## Evidence tier and negative results
Main non-production WTA Web Shadow: 88 settled records, 85 scored, 46 correct (54.12%), Brier 0.251461, log loss 0.696908; **not qualified forward performance**. Previously verified forward aggregate reported zero qualified observations; no fresh forward aggregate executed this iteration. Open PR #428 contains 1 proposed Chennai result, 13 unresolved and 2 excluded conflicts. PR #430 diagnostic remains draft/unmerged. Current acquisition main workflow blocks on open result proposal. This audit did not match provider records for the 13 IDs; **no causal identity diagnosis or new settlement**. No CI executed for this research-only ledger yet. No model altered.

## Prioritized executable queue
1. Compare the 13 legacy prediction IDs against **retained official WTA Seoul/Singapore provider rows** using original player pairs, dates, round, event group IDs and immutable pre-start prediction SHA; distinguish nonexistence, rescheduling, and ambiguous identities. No inferred settlement.
2. Human-review PR #428's single result and original source/provenance, safely resolve blocking proposal without bypassing safety.
3. End-to-end validate blocked receipt from PR #430 on main after review, then track fresh acquisition and qualified forward N.
4. Once new locked, independently verified forward observations exist, prespecify paired champion vs research-only fixed log-odds slope 0.5 Brier/log loss and untouched chronological holdout.
