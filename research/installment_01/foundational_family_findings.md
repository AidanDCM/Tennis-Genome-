# Foundational Family Laboratory — Accepted Findings

Status: **accepted aggregate result; recent-block diagnostic pending for final A-grade confirmation**

Accepted workflow run: `34415444292`

Accepted source/code head: `05aeb1a6e9efdf753109e9e424aa83fedff4a309`

Accepted artifact: `tennis-genome-research-baselines`

Artifact digest: `sha256:54d9e469f13b28c98bcc04d5d7fb7cb306b1005abde9012fbdc84f1c8c8cfda7`

Research source: pinned `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`, 2000–2025, CC BY-NC-SA 4.0 research-only.

These findings apply only to the registered representations and source quality tested. They are predictive findings, not causal claims and not profitability results.

---

## Core benchmark entering the laboratory

The common benchmark is chronologically recalibrated overall Elo plus the EXP-003 opponent-adjusted serve/return matchup edge.

### ATP
- N: 71,832
- core Brier: 0.208790
- core log loss: 0.603402
- core accuracy: 66.267%
- full foundational model Brier: 0.204714
- full foundational model log loss: 0.594213
- full foundational model accuracy: 67.633%
- full-vs-core Brier improvement: **+0.004076**
- full-vs-core log-loss improvement: **+0.009189**
- accuracy change: **+1.366 percentage points**

### WTA
- N: 66,224
- core Brier: 0.210685
- core log loss: 0.608530
- core accuracy: 66.719%
- full foundational model Brier: 0.205079
- full foundational model log loss: 0.595619
- full foundational model accuracy: 67.685%
- full-vs-core Brier improvement: **+0.005606**
- full-vs-core log-loss improvement: **+0.012911**
- accuracy change: **+0.966 percentage points**

The combined foundational families therefore add substantial probability signal beyond the validated Elo + serve/return core on both tours. This does not imply that every individual family should survive production promotion.

---

## Family grades — ATP

### Recent form — provisional A / Core candidate
- add-one Δ Brier: **+0.000190**
- add-one Δ log loss: **+0.000461**
- Brier improved in 20/25 seasons
- log loss improved in 20/25 seasons
- full-model ablation Brier contribution: **+0.000145**
- full-model ablation log-loss contribution: **+0.000377**

Interpretation: small but unusually stable incremental signal. It survives both add-one and remove-one tests. Final A promotion is contingent only on the preregistered recent multi-season collapse check.

### Workload / rest proxy — provisional A / Core candidate
- add-one Δ Brier: **+0.002745**
- add-one Δ log loss: **+0.005724**
- Brier improved in 25/25 seasons
- log loss improved in 25/25 seasons
- full-model ablation Brier contribution: **+0.001923**
- full-model ablation log-loss contribution: **+0.004099**

Interpretation: strongest newly tested ATP family by a large margin. Despite coarse event-date timing, the proxy contains large, unique, stable information. This strongly justifies acquiring true match timestamps and exact recovery/load data. Final A promotion is contingent only on the recent-block check.

### Age / career / physical — provisional A / Core candidate
- add-one Δ Brier: **+0.001322**
- add-one Δ log loss: **+0.002721**
- Brier improved in 25/25 seasons
- log loss improved in 24/25 seasons
- full-model ablation Brier contribution: **+0.000488**
- full-model ablation log-loss contribution: **+0.000911**

Interpretation: stable signal beyond Elo and serve/return, with some redundancy once workload/context are present. Final A promotion is contingent only on the recent-block check.

### Age × fatigue interaction — B / Conditional or redundant
- add-one Δ Brier: **+0.001072**
- add-one Δ log loss: **+0.002319**
- Brier improved in 24/25 seasons
- log loss improved in 24/25 seasons
- full-model ablation Brier contribution: **-0.000059**
- full-model ablation log-loss contribution: **-0.000150**

Interpretation: strong standalone interaction signal, but it adds no unique information once the age and workload families are simultaneously present. Preserve the hypothesis, but do not add a separately weighted production family in Core v1. Future exact-timestamp fatigue research should revisit it.

### Head-to-head — B / Low-weight candidate
- add-one Δ Brier: **+0.000087**
- add-one Δ log loss: **+0.000213**
- Brier improved in 18/25 seasons
- log loss improved in 19/25 seasons
- full-model ablation Brier contribution: **+0.000114**
- full-model ablation log-loss contribution: **+0.000238**

Interpretation: H2H is not zero, but the incremental effect is tiny. It survives ablation and barely clears the preregistered rough stability threshold. Treat as low-weight/conditional rather than a major core driver.

### Handedness / basic matchup — D / Rejected under current representation
- add-one Δ Brier: **-0.000036**
- add-one Δ log loss: **-0.000091**
- Brier improved in only 7/25 seasons
- log loss improved in only 8/25 seasons
- full-model ablation Brier contribution: **-0.000062**
- full-model ablation log-loss contribution: **-0.000154**

Interpretation: the registered left/right and opposite-hand × serve/return representation does not improve future prediction. This does **not** reject richer style geometry, serve direction, return position, spin, backhand, or rally-pattern matchup effects.

### Surface / tournament context — provisional A / Core candidate
- add-one Δ Brier: **+0.000320**
- add-one Δ log loss: **+0.001209**
- Brier improved in 19/25 seasons
- log loss improved in 21/25 seasons
- full-model ablation Brier contribution: **+0.000414**
- full-model ablation log-loss contribution: **+0.001462**

Interpretation: pure independent Surface Elo failed in EXP-002, but conditional context around validated strength signals is useful. Context should therefore enter as interactions/modifiers rather than as a replacement rating. Final A promotion is contingent only on the recent-block check.

---

## Family grades — WTA

### Recent form — provisional A / Core candidate
- add-one Δ Brier: **+0.001163**
- add-one Δ log loss: **+0.002783**
- Brier improved in 25/25 seasons
- log loss improved in 25/25 seasons
- full-model ablation Brier contribution: **+0.000641**
- full-model ablation log-loss contribution: **+0.001492**

Interpretation: materially stronger than ATP recent form and stable in every evaluated season. Final A promotion is contingent only on the recent-block check.

### Workload / rest proxy — provisional A / Core candidate
- add-one Δ Brier: **+0.003279**
- add-one Δ log loss: **+0.007503**
- Brier improved in 24/25 seasons
- log loss improved in 24/25 seasons
- full-model ablation Brier contribution: **+0.001430**
- full-model ablation log-loss contribution: **+0.003312**

Interpretation: strongest newly tested WTA family. As with ATP, this is compelling evidence that higher-resolution workload/rest data is worth acquiring. Final A promotion is contingent only on the recent-block check.

### Age / career / physical — provisional A / Core candidate
- add-one Δ Brier: **+0.001950**
- add-one Δ log loss: **+0.004608**
- Brier improved in 19/25 seasons
- log loss improved in 19/25 seasons
- full-model ablation Brier contribution: **+0.000854**
- full-model ablation log-loss contribution: **+0.002213**

Interpretation: significant unique probability signal, though more era-variable than ATP. Final A promotion is contingent on the recent-block check.

### Age × fatigue interaction — B / Conditional or redundant
- add-one Δ Brier: **+0.001666**
- add-one Δ log loss: **+0.003959**
- Brier improved in 24/25 seasons
- log loss improved in 24/25 seasons
- full-model ablation Brier contribution: **-0.000007**
- full-model ablation log-loss contribution: **-0.000020**

Interpretation: the interaction is strongly predictive by itself but is essentially fully absorbed by age and workload in the full model. Preserve as a research interaction rather than a separate Core v1 family.

### Head-to-head — C / Experimental
- add-one Δ Brier: **+0.000023**
- add-one Δ log loss: **-0.000052**
- Brier improved in 18/25 seasons
- log loss improved in 16/25 seasons
- full-model ablation Brier contribution: **+0.000113**
- full-model ablation log-loss contribution: **+0.000181**

Interpretation: mixed add-one signs and extremely small magnitude. The full model appears to use some H2H information, but the registered family is too weak/mixed for production promotion.

### Handedness / basic matchup — D / Rejected under current representation
- add-one Δ Brier: **-0.000013**
- add-one Δ log loss: **-0.000048**
- Brier improved in 12/25 seasons
- log loss improved in 14/25 seasons
- full-model ablation Brier contribution: **-0.000023**
- full-model ablation log-loss contribution: **-0.000076**

Interpretation: no reliable future predictive value under the registered basic representation. Rich style/tracking remains untested.

### Surface / tournament context — provisional A / Core candidate
- add-one Δ Brier: **+0.000506**
- add-one Δ log loss: **+0.000895**
- Brier improved in 19/25 seasons
- log loss improved in 19/25 seasons
- full-model ablation Brier contribution: **+0.000477**
- full-model ablation log-loss contribution: **+0.001099**

Interpretation: conditional surface/tournament context is useful even though pure Surface Elo is not. Final A promotion is contingent only on the recent-block check.

---

## Serve / return decomposition

EXP-003's combined opponent-adjusted serve/return result remains the governing production finding. The decomposition is diagnostic.

### ATP
Relative to Elo-only:
- serve alone Δ Brier: **+0.000381**; Δ log loss: **+0.000916**
- return alone Δ Brier: **+0.000064**; Δ log loss: **+0.000129**
- serve + return Δ Brier: **+0.001577**; Δ log loss: **+0.003652**

The combined gain is much larger than either component alone, supporting a matchup interaction/synergy interpretation rather than independent additive ratings only.

### WTA
Relative to Elo-only:
- serve alone Δ Brier: **+0.000053**; Δ log loss: **+0.000014**
- return alone Δ Brier: **+0.000069**; Δ log loss: **+0.000099**
- serve + return Δ Brier: **+0.000214**; Δ log loss: **+0.000296**

Again, the combination is more useful than either isolated component, but the total WTA effect remains much weaker than ATP and retains its prior B / conditional classification.

---

## Current promotion map before recent-block diagnostic

### ATP
- A provisional: Overall Elo; opponent-adjusted Serve/Return; Recent Form; Workload/Rest Proxy; Age/Career/Physical; Surface/Tournament Context
- B: Age × Fatigue interaction; Head-to-Head
- D: Basic Handedness/Matchup
- previously rejected representation: pure independent Surface Elo

### WTA
- A provisional: Overall Elo; Recent Form; Workload/Rest Proxy; Age/Career/Physical; Surface/Tournament Context
- B: opponent-adjusted Serve/Return; Age × Fatigue interaction
- C: Head-to-Head
- D: Basic Handedness/Matchup
- previously rejected representation: pure independent Surface Elo

No final A promotion is recorded until the preregistered recent multi-season collapse check is made explicit. No B/C/D classification will be upgraded based on that post-result diagnostic.
