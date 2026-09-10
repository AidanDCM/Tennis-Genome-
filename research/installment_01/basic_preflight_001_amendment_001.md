# BASIC-PREFLIGHT-001 Amendment 001 — Source-Package Integrity Guard

Status: **PREREGISTERED IMPLEMENTATION HARDENING BEFORE ANY REAL BASIC OR ADVANCED MARKET-PERFORMANCE RESULT**

## Reason for amendment

The original BASIC-PREFLIGHT-001 protocol already freezes the source package as exactly `BASIC` and states that ADVANCED and PRO input must be rejected. The initial implementation passed `data_package="BASIC"` into the shared Betfair parser, but that argument controls which fields are reconstructed; it does not itself prove that the raw source stream lacks ADVANCED/PRO executable price ladders.

That creates a source-boundary loophole: a richer Betfair stream could be supplied to BASIC-PREFLIGHT-001 and interpreted under BASIC semantics instead of being rejected.

## Frozen hardening

Before any BASIC coverage calculation or canonical join is run, BASIC-PREFLIGHT-001 must inspect the raw Betfair MarketChangeMessages and fail closed if a runner change contains any executable ladder field supported by the repository's Betfair parser:

- ADVANCED: `batb`, `batl`;
- PRO: `atb`, `atl`.

The guard applies to both plain-text and `.bz2` supported Betfair source files.

Detection of any of these fields is a structural failure. The command must not continue to coverage calculation, purchase-window recommendation, or artifact creation.

## What does not change

This amendment does not change:

- the provider floor (`2015-04-01`);
- the development end (`2025-12-31`);
- the 21-day right-edge buffer;
- ATP/WTA identity-coverage thresholds;
- the >=1,000 prior-row requirement;
- the frozen 2021-2025 recent-period checks;
- the minimum-window algorithm;
- any Tennis Genome feature, outcome, market-edge model, inference rule, or profitability criterion.

It only enforces an evidence boundary that was already required by the original preregistration.

## Result-blind status

At the time of this amendment, no licensed Betfair outcome bundle has been opened for market-performance evaluation and no MARKET-EDGE or MARKET-EDGE-ADV confirmatory result has been observed. This remains a pre-result integrity hardening.
