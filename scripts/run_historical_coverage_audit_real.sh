#!/usr/bin/env bash
set -euo pipefail

ARCHIVE_REPO="Aneeshers/tennis-sackmann-archive"
ARCHIVE_COMMIT="83733587353df8a41f2fd4f516147d5aa83f5a8d"
START_YEAR="2000"
END_YEAR="2025"
LICENSE_NAME="CC BY-NC-SA 4.0"
LICENSE_URL="https://creativecommons.org/licenses/by-nc-sa/4.0/"

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

rm -rf data/coverage_audit_raw data/coverage_audit_processed
rm -rf artifacts/historical_availability_coverage_001
mkdir -p data/coverage_audit_raw/atp data/coverage_audit_raw/wta
mkdir -p artifacts/historical_availability_coverage_001

for year in $(seq "$START_YEAR" "$END_YEAR"); do
  for tour in atp wta; do
    filename="${tour}_matches_${year}.csv"
    url="https://raw.githubusercontent.com/${ARCHIVE_REPO}/${ARCHIVE_COMMIT}/${tour}/${filename}"
    curl --fail --location --silent --show-error --retry 3 \
      --output "data/coverage_audit_raw/${tour}/${filename}" "$url"
  done
done

test "$(find data/coverage_audit_raw -type f | wc -l)" -eq 52

for tour in atp wta; do
  mkdir -p "data/coverage_audit_processed/${tour}"
  args=()
  for year in $(seq "$START_YEAR" "$END_YEAR"); do
    args+=(--input "data/coverage_audit_raw/${tour}/${tour}_matches_${year}.csv")
  done
  upper="$(printf '%s' "$tour" | tr '[:lower:]' '[:upper:]')"
  python -m tennis_genome.pipeline.build_dataset \
    "${args[@]}" \
    --tour "$upper" \
    --output-dir "data/coverage_audit_processed/${tour}" \
    --source-id "sackmann-archive-${ARCHIVE_COMMIT}-${tour}-${START_YEAR}-${END_YEAR}" \
    --provider "Jeff Sackmann / Tennis Abstract via Aneeshers archival mirror" \
    --source-version "$ARCHIVE_COMMIT" \
    --license-name "$LICENSE_NAME" \
    --license-url "$LICENSE_URL" \
    --allowed-use-status research_allowed \
    > "data/coverage_audit_processed/${tour}/build_output.json"
done

python - <<'PY'
import json
from pathlib import Path

expected = {
    "atp": {
        "row_count": 77850,
        "source_bundle_sha256": "b5cf078bb2bc035bb3a2c3bdc7d70b2eeabf38957ce5a2614f5d129c8484627c",
        "pre_match_sha256": "d1003f47322a58ff92ec1dc98d68168c136a7423a58cfd8e9f43530a6b252442",
        "outcome_sha256": "9ab4a2f850554081bc74eb381479a9529157ab8eb5f24d99cc13be57ee200fa0",
        "stats_sha256": "56b542915523a5e78bf7eedf91b6fbfea5a83f0a10498496bd4689747e08c0d9",
    },
    "wta": {
        "row_count": 71419,
        "source_bundle_sha256": "b98b0b28e447eb13e2352b3d555be96d39d7dd4e49121fa84eaf87b9465a3fc2",
        "pre_match_sha256": "16c1b6ff231c10169142a6e038d035d56c082f843fe509084eda5436d4b39262",
        "outcome_sha256": "1b3da999ca7d8921d039766854386a1038962d564fc65e348dcec1e4c461a8a8",
        "stats_sha256": "db75fe1b22ab48c64e024a5acadc44ec1b18f536516ef7fb02f806c672bf1df1",
    },
}
for tour, required in expected.items():
    path = Path("data/coverage_audit_processed") / tour / f"{tour}_manifest.json"
    manifest = json.loads(path.read_text())
    observed = {key: manifest.get(key) for key in required}
    if observed != required:
        raise SystemExit(
            f"{tour.upper()} canonical snapshot failed archived-hash reproduction:\n"
            + json.dumps({"expected": required, "observed": observed}, indent=2, sort_keys=True)
        )
    print(tour.upper(), json.dumps(observed, sort_keys=True))
PY

for tour in atp wta; do
  upper="$(printf '%s' "$tour" | tr '[:lower:]' '[:upper:]')"
  python -m tennis_genome.research_workbench.historical_coverage_audit \
    --manifest "data/coverage_audit_processed/${tour}/${tour}_manifest.json" \
    --pre-match "data/coverage_audit_processed/${tour}/${tour}_pre_match.parquet" \
    --outcomes "data/coverage_audit_processed/${tour}/${tour}_outcomes.parquet" \
    --stats "data/coverage_audit_processed/${tour}/${tour}_stats.parquet" \
    --tour "$upper" \
    --output "artifacts/historical_availability_coverage_001/${tour}.json"
done

python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("artifacts/historical_availability_coverage_001")
reports = {
    tour: json.loads((root / f"{tour}.json").read_text())
    for tour in ("atp", "wta")
}

lines = [
    "# HISTORICAL-AVAILABILITY-COVERAGE-001",
    "",
    "Status: **DESCRIPTIVE_ONLY**",
    "",
    "Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`",
    "",
    "Rates use non-walkover, non-retirement rows as the denominator. No year is excluded or promoted by this audit.",
    "",
    "| Tour | Year | N strict | Any stats | Usable serve both | Duration |",
    "|---|---:|---:|---:|---:|---:|",
]
for tour in ("atp", "wta"):
    for row in reports[tour]["rows"]:
        lines.append(
            f"| {row['tour']} | {row['year']} | {row['n_strict_eligible']} | "
            f"{row['stats_present_rate']:.2%} | {row['service_both_rate']:.2%} | "
            f"{row['duration_present_rate']:.2%} |"
        )

lines.extend(["", "Artifact identities:"])
for tour in ("atp", "wta"):
    path = root / f"{tour}.json"
    lines.append(f"- {tour.upper()}: `{hashlib.sha256(path.read_bytes()).hexdigest()}`")
lines.extend(
    [
        "",
        "This audit describes source coverage only. It does not establish causality, justify year removal, alter a model, or upgrade any target-row field to verified T0 availability.",
    ]
)
summary = "\n".join(lines) + "\n"
(root / "SUMMARY.md").write_text(summary, encoding="utf-8")
print(summary)
PY
