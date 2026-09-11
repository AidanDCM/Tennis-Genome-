# MARKET-EDGE-001 — Pre-Result Amendment 008

Status: **FROZEN BEFORE POWER-MDE-001 AND BEFORE ANY BOOKMAKER-VS-SIGNAL RESULT**

## Purpose

Bind the bookmaker confirmatory path to the exact already-accepted historical signal artifacts before outcome-blind POWER-MDE-001 and before the Stage-A outcome-lock seal.

No `MARKET-EDGE-001`, `MARKET-EDGE-ADV-001`, bookmaker-vs-Profile-Gap, or bookmaker-vs-Genome outcome has been evaluated or inspected before this freeze.

This amendment does not change a signal definition, statistical threshold, market source, coverage gate, chronology rule, or claim family. It only removes filename/artifact ambiguity by recording the exact accepted development artifacts and SHA-256 values that the existing loaders must consume.

## Frozen Profile Gap inputs

Accepted historical run documented in `profile_gap_findings.md`:

- workflow run: `34427178193`
- accepted head: `4b6631d548dd563fab7802150c247bc62d56348d`
- artifact ID: `10133269797`
- artifact digest: `sha256:a1444c788796afb45696c7acd63fbdf93125c759a0d8550daa50c952842ccf94`

Confirmatory files:

- ATP Profile Gap: `profile_gap_atp_strict.json`
  - SHA-256: `532ff66304914f0962e5747f20790916c70e082efedba695d26717632db946fd`
- WTA Profile Gap: `profile_gap_wta_strict.json`
  - SHA-256: `343903af5f53cd1d519ebafdabf6ddb2dd0645847ff77e1820a156caf012bc55`

The WTA conditional serve/return execution is **not** the confirmatory WTA Profile Gap input. It was preregistered and interpreted as a diagnostic only, and the accepted findings explicitly left serve/return B/Conditional and did not promote that representation. The strict WTA artifact therefore remains the fixed representation for the already-frozen WTA × Profile Gap claim.

No threshold is applied to Profile Gap. The existing `load_profile_gap_values` loader consumes only the frozen `profile_gap_match` field keyed by canonical match ID.

## Frozen Genome inputs

Accepted historical adversarial run documented in `genome_adversarial_controls_findings.md`:

- workflow run: `34433553870`
- accepted head: `db0cc49f2b71c97d4c18b1b03edfd84534e4188d`
- artifact ID: `10135919958`
- artifact digest: `sha256:f51e96573f0bc967be898f095afd64db8b3844a01dbc4755974ab0b193bce299`

Confirmatory files:

- ATP Genome: `genome_adv_atp.json`
  - SHA-256: `37671b15b4f7bb4db98767f09a10f57dd43eb61baeacd2aed0713e8a67b298fa`
- WTA Genome: `genome_adv_wta.json`
  - SHA-256: `08df00ce43bed558f8d479f14e74bdb05504864ab0c4310aa3f3979029d0e2a3`

The existing frozen `load_genome_values` rule remains unchanged:

- ATP uses `full_neighbor_residual`;
- WTA uses `core_neighbor_residual`.

That tour-specific choice was already encoded before bookmaker outcomes were opened and corresponds to the accepted GENOME-ADV-001 adversarial interpretation: ATP full Genome cleared the stronger geometry gate, while WTA did not promote the Profile-mean extension beyond Core geometry.

## Frozen real bookmaker QA inputs

The Stage-A path must bind to the corrected real-source QA run on `dev/bookmaker-real-source-preflight-v1`:

- workflow run: `34616782073`
- head: `e2faeb9794225f1b72f0f826620afaf4e4eb187d`
- artifact ID: `10271297009`
- artifact digest: `sha256:c25a51fec003ceb3e48e68de3ac87c5af8cf8aec5000ac4246ca9b571c5ed425`
- QA global status: `ELIGIBLE_CONFIRMATORY`
- structural status: pass

Exact Stage-A source files:

- `source-manifest.json`
  - SHA-256: `0b02e33be720b9becff770d8527b25c3fe33f464bb4e83c7bf70f02715c16be6`
- `market_book_001_records.jsonl`
  - SHA-256: `6b8b04f7bf261bca68818260e62b00549012b5a9408a4a399544ac91c52fea4c`
- `market_book_qa_001.json`
  - SHA-256: `9304c4c3208dc8ab2df9e96f57bef4c3f8be3df18440c2d019c3c11b356c5304`
- combined `pre_match.parquet`
  - SHA-256: `557e579cd69b04b7436fee342d90d44a3a7e982f128b586ca0e6d1e01b0eec9e`
- QA-used combined `outcomes.parquet`
  - SHA-256: `c509dff1bbe4b1e10944f5b361138790f85ccdb21b7d12aafb03ddc0b1e8c63d`

The outcome file remains unavailable to Stage-A scoring. Its digest is recorded solely because MARKET-BOOK-QA used it for the preregistered walkover/retirement eligibility denominator and the Stage-A seal must bind Stage B to that exact ledger.

## Statistical design remains unchanged

The four claims remain exactly:

1. ATP × Profile Gap;
2. WTA × Profile Gap;
3. ATP × Genome;
4. WTA × Genome.

Frozen settings remain:

- `family_size = 4`;
- family alpha `0.05`;
- conservative planning alpha `0.0125`;
- Holm family-wise correction for confirmatory inference;
- `min_prior_rows = 1000`;
- strictly earlier-year fitting;
- all existing market-coverage gates;
- `BOOKMAKER_CLOSE_V1` source hierarchy and proportional no-vig transform;
- no post-2025 rows;
- no post-result tuning.

POWER-MDE-001 may now be run outcome-blind on these exact inputs. If all four claims have identifiable 2021-2025 evaluation years under the existing frozen rules, the existing bookmaker Stage-A seal may be created. Stage B remains blocked until that seal exists and is independently verified.
