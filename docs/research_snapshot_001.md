# Research Snapshot 001 — ATP/WTA Baseline History

Status: **approved for Tennis Genome non-commercial methodology research only**

## Purpose

This snapshot is the first real historical dataset used to exercise the canonical pipeline and run EXP-001 / EXP-002. It is not a production data source and does not establish commercial data rights.

## Source

Archival mirror:

- repository: `Aneeshers/tennis-sackmann-archive`
- pinned archive commit: `83733587353df8a41f2fd4f516147d5aa83f5a8d`
- archive commit date: 2026-06-25
- original compiler: Jeff Sackmann / Tennis Abstract
- original ATP source: `JeffSackmann/tennis_atp`
- original WTA source: `JeffSackmann/tennis_wta`

The archive README states that its ATP and WTA snapshots were taken from upstream commits made in June 2026.

## License / allowed use

License: **Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)**.

Project classification:

`allowed_use_status = research_allowed`

This snapshot must not be treated as production-cleared or used as the legal basis for a profit-oriented deployed betting product. Converting the files into Tennis Genome canonical Parquet does not expand the source license.

Raw files are downloaded transiently in the research workflow and are not committed to this repository or uploaded as workflow artifacts.

## Match population

Initial baseline population:

- ATP tour-level singles files `atp_matches_2000.csv` through `atp_matches_2025.csv`
- WTA tour-level singles files `wta_matches_2000.csv` through `wta_matches_2025.csv`
- 26 completed seasons per tour
- qualifying, Challenger/ITF, Futures, and doubles files excluded from this first baseline
- 2026 excluded because the pinned archive was created during the 2026 season and therefore contains an incomplete calendar year

The source file bundle is hashed file-by-file by the canonical builder. The resulting manifest records every source filename/hash plus a deterministic bundle digest.

## Ranking timestamp semantics

The ATP upstream documentation states that the ranking and ranking-points values repeated into match rows are **as of `tourney_date`**, and that `tourney_date` is almost always the Monday at or near the beginning of the event.

The WTA upstream documentation states that WTA match files use the same format as the ATP databases and include ranking/ranking-points redundancy for both players.

Research decision:

- treat ATP/WTA match-row ranks as event-start-era pre-match information for EXP-001,
- do not interpret them as exact match-start timestamps,
- continue using the conservative date-batched Elo rule because exact same-day start order is not established by this source.

If later source auditing contradicts these semantics, EXP-001 must be rerun and the old result invalidated rather than silently retained.

## Experiment rules

### EXP-001

- Ranking-logit vs overall Elo.
- Walkovers excluded.
- Retirements excluded in the primary view.
- Ranking calibration fitted on prior years only.
- Models scored on identical common match IDs.

### EXP-002

- Overall Elo vs pure surface-specific Elo.
- Unknown-surface matches excluded from both models and their EXP-002 training stream.
- Walkovers excluded.
- Retirements excluded in the primary view.
- Year, surface, and prior-surface-experience diagnostics retained.

## Reproducibility

The workflow `.github/workflows/research_baselines.yml` pins the archive commit and year range. It downloads source files directly from that immutable commit, runs the canonical build, verifies the generated manifests before experiments, and uploads only report JSON plus provenance manifests and a summary.

No metric from this snapshot should be described as evidence of betting profitability. These experiments measure probability-model baselines only.
