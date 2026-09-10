# MARKET-HIST-QA-001 — Pre-Result Amendment 002

Status: **FROZEN BEFORE LICENSED BETFAIR DATA IS SUPPLIED OR INSPECTED**

## Purpose

Make earlier-price coverage explicit enough for later tradeability research without changing the
primary closing-market eligibility gate.

An external methodological review correctly noted that a dataset may have excellent
`CLOSE_PREPLAY` coverage while having poor T-1H or T-15M coverage. Global checkpoint counts alone
cannot distinguish that problem from representative per-tour coverage.

No licensed Betfair historical bundle or MARKET-EDGE result has been supplied or inspected.

## Added reporting

For each tour, and separately for each calendar year in the boundary-safe canonical denominator,
report for every registered checkpoint:

- `T-24H`;
- `T-6H`;
- `T-1H`;
- `T-15M`;
- `CLOSE_PREPLAY`.

For each checkpoint report:

- eligible canonical completed matches;
- canonical matches with a joined checkpoint observation;
- canonical matches with an executable two-way checkpoint;
- observed coverage fraction;
- executable coverage fraction.

Also report the same five checkpoint quantities over the full per-tour eligible denominator.

Counts are based on unique canonical `match_id`, not raw snapshot/message count.

## Primary gate unchanged

`CLOSE_PREPLAY` remains the only checkpoint used by the frozen MARKET-HIST-QA confirmatory
eligibility rules and by primary MARKET-EDGE-001.

Absence of T-24H/T-6H/T-1H/T-15M data does **not** invalidate the closing-market information test.
It only constrains later tradeability/CLV claims.

No minimum earlier-checkpoint coverage threshold is introduced here.

## Selection discipline

Checkpoint coverage, spread, liquidity and quote-age diagnostics may not be converted into
post-hoc filters for MARKET-EDGE-001 after model-vs-market outcomes are inspected.

Any future decision such as "only analyze T-1H when executable coverage exceeds X" or "exclude
wide-spread quotes" must be preregistered as a separate economic/tradeability experiment.

## Unchanged

This amendment does not change:

- the 21-day boundary-safe denominator rule;
- the >=60% overall executable-close gate;
- the >=50% per-year 2021–2025 executable-close gate;
- the >=100 recent rows gate;
- the >=1,000 earlier rows gate;
- the >=5 evaluation-years gate;
- the completed non-walkover/non-retirement primary population;
- the Betfair package requirement;
- the MARKET-EDGE four-claim Holm family;
- the market probability transform;
- any predictive signal;
- the prohibition on post-2025 confirmatory data.