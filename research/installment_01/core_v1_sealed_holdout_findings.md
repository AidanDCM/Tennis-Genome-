# Core v1 — Sealed Partial-2026 Holdout Findings

Status: **accepted forward confirmation for strict A-only Core v1 on ATP and WTA**

This result was inspected only after family grades and tour-specific Core v1 membership were frozen.

## Provenance

- accepted workflow run: `34422558010`
- accepted code head: `4ab65022542f5ca26c4a6990945a4ec671835854`
- artifact: `tennis-genome-core-v1-sealed-holdout`
- artifact id: `10131492874`
- artifact digest: `sha256:3b581294a85baf502c3ea4132248e84a55a16ad477892920da156d1c9b0d3959`
- experiment: `CORE-V1-SEALED-HOLDOUT-001`
- model coefficients, imputation, scaling, family membership, and hyperparameters were fitted/frozen using 2000–2025 only
- dynamic player state was allowed to update sequentially from genuinely earlier 2026 results under the existing source-date freeze rule
- source is research-only CC BY-NC-SA 4.0 and is **not** production/commercial-cleared

The pinned snapshot contains only a **partial 2026 season through 2026-05-25**. These results must never be described as full-season 2026 validation.

### Canonical ATP holdout dataset
- schema: `canonical-v3`
- rows: 79,299
- source files: 27 (2000–2026)
- source bundle SHA-256: `62a1ab7794769f70468d580bb744b2c194051622a9942bed49af97e239408f26`
- pre-match SHA-256: `ddca2288f7e8d420182ee9fb71ffae4c94bb92619a0d34585b43c3e5f0cef4fc`
- outcome SHA-256: `7039c2225191f2d7a82adcbbbf301fa9b4db17b3fe40b6cabf597f9b907f8f1c`
- stats SHA-256: `9a07d786e8782a95b67dfcd7941b802c735df04c99d642ead32a210868f61426`
- canonical warning count: 53 unknown-surface rows

### Canonical WTA holdout dataset
- schema: `canonical-v3`
- rows: 72,714
- source files: 27 (2000–2026)
- source bundle SHA-256: `e92d7bda10561944dae7bcaed5d4cf6594ca50e0c47bf0a9923b5f5a0ba32d4c`
- pre-match SHA-256: `8cb2b83653410c0164e2e50d60c6d2a2e41697443299ab0ac22eb3ffc7ffe92f`
- outcome SHA-256: `9e4f59903cd0db87888f3b908349c463e1659916035ecce8e755a2deeac7db5e`
- stats SHA-256: `37e8aa3ddab413cc834115c8406733d3fe39fc10b1c1ac6c3f9f01b602e6f26b`
- canonical warning count: 135 unknown-surface rows

---

# ATP sealed holdout

Holdout population: **1,406** eligible partial-2026 matches.

Training population through 2025: **75,112** matches.

## Historical benchmark

Features: overall Elo + opponent-adjusted serve/return control.

- Brier: `0.2167479064`
- log loss: `0.6223659275`
- accuracy: `65.6472%`
- ECE-10: `0.0308357`

## Strict A-only Core v1

Frozen ATP A families:
1. overall Elo
2. opponent-adjusted serve/return
3. recent form
4. workload/rest proxy
5. age/career/physical
6. surface/tournament context

Results:
- Brier: **`0.2105114568`**
- log loss: **`0.6084303843`**
- accuracy: **`66.9986%`**
- ECE-10: `0.0348706`

Versus benchmark:
- Brier improvement: **`+0.0062364496`**
- log-loss improvement: **`+0.0139355432`**
- accuracy change: **`+1.3514 percentage points`**

### ATP decision

**Forward confirmation PASSED.**

The pre-registered primary rule required strict A-only Core v1 to improve both Brier and log loss versus the historical benchmark. It improves both by substantial margins on the untouched partial-2026 slice and also improves accuracy.

Calibration does **not** improve: ECE-10 rises from `0.03084` to `0.03487`. This is an explicit warning, not a reason to discard the probability-quality win. Calibration remains a separate required development track before market EV decisions can be trusted.

## ATP A+B diagnostic

Adds B-grade age×fatigue and H2H.

- Brier: `0.2101703387`
- log loss: `0.6075074620`
- accuracy: `66.5007%`
- ECE-10: `0.0354577`
- Brier improvement vs benchmark: `+0.0065775678`
- log-loss improvement vs benchmark: `+0.0148584655`

The B families marginally improve Brier/log loss beyond strict A-only, but reduce accuracy and worsen ECE. **They remain B.** This diagnostic cannot promote them because the grade map was frozen before the holdout.

---

# WTA sealed holdout

Holdout population: **1,249** eligible partial-2026 matches.

Training population through 2025: **69,105** matches.

## Historical benchmark

Features: overall Elo + opponent-adjusted serve/return control, retained as the same common family-lab benchmark even though WTA serve/return has a B grade.

- Brier: `0.2105584507`
- log loss: `0.6068038241`
- accuracy: `66.2130%`
- ECE-10: `0.0389318`

## Strict A-only Core v1

Frozen WTA A families:
1. overall Elo
2. recent form
3. workload/rest proxy
4. surface/tournament context

Notably excluded before the holdout:
- opponent-adjusted serve/return (B)
- age×fatigue (B)
- age/career/physical (C after 2021–2025 regime collapse)
- H2H (C)
- basic handedness (D)

Results:
- Brier: **`0.2071013102`**
- log loss: **`0.5982921022`**
- accuracy: **`66.8535%`**
- ECE-10: **`0.0291524`**

Versus benchmark:
- Brier improvement: **`+0.0034571405`**
- log-loss improvement: **`+0.0085117219`**
- accuracy change: **`+0.6405 percentage points`**

### WTA decision

**Forward confirmation PASSED.**

Strict A-only Core v1 improves both pre-registered primary metrics, improves accuracy, and also materially improves ECE. The decision to demote WTA age/career/physical before opening the holdout therefore survives its first forward test rather than being repaired after the fact.

## WTA A+B diagnostic

Adds B-grade serve/return and age×fatigue.

- Brier: `0.2070123285`
- log loss: `0.5980690586`
- accuracy: `67.1737%`
- ECE-10: `0.0337459`
- Brier improvement vs benchmark: `+0.0035461222`
- log-loss improvement vs benchmark: `+0.0087347656`

A+B slightly improves Brier/log loss and accuracy beyond strict A-only, but has worse calibration than strict A-only. The B components remain **diagnostic only** and are not promoted by this holdout.

---

# Governing conclusion

The strict A-only foundational architecture receives its **first genuine forward confirmation on both ATP and WTA**.

This is stronger evidence than the prior walk-forward discovery results because:
- 2026 outcomes were not used to discover families;
- final family grades were frozen before the holdout was inspected;
- WTA's historically attractive but recently unstable age family was demoted before the holdout;
- the predictive mapping was fit only through 2025;
- the 2026 sequence was scored without coefficient/hyperparameter refitting.

It is still **not evidence of betting profitability**. There are no sportsbook odds, no no-vig market probabilities, no CLV, no transaction/availability assumptions, and no wager policy in this experiment.

It is also only a partial-season holdout. Core v1 should therefore be described as **forward-confirmed probability architecture**, not a finished or production-ready betting engine.

---

# Next gates

1. calibration architecture, especially ATP where ECE worsened despite improved Brier/log loss;
2. model-disagreement and selective-prediction/abstention measurement;
3. Player Profile v1 built from surviving evidence only;
4. Tennis Genome historical-neighborhood experiment against Core v1 residuals;
5. production-compatible data-source acquisition, especially exact match times/workload and contextual families;
6. only after the independent engine is stable: market/no-vig/EV and paper-profitability evaluation.

The 2026 holdout must not be reused as an independent validation set for any model change made after these findings were inspected.
