# Profitability and Decision Framework

## Purpose

The long-term objective is to make consistently profitable decisions, but the project must never confuse predictive accuracy with profitability.

A match can be highly predictable and still be a bad bet if the price is worse than fair value.

## Separate probability from price

The independent model produces:

`p_model = P(outcome | tennis information available at T0)`

The market layer produces:

`p_market_novig = implied fair probability from the selected market snapshot after vig removal`

Define:

`edge_pp = p_model - p_market_novig`

This is an estimated probability edge, not guaranteed profit.

## Expected value

For decimal odds `d` and unit stake:

`EV = p_model * (d - 1) - (1 - p_model)`

For American odds convert to decimal first.

The decision layer must use uncertainty around `p_model`, not only its point estimate.

## Conservative edge

Candidate robust decision quantity:

`conservative_edge = lower_probability_bound - p_market_novig`

or a posterior/empirical probability that EV > 0.

This prevents tiny apparent edges from being treated as equally trustworthy as large, well-supported discrepancies.

## Decision outputs

Every market evaluation should produce:
- model probability
- uncertainty estimate
- no-vig market probability
- edge in percentage points
- offered odds
- EV estimate
- model disagreement
- historical density / out-of-distribution score
- data-quality grade
- calibration reliability
- policy version
- action: `BET` or `PASS`
- reason codes

## PASS reasons

Candidate reason codes:
- `EDGE_TOO_SMALL`
- `UNCERTAINTY_TOO_HIGH`
- `MODEL_DISAGREEMENT`
- `OUT_OF_DISTRIBUTION`
- `LOW_DATA_QUALITY`
- `INSUFFICIENT_HISTORY`
- `CALIBRATION_UNRELIABLE`
- `MARKET_STALE`
- `POLICY_FILTER`

## Betting-policy experiments

Do not bake one threshold into the probability model.

Freeze prediction outputs and evaluate policy layers such as:
- edge >= 1 pp
- edge >= 2 pp
- edge >= 4 pp
- edge >= 6 pp
- lower-bound edge > 0
- confidence >= threshold
- low disagreement only
- high-density neighborhoods only
- combinations of edge + confidence + density

Use nested/chronological validation so policy thresholds are not tuned on the final test period.

## Key market-aware metrics

### CLV
Closing-line value tests whether the chosen price tends to beat the eventual closing market price. Consistent positive CLV is useful evidence that decisions contain pricing information, though it does not guarantee future profit.

### ROI
`ROI = total_profit / total_amount_staked`

Always report:
- number of bets
- total stake
- average odds
- hit rate
- confidence interval / bootstrap uncertainty where appropriate
- drawdown
- period covered

### Profit factor
`gross_wins / abs(gross_losses)`

Useful as a descriptive metric, never sufficient by itself.

### Drawdown
Track maximum and rolling drawdowns. A positive average edge can still produce severe variance.

## Win rate requirement

The user goal includes winning more selected bets than losing. That can be tracked as a policy objective, but it is not mathematically sufficient for profitability.

A strategy betting heavy favorites may have a high win rate and negative ROI. Therefore promotion requires both probability/price discipline and profitability metrics.

## Odds-aware break-even

For decimal odds `d`:

`p_break_even = 1 / d`

For a two-way market, remove vig across both sides before comparing the model to market consensus.

## No-vig methods

Initial candidates:
- proportional normalization of implied probabilities
- power method
- Shin method later if justified

The chosen method must be versioned because small no-vig differences can affect marginal-edge decisions.

## Market snapshots

Store timestamped price records rather than only final odds.

Useful checkpoints may include:
- open
- 24h
- 12h
- 6h
- 3h
- 1h
- 30m
- 15m
- 5m
- close

Exact retention depends on data availability. Do not fabricate missing timestamps.

## Paper mode before real-money claims

Before any real-money deployment, run immutable paper predictions and decisions.

For each day:
1. freeze input data cutoff;
2. generate probabilities;
3. capture market prices at decision time;
4. lock `BET/PASS` decisions;
5. record outcomes later;
6. evaluate calibration, CLV, EV expectation, ROI, and error decomposition.

A short hot streak is not proof. Evidence should accumulate over hundreds/thousands of relevant decisions and multiple regimes.

## Promotion standard

A policy becomes a production candidate only if:
- the underlying probability model is calibrated out-of-sample;
- expected edge survives chronological holdouts;
- results are not concentrated in one player/event/season;
- edge survives reasonable no-vig and pricing assumptions;
- CLV is directionally supportive where available;
- realized ROI is positive with uncertainty acknowledged;
- drawdown is acceptable for the intended risk policy;
- the result survives adversarial review.

## Staking

Staking is deferred until the probability and policy layers prove useful.

When studied, candidates include:
- flat unit stakes for clean research comparison
- fractional Kelly based on conservative probabilities
- capped stakes
- portfolio exposure limits

Full Kelly is inappropriate when probability estimates are uncertain.

## Non-goal

The system must never output language such as `LOCK`, `GUARANTEED`, or `SURE WIN`. It estimates uncertainty and makes probabilistic decisions.
