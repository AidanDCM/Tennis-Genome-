# Historical CSV Bundle Ingestion

## Purpose

Long tennis histories are commonly distributed as one match CSV per season or year. Tennis Genome must ingest those files without requiring an analyst to manually concatenate them outside the audited pipeline.

The bundle builder therefore accepts one or more local source CSVs and produces the same canonical outputs used by the experiments:

- `<tour>_pre_match.parquet`
- `<tour>_outcomes.parquet`
- `<tour>_manifest.json`

Raw source files remain outside the repository unless their license explicitly permits redistribution.

## CLI

Repeat `--input` for every file in the research snapshot:

```bash
python -m tennis_genome.pipeline.build_dataset \
  --input data/raw/atp_matches_2022.csv \
  --input data/raw/atp_matches_2023.csv \
  --input data/raw/atp_matches_2024.csv \
  --tour ATP \
  --output-dir data/processed/atp_research_snapshot \
  --source-id atp-research-snapshot \
  --provider "Audited research source" \
  --source-version "snapshot-id-or-commit" \
  --license-name "verified license" \
  --allowed-use-status research_allowed
```

WTA is built separately.

## Determinism

Input paths are resolved and sorted before parsing. Passing the same files in a different command-line order therefore produces the same source sequence.

Within the canonical dataset, `source_order` is rewritten as one monotonically increasing sequence across all input files. This field is provenance/diagnostic information only; date-only prediction code still refuses to treat source row order as match chronology.

## Provenance manifest

The manifest records:

- every source filename,
- SHA-256 of every source file,
- source-file count,
- a deterministic SHA-256 of the ordered filename/hash bundle manifest,
- canonical output hashes,
- source license/use metadata,
- date coverage and row count,
- quality-warning counts.

For a one-file build, the legacy `source_filename` and `source_sha256` fields remain populated. For a multi-file build, `source_filename` is `multi_file_bundle` and `source_sha256` is the bundle digest. The explicit `source_files` list is the authoritative per-file provenance record.

## Fail-closed rules

The builder does not silently repair cross-file identity conflicts. In particular, if two files generate the same canonical `match_id`, the existing quality gate rejects the build with `duplicate_match_id`.

That behavior is intentional. A duplicate may represent a repeated source row, a source-version overlap, or a genuine identifier collision; choosing which row to keep requires an explicit source-audit decision rather than automatic deduplication.

## Research vs production

Multi-file support changes ingestion mechanics only. It does not change source rights.

A research-only or non-commercial source remains research-only after conversion to canonical Parquet. Derived canonical files must not be described as production-cleared merely because they were processed by Tennis Genome.
