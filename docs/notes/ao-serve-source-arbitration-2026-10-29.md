# Australian Open serve-stat source arbitration, 2026-10-29

**Decision:** The retained Sportradar 2026 Australian Open first/second-serve splits are not qualified for mixing into pinned Tennis Genome history. This is a small retrospective source-quality check, not a new prediction, a representative error-rate estimate, or a claim about every Sportradar tournament.

## Fixed diagnostic sample and provenance

We compared five Australian Open men's singles matches across three independently stored records: the Australian Open's public match-centre JSON, the pinned ATP 2026 match CSV, and the retained Sportradar season-summary pages. The match IDs `MS101`, `MS102`, `MS119`, `MS219`, `MS301` were fixed before fetching Australian Open JSON. `MS219` was already known to have a large disagreement, so this is deliberately a **diagnostic**, not a random sample. The five joins used the same two normalized player names within the Australian Open tournament; every joined source had a full-match stat line.

The pinned CSV SHA-256 was `ceb157ae698f79f4148f7bb6253bbcf6a8c8eb9ff94670dd83aa0428802cfd59`. The retained Sportradar pages for `sr:season:128143` had SHA-256 `5396f0524dd825a9d400eac16d9c0535f221a501e2804f88e187fbe46ab6f00b` (offset 0) and `9b459fd34b7393feb08fe4377f4d810d93c13c1c03430cc5eada6b6692382b86` (offset 200). Australian Open pages were retrieved from its public match-centre endpoint at 2026-10-29 17:36 UTC. Exact JSON and the comparison report are retained locally under `outputs/sportradar-check-2026-10-29/ao-official-fixed-sample/`; this note contains hashes rather than redistributing raw match data.

| AO match | AO match page | AO JSON SHA-256 | Sportradar event |
| --- | --- | --- | --- |
| MS101 | [Alcaraz–Walton](https://ausopen.com/match/2026-carlos-alcaraz-vs-adam-walton-ms101) | `796af922c683d3af64b07fccb6b97269957a7023a8a2789309e6be406c7335c8` | `sr:sport_event:67817218` |
| MS102 | [Hanfmann–Svajda](https://ausopen.com/match/2026-yannick-hanfmann-vs-zachary-svajda-ms102) | `f9910563c2326c3d2d48916814a58973e41c545b2fd21b51b7c48d9f1ac6488c` | `sr:sport_event:67832202` |
| MS119 | [Nava–Jacquet](https://ausopen.com/match/2026-emilio-nava-vs-kyrian-jacquet-ms119) | `9b4eb0e19e7247f90cd52cb01d2544370228b3972731ef0ce5c6c7a06a5c9973` | `sr:sport_event:67817192` |
| MS219 | [Gea–Wawrinka](https://ausopen.com/match/2026-arthur-gea-vs-stan-wawrinka-ms219) | `ec0030b441c81aab8b72d09e27527aeaaee172351f96be8ca87cbfced1610082` | `sr:sport_event:67664636` |
| MS301 | [Alcaraz–Moutet](https://ausopen.com/match/2026-carlos-alcaraz-vs-corentin-moutet-ms301) | `fcef6da3a01d56ff2b7d458562302bb26dacdaa64ea2544c4af74e0ddeb87f1c` | `sr:sport_event:67664608` |

## Comparison

For each of the ten player rows, we checked aces, double faults, service points, first serves in, first-serve points won, and second-serve points won. The pinned CSV agreed with the Australian Open on **60/60 field values**. Sportradar agreed on all aces, double faults and service-point denominators (**30/30**), but on only **1/10** rows for each of the three serve-split fields (**3/30**). Its aggregate serve wins can remain consistent while the first/second split changes, so the match-level point-conservation guard from PR #331 does not detect this issue.

| Match | AO/pinned first serves in | Sportradar first serves in |
| --- | --- | --- |
| MS101 Alcaraz; Walton | 56/83; 66/91 | 59/83; 68/91 |
| MS102 Hanfmann; Svajda | 73/125; 98/142 | 75/125; 102/142 |
| MS119 Nava; Jacquet | 112/159; 102/179 | 110/159; 103/179 |
| MS219 Gea; Wawrinka | 100/170; 109/176 | 121/170; 139/176 |
| MS301 Alcaraz; Moutet | 51/72; 57/93 | 51/72; 56/93 |

This triangulation supports the pinned Australian Open serve splits for these five matches and identifies a concrete Sportradar split-stat mismatch. It does not reveal whether the cause is collection, revision, or a field interpretation, and it does not prove the pinned source is correct elsewhere.

## Small WTA Rome contrast

Three retrospectively chosen Rome matches had visible match-stat lines on WTA's official pages: [Cirstea–Gauff semifinal](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS002), [Gauff–Andreeva quarterfinal](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS005), and [Gauff–Jovic round of 16](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS010). These were chosen for source availability, so they provide no representative error-rate estimate. We joined by normalized player pair and Rome tournament to the pinned WTA CSV and the retained Rome Sportradar page (SHA-256 `34c4c81711ce262eed3866767daa78d21691aef50f9bc688b236cd781d10598b`).

For the six player rows, WTA and pinned history agree on first serves in, first-serve points won and second-serve points won (**18/18 values**). Sportradar agrees on **17/18**: Mirra Andreeva's first serves in are **69/104** in Sportradar but **65/104** on the [WTA match page](https://www.wtatennis.com/tournaments/709/rome/2026/scores/LS005) and in pinned history. Her first- and second-serve points won agree across all three sources. The other five players' checked split fields agree. This is a field-level conflict in one small WTA sample, not grounds to accept the rest of the WTA feed without checks.

## Admission rule and next test

Keep Sportradar's first/second-serve splits for this Australian Open season **unapproved** for historical source replacement unless the exact event and fields are corroborated by tournament evidence. Do not repair them by arithmetic or silently substitute the pinned values into a purported Sportradar record. A source manifest should carry field-level provenance and a rejection reason. Before any large season capture, repeat the same limited triangulation on an ATP non-Grand-Slam event and expand the WTA check beyond three convenience matches. If official statistics are unavailable, retain the source conflict as unresolved and exclude the split fields from source admission. No frozen model definition, registered experiment, or prospective observation changes here.
