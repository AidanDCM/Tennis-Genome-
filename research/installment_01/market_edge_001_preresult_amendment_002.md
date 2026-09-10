# MARKET-EDGE-001 — Pre-Result Amendment 002

Status: **FROZEN BEFORE LICENSED BETFAIR MARKET RESULTS**

## Purpose

Freeze the primary Betfair two-runner probability transform and initial commission stress assumptions before MARKET-HIST-001 licensed price data are inspected.

## Primary exchange probability transform

Version: `exchange_mid_implied_proportional_v1`

For each runner with executable best back price `B` and best lay price `L`:

```text
q_runner = 0.5 * (1 / B + 1 / L)
```

For the two runners A and B:

```text
p_market_A = q_A / (q_A + q_B)
p_market_B = q_B / (q_A + q_B)
```

Requirements:

- both runners must have best back and best lay prices;
- all prices must exceed 1.0;
- best back must not exceed best lay for the same runner;
- A/B identity orientation must come from the MARKET-HIST deterministic join;
- the selected snapshot must satisfy the checkpoint chronology contract.

This transform is symmetric under A/B exchange and uses both sides of the exchange spread. It is a market-probability benchmark, not an assertion that the midpoint itself was executable.

Last traded price is not substituted when an executable side is missing.

## Supporting transforms

The following may be reported only as sensitivity diagnostics unless separately preregistered:

- back-only proportional implied probability;
- lay-only proportional implied probability;
- odds-space midpoint;
- last-traded-price transforms.

They cannot replace the primary transform because one produces a more favorable model result.

## Executable back EV

For a single isolated unit-stake back position at decimal odds `O`, model win probability `p`, and effective commission fraction `c` applied to positive winnings:

```text
EV = p * (O - 1) * (1 - c) - (1 - p)
```

This isolated-position equation is valid only when the position is evaluated independently. If later policies create multiple positions within the same Betfair market, settlement must move to market-level net-winnings accounting before commission.

## Commission stress grid

Until an account/jurisdiction-specific effective rate is established, report executable EV sensitivity at:

- 0%;
- 2%;
- 5%;
- 7%.

The source `marketBaseRate`, when present, is preserved separately and reported. The stress grid is not a claim that any one listed value is the user's actual charged rate.

No candidate is called robustly positive-EV from historical research unless its sign survives the commission assumption explicitly attached to that claim.

## CLV definitions

At an executable decision checkpoint, retain the closing pre-play primary market probability and closing best-back price when available.

For a position on a selected runner, report:

1. probability CLV: `p_market_close - p_market_decision`;
2. log-odds probability CLV: `logit(p_market_close) - logit(p_market_decision)`;
3. executable back-price CLV: `log(decision_back / close_back)` when both back prices exist.

Positive values indicate that the closing market moved toward the selected runner and/or that the earlier available back price was better than the later close.

Closing information never enters the earlier decision rule.

## Non-claims

The primary probability transform does not remove exchange commission, model liquidity, queue priority, fill probability, premium charges, limits, or execution latency. Those are separate economic/operational layers.
