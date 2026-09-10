# BASIC-PREFLIGHT-001 — Outcome-Blind Betfair Purchase-Window Preflight

Status: **PREREGISTERED BEFORE ANY BASIC OR ADVANCED MARKET OUTCOME COMPARISON**

## Purpose

Use Betfair BASIC Tennis `MATCH_ODDS` history only as a low-cost / potentially free **coverage preflight** to estimate the smallest ADVANCED historical interval worth purchasing for MARKET-HIST-QA / MARKET-EDGE research.

This experiment does **not** test prediction quality, market edge, EV, CLV, ROI, or profitability.

BASIC lacks the executable best-back/best-lay fields required by the confirmatory market experiments. A positive BASIC preflight therefore cannot unlock MARKET-EDGE and cannot substitute for ADVANCED MARKET-HIST-QA.

## Evidence boundary

BASIC-PREFLIGHT-001 is strictly outcome-blind. It may read only:

1. a local Betfair BASIC historical Tennis bundle;
2. canonical `pre_match.parquet` containing no outcome fields;
3. declared source start/end dates.

It must not read:

- match winners;
- score;
- retirement/walkover outcomes;
- Profile Gap outcomes or residuals;
- Genome outcomes or residuals;
- Strict Core outcomes;
- MARKET-EDGE results;
- ADVANCED/PRO executable prices.

Frozen tennis-model signals are unnecessary for this preflight and must not be supplied.

## Provider/source limits

Use Betfair Stream-format historical data only from the documented provider floor:

`2015-04-01`

No requested interval may begin earlier than that date or end after `2025-12-31` for development research.

Australian/New Zealand market-history limitations may reduce coverage before October 2016 and must be allowed to appear naturally in the coverage report; they are not patched or imputed.

## Data package

The source package for this preflight is exactly:

`BASIC`

ADVANCED and PRO are intentionally rejected by this command so the preflight cannot accidentally become an outcome/price experiment.

Use the existing Tennis Genome Betfair Stream parser and canonical identity join. Do not create a second name-matching implementation.

## Market universe

Retain only reconstructed two-runner Tennis `MATCH_ODDS` markets accepted by the existing Betfair parser.

For each source market, run the same deterministic canonical identity resolver used by MARKET-HIST-001.

Statuses:

- `MATCHED` — exactly one canonical pre-match match resolved;
- `UNMATCHED` — no canonical match resolved;
- `AMBIGUOUS` — multiple candidates remain.

Duplicate Betfair `marketId` across source files fails closed.

## Canonical preflight denominator

Because outcomes are forbidden, the preflight denominator is **not** the final MARKET-HIST-QA completed/non-retirement population.

For each tour/year, define the proxy denominator as all canonical pre-match rows whose `event_date` lies inside the declared BASIC source interval after applying the same 21-day right-edge safety buffer used by MARKET-HIST-QA.

A canonical row is counted as BASIC-covered only when exactly one reconstructed Betfair BASIC market joins to that `match_id`.

Report this explicitly as **pre-match identity coverage**, never executable-close coverage.

## Frozen per-tour/year diagnostics

For ATP and WTA separately report:

- canonical proxy denominator;
- BASIC matched canonical rows;
- pre-match identity coverage fraction;
- unmatched source markets;
- ambiguous source markets;
- duplicate canonical-match joins (hard failure);
- monthly matched-row counts;
- cumulative matched rows available before each calendar year.

The report must include every calendar year touched by the boundary-safe source interval, including years with zero matches.

## Recent-period proxy checks

For each tour, evaluate the following **purchase-feasibility proxies** using BASIC identity coverage:

1. overall BASIC identity coverage >= 60%;
2. each year 2021–2025 has BASIC identity coverage >= 50%;
3. each year 2021–2025 has >= 100 BASIC-matched canonical rows.

These mirror MARKET-HIST-QA minimums only as an upper-bound feasibility screen. They do not certify that ADVANCED will have executable closing quotes.

If a BASIC proxy fails, flag the corresponding ADVANCED purchase as `HIGH_RISK_COVERAGE` rather than retuning the threshold.

## Minimum prior-history calculation

The confirmatory market program requires at least 1,000 earlier matched rows before the first evaluation year.

For purchase planning, freeze the target first recent evaluation year as `2021` because all five recent years 2021–2025 must ultimately be represented.

For each tour independently:

1. consider monthly purchase boundaries from `2015-04-01` through `2020-12-01`;
2. for each candidate start month, count BASIC-matched canonical rows with event date from that month through `2020-12-31`;
3. select the **latest** candidate start month whose count is >= 1,000;
4. if no candidate reaches 1,000, return `INSUFFICIENT_BASIC_PRIOR_HISTORY`.

The joint ATP+WTA recommended ADVANCED start month is the **earlier** of the two tour-specific latest qualifying start months. The recommended end is `2025-12-31`.

This mechanically minimizes the purchased interval while preserving the frozen 1,000-row training requirement for both tours.

## Purchase recommendation classes

Return one of:

- `CANDIDATE_MINIMUM_WINDOW` — both tours satisfy all BASIC proxy checks and each has a qualifying >=1,000-row start month;
- `HIGH_RISK_COVERAGE` — a start month can be calculated but one or more BASIC coverage/count proxies fail;
- `INSUFFICIENT_BASIC_PRIOR_HISTORY` — at least one tour cannot accumulate 1,000 BASIC-matched rows before 2021 even from the full available source history;
- `BLOCKED_STRUCTURAL` — malformed source, duplicate market/canonical join, impossible dates, outcome leakage, or provenance failure.

## Provenance

The artifact must record:

- experiment ID;
- declared BASIC source interval;
- source file count and total bytes;
- SHA-256 for every BASIC source file;
- deterministic bundle SHA-256;
- canonical pre-match file SHA-256;
- per-tour/year diagnostics;
- tour-specific recommended start months;
- joint recommended purchase interval;
- deterministic artifact SHA-256.

Raw Betfair data must not be committed to Git.

## Interpretation

A passing preflight means only:

> The BASIC market-definition sample suggests that purchasing ADVANCED for the recommended interval is plausibly sufficient to ask the frozen market-validation questions economically.

It does **not** mean:

- ADVANCED executable-close coverage will pass QA;
- the market is beaten;
- Profile Gap or Genome survives the market;
- a profitable betting strategy exists.

After ADVANCED is acquired, the complete MARKET-HIST-001 and MARKET-HIST-QA-001 gates must still run unchanged before any MARKET-EDGE result is opened.
