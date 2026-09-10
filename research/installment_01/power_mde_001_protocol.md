# POWER-MDE-001 — Outcome-Blind MARKET-EDGE Feasibility Gate

Status: **PREREGISTERED BEFORE LICENSED BETFAIR OUTCOMES / MARKET-EDGE RESULTS**

## Purpose

POWER-MDE-001 measures whether the eventual Betfair-matched sample is statistically capable of
resolving small incremental tennis signals before the real settled outcomes are opened.

This is a planning / feasibility analysis. It is not a predictive result, market-edge result, or
promotion gate.

## Why this exists

MARKET-EDGE-001 can be perfectly implemented yet still be underpowered. A null result from a
sample that could only detect very large effects would be weak evidence against Tennis Genome.
Conversely, a large enough sample can make very small effects detectable even when they are not
economically useful.

POWER-MDE-001 therefore separates:

1. statistical resolvability;
2. predictive incrementality;
3. later economic usefulness.

## Outcome-blind inputs

POWER-MDE-001 may use only:

- canonical `match_id` and pre-match year;
- frozen Betfair `CLOSE_PREPLAY` market probability;
- frozen Profile Gap or Genome signal values;
- tour identity.

It must not read:

- match winner;
- retirement settlement outcome;
- realized P&L;
- CLV;
- any MARKET-EDGE result that depends on real outcomes.

The same frozen tour-specific signal definitions used by MARKET-EDGE-001 apply:

- ATP Profile Gap: `profile_gap_match`;
- WTA Profile Gap: `profile_gap_match`;
- ATP Genome: `full_neighbor_residual`;
- WTA Genome: `core_neighbor_residual`.

## Four planning claims

Report separately for the same four MARKET-EDGE hypotheses:

1. ATP Profile Gap;
2. WTA Profile Gap;
3. ATP Genome;
4. WTA Genome.

POWER-MDE-001 does not accept or reject any of them.

## Chronological design

For every prospective evaluation year `Y`:

- training rows are strictly earlier than `Y`;
- at least 1,000 earlier matched rows are required;
- signal mean and standard deviation are computed on those earlier rows only;
- the evaluation-year row count is reported but not used to fit the design matrix;
- no post-2025 row is allowed.

This mirrors the chronology of MARKET-EDGE-001.

## Null-information calculation

The MARKET-EDGE challenger is:

```text
logit(p) = alpha + gamma * logit(p_market) + beta * z(signal)
```

For power planning, construct the earlier-row design matrix:

```text
X = [1, logit(p_market), z(signal)]
```

Use the same probability clipping boundary as MARKET-EDGE-001 for the logit transform:

```text
p_market in [1e-6, 1 - 1e-6]
```

Under the null `beta = 0`, use `p_market` only to construct Bernoulli Fisher weights:

```text
w_i = p_market_i * (1 - p_market_i)
I = X' W X
```

The planning standard error for `beta` is:

```text
SE_beta = sqrt((I^-1)[beta,beta])
```

A rank-deficient information matrix or a condition number `>= 1e12` is reported as
non-identifiable rather than silently regularized.

## Multiplicity-aware alpha

MARKET-EDGE-001 has four confirmatory claims and uses Holm FWER correction. Holm's realized
critical value depends on the ordered p-values, which are unknown before outcomes exist.

POWER-MDE-001 therefore uses the conservative first-step family threshold:

```text
alpha_plan = 0.05 / 4 = 0.0125
```

with a **two-sided** normal approximation, matching the two-sided paired sign-flip philosophy.
This is intentionally conservative and is not a replacement for the actual Holm procedure.

## Minimum detectable beta

Primary planning power is 80%; 90% is also reported.

For target power `1 - delta`:

```text
MDE_beta ≈ (z_(1-alpha_plan/2) + z_(1-delta)) * SE_beta
```

This is a coefficient-scale feasibility estimate, not a MARKET-EDGE promotion criterion.

## Power grid

For transparency, approximate two-sided Wald power is reported for absolute standardized-signal
log-odds effects:

```text
|beta| = 0.02, 0.05, 0.10, 0.15, 0.20
```

These are sensitivity scenarios, not claims about the true effect.

## Probability-scale interpretation

For the 80% and 90% MDE beta values, also report the one-standard-deviation probability shift at
representative market probabilities:

- 0.50;
- 0.65;
- 0.80.

For market probability `p` and positive one-SD signal:

```text
shift(p, beta) = logistic(logit(p) + beta) - p
```

This makes the abstract log-odds MDE interpretable without claiming that a given shift is
profitable.

## Collinearity diagnostics

Report, from earlier rows only:

- Pearson correlation between market logit and standardized signal;
- information-matrix condition number.

Strong collinearity is a real power penalty because MARKET-EDGE asks the tennis signal to add
information beyond the market, not merely correlate with it.

## Procurement interpretation

After MARKET-HIST-QA produces an eligible outcome-blind market/signal join, POWER-MDE-001 should
run **before canonical outcomes are joined to MARKET-EDGE**.

The report should inform whether the purchased history is deep enough to resolve plausibly useful
signals. It must not change MARKET-EDGE's frozen promotion gates.

If the sample is weak, valid responses include acquiring more history or accepting that the test
has limited resolution. Do not lower significance thresholds after seeing data.

## Non-claims

POWER-MDE-001 does not establish:

- that Profile Gap or Genome has a real effect;
- that any effect beats Betfair;
- that the coefficient Wald approximation equals the eventual paired proper-score test power;
- positive EV;
- positive CLV;
- profitability;
- a betting threshold.

The actual MARKET-EDGE-001 result still depends on real held-out chronological outcomes, paired
proper-score inference, stability gates, concentration checks, and Holm correction.