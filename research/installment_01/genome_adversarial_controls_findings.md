# GENOME-ADV-001 — Findings

Status: **historical adversarial development result**

GENOME-ADV-001 tested whether the historical residual signal previously observed in the full Tennis Genome neighborhood is genuinely attributable to richer matchup/profile geometry, or whether it can be explained by simpler local correction of the existing Core model.

The experiment was preregistered before historical output was inspected. It compares four models on the same future match population and the same chronological OOS Core residual ledger:

- **M0** — calibration control: `logit(p_core)` only;
- **M1** — `logit(p_core)` + k=100 residual from a one-dimensional Core-probability neighborhood;
- **M2** — `logit(p_core)` + k=100 residual from strict Core-feature geometry only;
- **M3** — `logit(p_core)` + k=100 residual from the full Genome representation (strict Core geometry + strict Profile absolute means).

All neighborhood residual labels are historical OOS Core residuals, all preprocessing/index fitting is historical-only, all comparisons use identical future match IDs, and the partial-2026 holdout remains excluded because it was already spent by earlier work.

## Accepted run

- workflow: `34433553870`
- accepted head: `db0cc49f2b71c97d4c18b1b03edfd84534e4188d`
- artifact: `tennis-genome-adversarial-controls`
- artifact ID: `10135919958`
- artifact SHA-256: `f51e96573f0bc967be898f095afd64db8b3844a01dbc4755974ab0b193bce299`
- source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- coverage: 2000–2025 only
- source status: CC BY-NC-SA 4.0 research-only
- primary neighborhood size: `k=100`

Both ATP and WTA runs, canonical rebuilds, summary generation, provenance copying, and artifact upload completed successfully on the same frozen workflow head.

## Decision summary

| Tour | Gate A: full > probability-only | Gate B: full > Core-only | Frozen interpretation |
|---|---|---|---|
| ATP | **PASS** | **PASS** | structured matchup historical alignment beyond local Core correction |
| WTA | **PASS** | **FAIL** | Core-geometry local residual correction; Profile means not promoted as neighborhood value |

This is historical development evidence only. It is not independent future confirmation, market evidence, or a profitability result.

## ATP — full Genome survives both adversarial controls

Matched population: **65,419** future OOS matches.

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| M0 calibration control | 0.203211 | 0.590661 | 68.0414% | 0.003677 |
| M1 probability-only neighborhood | 0.203272 | 0.590759 | 68.0506% | 0.003725 |
| M2 strict-Core neighborhood | 0.203054 | 0.590222 | 67.9008% | 0.006057 |
| **M3 full Genome** | **0.202880** | **0.589868** | 67.9390% | 0.005824 |

### Gate A — full Genome versus probability-only local correction

- Brier improvement: **+0.000392**;
- log-loss improvement: **+0.000891**;
- joint Brier + log-loss year wins: **16/23 = 69.57%**;
- 2021–2025 Brier improvement: **+0.000172**;
- 2021–2025 log-loss improvement: **+0.000452**.

Gate A therefore **passes**.

### Gate B — full Genome versus strict-Core geometry

- Brier improvement: **+0.000174**;
- log-loss improvement: **+0.000354**;
- joint Brier + log-loss year wins: **16/23 = 69.57%**;
- 2021–2025 Brier improvement: **+0.000191**;
- 2021–2025 log-loss improvement: **+0.000383**.

Gate B therefore **passes**.

### ATP residual structure

Direct future Core-residual diagnostics:

| Representation | Residual slope | Q5-Q1 realized Core residual | 2021–2025 slope | 2021–2025 Q5-Q1 |
|---|---:|---:|---:|---:|
| probability-only | +0.067436 | +0.006810 | **-0.016685** | **-0.006672** |
| strict Core | +0.286611 | +0.040486 | +0.158553 | +0.026121 |
| **full Genome** | **+0.352258** | **+0.046458** | **+0.249510** | **+0.032232** |

The probability-only residual relation actually reverses in the recent period, while Core geometry remains useful and Profile-aware full Genome strengthens that relation further.

### ATP interpretation

Under the frozen gates, ATP earns the stronger historical interpretation:

> **Transparent full-Genome historical alignment contains incremental structure beyond both local Core-probability correction and strict Core-feature geometry.**

This supports the idea that absolute Profile state contributes useful historical-matchup geometry on ATP under the current representation.

The probability-score gain remains small, and ECE remains worse than the simple calibration control. Therefore the Genome layer is still a **conditional residual-correction module**, not a replacement for calibration and not yet an independently forward-confirmed production component.

## WTA — Core geometry survives, Profile means do not clear the stronger gate

Matched population: **60,129** future OOS matches.

| Model | Brier | Log loss | Accuracy | ECE-10 |
|---|---:|---:|---:|---:|
| M0 calibration control | 0.205334 | 0.595734 | 67.6595% | 0.006572 |
| M1 probability-only neighborhood | 0.205340 | 0.595757 | 67.6662% | 0.006510 |
| **M2 strict-Core neighborhood** | **0.205171** | **0.595397** | **67.7028%** | 0.007193 |
| M3 full Genome | 0.205118 | 0.595259 | 67.7360% | 0.007743 |

Aggregate M3 is slightly better than M2, but the preregistered interpretation gate requires more than an aggregate edge.

### Gate A — full Genome versus probability-only local correction

- Brier improvement: **+0.000222**;
- log-loss improvement: **+0.000499**;
- joint Brier + log-loss year wins: **15/23 = 65.22%**;
- 2021–2025 Brier improvement: **+0.000095**;
- 2021–2025 log-loss improvement: **+0.000216**.

Gate A **passes**. WTA neighborhood value is not explained by a one-dimensional probability recalibration effect.

### Gate B — full Genome versus strict-Core geometry

- aggregate Brier improvement: **+0.000053**;
- aggregate log-loss improvement: **+0.000138**;
- joint Brier + log-loss year wins: **13/23 = 56.52%**, below the frozen 60% rule;
- 2021–2025 Brier change: **-0.000053** (worse);
- 2021–2025 log-loss change: **-0.000102** (worse).

Gate B therefore **fails**.

### WTA residual structure

| Representation | Residual slope | Q5-Q1 realized Core residual | 2021–2025 slope | 2021–2025 Q5-Q1 |
|---|---:|---:|---:|---:|
| probability-only | +0.061928 | +0.005442 | +0.081069 | +0.011182 |
| **strict Core** | **+0.271195** | **+0.038980** | **+0.217699** | +0.040048 |
| full Genome | +0.298680 | +0.045170 | +0.203086 | +0.040090 |

The direct residual relation remains positive for full Genome, but that additional Profile-aware geometry does not translate into sufficiently stable probability improvement over Core-only neighborhoods.

### WTA interpretation

The strongest interpretation allowed by the frozen rules is:

> **WTA contains useful local residual structure in strict Core feature geometry, but the current Profile absolute means have not earned incremental neighborhood weight.**

Therefore WTA historical alignment should use **Core-only geometry** as the justified development candidate. The full Profile-aware Genome remains experimental for WTA and must not be promoted on the basis of its tiny aggregate edge.

## Architecture consequence

The project must now maintain a tour-specific historical-alignment specification:

- **ATP historical alignment:** full Genome (`strict Core geometry + permitted strict Profile absolute means`) is the preferred historical development candidate;
- **WTA historical alignment:** strict Core geometry only is the preferred historical development candidate;
- **probability-only local neighborhoods:** rejected as the explanation of the main historical-neighbor effect on both tours.

This is deliberately asymmetric. The project does not force a common representation across tours when the evidence does not support one.

## Calibration consequence

Neither ATP nor WTA historical-neighborhood modules improve ECE versus the simple calibration control. Historical alignment therefore remains separate from calibration. Previously accepted calibration findings remain authoritative; this experiment does not replace them.

## What is not established

GENOME-ADV-001 does **not** establish:

- independent forward confirmation of the ATP full-Genome effect;
- independent forward confirmation of WTA Core-neighborhood correction;
- a production-ready neighborhood layer;
- an optimal k, metric, weighting function, or representation;
- learned embeddings or metric learning;
- a valid OOD/PASS coordinate;
- sportsbook mispricing;
- positive EV, CLV, ROI, or profitability.

## Next work

1. merge this adversarial-control milestone after exact-head CI and PR audit;
2. freeze the tour-specific historical-alignment representation above;
3. build the next uncertainty/OOD experiment around **difficulty-conditioned unfamiliarity**, because raw `D100` already failed;
4. combine validated uncertainty candidates with model disagreement, missingness/data depth, and historical-support variables under chronological evaluation;
5. build a tour-specific ensemble candidate in which ATP may use full-Genome residual correction while WTA uses Core-geometry residual correction;
6. rerun/select calibration only under prior-data chronology and preserve the earlier calibration conclusions unless a preregistered ensemble-calibration experiment earns a change;
7. evaluate selective prediction/PASS behavior on the ensemble candidate;
8. freeze an immutable market-blind independent model version only after those uncertainty and ensemble gates are complete;
9. continue production-compatible match/odds data acquisition before market, EV, or paper-profitability work.
