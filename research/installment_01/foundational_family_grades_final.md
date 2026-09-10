# Foundational Metric Families — Final Grades

Status: **frozen before the sealed 2026 holdout is inspected**

This document supersedes the provisional promotion map in `foundational_family_findings.md`.

## Evidence provenance

Primary family laboratory:
- workflow run: `34415444292`
- code/source head: `05aeb1a6e9efdf753109e9e424aa83fedff4a309`
- artifact digest: `sha256:54d9e469f13b28c98bcc04d5d7fb7cb306b1005abde9012fbdc84f1c8c8cfda7`

Recent-block stability diagnostic:
- workflow run: `34421729021`
- diagnostic code head: `941bcb17b7dd02f9ac815fb2c4875b58529cb118`
- artifact: `tennis-genome-recent-family-diagnostic`
- artifact id: `10131261165`
- artifact digest: `sha256:be231fc46722598152ca8b68ee3a7559692c176bc43fd49d9f792a28d261cd09`
- recent block: 2021–2025

Research source remains the pinned 2000–2025 CC BY-NC-SA research-only snapshot. These grades describe predictive evidence for the registered representations; they do not establish causality or profitability.

---

# ATP

## A — Core

### Overall Elo
Previously promoted by EXP-001. It remains the foundational ability signal.

### Opponent-adjusted serve/return matchup
Previously promoted by EXP-003. ATP effect is stable across all evaluated historical seasons and grows with point-history depth.

### Recent form
Full-history family lab:
- add-one Δ Brier: `+0.000190`
- add-one Δ log loss: `+0.000461`
- Brier/log-loss wins: `20/25`, `20/25`
- ablation Δ Brier: `+0.000145`
- ablation Δ log loss: `+0.000377`

2021–2025 stability:
- add-one Δ Brier: `+0.000231`
- add-one Δ log loss: `+0.000524`
- ablation Δ Brier: `+0.000133`
- ablation Δ log loss: `+0.000295`
- recent Brier/log-loss wins: `4/5`, `4/5`

Decision: **A**. Small but genuinely incremental and stable.

### Workload / rest proxy
Full-history family lab:
- add-one Δ Brier: `+0.002745`
- add-one Δ log loss: `+0.005724`
- Brier/log-loss wins: `25/25`, `25/25`
- ablation Δ Brier: `+0.001923`
- ablation Δ log loss: `+0.004099`

2021–2025 stability:
- add-one Δ Brier: `+0.001629`
- add-one Δ log loss: `+0.003262`
- ablation Δ Brier: `+0.001208`
- ablation Δ log loss: `+0.002371`
- recent Brier/log-loss wins: `5/5`, `5/5`

Decision: **A**. Strongest newly tested ATP family. Higher-resolution timing/recovery data is a high-priority acquisition target.

### Age / career / physical
Full-history family lab:
- add-one Δ Brier: `+0.001322`
- add-one Δ log loss: `+0.002721`
- Brier/log-loss wins: `25/25`, `24/25`
- ablation Δ Brier: `+0.000488`
- ablation Δ log loss: `+0.000911`

2021–2025 stability:
- add-one Δ Brier: `+0.001174`
- add-one Δ log loss: `+0.001914`
- ablation Δ Brier: `+0.000534`
- ablation Δ log loss: `+0.000424`
- recent Brier/log-loss wins: `5/5`, `4/5`

Decision: **A**. Survives the recent-regime gate.

### Surface / tournament context
Full-history family lab:
- add-one Δ Brier: `+0.000320`
- add-one Δ log loss: `+0.001209`
- Brier/log-loss wins: `19/25`, `21/25`
- ablation Δ Brier: `+0.000414`
- ablation Δ log loss: `+0.001462`

2021–2025 stability:
- add-one Δ Brier: `+0.001005`
- add-one Δ log loss: `+0.002588`
- ablation Δ Brier: `+0.001135`
- ablation Δ log loss: `+0.002824`
- recent Brier/log-loss wins: `5/5`, `5/5`

Decision: **A**. The result reinforces the EXP-002 conclusion: context should modify validated strength rather than be represented as isolated pure Surface Elo.

## B — Conditional / redundant

### Age × fatigue
Strong add-one relationship, but historical full-model ablation was slightly negative. Recent ablation is approximately zero. The interaction is largely absorbed by the A-grade age and workload families.

Decision: **B**. Retain for research and future exact-timestamp fatigue modeling; exclude from strict Core v1.

### Head-to-head
Historically tiny but positive incremental and ablation signal. Recent 2021–2025 signal is also positive, but the magnitude remains small.

Decision: **B**. Low-weight/conditional; exclude from strict Core v1.

## D — Rejected representation

### Basic handedness / matchup
Historical add-one and ablation effects were negative and unstable. A small recent positive patch cannot upgrade a pre-existing D grade.

Decision: **D** for the registered left/right representation. Rich style geometry remains untested.

### Pure independent Surface Elo
Previously rejected by EXP-002 as a general replacement for overall Elo.

---

# WTA

## A — Core

### Overall Elo
Previously promoted by EXP-001.

### Recent form
Full-history family lab:
- add-one Δ Brier: `+0.001163`
- add-one Δ log loss: `+0.002783`
- Brier/log-loss wins: `25/25`, `25/25`
- ablation Δ Brier: `+0.000641`
- ablation Δ log loss: `+0.001492`

2021–2025 stability:
- add-one Δ Brier: `+0.000795`
- add-one Δ log loss: `+0.001767`
- ablation Δ Brier: `+0.000830`
- ablation Δ log loss: `+0.001868`
- recent Brier/log-loss wins: `5/5`, `5/5`

Decision: **A**.

### Workload / rest proxy
Full-history family lab:
- add-one Δ Brier: `+0.003279`
- add-one Δ log loss: `+0.007503`
- Brier/log-loss wins: `24/25`, `24/25`
- ablation Δ Brier: `+0.001430`
- ablation Δ log loss: `+0.003312`

2021–2025 stability:
- add-one Δ Brier: `+0.002234`
- add-one Δ log loss: `+0.005327`
- ablation Δ Brier: `+0.002262`
- ablation Δ log loss: `+0.005345`
- recent Brier/log-loss wins: `4/5`, `4/5`

Decision: **A**. Strongest newly tested WTA family.

### Surface / tournament context
Full-history family lab:
- add-one Δ Brier: `+0.000506`
- add-one Δ log loss: `+0.000895`
- Brier/log-loss wins: `19/25`, `19/25`
- ablation Δ Brier: `+0.000477`
- ablation Δ log loss: `+0.001099`

2021–2025 stability:
- add-one Δ Brier: `+0.000206`
- add-one Δ log loss: `+0.000467`
- ablation Δ Brier: `+0.000333`
- ablation Δ log loss: `+0.000784`
- recent Brier/log-loss wins: `4/5`, `3/5`

Decision: **A**. Smaller than workload/form but still positive in aggregate, positive under ablation, and not collapsed in the recent block.

## B — Conditional / redundant

### Opponent-adjusted serve/return matchup
EXP-003 showed a small positive WTA effect that strengthens with deeper historical point data, but it remains materially weaker than ATP.

Decision: **B**. Excluded from strict A-only Core v1; retained in the pre-registered A+B diagnostic candidate.

### Age × fatigue
Strong add-one signal, but essentially zero unique historical ablation contribution. Recent ablation turns slightly positive but is too small and is post-grade diagnostic evidence.

Decision: **B**. Retain for research; exclude from strict Core v1.

## C — Experimental / unstable

### Age / career / physical
Full 2000–2025 history looked strong:
- add-one Δ Brier: `+0.001950`
- add-one Δ log loss: `+0.004608`
- historical ablation Δ Brier: `+0.000854`
- historical ablation Δ log loss: `+0.002213`

But the pre-registered recent-regime gate fails decisively in 2021–2025:
- add-one Δ Brier: **`-0.005191`**
- add-one Δ log loss: **`-0.012496`**
- ablation Δ Brier: **`-0.002452`**
- ablation Δ log loss: **`-0.005756`**
- Brier/log-loss winning recent years: **`0/5`, `0/5`**

Decision: **C**, not A. The historical association is real enough to preserve, but the registered representation is regime-unstable and unsafe for Core v1. Future work should determine whether changing career-age distributions, tour composition, missingness, or a nonlinear/time-varying age function explains the reversal. The sealed 2026 holdout may not be used to repair or promote this family.

### Head-to-head
Historical add-one log loss was slightly negative and total effect tiny despite positive ablation. Recent behavior is somewhat positive, but B/C/D grades cannot be upgraded from the post-result diagnostic.

Decision: **C**.

## D — Rejected representation

### Basic handedness / matchup
Historical registered representation did not reliably improve future probability quality. Recent positive noise does not reverse the pre-existing D classification.

Decision: **D**.

### Pure independent Surface Elo
Previously rejected by EXP-002 as a general replacement for overall Elo.

---

# Frozen Core v1 family membership

## ATP strict A-only
1. Overall Elo
2. Opponent-adjusted Serve/Return
3. Recent Form
4. Workload/Rest Proxy
5. Age/Career/Physical
6. Surface/Tournament Context

## ATP A+B diagnostic
Strict A-only plus:
- Age × Fatigue
- Head-to-Head

## WTA strict A-only
1. Overall Elo
2. Recent Form
3. Workload/Rest Proxy
4. Surface/Tournament Context

## WTA A+B diagnostic
Strict A-only plus:
- Opponent-adjusted Serve/Return
- Age × Fatigue

These memberships are frozen before the sealed partial-2026 holdout is read. No 2026 outcome may alter these grade assignments.
