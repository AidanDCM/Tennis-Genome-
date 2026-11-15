# Hong Kong identity-conflict longitudinal audit — 2026-11-12

**Status:** read-only, non-production; no settlement authorization. **Base commit:** 8af76720a6291b166263fa1cd8191504f84ed6b6.

## Prespecified hypothesis
Across retained official WTA intake snapshots, the locked pairs for LS031 and LS020 become exact matches by November 8. Baseline: immutable locked prediction pairs. Success: both exact unordered pairs on latest snapshot; failure: any mismatched pair. Use three chronologically spaced, already-retained manifests; no retrospective remapping.

## Reproducible evidence
Read each JSON at `web-shadow/result-evidence/wta-results-<timestamp>/result-intake-manifest.json` at base SHA above. Compare `set(predicted_players)==set(source_players)` for each conflict; count intersections and compare immutable prediction hashes and source hashes. Commands: `git show 8af76720a6291b166263fa1cd8191504f84ed6b6:web-shadow/result-evidence/wta-results-20261108t104527z/result-intake-manifest.json` (repeat for the other timestamps). No code dependencies.

| Snapshot UTC | Manifest blob | Conflict IDs | Pending | Unresolved |
|---|---|---|---:|---:|
| 20261103t171052z | `beb30215808c62e882b61d407a4315a3e9533b8d` | LS031 | 19 | 13 |
| 20261104t221217z | `dc34636d2fe2571c3d3dfe1fb2a111a0d46976cb` | LS031, LS020 | 16 | 13 |
| 20261108t104527z | `8635063873e8b341ac7c67ce38e4fdecde0e4d2b` | LS031, LS020 | 17 | 13 |

### 20261103t171052z
- web:wta:1074:2026:LS031: locked `Alycia Parks / Alexandra Eala`; provider `Emerson Jones / Alexandra Eala`; overlap 1/2; locked SHA `31f68ecdcf09809eea97b95b257c1a7d671ab63e6ef1a016bfacd770d51c69cb`; source SHA `8d2fba9af76ea570fbdb3b0dd3e6b5b362554e37e980ce0d30231e051e516b41`.

### 20261104t221217z
- web:wta:1074:2026:LS031: locked `Alycia Parks / Alexandra Eala`; provider `Emerson Jones / Alexandra Eala`; overlap 1/2; locked SHA `31f68ecdcf09809eea97b95b257c1a7d671ab63e6ef1a016bfacd770d51c69cb`; source SHA `84fe61cf5e1a634891a69625c2df9041f86356c8769abffe41beccd9a1dbc568`.
- web:wta:1074:2026:LS020: locked `Sofia Kenin / Leylah Fernandez`; provider `Mika Stojsavljevic / Sofia Kenin`; overlap 1/2; locked SHA `acafa5294de9f230cb7ab656a04ea54074501295be52a0b15e5a22b7e1017800`; source SHA `84fe61cf5e1a634891a69625c2df9041f86356c8769abffe41beccd9a1dbc568`.

### 20261108t104527z
- web:wta:1074:2026:LS031: locked `Alycia Parks / Alexandra Eala`; provider `Emerson Jones / Alexandra Eala`; overlap 1/2; locked SHA `31f68ecdcf09809eea97b95b257c1a7d671ab63e6ef1a016bfacd770d51c69cb`; source SHA `8355ca3b614f82e6b8fe1248af00a386d553ad333d3158b464f593982f4a45fc`.
- web:wta:1074:2026:LS020: locked `Sofia Kenin / Leylah Fernandez`; provider `Mika Stojsavljevic / Sofia Kenin`; overlap 1/2; locked SHA `acafa5294de9f230cb7ab656a04ea54074501295be52a0b15e5a22b7e1017800`; source SHA `8355ca3b614f82e6b8fe1248af00a386d553ad333d3158b464f593982f4a45fc`.

## Observed result
Hypothesis **rejected**. LS031 persists in all three snapshots; LS020 persists in both later snapshots. Each recorded conflict shares exactly one of two players, not both. Unresolved count remains 13 across these snapshots. Provider source digests differ across dates, but this alone cannot establish fixture replacement versus ID reuse. No attempt was made to relabel, backfill or settle either conflict. No new qualified observation.

## Literature and contrary evidence
- Bunker et al. (first online 2023-11-10), DOI https://doi.org/10.1177/17543371231212235 — chronological ATP evaluation (14 annual test periods); some studied features are excluded from Tennis Genome. Direct transfer is invalid without matching populations and input availability. Implementation license not verified.
- Clegg & Cartlidge (2025), https://research-information.bris.ac.uk/en/publications/tennis-match-outcome-prediction-using-temporal-directed-graph-neu/ — temporal surface-specific graph models comparable to weighted Elo on their out-of-sample ATP population; no established WTA prospective advantage, license/reproduction not verified. Prefer simpler Elo first.

## Next executable queue
1. Inspect original retained provider raw match rows and stable participant IDs for LS031/LS020 across timestamps; establish whether provider match IDs changed identity, without relaxing gates.
2. Emit a deterministic non-sensitive Chennai settlement summary in isolated CI; inspect bytes and source/settlement hashes before human review.
3. Restore prospective capture and verify qualified production-forward N and immutable champion SHA.
4. Only on newly locked chronological pairs compare frozen champion with 0.5 and Elo by paired Brier/log loss and calibration; keep final holdout untouched.

No model tuning, prediction changes, settlement publication, or champion promotion.
