# Betfair Historical Ingestion Runbook

Status: **MARKET-HIST-001 infrastructure**

This runbook describes how to turn licensed Betfair Historical Data into an auditable Tennis Genome market artifact without committing purchased source files to Git.

## Required source

Use Betfair Historical Data for:

- sport: Tennis;
- market type: `MATCH_ODDS`;
- market-file (`M`) stream data;
- ADVANCED or PRO package for executable-price research.

BASIC may be used for parser/coverage diagnostics but is not eligible for the primary executable-price edge analysis because it does not contain best available back/lay ladders.

The repository does not download, redistribute, or commit Betfair historical files. Source acquisition and use remain subject to the user's Betfair licence/terms.

## Directory layout

Extract the purchased archive outside the Git repository, for example:

```text
/data/betfair-tennis/
  2019/
    1.xxxxx.bz2
  2020/
    1.yyyyy.bz2
  ...
```

The batch runner recursively discovers `.bz2`, `.json`, `.jsonl`, `.txt`, and extensionless market files.

Keep the output directory outside the source directory so generated JSON artifacts are never re-read as Betfair Stream API inputs.

## Canonical pre-match input

MARKET-HIST-001 intentionally reads only the canonical pre-match Parquet table.

It does **not** require the outcome or post-match-stat tables to resolve Betfair markets. If outcome fields such as `a_won`, `score`, `retirement`, or `walkover` appear in the supplied pre-match table, the loader fails closed.

## Run

Example for ADVANCED data:

```bash
python -m tennis_genome.market.historical_batch \
  --betfair-root /data/betfair-tennis \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --data-package ADVANCED \
  --output-dir /data/tennis-genome/market-hist-001
```

PRO data uses the same command with `--data-package PRO`.

Default join window:

- 4 days before the canonical source tournament-start date;
- 21 days after it.

These values are part of the MARKET-HIST-001 record and must not be relaxed after looking at outcome or edge results. If a future resolver changes them, it receives a new resolver/experiment version.

## Outputs

The runner writes:

### `market_hist_001_records.jsonl`

One immutable record per reconstructed Betfair market containing:

- Betfair market/event IDs;
- source file SHA-256;
- source package;
- outcome-free join status;
- candidate canonical match IDs;
- deterministic join hash when matched;
- canonical A/B selection orientation;
- selected T-24H, T-6H, T-1H, T-15M and CLOSE_PREPLAY checkpoints when available;
- actual publish time and contemporaneously known market start time;
- seconds to start and checkpoint lag;
- best available back/lay price and size for canonical A/B;
- last traded price as metadata only;
- market base rate and total matched when present;
- source-message and checkpoint hashes.

Unmatched and ambiguous markets remain in the artifact for coverage diagnostics but do not receive model-vs-market edge analysis.

### `market_hist_001_summary.json`

Reports:

- files inspected;
- files yielding tennis MATCH_ODDS snapshots;
- markets reconstructed;
- matched/unmatched/ambiguous counts;
- join rate;
- checkpoint availability;
- executable two-way checkpoint availability;
- source-package distribution;
- deterministic SHA-256 of the complete market-record payload.

## Determinism check

Running the batch twice on the same source files, canonical pre-match table, package declaration and join parameters must produce the same record payload hash.

The repository's `MARKET-HIST-001 synthetic gate` performs this check on synthetic Stream API fixtures without licensed source data.

## What counts as executable

For MARKET-HIST-001, `executable_two_way=true` means both canonical runners have a reconstructed best back price/size and best lay price/size at that snapshot.

It does **not** assert that a requested stake would have been fully filled. Available size is preserved so later execution research can model stake-dependent fill constraints.

Last traded price is never substituted for an executable back price.

## Chronology

Checkpoint selection is strictly pre-play:

- fixed checkpoints select the latest eligible state still at least the requested horizon from the market start time known in that state;
- CLOSE_PREPLAY is the latest eligible OPEN state strictly before the contemporaneously known market start;
- suspended/in-play observations do not become executable checkpoints;
- later closing information cannot alter an earlier checkpoint.

## Identity failures

Automatic v1 matching is exact after Unicode/case/punctuation normalization of the unordered player-name pair plus the frozen date window.

- zero candidates -> `UNMATCHED`;
- more than one candidate -> `AMBIGUOUS`;
- both are excluded from edge research.

Do not manually choose the candidate that makes a historical result look correct. Any manual alias/identity registry must be versioned separately and established without outcomes or price-performance information.

## After ingestion

The first downstream experiment is **MARKET-EDGE-001**, not an optimized betting strategy.

Its order is:

1. establish Betfair's own closing probability-quality baseline;
2. test Profile Gap for incremental information beyond closing market prices;
3. test the frozen Genome signal secondarily;
4. quantify paired Brier/log-loss uncertainty and multiplicity;
5. only then inspect executable decision-point edge/CLV and commission-aware economics.

The ingestion artifact itself does not establish edge, expected value, CLV, ROI, or profitability.
