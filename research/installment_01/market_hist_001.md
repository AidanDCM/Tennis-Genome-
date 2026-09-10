# MARKET-HIST-001 — Betfair Historical Exchange Ingestion

Status: **PREREGISTERED / DATA NOT YET SUPPLIED**

## Purpose

Build an auditable historical market-data layer that reconstructs what the Betfair Exchange published before tennis matches and joins those markets to Tennis Genome's canonical historical matches without using outcomes.

This experiment is a **data reconstruction and join-quality gate**. It does not test model edge, EV, ROI, CLV, staking, or profitability.

## Source boundary

Primary source: licensed Betfair Historical Data purchased by the user and downloaded from the Betfair Historical Data service.

Primary filter:

- sport: Tennis
- market type: `MATCH_ODDS`
- file type: `M` (one file per market)
- package: ADVANCED or PRO for primary price research
- target historical period: 2015-2025, subject to purchased availability

BASIC files may be parsed for metadata, identity, and coverage diagnostics, but BASIC is **not eligible for executable-price edge research** because it lacks the best available back/lay ladders required by Market Layer v1 research.

No source file is committed to the repository.

## Source semantics

Betfair historical files use Exchange Stream API MarketChangeMessage (`mcm`) JSON updates. The parser must reconstruct state from the ordered update stream rather than treating individual lines as standalone full snapshots.

The parser must preserve:

- Betfair market ID
- Betfair event ID
- event type ID
- `MATCH_ODDS` market type
- event name
- current market start time
- publish time (`pt`)
- in-play and market status
- market base rate / commission metadata when present
- runner Betfair IDs and names
- last traded price when available
- best available back/lay when available
- available volumes when available
- source package
- source file SHA-256
- source message SHA-256

ADVANCED `batb` / `batl` values are reconstructed as level-indexed price/volume state. PRO `atb` / `atl` values are reconstructed as price-indexed ladder state. A zero volume removes the supplied level/price.

## Pre-match checkpoint contract

Primary checkpoints:

- `T-24H` = 86,400 seconds before start
- `T-6H` = 21,600 seconds before start
- `T-1H` = 3,600 seconds before start
- `T-15M` = 900 seconds before start
- `CLOSE_PREPLAY` = latest eligible observation strictly before start

For fixed checkpoints, select the latest eligible observation whose **contemporaneously known** `marketTime - published_at` is at least the checkpoint horizon.

This intentionally avoids looking ahead to a later/final rescheduled market time when choosing an earlier historical observation.

Eligible observations must be:

- `marketType == MATCH_ODDS`
- two-runner tennis match market
- not in play
- published strictly before the market start time known at that observation

Market suspension/status is preserved. Suspended observations may exist in the raw state but are not executable-price checkpoints.

Checkpoint output must record the actual seconds-to-start and distance from the requested checkpoint. Staleness is measured, not silently filtered.

## Identity/join contract

Historical Betfair runner identities are joined to canonical Tennis Genome matches using **pre-outcome information only**.

Initial automatic resolver:

1. Unicode/case/punctuation-normalized unordered player-name pair.
2. Betfair market start date must fall within a configurable tournament-date window around the canonical source tournament start date.
3. Exactly one canonical candidate must remain.

The initial default window may allow qualifying matches shortly before the source tournament start and main-draw matches afterward. Window size is a join parameter and must be reported.

If zero candidates remain, the market is `UNMATCHED`.

If multiple candidates remain, the market is `AMBIGUOUS` and must **fail closed** for model-vs-market research. No winner, settlement status, price behavior, or post-match statistics may be used to break the tie.

Unresolved aliases may later be supplied through a separately versioned/manual-verified alias registry. Automatic fuzzy matching is not permitted in v1.

## Primary outputs

MARKET-HIST-001 must report:

- files inspected
- source-package distribution
- valid tennis `MATCH_ODDS` markets
- exact-name join count
- unmatched count
- ambiguous count
- checkpoint availability by horizon
- executable back/lay completeness by horizon
- quote-age / checkpoint-lag distributions
- source and output hashes
- per-market immutable join/checkpoint records

## Promotion gate

The Betfair ingestion layer may enter market-edge research only if:

1. parser regression tests pass;
2. source hashes are preserved;
3. market reconstruction is deterministic;
4. A/B identity mapping is deterministic and outcome-free;
5. ambiguous joins are excluded/fail closed;
6. checkpoint selection is strictly pre-play;
7. ADVANCED/PRO price ladders reconstruct deterministic best back/lay;
8. no Betfair market information imports into `tennis_genome.independent`.

Coverage is measured rather than optimized. Low coverage does not justify relaxing identity or chronology rules.

## Explicit non-claims

A successful MARKET-HIST-001 does **not** establish:

- that Tennis Genome beats Betfair;
- that any model edge is positive EV;
- that last traded price is executable;
- that best back/lay midpoint is a fair probability;
- that Betfair commission has been correctly converted into sportsbook-equivalent vig;
- that a betting policy is profitable.

Those are separate preregistered experiments downstream of this data gate.
