# Data Architecture

## Design goals

- reproducible historical reconstruction
- strict time semantics
- compact local storage
- easy analytical querying
- no unnecessary raw-media retention
- clear separation of raw, canonical, feature, model, prediction, and market layers

## Recommended local stack

- **Parquet**: immutable/canonical analytical tables
- **DuckDB**: local query/joins/feature research
- **Python**: ingestion, transforms, ratings, modeling, validation
- **JSON/YAML**: schemas/configs/registries only

Avoid giant CSV workflows once the pipeline stabilizes.

## Directory convention

```text
data/
  raw/           # downloaded source files; not committed
  interim/       # normalized source-specific tables; not committed
  processed/     # canonical Parquet tables; not committed
  reference/     # small static mappings optionally committed
  cache/         # disposable feature/API cache
  predictions/   # immutable paper/live prediction records
```

Git tracks schemas, manifests, checksums/sample data, and code—not large datasets.

## Canonical tables

### players.parquet
One canonical row per player identity.

### events.parquet
Tournament/event identity and metadata.

### matches.parquet
One row per match with canonical players, event, status, surface, timing, outcome.

### match_stats.parquet
Match-level serve/return/point aggregates where available.

### rankings.parquet
Timestamped ranking/points snapshots.

### player_snapshots.parquet
Versioned pre-match player state/profile records.

### fingerprints.parquet
Versioned Match Fingerprints/features.

### market_snapshots.parquet
Timestamped sportsbook/market records, kept separate from tennis features.

### predictions.parquet
Immutable model outputs/decisions.

### hypotheses.parquet or DuckDB table
Research ledger.

### sources.parquet
Provenance and source reliability metadata.

## Identity strategy

Never join on display names alone.

Create stable internal IDs:
- `player_id`
- `event_id`
- `match_id`
- `source_id`

Maintain source mappings:

```text
internal_player_id | source_name | external_player_id | source_display_name | valid_from | valid_until
```

Name changes, accents, transliterations, and duplicate names must not create false identities.

## Time fields

Distinguish:
- `event_time`: when something happened
- `observed_at`: timestamp represented by source record
- `available_at`: earliest time system/user could know it
- `collected_at`: when our pipeline acquired it

Feature legality is governed by `available_at <= prediction_cutoff_at`.

## Provenance

Every source-derived table should preserve enough information to reconstruct where a row came from:
- source name
- source dataset/version
- external ID
- source URL/reference when appropriate
- checksum/version
- acquisition date
- parsing version

Derived features carry code/feature versions rather than duplicating every raw source field.

## Storage efficiency

Use:
- dictionary/categorical encoding for strings
- compact integer IDs
- float32 for many analytical features when numerical precision is adequate
- partitioning by tour/year only when it improves workflows
- compression (Parquet default codecs such as ZSTD/Snappy depending environment)
- deduplication of repeated source records

Do not duplicate full player profiles into every match row; reference snapshot IDs and materialize model matrices as needed.

## Realistic scale

Structured professional-tennis match data are small relative to raw video/media. Even hundreds of numerical features across hundreds of thousands to low millions of rows are typically manageable on a normal workstation when stored in compressed columnar form.

Early target: keep the core research dataset in the single-digit to tens-of-GB range, excluding optional raw archives. Exact size must be measured after source selection rather than assumed.

## Raw-source retention policy

Keep raw data when:
- licensing permits;
- reacquisition is difficult;
- source may need reparsing;
- evidence provenance matters.

Prefer compact structured extraction over permanent retention for:
- screenshots
- video
- web-page snapshots
- large redundant API responses

For human/current-event evidence, retain source reference, timestamps, extracted event, reliability, and a concise evidence record rather than copying entire websites.

## Dataset manifests

Each processed dataset build should write a manifest containing:
- build timestamp
- git commit
- source versions/checksums
- row counts
- date range
- tours/surfaces covered
- schema version
- known exclusions
- data-quality warnings

## Reproducibility

A model report should be reproducible from:
- dataset manifest
- code commit
- configuration
- chronological split definition
- random seed where relevant
- model/calibration versions

## Backups

Code and lightweight manifests: GitHub.
Large local datasets: separate backup/storage strategy.
Never rely on Git history as a data warehouse.
