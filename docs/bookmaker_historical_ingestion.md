# Bookmaker Historical Ingestion Runbook

Status: **MARKET-BOOK-001 + MARKET-BOOK-QA-001 pre-result infrastructure**

This runbook constructs an outcome-blind closing-bookmaker market artifact for the frozen MARKET-EDGE information-overlap tests. It is the operational alternative to the Betfair historical runbook; the Betfair path remains preserved separately.

## Confirmatory source policy

`BOOKMAKER_CLOSE_V1` is frozen as:

1. Valuebetennis two-sided closing odds when valid;
2. otherwise Tennis-Data Pinnacle `PSW`/`PSL` latest-pre-match odds when valid;
3. otherwise no primary quote.

Do not replace a valid higher-priority quote with another source based on price, signal, winner, or later performance.

Do not use opening odds, Bet365, max, or average odds as confirmatory fallbacks.

## Source files

Keep raw source files outside Git. Recommended layout:

```text
/data/bookmaker-market/
  valuebetennis/
    valuebetennis-matchs-2021.csv
    ...
    valuebetennis-matchs-2025.csv
  tennis-data-uk/
    atp/
      atp_singles_results_2015.csv
      ...
    wta/
      wta_singles_results_2015.csv
      ...
```

2026-or-later rows/files are outside the frozen confirmatory development interval and must not be included in a confirmatory manifest.

The current public Tennis-Data GitHub mirror is suitable for research reproducibility only under its stated non-commercial terms. Do not make a future commercial/live trading feed depend on that mirror without resolving rights separately.

## Outcome firewall

Both source families are result-bearing raw files.

- Valuebetennis result fields (`vainqueur_id`, score, duration) are ignored by the market adapter.
- Tennis-Data's Winner/Loser orientation is neutralized inside the adapter by normalized-name sorting while carrying each contestant's Pinnacle price with that contestant. Winner/Loser roles and all score/result fields are discarded from emitted records.

Downstream market joining and QA operate only on sanitized outcome-free quotes.

## Step 1 — freeze the exact source bundle

Example:

```bash
python -m tennis_genome.market.bookmaker_manifest \
  --valuebet-root /data/bookmaker-market/valuebetennis \
  --tennis-data-atp-root /data/bookmaker-market/tennis-data-uk/atp \
  --tennis-data-wta-root /data/bookmaker-market/tennis-data-uk/wta \
  --start-date 2015-01-01 \
  --end-date 2025-12-31 \
  --output /data/tennis-genome/market-book-001/source-manifest.json
```

The manifest records every included relative path, source family, byte size, SHA-256, requested interval, frozen hierarchy, neutralization version, no-vig method, and deterministic aggregate bundle hash.

The manifest rejects a requested end after 2025-12-31. Structurally invalid source files and files wholly outside the requested interval are quarantined in the manifest with a deterministic exclusion reason; a file that straddles the confirmatory interval fails closed rather than being partially consumed.

## Step 2 — construct MARKET-BOOK-001

```bash
python -m tennis_genome.market.bookmaker_batch \
  --source-manifest /data/tennis-genome/market-book-001/source-manifest.json \
  --valuebet-root /data/bookmaker-market/valuebetennis \
  --tennis-data-atp-root /data/bookmaker-market/tennis-data-uk/atp \
  --tennis-data-wta-root /data/bookmaker-market/tennis-data-uk/wta \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --output-dir /data/tennis-genome/market-book-001
```

The absolute source roots are supplied at runtime instead of stored in the manifest so the artifact is portable between machines. The exact relative file set, sizes, and SHA-256 values must still match the manifest before construction proceeds.

The canonical pre-match loader fails closed if outcome fields are present.

### Identity window

The source provides actual match date while canonical `event_date` is tournament start. Reuse the frozen market identity interval:

```text
-4 <= source_match_date - canonical_event_date <= 21 days
```

Matching is exact after the existing Unicode/case/punctuation name normalization on the unordered player pair.

No manual outcome-informed matching is allowed.

### Outputs

`market_book_001_records.jsonl` contains deterministic canonical records with:

- canonical match ID/tour when matched;
- source identity status and candidate IDs;
- selected primary source under `BOOKMAKER_CLOSE_V1`;
- source path/hash and sanitized-row hash;
- source match date;
- canonical A/B raw decimal odds;
- raw implied probability sum / overround;
- proportional no-vig `market_probability_a/b`;
- join hash and record hash;
- retained non-selected overlap source rows for outcome-blind disagreement diagnostics.

It contains no winner, `a_won`, score, retirement, walkover, Profile Gap, Genome, Strict Core output, or model-vs-market result.

`market_book_001_summary.json` reports ingestion, joining, source selection, conflict, overlap and deterministic artifact hashes.

## Step 3 — determinism check

Run MARKET-BOOK-001 twice against the exact same manifest/pre-match table and source directories. The canonical record ordering and summary-reported output SHA-256 must be identical.

## Step 4 — run MARKET-BOOK-QA-001

```bash
python -m tennis_genome.experiments.market_book_qa \
  --source-manifest /data/tennis-genome/market-book-001/source-manifest.json \
  --market-book-records /data/tennis-genome/market-book-001/market_book_001_records.jsonl \
  --pre-match /data/tennis-genome/canonical/pre_match.parquet \
  --outcomes /data/tennis-genome/canonical/outcomes.parquet \
  --valuebet-root /data/bookmaker-market/valuebetennis \
  --tennis-data-atp-root /data/bookmaker-market/tennis-data-uk/atp \
  --tennis-data-wta-root /data/bookmaker-market/tennis-data-uk/wta \
  --output /data/tennis-genome/market-book-001/market_book_qa_001.json
```

Outcomes are used only to remove walkovers/retirements from the denominator. QA never evaluates signal success.

Frozen eligibility gates per ATP/WTA:

- >=60% overall usable close coverage;
- >=50% each year 2021-2025;
- >=100 usable quotes each year 2021-2025;
- >=1,000 usable pre-2021 joined quotes;
- all five evaluation years 2021-2025 represented.

Both tours must pass for global `ELIGIBLE_CONFIRMATORY`.

## Step 5 — outcome-blind POWER-MDE-001

Only after QA passes, run the bookmaker POWER-MDE adapter using the exact selected `market_probability_a` values and frozen Profile Gap/Genome signals, without settled winners.

The four claims remain ATP/WTA × Profile Gap/Genome with family size 4, alpha .05, conservative planning alpha .0125, and min prior rows 1000.

Power/MDE may justify acquiring more source coverage. It may not change significance thresholds or source semantics.

## Step 6 — Stage-A seal

Freeze hashes for:

- bookmaker source manifest;
- MARKET-BOOK-001 records/summary;
- MARKET-BOOK-QA-001 report;
- POWER-MDE-001 artifact;
- canonical pre-match table;
- frozen signal artifacts;
- applicable preregistration/amendment files.

The Stage-A seal also binds the exact outcome file hash used by QA for walkover/retirement eligibility. No winner-dependent evaluator is allowed to run until the same outcome-file hash is supplied to Stage B.

## Step 7 — only then run MARKET-EDGE outcomes

The primary informational models remain:

```text
control:    alpha + gamma * logit(p_market)
challenger: alpha + gamma * logit(p_market) + beta * z(signal)
```

and the stronger Strict-Core adversary remains separately frozen.

A surviving result means the frozen signal contains information beyond the mature bookmaker close benchmark. It does not by itself establish tradable profit.

## Deferred execution/economic layer

This bookmaker source does not supply exchange liquidity, executable back/lay spread/size, commission, or timestamped earlier checkpoints. CLV, fills, staking, EV/ROI, and live paper execution require a later legally accessible source and a separate preregistration.
