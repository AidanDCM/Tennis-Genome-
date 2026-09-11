#!/usr/bin/env bash
set -euo pipefail

: "${RUNNER_TEMP:?RUNNER_TEMP is required}"

BOOK_ROOT="$RUNNER_TEMP/bookmaker-source"
VALUEBET="$BOOK_ROOT/valuebetennis"
ATP_ODDS="$BOOK_ROOT/tennis-data-atp"
WTA_ODDS="$BOOK_ROOT/tennis-data-wta"
REPORT_ROOT="$RUNNER_TEMP/bookmaker-real"
RAW="$RUNNER_TEMP/canonical-raw"
PROCESSED="$RUNNER_TEMP/canonical-processed"
COMBINED="$RUNNER_TEMP/canonical-combined"

TENNIS_DATA_COMMIT="c766bf79b7e2b421680c548b3aafe19db3a88720"
SACKMANN_ARCHIVE_REPO="Aneeshers/tennis-sackmann-archive"
SACKMANN_ARCHIVE_COMMIT="83733587353df8a41f2fd4f516147d5aa83f5a8d"

mkdir -p "$VALUEBET" "$ATP_ODDS" "$WTA_ODDS" "$REPORT_ROOT" \
  "$RAW/atp" "$RAW/wta" "$PROCESSED/atp" "$PROCESSED/wta" "$COMBINED"

for year in 2021 2022 2023 2024 2025; do
  curl --fail --location --retry 4 --retry-all-errors \
    --output "$VALUEBET/valuebetennis-matchs-${year}.csv" \
    "https://www.valuebetennis.com/datasets/valuebetennis-matchs-${year}.csv"
done

for year in $(seq 2015 2024); do
  curl --fail --location --retry 4 --retry-all-errors \
    --output "$ATP_ODDS/atp_singles_results_${year}.csv" \
    "https://raw.githubusercontent.com/nick-benelli/Tennis-Data/${TENNIS_DATA_COMMIT}/data/atp/tennis-data-uk/atp_singles_results_${year}.csv"
  curl --fail --location --retry 4 --retry-all-errors \
    --output "$WTA_ODDS/wta_singles_results_${year}.csv" \
    "https://raw.githubusercontent.com/nick-benelli/Tennis-Data/${TENNIS_DATA_COMMIT}/data/wta/tennis-data-uk/wta_singles_results_${year}.csv"
done

python -m tennis_genome.market.bookmaker_manifest \
  --valuebet-root "$VALUEBET" \
  --tennis-data-atp-root "$ATP_ODDS" \
  --tennis-data-wta-root "$WTA_ODDS" \
  --start-date 2015-01-01 \
  --end-date 2025-12-31 \
  --output "$REPORT_ROOT/source-manifest.json" \
  > /dev/null

for year in $(seq 2000 2025); do
  for tour in atp wta; do
    file="${tour}_matches_${year}.csv"
    curl --fail --location --silent --show-error --retry 4 --retry-all-errors \
      --output "$RAW/$tour/$file" \
      "https://raw.githubusercontent.com/${SACKMANN_ARCHIVE_REPO}/${SACKMANN_ARCHIVE_COMMIT}/${tour}/${file}"
  done
done

for tour in atp wta; do
  args=()
  for year in $(seq 2000 2025); do
    args+=(--input "$RAW/$tour/${tour}_matches_${year}.csv")
  done
  upper=$(echo "$tour" | tr '[:lower:]' '[:upper:]')
  python -m tennis_genome.pipeline.build_dataset \
    "${args[@]}" \
    --tour "$upper" \
    --output-dir "$PROCESSED/$tour" \
    --source-id "sackmann-archive-${SACKMANN_ARCHIVE_COMMIT}-${tour}-2000-2025" \
    --provider "Jeff Sackmann / Tennis Abstract via Aneeshers archival mirror" \
    --source-version "$SACKMANN_ARCHIVE_COMMIT" \
    --license-name "CC BY-NC-SA 4.0" \
    --license-url "https://creativecommons.org/licenses/by-nc-sa/4.0/" \
    --allowed-use-status research_allowed \
    > "$PROCESSED/$tour/build_output.json"
done

python - <<'PY'
import os
from pathlib import Path
import pandas as pd

root = Path(os.environ["RUNNER_TEMP"])
processed = root / "canonical-processed"
out = root / "canonical-combined"
pre = pd.concat(
    [
        pd.read_parquet(processed / "atp" / "atp_pre_match.parquet"),
        pd.read_parquet(processed / "wta" / "wta_pre_match.parquet"),
    ],
    ignore_index=True,
)
outcomes = pd.concat(
    [
        pd.read_parquet(processed / "atp" / "atp_outcomes.parquet"),
        pd.read_parquet(processed / "wta" / "wta_outcomes.parquet"),
    ],
    ignore_index=True,
)
if pre["match_id"].astype(str).duplicated().any():
    raise RuntimeError("combined canonical pre-match contains duplicate match_id")
if outcomes["match_id"].astype(str).duplicated().any():
    raise RuntimeError("combined canonical outcomes contain duplicate match_id")
pre = pre.sort_values(["event_date", "tour", "match_id"], kind="stable").reset_index(drop=True)
outcomes = outcomes.sort_values("match_id", kind="stable").reset_index(drop=True)
pre.to_parquet(out / "pre_match.parquet", index=False)
outcomes.to_parquet(out / "outcomes.parquet", index=False)
print("combined_pre_match_rows", len(pre))
print("combined_outcome_rows", len(outcomes))
PY

mkdir -p "$REPORT_ROOT/market-book-001"
python -m tennis_genome.market.bookmaker_batch_v3 \
  --source-manifest "$REPORT_ROOT/source-manifest.json" \
  --valuebet-root "$VALUEBET" \
  --tennis-data-atp-root "$ATP_ODDS" \
  --tennis-data-wta-root "$WTA_ODDS" \
  --pre-match "$COMBINED/pre_match.parquet" \
  --output-dir "$REPORT_ROOT/market-book-001"

python -m tennis_genome.experiments.market_book_qa_v3 \
  --source-manifest "$REPORT_ROOT/source-manifest.json" \
  --market-book-records "$REPORT_ROOT/market-book-001/market_book_001_records.jsonl" \
  --pre-match "$COMBINED/pre_match.parquet" \
  --outcomes "$COMBINED/outcomes.parquet" \
  --valuebet-root "$VALUEBET" \
  --tennis-data-atp-root "$ATP_ODDS" \
  --tennis-data-wta-root "$WTA_ODDS" \
  --output "$REPORT_ROOT/market_book_qa_001.json" \
  > /dev/null

python - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["RUNNER_TEMP"]) / "bookmaker-real" / "market_book_qa_001.json"
report = json.loads(path.read_text())
print("overall_status", report["overall_status"])
print("structural_pass", report["structural_pass"])
print("bundle_sha256", report["bundle_sha256"])
for tour in report["tours"]:
    print(
        tour["tour"],
        "status", tour["status"],
        "eligible", tour["eligible_canonical"],
        "usable_close", tour["usable_close"],
        "coverage", tour["overall_close_coverage"],
        "prior_rows", tour["prior_rows_before_2021"],
        "gates", tour["gates"],
    )
    for annual in tour["annual"]:
        print(tour["tour"], "annual", annual)
print("No Profile Gap, Genome, Strict Core, or signal-vs-market outcome was evaluated.")
PY
