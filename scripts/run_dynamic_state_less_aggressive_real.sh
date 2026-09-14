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

python - <<'PY'
from tennis_genome.research_workbench.dynamic_state_search_family import (
    DynamicStateLessAggressiveFamilySpec,
)

spec = DynamicStateLessAggressiveFamilySpec()
assert len(spec.candidates) == 8
assert spec.primary_claim_count == 32
assert abs(spec.bonferroni_alpha - 0.0015625) < 1e-15
print("Frozen family verified:", spec.semantic_sha256)
PY

rm -rf data/research_raw/atp data/research_raw/wta
rm -rf data/research_processed/atp data/research_processed/wta
rm -rf artifacts/dynamic_state_less_aggressive_search
mkdir -p data/research_raw/atp data/research_raw/wta
mkdir -p artifacts/dynamic_state_less_aggressive_search

for year in $(seq "$START_YEAR" "$END_YEAR"); do
  for tour in atp wta; do
    filename="${tour}_matches_${year}.csv"
    url="https://raw.githubusercontent.com/${ARCHIVE_REPO}/${ARCHIVE_COMMIT}/${tour}/${filename}"
    curl --fail --location --silent --show-error --retry 3 \
      --output "data/research_raw/${tour}/${filename}" "$url"
  done
done

test "$(find data/research_raw -type f | wc -l)" -eq 52

mkdir -p data/research_processed/atp
atp_args=()
for year in $(seq "$START_YEAR" "$END_YEAR"); do
  atp_args+=(--input "data/research_raw/atp/atp_matches_${year}.csv")
done
python -m tennis_genome.pipeline.build_dataset \
  "${atp_args[@]}" \
  --tour ATP \
  --output-dir data/research_processed/atp \
  --source-id "sackmann-archive-${ARCHIVE_COMMIT}-atp-${START_YEAR}-${END_YEAR}" \
  --provider "Jeff Sackmann / Tennis Abstract via Aneeshers archival mirror" \
  --source-version "$ARCHIVE_COMMIT" \
  --license-name "$LICENSE_NAME" \
  --license-url "$LICENSE_URL" \
  --allowed-use-status research_allowed \
  > data/research_processed/atp/build_output.json

mkdir -p data/research_processed/wta
wta_args=()
for year in $(seq "$START_YEAR" "$END_YEAR"); do
  wta_args+=(--input "data/research_raw/wta/wta_matches_${year}.csv")
done
python -m tennis_genome.pipeline.build_dataset \
  "${wta_args[@]}" \
  --tour WTA \
  --output-dir data/research_processed/wta \
  --source-id "sackmann-archive-${ARCHIVE_COMMIT}-wta-${START_YEAR}-${END_YEAR}" \
  --provider "Jeff Sackmann / Tennis Abstract via Aneeshers archival mirror" \
  --source-version "$ARCHIVE_COMMIT" \
  --license-name "$LICENSE_NAME" \
  --license-url "$LICENSE_URL" \
  --allowed-use-status research_allowed \
  > data/research_processed/wta/build_output.json

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
    path = Path("data/research_processed") / tour / f"{tour}_manifest.json"
    manifest = json.loads(path.read_text())
    observed = {key: manifest.get(key) for key in required}
    if observed != required:
        raise SystemExit(
            f"{tour.upper()} canonical snapshot failed archived-hash reproduction:\n"
            + json.dumps({"expected": required, "observed": observed}, indent=2, sort_keys=True)
        )
    print(tour.upper(), json.dumps(observed, sort_keys=True))
PY

python -m tennis_genome.research_workbench.dynamic_state_search_runner \
  --atp-manifest data/research_processed/atp/atp_manifest.json \
  --atp-pre-match data/research_processed/atp/atp_pre_match.parquet \
  --atp-outcomes data/research_processed/atp/atp_outcomes.parquet \
  --atp-stats data/research_processed/atp/atp_stats.parquet \
  --wta-manifest data/research_processed/wta/wta_manifest.json \
  --wta-pre-match data/research_processed/wta/wta_pre_match.parquet \
  --wta-outcomes data/research_processed/wta/wta_outcomes.parquet \
  --wta-stats data/research_processed/wta/wta_stats.parquet \
  --repo-root . \
  --output artifacts/dynamic_state_less_aggressive_search/evidence.json

python - <<'PY'
import hashlib
import json
from pathlib import Path

root = Path("artifacts/dynamic_state_less_aggressive_search")
evidence_path = root / "evidence.json"
evidence = json.loads(evidence_path.read_text())
report = evidence["report"]
by_candidate = {row["candidate_id"]: row for row in report["candidate_aggregates"]}
by_cell = {
    (row["candidate_id"], row["tour"]): row
    for row in report["candidate_tour_results"]
}

lines = [
    "# DYNAMIC-STATE-LESS-AGGRESSIVE-SEARCH-001",
    "",
    "Pinned source: `Aneeshers/tennis-sackmann-archive@83733587353df8a41f2fd4f516147d5aa83f5a8d`",
    "",
    f"Primary historical claims: **{report['primary_claim_count']}**",
    f"Bonferroni familywise alpha: **{report['bonferroni_alpha']:.7f}**",
    f"Selection status: **{report['selection_status']}**",
    f"Selected candidate: **{report['selected_candidate_id'] or 'NO_CANDIDATE'}**",
    "",
    "A candidate is eligible only if ATP and WTA both improve on Brier and log loss.",
    "",
    "| Candidate | ATP dBrier | ATP dLog | WTA dBrier | WTA dLog | 4-cell positive | Pooled dBrier | Pooled dLog |",
    "|---|---:|---:|---:|---:|:---:|---:|---:|",
]
for candidate_id in sorted(by_candidate):
    agg = by_candidate[candidate_id]
    atp = by_cell[(candidate_id, "ATP")]
    wta = by_cell[(candidate_id, "WTA")]
    lines.append(
        f"| {candidate_id} | {atp['brier_improvement']:+.8f} | {atp['log_loss_improvement']:+.8f} | "
        f"{wta['brier_improvement']:+.8f} | {wta['log_loss_improvement']:+.8f} | "
        f"{'YES' if agg['four_cell_positive'] else 'NO'} | "
        f"{agg['pooled_brier_improvement']:+.8f} | {agg['pooled_log_loss_improvement']:+.8f} |"
    )
lines.extend(
    [
        "",
        f"ATP dataset fingerprint: `{evidence['atp_dataset_fingerprint']['sha256']}`",
        f"WTA dataset fingerprint: `{evidence['wta_dataset_fingerprint']['sha256']}`",
        f"Parent code fingerprint: `{evidence['parent_code_fingerprint']['sha256']}`",
        f"Search code fingerprint: `{evidence['search_code_fingerprint']['sha256']}`",
        "",
        "**DEVELOPMENT_SEARCH_ONLY.** No production, protected, prospective, sportsbook-edge, or profitability claim follows from this search.",
    ]
)
summary = "\n".join(lines) + "\n"
(root / "SUMMARY.md").write_text(summary, encoding="utf-8")
print(summary)
print("Evidence SHA-256:", hashlib.sha256(evidence_path.read_bytes()).hexdigest())
PY
