# Iteration 35 — legacy round-gate source audit (2026-11-10)

## Prespecified question
Does the actual current acquisition implementation force all 13 legacy pending IDs through the round-sensitive participant-pair join, while treating the three numeric IDs through the exact MatchID join? Baseline: 13 legacy unresolved, 3 numeric IDs (one proposed result, two identity conflicts). Success: all 8 source assertions pass, without claiming that a different round mapping is correct.

## Immutable inputs
- Main `web-shadow/scorecard.json` blob SHA `60082a6292087e2b6e902faca79f2f4c847d8fdb`.
- Main `scripts/web_shadow_wta_result_core.py` blob SHA `e4785a6d0b9b07c4fd4a52d2b44927211e5f7172`.
- Historical research PR #433, https://github.com/AidanDCM/Tennis-Genome-/pull/433, and official provider evidence retained in PR #428. No outcome mutation.

## Executed reproducible check
GitHub connector `fetch_file` for both paths on main. Parse scorecard JSON; flatten `slates[].predictions`; select `status === "PENDING"`; classify `match_id.split(":").length === 6` as legacy versus `=== 5` as numeric. Inspect the actual Python `_pending_predictions`, `_row_identity`, and `_match_row` implementation for the exact-ID branch and the legacy `player_pair AND round` branch. Deterministic JavaScript assertions:

```js
const pending = scorecard.slates.flatMap(s => s.predictions).filter(p => p.status === "PENDING");
const legacy = pending.filter(p => p.match_id.split(":").length === 6);
const numeric = pending.filter(p => p.match_id.split(":").length === 5);
const checks = {
  total16: pending.length === 16,
  legacy13: legacy.length === 13,
  numeric3: numeric.length === 3,
  legacyCannotUseExactID: legacy.every(p => !/^web:wta:\d+:\d+:[^:]+$/.test(p.match_id)),
  legacyRequiresRound: source.includes('item["round"] == pending["round"]'),
  numericSkipsRound: source.includes('return match\n\n    matches = ['),
  strictRoundMapping: source.includes('1: "F"') && source.includes('2: "SF"'),
  noPermissiveFallback: source.includes('if len(matches) > 1:')
};
if (!Object.values(checks).every(Boolean)) throw new Error(JSON.stringify(checks));
```

## Actual result
**8/8 source/data assertions passed**. 16 pending: 13 legacy namespaced IDs, 3 numeric IDs. Legacy IDs cannot populate `source_match_id` and therefore require both the normalized participant pair and interpreted round to agree. Numeric IDs join by exact provider MatchID and verify participant pair; source round discrepancy is retained in evidence instead of blocking the exact-ID join. The numeric `_ROUND_ID_MAP` still interprets 1 as F and 2 as SF; previous PR #433 observed 11 R32 and one R16 legacy candidate with provider RoundID 1/2. These conditions are consistent with the 13 unresolved cases, **but do not independently prove official round semantics or settlement eligibility**.

## External methodological research (no copied code)
- Pic et al. (2025), https://doi.org/10.5194/ascmo-11-23-2025; open CC BY 4.0 paper, reproducible R experiments, weather forecast evaluation. Multiple complementary proper scoring rules can reveal different deficiencies. Application to tennis: retain paired Brier and log loss and calibration once forward outcomes qualify; no direct tennis benchmark.
- Kleen (2024), https://doi.org/10.1002/jae.3056; open access economic forecast theory/simulations; observation error can distort score rankings. Do not treat candidate joins as validated labels.
- Loveday et al. (2024), https://doi.org/10.1175/WAF-D-23-0201.1; binary forecast threshold-sensitive evaluation on weather data. No code imported, no comparative tennis accuracy claim.

## Evidence tier and negative results
Main's historical **non-production WTA Web Shadow**: 85 scored, 46 correct (54.12%), Brier 0.251461, log loss 0.696908. Independent forward challenger N not refreshed; previous aggregate N=0. No qualified settlement added, no model ablation executed, no accuracy gain, no global round map changed. PR #428 remains the acquisition blocker pending review. Static source assertions are not end-to-end CI, and do not verify the official meaning of RoundID.

## Priority queue
1. Independently corroborate WTA RoundID with event-specific official draw and round records; build a fail-closed fixture covering numeric and legacy IDs, negative wrong-round and duplicate-pair cases.
2. Audit the two prohibited schedule-source records and original feature manifests; reject tainted observations.
3. Verify three full-name variants using stable official player IDs and original pre-start locks.
4. Review PR #428 and unblock acquisition without bypassing gates; verify PR #430 blocked-receipt workflow end-to-end.
5. Accumulate new locked, qualified prospective outcomes and run paired champion/challenger Brier, log loss, calibration and coverage tests on chronological samples.
