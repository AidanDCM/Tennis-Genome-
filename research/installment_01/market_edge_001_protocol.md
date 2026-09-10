# MARKET-EDGE-001 — Independent Signal vs Betfair Market

Status: **PREREGISTERED / BLOCKED ON MARKET-HIST-001 DATA GATE**

## Purpose

Test whether already-developed Tennis Genome signals contain information that Betfair tennis MATCH_ODDS prices do not already contain.

This experiment is intentionally narrower than a full betting-policy search. Its first question is not "can we optimize ROI?" but:

> Does Profile Gap, and secondarily the frozen Genome signal, predict outcomes beyond the information already embedded in the exchange market?

No Profile Gap, Genome, calibration, uncertainty, or market thresholds may be retuned using MARKET-EDGE-001 outcomes.

## Preconditions

MARKET-HIST-001 must pass before this experiment can run. Required inputs are immutable matched records containing:

- canonical match ID and tour;
- frozen independent-model outputs produced without market information;
- frozen Profile Gap value/version;
- frozen Genome-neighborhood value/version where available;
- Betfair executable pre-match back/lay checkpoints;
- `CLOSE_PREPLAY` checkpoint;
- source hashes, join hash, and checkpoint provenance;
- actual seconds-to-start and quote age.

Ambiguous identity joins, in-play prices, and post-start observations are excluded.

## Two distinct questions

### A. Closing-market information-overlap test

This is a **diagnostic information test**, not an executable strategy.

For each tour separately, evaluate whether a pre-existing independent signal adds out-of-sample predictive information beyond the closing no-vig market probability.

Primary signal: **Profile Gap**.

Secondary signal: **frozen Genome residual / neighborhood signal**.

Chronological evaluation only. The market-only benchmark is compared against a model whose baseline log-odds are the closing market probability plus the pre-existing signal. Any mapping from signal to probability is fit on earlier years only and evaluated on later years.

Primary metrics:

- Brier score delta vs closing market;
- log-loss delta vs closing market.

Supporting metrics:

- calibration / ECE;
- signed residual relationship `outcome - p_market_close` vs signal;
- year-by-year stability;
- probability-bin stability;
- tour and competition-tier diagnostics.

A positive result means the signal contains information not fully absorbed by the closing market. It does **not** by itself establish a tradable edge because the closing price may not have been available at the live decision time.

### B. Executable decision-point test

Use only prices that actually existed at the selected decision checkpoint:

- T-24H;
- T-6H;
- T-1H;
- T-15M.

At each checkpoint, compare the frozen independent probability to the contemporaneous executable exchange quote. The quote used for a back decision is the available back price, not last traded price and not a later closing price.

`CLOSE_PREPLAY` is retained only for market-efficiency benchmarking and CLV evaluation unless the policy explicitly acts at close.

## Market probability baseline

For each eligible checkpoint, produce a two-runner market probability benchmark from contemporaneous exchange prices using a preregistered, symmetric no-vig transform. The transform must be fixed before outcome inspection and applied identically across tours.

Report the market's own:

- accuracy;
- Brier score;
- log loss;
- calibration / ECE;
- performance by probability bin, year, tour, and competition tier.

This establishes the actual market bar rather than assuming Elo is the relevant benchmark.

## Commission and executable EV

Betfair commission is a settlement cost and must be modeled explicitly for EV/P&L claims.

The experiment must not hard-code one universal commission rate. Record the market base rate when present and evaluate a declared effective-commission parameter or stress grid representing the account/jurisdiction assumptions used for the backtest.

For a single isolated back position in one market, commission applies only to positive net market winnings. If future policies place multiple positions in the same market, settlement must be calculated at the **market net-winnings level**, not independently per ticket.

Raw no-vig edge may be reported as a diagnostic, but a bet is not labeled positive-EV unless it remains positive after the declared commission and execution assumptions.

## CLV

For every executable candidate, record both:

- the actual decision-point price;
- the closing pre-play exchange price.

Report CLV in probability and price/log-odds space. CLV is a faster diagnostic of whether the model repeatedly obtains prices that later move in its direction, but it is not treated as a guarantee of profit.

No closing price may influence the earlier bet decision.

## Selective prediction / probability-region analysis

Do not assume the highest-confidence favorite bucket is the best place to find market edge.

Predeclare probability regions and report them all, including:

- strong favorites;
- moderate favorites;
- near-even matches;
- moderate underdogs;
- long underdogs where sample size permits.

Also report results by liquidity/competition tier when the source data supports a defensible pre-outcome tier label. Tier definitions must be frozen before result inspection.

These are stratified diagnostics, not permission to cherry-pick the best cell after the fact.

## Statistical inference

All model-vs-market comparisons are paired on the same matches.

Required uncertainty reporting:

- paired bootstrap confidence intervals for Brier and log-loss deltas;
- paired sign/permutation test for mean loss deltas as a robustness check;
- McNemar exact test for paired accuracy disagreements;
- sample counts and effective coverage for every reported subgroup.

The primary claim is based on probability-quality metrics, not accuracy alone.

## Multiplicity

The family of primary MARKET-EDGE-001 claims is fixed before results:

1. ATP Profile Gap incremental Brier/log loss vs close;
2. WTA Profile Gap incremental Brier/log loss vs close;
3. ATP Genome incremental Brier/log loss vs close;
4. WTA Genome incremental Brier/log loss vs close.

Profile Gap is the primary signal family; Genome is secondary. Report both raw and multiplicity-adjusted significance. Holm correction is the default confirmatory family-wise adjustment for these four primary claims.

Subgroup, checkpoint, liquidity, probability-bin, and tier analyses are exploratory unless separately preregistered.

## Promotion gate

A signal may be described as **market-incremental** only if it:

1. improves both Brier and log loss versus the paired market benchmark on chronological out-of-sample data;
2. has bootstrap confidence intervals supporting the direction of improvement;
3. is not driven by a single year or one narrow probability bucket;
4. survives the declared multiplicity treatment for its confirmatory claim;
5. has no chronology, identity, or market-snapshot integrity violation.

A signal may be described as **economically promising** only if, in addition, executable decision-point analysis shows a coherent relationship between predicted edge and either commission-aware EV realization and/or positive CLV across meaningful sample sizes.

No live staking is authorized by this experiment.

## Explicit non-claims

MARKET-EDGE-001 does not prove future profitability, capacity, fill quality, robustness to account limits, or that historical exchange behavior will persist.

It is the first test of whether our independently discovered tennis structure survives contact with the market itself.
