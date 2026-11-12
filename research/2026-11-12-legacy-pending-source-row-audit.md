# WTA legacy pending: retained-source row audit (2026-11-12)

**Status:** diagnostic only; non-production; no settlement, prediction, model, or trust-gate modification.

## Frozen evidence

- Main commit: `40bb697ec786527b7ed1a4c67d6d0a92aea17782`.
- Compiler: [web_shadow_wta_result_core.py](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/scripts/web_shadow_wta_result_core.py); prior blob `e4785a6d0b9b`.
- Scorecard: [scorecard.json](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json); blob `c9636ac9d86c256ccf241e652b9456034c451fc3`.
- Retained source: [Actions run 43270738286](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286), artifact 13967128659, ZIP SHA-256 `87c1a606aec15261b3a9295e767ff2e0add4db28a6ccc162d79ab9ad278ea2ce`. No live results were substituted.
- Raw main-draw singles: Seoul 31 of 58 raw rows; Singapore 26 of 53 raw rows. Main-draw round frequencies: Seoul 1=16, 2=8, Q=4, S=2, F=1; Singapore 1=12, 2=8, Q=4, S=1, F=1.

## Prespecified diagnostic hypothesis and comparator

H0: No more than 0 of the 13 legacy pending fixtures has an exact unordered player-name pair in the retained source when round is ignored. Comparator: current strict legacy round join. Failure of H0 requires at least one exact-pair match; an exact-pair match is **not** a verified eligible settlement. Match comparison is Unicode NFKD normalization, remove combining marks and non-alphanumeric characters, lowercase, unordered pair. Restrict source to DrawMatchType=S and DrawLevelType=M. Do not use result or winner information to change predictions.

## Executed results

12/13 legacy pending fixtures have **exactly one** source row with the same unordered player pair; every such row is marked finished (`MatchState=F`). The remaining fixture has no exact unordered pair in its tournament's retained main-draw singles source. All 12 exact-pair rows have source numeric `RoundID=1` (10 R32 predictions) or `RoundID=2` (2 R16 predictions), whereas current legacy compiler maps 1→F and 2→SF. Thus **all 12 fail the current round join**. The previous hypothesis that textual Q/S/F identifiers explain these 13 pending cases is **not supported** by this match-level test: none of the 12 exact pairs has Q/S/F.

| Prediction ID suffix | Source MatchID | Source RoundID | Locked round | Diagnostic |
|---|---|---|---|---|
| seoul:r32:sakatsume-preston | LS017 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:ruse-lys | LS027 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:montgomery-park | LS021 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:zarazua-bondar | LS024 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:ma-jones | LS030 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:ku-ibragimova | LS026 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:birrell-zidansek | LS031 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:zakharova-ostapenko | LS016 | 1 | R32 | exact pair; round mismatch |
| seoul:r32:kenin-charaeva | LS025 | 1 | R32 | exact pair; round mismatch |
| singapore:r32:oliynykova-wolff | LS022 | 1 | R32 | exact pair; round mismatch |
| singapore:r32:parks-yamaguchi | LS018 | 1 | R32 | exact pair; round mismatch |
| singapore:r16:sasnovich-andreeva | LS008 | 2 | R16 | exact pair; round mismatch |
| singapore:r16:anisimova-gibson | — | — | R16 | pair absent; no attribution |

**Correction to table summary:** The 12 matched cases comprise **11 R32 and 1 R16**, not 10 and 2. This table is the authoritative per-ID enumeration.

These matches remain unqualified. In particular, numeric round interpretation appears draw-dependent and must not be globally remapped on the basis of this sample. Official source identity, chronology, uniqueness, and original pre-start provenance still require review. The two exact-MatchID Hong Kong conflicts remain separate and blocked.

## Reproduction

Download the immutable Actions artifact and verify `sha256sum github-actions-artifact-13967128659.zip`. Parse `seoul-matches.json` and `singapore-matches.json` in the ZIP, filter `DrawMatchType == 'S' and DrawLevelType == 'M'`, compare normalized unordered player pairs from the 13 immutable prediction fixture JSONs listed in the main scorecard. For each pair report all MatchIDs, RoundIDs, MatchState; do not infer winner or settlement. Compare to `_ROUND_ID_MAP` in the pinned compiler. Python 3 stdlib `zipfile,json,unicodedata,re` suffices.

Actual run: `python /tmp/audit.py` printed 13 fixture diagnostics, with 12 unique pairs and one absent. ZIP digest verified independently. Repository clone attempt `git clone --depth 1 https://github.com/AidanDCM/Tennis-Genome-.git` failed due container DNS; connector read/write succeeded. No pytest, Ruff or CI executed.

## Research context

- Binette et al. (2024), [How to Evaluate Entity Resolution Systems](https://arxiv.org/abs/2404.05622): reusable entity-centric labeling and precision/recall diagnostics; not a tennis validation, code license not checked.
- Papadakis et al. (2024), [Critical Re-evaluation of Record Linkage Benchmarks](https://openresearch-repository.anu.edu.au/entities/publication/07b8afae-b60f-4b2b-93c0-179f5ca4d5c9): benchmark difficulty varies, so matching improvements need a separately labeled negative set. No external code imported.
- Contradiction: earlier static RoundID Q/S/F concern is real in code but is not the observed cause of the 12 recovered pairs.

## Operational risk and queue

A source provenance review also found that **some historical schedule_source_url fields point to disallowed market-related sources**. Do not use these fields as model inputs, cite or propagate those URLs, or assume the associated pre-start evidence is qualified. Audit these fixtures for independent, permitted, timestamped pre-start schedule evidence before any eligibility decision.

1. Review official source RoundID semantics by draw level and event, using independently labeled completed and non-completed rows; build a **diagnostic-only** regression test for numeric and textual rounds with negative controls.
2. Review the 12 potential pair matches' pre-start source provenance, unique event/round identity, and immutable timing; **do not** backfill outcomes automatically.
3. Investigate absent Singapore anisimova-gibson pairing with independent official evidence; leave pending if unsupported.
4. Validate failed/skipped/blocked acquisition-gate states in isolated CI; only then consider a separately reviewed safety-preserving change.
5. Accumulate new, genuinely qualified prospective locked predictions; compare frozen champion, Elo, and 0.5 baseline on identical chronological cohorts, report Brier, log loss, calibration and coverage. No holdout reuse or model promotion.
