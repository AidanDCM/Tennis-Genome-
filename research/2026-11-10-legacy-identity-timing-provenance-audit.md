# Iteration 34 — legacy WTA identity, timing, and provenance audit (2026-11-10)

## Frozen question and baseline
Hypothesis: the 12 unique surname-pair candidates from iteration 33 do **not** all satisfy strict exact-full-name, schedule-timing and permitted-source gates. Baseline: 12/13 surname matches, no qualified settlements. Population: all 13 pending legacy IDs (9 Seoul, 4 Singapore), fixed before comparison. Success: identify at least one additional exclusion without modifying immutable predictions or settling matches.

## Sources and reproducibility
Main scorecard `web-shadow/scorecard.json` blob SHA `60082a6292087e2b6e902faca79f2f4c847d8fdb`; each `prediction_path` from scorecard `slates[].predictions[]` with `status=PENDING`. Retained provider files on PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f`: `web-shadow/result-evidence/wta-results-20261109t083951z/sources/seoul-matches.json` blob `bcc4cc0dc4216d749c4cea78cb915a68a0fb4063` and Singapore counterpart blob `2d5c6a7248175c2a4be68c33fb32be59fc5c95d1`.

Executed GitHub connector reads and deterministic JavaScript: select the 13 pending IDs; fetch immutable prediction JSON by its scorecard path; in each tournament's provider main-draw singles rows, select unordered exact surname pair; compare unordered exact Unicode NFKD accent-stripped full names; check `committed_at < MatchTimeStamp` and `scheduled_start < MatchTimeStamp` separately; classify disallowed market-derived `fixture.schedule_source_url` by domain. No outcome records changed.

## Observed checks (read-only, 13 predictions)
- 12/13 unique surname candidates; one missing participant pair (Anisimova/Gibson).
- Only **9/12** unique surname matches pass exact normalized full-name equality. Three variants require independent identity evidence: Elena Gabriela / Elena-Gabriela Ruse, Ye Xin / Ye-Xin Ma, Yeon Woo / Yeonwoo Ku. Do not silently normalize these variants into eligibility.
- All 12 candidate prediction `committed_at` timestamps precede the provider `MatchTimeStamp`; **this is not proof of pre-start locking**, since provider MatchTimeStamp semantics were not verified as start times.
- Only **8/12** candidate scheduled-start timestamps precede the provider `MatchTimeStamp`. Four fail that comparison: Sakatsume/Preston, Ruse/Lys, Zarazua/Bondar, Oliynykova/Wolff. This is a diagnostic inconsistency, **not proof** of late prediction or invalid fixture, because MatchTimeStamp may not represent match start.
- **2/13** prediction schedule-source URLs point to prohibited market-derived sources (Oliynykova/Wolff and Parks/Yamaguchi). Do not use those sources, do not copy their content, and exclude these observations from any compliant candidate pool pending independently verified non-market provenance. Their probability-feature input manifests were not independently inspected for market leakage.
- Provider `RoundID` is numeric 1 for 11 candidate R32 predictions and 2 for one R16 candidate, whereas current `scripts/web_shadow_wta_result_core.py` has `_ROUND_ID_MAP={1:'F',2:'SF',3:'QF',4:'R16',5:'R32',6:'R64',7:'R128'}`. The current map interprets provider rows differently from the legacy predictions. Do **not** change this map without a source-backed, event-specific round semantic validation; this is a strong candidate root cause for zero legacy joins.
- The original 12 surname matches are **not** 12 verified settlements; conservative confirmed qualified new N=0.

## Research context and contrary evidence
- Buhamra, Groll, Brunner (2024), https://doi.org/10.3233/JSA-240670 : ATP Grand Slam logistic/regularized/spline models, 2011–2022, 2022 rolling evaluation; CC BY-NC 4.0. Includes prohibited market-derived covariates in some comparisons, so do not copy those features. Strictly different tour and selection population.
- Unified Benchmark (2026), https://www.mdpi.com/2813-2203/5/3/22 : 133,138 ATP matches and chronological train/validation/test; complex models only modestly outperform Elo. License and raw-data provenance not verified. Its reported accuracy is not comparable to WTA Web Shadow.
- Counter-hypothesis: poor data coverage is not exclusively a legacy-ID problem; identity spellings, round semantics, and noncompliant schedule provenance independently block trustworthy joins.

## Current evidence and prioritized queue
Main non-production WTA Web Shadow historical: 85 scored, 46 correct (54.12%), Brier 0.251461, log loss 0.696908. Last independently verified forward aggregate N=0, not refreshed here. PR #428 still open, blocks acquisition; PR #430 diagnostic unmerged; no champion changes.
1. Independently verify provider RoundID semantics from official draw positions; test round mapping with an explicit fail-closed regression fixture, not a global replacement.
2. Audit original pre-start source observation, actual match start and prediction input manifests for market-derived leakage. Reject contaminated observations.
3. Resolve three full-name variants using stable official player IDs, not permissive string heuristics.
4. Review PR #428 safely to restore acquisition, preserve immutable evidence and excluded identities.
5. Resume locked prospective champion–challenger Brier/log-loss evaluation after qualified N increases.

Negative result: strict full-name equality rejects 3 of 12 candidates; schedule-source policy rejects 2 of 13. No scoring improvement, settlements, or production changes.
