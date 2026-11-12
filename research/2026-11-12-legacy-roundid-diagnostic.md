# Legacy WTA RoundID diagnostic — 2026-11-12

## Prespecified hypothesis
For the current compiler, a legacy (no exact official MatchID) prediction cannot match a main-draw official row with textual RoundID Q, S, or F, even when tournament, player pair and round would otherwise agree. Baseline: numeric RoundID 3/2/1. Success criterion: all three textual cases yield no identity in legacy mode while numeric controls resolve; exact-ID textual controls remain supported. This is an operational static-code audit, **not** a model-performance improvement or a claim that any pending fixture is affected.

## Pinned evidence
- Main commit: [40bb697ec786](https://github.com/AidanDCM/Tennis-Genome-/commit/40bb697ec786527b7ed1a4c67d6d0a92aea17782)
- [Compiler](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/scripts/web_shadow_wta_result_core.py), blob e4785a6d0b9b07c4fd4a52d2b44927211e5f7172. _match_row uses strict_round=False for legacy predictions. _row_identity returns None on nonnumeric RoundID in this mode, while exact-ID mode recognizes Q/S/F.
- [Scorecard](https://github.com/AidanDCM/Tennis-Genome-/blob/40bb697ec786527b7ed1a4c67d6d0a92aea17782/web-shadow/scorecard.json), blob c9636ac9d86c256ccf241e652b9456034c451fc3: non-production, 86 completed scored, 47 correct, Brier 0.2513224181, log loss 0.6966212009, 15 pending.
- [Official acquisition run](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286), artifact [13967128659](https://github.com/AidanDCM/Tennis-Genome-/actions/runs/43270738286/artifacts/13967128659). Previous verified audit: 745 rows, 13 unresolved legacy joins and two exact-ID identity conflicts. **This run did not download or inspect the artifact rows.**

## Executed reproducible static branch test
Read the current compiler from connected GitHub. Asserted the strict textual alias branch and legacy nonnumeric return were both present. Evaluated nine branch cases with this JS command (equivalent to the current _row_identity RoundID control flow):
```js
const numeric={1:'F',2:'SF',3:'QF',4:'R16',5:'R32',6:'R64',7:'R128'};
const aliases={Q:'QF',S:'SF',F:'F'};
function round(id,strict){if(strict&&Object.hasOwn(aliases,id))return aliases[id];const n=Number(id);return Number.isInteger(n)?numeric[n]??null:null;}
for(const [id,strict,expected] of [['Q',false,null],['S',false,null],['F',false,null],[3,false,'QF'],[2,false,'SF'],[1,false,'F'],['Q',true,'QF'],['S',true,'SF'],['F',true,'F']]){if(round(id,strict)!==expected)throw Error('round mapping failed');}
```
Result: **9/9 expected cases passed**. This is a JS mirror of the inspected Python branch, **not a Python unit test or exact-head CI**. No historical settlement or match eligibility was changed.

## Interpretation and negative evidence
The legacy parser silently drops textual Q/S/F main-draw rows before player/round comparison. This is a potential false-negative mechanism, but **zero of the 13 pending cases have yet been attributed to it**. A change to automatically accept textual rounds in legacy joins would alter eligibility and must not be made without independent fixture-level evidence and human review. The safer next experiment is a diagnostic-only counterfactual count with no result writes.

## External methodological comparison
- Xu et al. (2024), [variable selection with missing data for record linkage](https://doi.org/10.1177/09622802241242317): simulations plus one non-tennis application; noisy matching fields can worsen linkage. License for implementation not verified; no code imported.
- Kamat and Gutman (2024), [Analysis of Linked Files: A Missing Data Perspective](https://arxiv.org/abs/2406.14717): survey and simulation of linkage errors and resulting inferential bias; supports retaining unmatched predictions in coverage accounting, not imputing results. Code license not verified.

## Prioritized executable queue
1. Download and verify artifact 13967128659; for each of 13 pending legacy IDs, compare event/player pair/round under existing rules versus a **read-only** textual RoundID diagnostic, with raw source-row identifiers and zero settlement writes.
2. Add a diagnostic-only reason enum and fixture-level regression tests; require exact-head CI, human review and immutable trust gates.
3. Exercise blocked/failed/skipped/empty gate states in isolated CI; inspect job logs.
4. On genuinely new locked prospective cohorts, evaluate paired frozen champion and simpler baseline with Brier, log loss, calibration, Wilson accuracy intervals and chronological coverage. Preserve final holdout.

No model promotion, prediction mutation, settlement, or trust-gate weakening.
