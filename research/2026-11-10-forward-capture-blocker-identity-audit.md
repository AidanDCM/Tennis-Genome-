# Iteration 24 — prospective settlement capture blocker and identity audit (2026-11-10 16:39 UTC)

**Read-only operational research.** No prediction, settlement, champion, or production changes. PR #429 research branch prior head `576bde513e0c8f8cdc369b14b963609c00b48430`; main as seen by forward workflow `8af76720a6291b166263fa1cd8191504f84ed6b6`. Open PR #428 head `e676c961d674ffd32d254bb96f738ae7242e211f`.

## Reproducible evidence and executed checks

Fetched official source snapshot on unmerged PR #428: `web-shadow/result-evidence/wta-results-20261109t083951z/sources/hong-kong-matches.json`, Git blob `9b1e1ab74b88c59f67692e66472ef814c9970d60`, provider bytes SHA256 `22e85823b9e098b08054fc3e2b4c14f705bbe163093c2018804567b6046a6d12`, source observed in acquisition at 2026-11-09T08:39:51Z. Intake manifest blob `7343dc4662cf9e0b35196592917d7468eb71a9aa`. Parsed source JSON and joined *only for diagnostic* on exact MatchID. For each conflict, counted source rows and compared both full-name participants (set equality), never inferring a settlement from match ID.

- `web:wta:1074:2026:LS031`: exactly one provider row; locked predicted Alycia Parks / Alexandra Eala; source Emerson Jones (provider ID 333111) / Alexandra Eala (330332); 1 of 2 names overlaps; source LastUpdated 2026-11-03T13:07:15.363Z. **Reject identity match**.
- `web:wta:1074:2026:LS020`: exactly one provider row; locked predicted Sofia Kenin / Leylah Fernandez; source Mika Stojsavljevic (333132) / Sofia Kenin (320942); 1 of 2 names overlaps; source LastUpdated 2026-11-04T08:29:19.707Z. **Reject identity match**.

Partition invariant executed on actual intake JSON: 16 pending = 1 captured result + 2 identity conflicts + 13 unresolved + 0 unfinished. Equality **PASS**; conflicts 2/16=12.5%; unresolved 13/16=81.25%; only 1/16=6.25% captured in this *unmerged* snapshot. These are capture-process diagnostics, **not winner-model accuracy**. Never retrospectively substitute the provider players for locked participants.

## Newly confirmed P0 blocker

Latest WTA Web Shadow Result Acquisition run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42798727961 (2026-11-10 10:23 UTC) succeeded as a job but explicitly logged **"A result proposal is already open; leaving it immutable."** The workflow exits before fresh acquisition because PR #428 remains open. Thus CI green does **not** mean result capture fresh. A reviewer must decide PR #428's disposition; do not merge automatically because it would modify active-results. Preferred safe future change: on an isolated branch, make an audit-only freshness/blocked-state receipt visible without mutating immutable proposal or relaxing provenance. Do not delete evidence.

Forward Validation Aggregate https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42839698243 (2026-11-10 14:59 UTC) logged `NO_SETTLED_FORWARD_OBSERVATIONS`, `population_match_count: 0`, `model_count: 0`. This is independently confirmed current **qualified forward N=0**, not the 85 scored non-production WTA Web Shadow matches. Main active-results manifest blob `52d8645a3389c9b2d8ba5a6c87e520e23ab80a25` still selects Hong Kong LS001; unmerged Chennai proposal is not incorporated. Main Web Shadow scorecard blob `60082a6292087e2b6e902faca79f2f4c847d8fdb`: 85 scored, 46 correct, Brier 0.2514610585, log loss 0.6969082733, production_eligible=false. No model promotion.

Research PR #429 exact head `576bde513e0c8f8cdc369b14b963609c00b48430` CI run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42847670781 successful; prior standalone 15-date experiment run https://github.com/AidanDCM/Tennis-Genome-/actions/runs/42836673187 successful, retrospective sign-flip fractions ~0.21 (fixed Brier) / ~0.22 (fixed log), insufficient evidence for superiority.

## External research and contrary evidence

Krall et al., 2025, https://doi.org/10.52383/itfcoaching.v32i94.559: 2,956 junior matches, four tournament divisions, comparisons with UTR and prior WTN; revised WTN not consistently better. Not directly transferable to professional WTA, no implementation/license verified. Adapt: treat simplicity and independent paired baselines seriously.

Live Tennis API academic data page (2026), https://livetennisapi.com/data/academic: explicitly distinguishes live-observed point sequences with timestamps from reconstructed post-match point sequences without capture timestamps; non-commercial access terms, not adopted. Adapt the provenance distinction: *observed before start* versus post-hoc reconstructed must never be conflated. Coverage and licensing require separate review.

## Reproduction

Use connected GitHub fetch_file on the two files above at ref `automation/wta-web-shadow-results-wta-results-20261109t083951z`; JSON parse; for conflicts select rows where `MatchID == match_id.split(':')[-1]`; compare ordered-independent full participant sets; assert `pending_prediction_count == result_count + identity_conflict_count + unresolved_prediction_count + unfinished_prediction_count`. Inspect exact job logs 129770464462 and 129911310667. Do not use future outcome rows to generate pre-start features.

## Prioritized queue

P0 reviewer adjudicate immutable result PR #428; add a **non-mutating** blocked-acquisition/freshness receipt and explicit alert if existing proposal prevents new source capture, then test against a synthetic open-PR fixture. P1 investigate why 13 pending cannot be matched without relaxing identity, timing, or source-byte trust gates. P2 obtain fresh locked champion/challenger pairs, strictly forward settle, report N, Wilson CI, Brier/log loss, surface/time coverage, missingness and drift; maintain untouched holdout. P3 fixed 0.5 calibration only on future prospective pairs; no promotion from reused 55-observation historical sample.

**Negative result:** Neither LS031 nor LS020 is safe to settle from match ID; zero new qualified forward observations. No CI/test suite newly run in this iteration; executed JSON invariant and exact-identity comparisons against fetched raw provider bytes, and inspected two actual workflow logs.
