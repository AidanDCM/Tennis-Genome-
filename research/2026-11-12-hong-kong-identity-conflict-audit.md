# Hong Kong identity-conflict audit — 2026-11-12 UTC

## Prespecified hypothesis and outcome
Hypothesis: either of the two excluded Hong Kong prediction IDs in acquisition PR #428 has an exact unordered player-pair match with the retained WTA source row. Success: 2/2 exact pair matches; failure: any mismatch. **Observed: 0/2 exact matches; hypothesis rejected.** Both have only one of two names overlapping. These are exclusions, NOT settlements.

| Match ID | Locked predicted pair | Provider pair | Overlap | Exact |
|---|---|---|---:|---|
| web:wta:1074:2026:LS031 | Alycia Parks / Alexandra Eala | Emerson Jones / Alexandra Eala | 1/2 | No |
| web:wta:1074:2026:LS020 | Sofia Kenin / Leylah Fernandez | Mika Stojsavljevic / Sofia Kenin | 1/2 | No |

Source: https://github.com/AidanDCM/Tennis-Genome-/pull/428 (head e676c961d674ffd32d254bb96f738ae7242e211f); source matches SHA-256 22e85823b9e098b08054fc3e2b4c14f705bbe163093c2018804567b6046a6d12; prediction record SHA-256 LS031 31f68ecdcf09809eea97b95b257c1a7d671ab63e6ef1a016bfacd770d51c69cb, LS020 acafa5294de9f230cb7ab656a04ea54074501295be52a0b15e5a22b7e1017800. Main scorecard blob 60082a6292087e2b6e902faca79f2f4c847d8fdb.

## Reproduction
Fetch PR #428 diff via GitHub, locate the JSON identity_conflicts array in the added acquisition report, remove unified-diff leading plus signs, parse JSON, then for each conflict compare sorted predicted_players with sorted source_players and count intersection. This run executed that exact JS comparison using the connected GitHub PR diff. Result: N=2, exact=0, one-name overlap=2. No backfill or permissive name matching.

## Operational evidence
At inspection PR #428 open and unmerged; main web-shadow/active-results.json still points to the Hong Kong result, not the proposed Chennai result. Main intake config restricts selection to Guangzhou (1023), Tokyo (1056), Hong Kong (1074), Chennai (1148), 8–48 hour lead window and maximum 8 per slate. PR #428 reports 16 pending: 1 captured, 13 unresolved, 2 identity conflicts. This snapshot does not prove current capture health or a production-forward qualified N. Non-production WTA scorecard: 46/85 accuracy, Brier 0.251461, log loss 0.696908, pending 16; not production evidence. No champion alteration.

## Research and contrary evidence
Bunker et al., first online 2023-11-10, published 2024, https://doi.org/10.1177/17543371231212235 : expanding yearly ATP evaluation 2007–2020. Some model comparisons rely on features disallowed in this project; **do not import those features**. The paper explicitly cautions that unusually high random-split accuracies may indicate future-to-past leakage. Adapt chronological split discipline and simple Elo comparisons only; ATP population and feature availability differ. Implementation license and dataset reproduction not verified. No external code copied.

## Negative findings and next executable queue
1. Preserve both Hong Kong exclusions; inspect retained raw row IDs, participant identifiers, schedule revisions and frozen slate provenance to determine whether provider match IDs were reused or fixtures changed. Never remap by partial-name overlap.
2. Emit deterministic read-only settlement diagnostics in isolated CI for Chennai proposal, with canonical-file hash comparison.
3. Verify current CI, immutable champion and qualified production-forward evidence; restore acquisition coverage under existing identity/prestart gates.
4. Only then preregister paired chronological champion vs Elo/fixed-50% Brier/log-loss comparison; untouched holdout, no tuning on shadow evaluation.

No model ablation or predictive performance improvement claimed. No merges or production mutations.
