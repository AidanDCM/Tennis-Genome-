# MARKET-HIST-QA-001 — Licensed Betfair Data Quality Gate

Status: **PREREGISTERED BEFORE LICENSED BETFAIR DATA IS SUPPLIED OR INSPECTED**

## Purpose

MARKET-HIST-QA-001 decides whether a licensed Betfair historical Tennis / MATCH_ODDS bundle is structurally sound, broad enough, and chronologically deep enough to unlock confirmatory MARKET-EDGE-001.

This is a data-quality gate, not a predictive experiment. It must be run before examining Profile Gap/Genome performance against Betfair.

## Inputs

1. A local licensed Betfair Historical Data directory.
2. A deterministic source-bundle manifest generated before outcome/model comparison.
3. MARKET-HIST-001 canonical records produced from that exact bundle.
4. Canonical pre-match table.
5. Canonical outcomes table only for defining the completed-match evaluation population; outcomes themselves are not used to judge price quality.

Raw licensed Betfair data must not be committed to Git.

## Frozen source requirements

Confirmatory MARKET-EDGE-001 requires:

- sport: Tennis;
- market type: MATCH_ODDS;
- package: ADVANCED or PRO;
- declared contiguous requested date interval;
- source file hashes recorded before analysis;
- no post-2025 match may enter the confirmatory research population.

BASIC may be inspected for metadata/coverage diagnostics but cannot unlock MARKET-EDGE-001 because it lacks the registered executable best-back/best-lay inputs.

## Why canonical coverage is primary

`matched Betfair markets / all Betfair markets` is not the primary coverage denominator. A Betfair Tennis bundle may contain qualifying, Challenger, ITF or other markets not represented by the canonical ATP/WTA research tables.

The primary coverage denominator is therefore the canonical completed, non-walkover, non-retirement ATP/WTA match population falling inside the declared source interval.

For each canonical match, the numerator requires exactly one identity-resolved, executable `CLOSE_PREPLAY` MATCH_ODDS observation.

## Structural hard gates

All must pass:

1. Source manifest package is ADVANCED or PRO.
2. Every source file has a valid SHA-256 and the bundle digest is reproducible.
3. MARKET-HIST source file hashes are members of the declared bundle manifest.
4. No duplicate Betfair market ID is accepted from multiple files.
5. No canonical `match_id` has more than one eligible executable closing market.
6. Every eligible close is `OPEN`, non-in-play upstream and strictly before the recorded market start.
7. `published_at`, `market_time` and `seconds_to_start` agree under the registered tolerance.
8. Canonical A/B identity/join hashes are internally consistent.
9. No post-2025 canonical match enters the QA/confirmatory population.
10. No walkover or retirement enters the primary MARKET-EDGE proper-score population.
11. No outcome field is required for MARKET-HIST identity resolution or checkpoint selection.
12. Zero schema/provenance failures may be silently dropped. A malformed eligible record fails the QA run rather than reducing the denominator.

Failure of any structural gate means `BLOCKED_STRUCTURAL`.

## Coverage quantities

Report separately for ATP and WTA:

- canonical eligible completed matches in the declared interval;
- canonical matches with any exact identity-resolved Betfair market;
- canonical matches with executable `CLOSE_PREPLAY`;
- canonical close coverage fraction;
- annual canonical close coverage;
- 2021–2025 canonical close coverage;
- counts for T-24H, T-6H, T-1H, T-15M and CLOSE_PREPLAY;
- executable counts at each checkpoint;
- unmatched and ambiguous source-market counts as diagnostics only;
- closing quote age distribution;
- spread in implied probability and in price space;
- market total-matched distribution when available;
- market base-rate availability.

Unmatched source-market rate is not itself a hard failure because the source universe can exceed the canonical universe.

## Frozen confirmatory coverage gates

A tour is eligible for its MARKET-EDGE-001 claims only if all are true:

1. **Overall canonical executable-close coverage >= 60%.**
2. **Every recent year 2021, 2022, 2023, 2024 and 2025 has canonical executable-close coverage >= 50%.**
3. **Every recent year has >= 100 completed executable closing observations.**
4. **At least 1,000 matched completed rows occur before the first confirmatory evaluation year**, consistent with MARKET-EDGE-001's frozen chronological training gate.
5. **At least five distinct evaluation years are available after the 1,000-row history threshold.**
6. **All five recent years 2021–2025 are represented in the confirmatory evaluation population.**

These thresholds are minimum data sufficiency rules, not evidence of market edge.

A tour that fails a coverage gate may still be analyzed descriptively/exploratorily but cannot receive a confirmatory MARKET-EDGE promotion decision from that bundle.

## Selection-bias diagnostics

Even when the 60%/50% minimum gates pass, compare covered versus uncovered canonical matches by pre-match-only variables where available:

- tournament level;
- surface;
- round;
- ranking/probability-region proxy;
- calendar year.

Large coverage imbalances are reported explicitly. No post-result reweighting is allowed inside MARKET-EDGE-001 unless a separate method is preregistered before looking at the signal-vs-market result.

## Checkpoint quality

`CLOSE_PREPLAY` is required for the primary market-incrementality test.

T-24H/T-6H/T-1H/T-15M are economic-timing diagnostics and later policy inputs. Their absence does not invalidate closing-market science, but coverage must be reported separately so a later executable-policy study cannot pretend an earlier decision price existed.

## Liquidity/spread

No minimum liquidity or maximum spread threshold is selected here for the primary probability-incrementality claim. Applying such a threshold after seeing model performance could induce selection bias.

Liquidity, spread and quote age are retained for stratified diagnostics and for separately preregistered executable-policy research.

## Statuses

Per tour:

- `ELIGIBLE_CONFIRMATORY`: all structural and coverage gates pass.
- `EXPLORATORY_ONLY_COVERAGE`: structural gates pass but one or more coverage gates fail.
- `BLOCKED_STRUCTURAL`: any structural gate fails.

The four-claim MARKET-EDGE family may run confirmatorily only for tours marked `ELIGIBLE_CONFIRMATORY`. If only one tour qualifies, the preregistered four-claim family is still reported with the ineligible tour claims marked unavailable; it is not silently redefined into a smaller multiplicity family.

## Non-claims

Passing MARKET-HIST-QA-001 does not establish:

- predictive incrementality over Betfair;
- positive EV;
- positive CLV;
- profitability;
- fill quality;
- a BET/PASS policy;
- real-money readiness.

It only establishes that the licensed market dataset is adequate to ask the next question honestly.
