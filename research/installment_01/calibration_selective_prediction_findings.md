# CAL-SEL-001 — Calibration and Selective Prediction Findings

Status: accepted development research result. These findings are from the frozen 2000–2025 protocol and do **not** use the spent partial-2026 Core-v1 holdout.

## Provenance

- Accepted workflow run: `34424871271`
- Accepted head: `3fc3427f18a99fa8dc4995493d928f3f665511ff`
- Artifact: `tennis-genome-calibration-selective`
- Artifact digest: `sha256:302a39692f934a1efb81e999889fd44d32d58efda58a47f2906235bd6f19bd0a`
- Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`
- Historical source license: CC BY-NC-SA 4.0 / research-only for this project
- Base OOF years: 2001–2025
- Nested calibration years: 2002–2025
- ATP base OOF N: 71,832; common calibration N: 68,518
- WTA base OOF N: 66,224; common calibration N: 63,201

## Calibration decision

### ATP — keep Identity

Aggregate common-population results:

| Method | Brier | Log loss | ECE-10 | Accuracy |
|---|---:|---:|---:|---:|
| Identity | **0.203865** | **0.592218** | 0.007173 | 67.8595% |
| Platt | 0.203878 | 0.592236 | 0.005989 | 67.8289% |
| Beta | 0.203890 | 0.592268 | 0.005658 | 67.8362% |
| Isotonic | 0.204144 | 0.594258 | **0.005140** | 67.8698% |

All three post-hoc methods improve aggregate ECE, but all three worsen at least both registered primary metrics relative to Identity. Under the pre-registered promotion gate, none may replace Identity.

ATP Identity calibration slope is `0.9514` aggregate, but only `0.8848` on 2021–2025, indicating recent over-confidence drift worth monitoring. Platt improves recent 2021–2025 Brier/log loss in all five individual years, but that is a **new follow-up hypothesis**, not permission to override the frozen aggregate gate after seeing the result.

**Decision:** ATP calibration v1 remains `Identity`.

### WTA — Beta preferred development candidate; Platt secondary

Aggregate common-population results:

| Method | Brier | Log loss | ECE-10 | Accuracy |
|---|---:|---:|---:|---:|
| Identity | 0.205914 | 0.597593 | 0.018858 | 67.6461% |
| Platt | 0.205536 | 0.596208 | **0.007826** | 67.6223% |
| Beta | **0.205514** | **0.596065** | 0.008218 | **67.6619%** |
| Isotonic | 0.205747 | 0.596880 | 0.007727 | 67.6651% |

Beta improves Brier in 20/24 calibration years and log loss in 19/24. In 2021–2025 it improves Brier in 4/5 years, log loss in 4/5, and ECE in 4/5.

Platt also passes the broad promotion criteria: aggregate/recent Brier and log loss improve, ECE improves strongly, and the effect is not concentrated in one season. However, the protocol declared Brier/log loss primary and calibration diagnostics secondary. Beta therefore receives the preferred candidate slot because it has the best aggregate primary metrics, with Platt retained as a credible secondary calibration model.

WTA raw Identity is visibly over-confident: aggregate calibration slope `0.8677`. Beta moves the aggregate slope to `1.0373` and recent 2021–2025 slope to `1.0247`.

**Decision:** WTA `Beta` becomes the preferred development calibration candidate. This is **not independently forward-confirmed**, because the only partial-2026 holdout was already opened before CAL-SEL-001 existed. A genuinely later forward sample is required before calling Beta production-validated.

## Selective-prediction curve

The fixed confidence baseline is probability distance from 50%. This is a predictability/abstention experiment, not a betting strategy.

### ATP — Identity

| Coverage | N | Accuracy | Brier | Log loss | ECE-10 | Mean favorite p | Favorite win rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100% | 68,518 | 67.86% | 0.203865 | 0.592218 | 0.007173 | 68.56% | 67.86% |
| 75% | 51,389 | 72.56% | 0.189029 | 0.559660 | 0.008320 | 73.37% | 72.56% |
| 50% | 34,259 | 77.86% | 0.166179 | 0.508387 | 0.009674 | 78.77% | 77.86% |
| 25% | 17,130 | 84.42% | 0.128191 | 0.418465 | 0.011960 | 85.54% | 84.42% |
| 10% | 6,852 | 90.81% | 0.082252 | 0.299832 | 0.006816 | 91.30% | 90.81% |
| 5% | 3,426 | **93.75%** | 0.058110 | 0.231307 | 0.006139 | 94.12% | 93.75% |

The 10% subset begins around a raw probability margin of `0.364`, equivalent to a favored-side probability of roughly 86.4% or higher. The 5% subset begins around a margin of `0.408`, roughly 90.8% favored-side probability or higher.

### WTA — Beta candidate

| Coverage | N | Accuracy | Brier | Log loss | ECE-10 | Mean favorite p | Favorite win rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 100% | 63,201 | 67.66% | 0.205514 | 0.596065 | 0.008218 | 67.29% | 67.66% |
| 75% | 47,401 | 72.09% | 0.191506 | 0.565348 | 0.008290 | 71.78% | 72.09% |
| 50% | 31,601 | 77.21% | 0.169607 | 0.516323 | 0.009064 | 76.84% | 77.21% |
| 25% | 15,801 | 83.73% | 0.132599 | 0.429136 | 0.009313 | 83.32% | 83.73% |
| 10% | 6,321 | 90.08% | 0.088141 | 0.315338 | 0.008460 | 89.24% | 90.08% |
| 5% | 3,161 | **93.23%** | 0.062498 | 0.242292 | 0.010180 | 92.32% | 93.23% |

The WTA Beta 10% subset begins around a calibrated margin of `0.341`, roughly an 84.1% favored-side probability. The 5% subset begins around `0.385`, roughly 88.5%.

### Interpretation

Selective prediction works strongly in the intended descriptive sense: allowing the model to abstain from progressively less-separated matches produces a monotonic and substantial increase in winner accuracy on both tours.

This is **not evidence of betting profitability**. The most predictable matches are generally strong favorites and may be priced too expensively by sportsbooks. The market layer must later test whether any accuracy/confidence bucket produces value relative to no-vig prices.

No fixed 10%, 5%, or other coverage threshold is promoted as a production PASS rule from this experiment alone. Coverage cutoffs are descriptive diagnostics and require later forward and market-aware validation.

## Model-disagreement finding

Raw disagreement is the range across Elo-only, strict Core v1, and the A+B diagnostic model.

### ATP disagreement quintiles

Brier deteriorates from `0.194005` in the lowest-disagreement quintile to `0.211040` in the highest; log loss deteriorates from `0.566718` to `0.611005`, while accuracy falls from `69.39%` to `66.85%`.

### WTA disagreement quintiles

Brier is `0.191610` in the lowest-disagreement quintile versus `0.212986` in the highest; log loss is `0.562973` versus `0.615208`, and accuracy is `70.26%` versus `66.44%`.

There is an important confounder: low-disagreement matches are also more confident on average. The joint confidence × disagreement diagnostic shows the strongest independent-looking disagreement effect in the highest-confidence quintile:

- ATP high-confidence: Brier worsens approximately `0.1008 → 0.1324` from disagreement Q1 to Q5; accuracy `88.1% → 84.2%`.
- WTA high-confidence: the corresponding pattern is roughly Brier `0.1100 → 0.1387` and accuracy `87.0% → 83.5%`, with some non-monotonicity in the final two disagreement cells.

At low and medium confidence the conditional relationship is much less consistent. Therefore disagreement appears useful as an **uncertainty/exception diagnostic**, especially for apparently high-confidence matches, but CAL-SEL-001 does not justify a hard disagreement-based PASS gate.

**Decision:** retain model disagreement as a B/conditional Confidence-v1 research component. It must receive separate chronological/forward gating before it can veto a wager or prediction.

## Development state after CAL-SEL-001

- ATP calibration candidate: **Identity**
- WTA calibration candidate: **Beta**, future forward confirmation required
- Probability margin: validated as a strong **descriptive selective-prediction ranking signal**
- Model disagreement: conditional uncertainty signal, not yet a hard gate
- 2026: remains spent and unavailable for independent validation of these changes
- Market value/profitability: completely untested in this installment

## Registered follow-ups suggested by this result

These are new hypotheses and must not retroactively alter CAL-SEL-001:

1. **CAL-SEL-002 — ATP recent calibration drift:** test a predeclared rolling or recency-weighted calibrator because 2021–2025 differs from the long-run ATP aggregate.
2. **CONF-002 — disagreement conditional on confidence:** test whether disagreement adds error-risk information within predeclared confidence strata and can support an uncertainty penalty.
3. **Forward confirmation:** freeze ATP Identity / WTA Beta and Confidence-v1 candidates, then evaluate on genuinely later data not used here or in the spent partial-2026 holdout.
4. **Market layer:** once production-compatible odds exist, test whether confidence-ranked accuracy corresponds to positive no-vig edge or simply increasingly expensive favorites.
