# Betfair Historical Ingestion Runbook

Status: **MARKET-HIST-001 + MARKET-HIST-QA-001 infrastructure**

This runbook describes how to turn licensed Betfair Historical Data into an auditable Tennis Genome market artifact without committing purchased source files to Git, and how to decide whether that artifact is eligible for confirmatory market research before any model-vs-market outcomes are inspected.

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

## Step 1 — freeze the licensed source bundle

Before reconstruction, hash the exact local Betfair source directory:

```bash
python -m tennis_genome.market.historical_manifest \
  --root /data/betfair-tennis \
  --data-package ADVANCED \
  --start-date 2019-01-01 \
  --end-date 2025-12-31 \
  --output /data/tennis-genome/market-hist-001/source-manifest.json
```

The manifest records each relative file path, byte size and SHA-256 plus a deterministic aggregate bundle hash. The raw licensed files remain local and outside Git. Re-verification fails if the file set, size, or content changes.

The confirmatory research manifest rejects an interval ending after 2025 because the partial-2026 holdout is already spent.

## Step 2 — reconstruct MARKET-HIST-001

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

## MARKET-HIST outputs

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

## Step 3 — run MARKET-HIST-QA-001 before edge results

The real-data quality gate must run before model-vs-market outcomes are inspected:

```bash
python -m tennis_genome.experiments.market_hist_qa_bundle \
  --source-manifest /data/tennis-genome/market-hist-001/source-manifest.json \
  --market-hist-records /data/tennis-genome/market-hist-001/market_hist_001_records.jsonl \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --outcomes /data/tennis-genome/canonical/outcomes.parquet \
  --source-root /data/betfair-tennis \
  --output /data/tennis-genome/market-hist-001/market_hist_qa_001.json
```

The QA outcome table is used only to remove walkovers/retirements from the denominator; it is not used to score model probabilities. MARKET-EDGE receives settled outcomes separately later.

Per tour, confirmatory closing-market eligibility is frozen at:

- at least 60% overall canonical executable-close coverage;
- at least 50% executable-close coverage in every year 2021–2025;
- at least 100 executable closes in every year 2021–2025;
- at least 1,000 earlier usable closes before the first confirmatory evaluation year;
- at least five evaluation years;
- all years 2021–2025 represented in the evaluation population.

The denominator is eligible canonical completed matches, not all Betfair markets. Because canonical `event_date` is currently tournament start rather than exact match time, the upper denominator boundary is the declared source end minus 21 days.

The QA bundle also reports observed and executable coverage separately for T-24H, T-6H, T-1H, T-15M and CLOSE_PREPLAY, both overall and by year/tour. These earlier-checkpoint diagnostics constrain later CLV/tradeability research but do not change the primary CLOSE_PREPLAY eligibility gate.

Coverage bias by surface, tournament level, round and ranking band is diagnostic. Spread, liquidity and quote age must not be converted into post-hoc filters for MARKET-EDGE-001.

## Step 4 — run POWER-MDE-001 outcome-blind

Only after the historical market dataset has passed the relevant QA gate, run POWER-MDE-001 using closing Betfair probabilities and frozen Profile Gap/Genome signals **without canonical winners**.

POWER-MDE estimates the signal-coefficient resolution available to the four MARKET-EDGE claims after controlling for market probability. It is a procurement/feasibility diagnostic, not a signal promotion test.

Its report may justify acquiring more historical data or accepting limited resolution. It may not lower MARKET-EDGE significance thresholds or rescue a failed claim.

## Step 5 — only then open MARKET-EDGE-001 outcomes

After QA and outcome-blind power analysis are frozen for the exact source bundle, join the canonical settled outcomes and run MARKET-EDGE-001.

The primary comparison is:

```text
market control:    alpha + gamma * logit(p_market)
market + signal:   alpha + gamma * logit(p_market) + beta * z(signal)
```

with strictly earlier-year training, paired proper-score inference, annual/recent stability checks and the frozen four-claim Holm family.

CLOSE_PREPLAY answers the informational question: **did Tennis Genome retain information the mature market never absorbed?** Earlier checkpoints answer a later tradeability question and are not substitutes for the closing-market test.

## What comes after a surviving market signal

If—and only if—a signal survives MARKET-EDGE, the next research layer is economic:

1. CLV at executable earlier checkpoints;
2. edge monotonicity versus later CLV;
3. commission-adjusted historical EV/ROI;
4. spread/liquidity/fill and time-of-entry realism;
5. preregistered BET/PASS policy;
6. genuinely future immutable paper testing.

The ingestion, QA and power artifacts themselves do not establish edge, expected value, CLV, ROI, or profitability.
